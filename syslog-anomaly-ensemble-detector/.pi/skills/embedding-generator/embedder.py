#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — embedding-generator skill.

Dùng model all-MiniLM-L6-v2 (sentence-transformers) để chuyển mỗi dòng
log message thành vector embedding 384 chiều.

Input : data/processed/parsed_logs.json
Output: data/processed/embeddings.npy       – ma trận (5000, 384)
        data/processed/embeddings_meta.json  – metadata mô tả embedding
"""

import json
import argparse
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Cấu hình mặc định
# ---------------------------------------------------------------------------
DEFAULT_INPUT_JSON = "data/processed/parsed_logs.json"
DEFAULT_OUTPUT_NPY = "data/processed/embeddings.npy"
DEFAULT_OUTPUT_META = "data/processed/embeddings_meta.json"
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 64

# ---------------------------------------------------------------------------
# Embedding dimensions của model all-MiniLM-L6-v2
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 384


# ===================================================================
# Hàm chính
# ===================================================================

def generate_embeddings(
    input_json: str = DEFAULT_INPUT_JSON,
    output_npy: str = DEFAULT_OUTPUT_NPY,
    output_meta: str = DEFAULT_OUTPUT_META,
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> np.ndarray:
    """Chuyển toàn bộ parsed log messages thành embedding vectors.

    Args:
        input_json:  Đường dẫn file parsed_logs.json (từ syslog-parser).
        output_npy:  Đường dẫn lưu ma trận embedding .npy.
        output_meta: Đường dẫn lưu file metadata JSON.
        model_name:  Tên model sentence-transformers.
        batch_size:  Số dòng encode mỗi lần (càng lớn → càng nhanh, tốn RAM).

    Returns:
        embedding_matrix: numpy array shape (total_messages, 384), float32.
    """
    # ------------------------------------------------------------------
    # Bước 1: Đọc parsed logs
    # ------------------------------------------------------------------
    input_path = Path(input_json)
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file input: {input_path.resolve()}")

    with open(input_path, "r", encoding="utf-8") as file_handle:
        parsed_entries = json.load(file_handle)

    total_messages = len(parsed_entries)

    print(f"[embedding-generator] Da doc {total_messages} dong log tu '{input_json}'.")

    # ------------------------------------------------------------------
    # Bước 2: Trích xuất danh sách message + line_number
    # ------------------------------------------------------------------
    # Mỗi dòng log có cấu trúc:
    #   {timestamp, host, service, severity, message, line_number}
    # Ta chỉ cần message để encode, và line_number để ánh xạ ngược.

    log_messages = []
    line_numbers = []

    for entry in parsed_entries:
        log_messages.append(entry["message"])
        line_numbers.append(entry["line_number"])

    # ------------------------------------------------------------------
    # Bước 3: Load model sentence-transformers
    # ------------------------------------------------------------------
    print(f"[embedding-generator] Dang tai model '{model_name}'...")
    load_start_time = time.time()

    model = SentenceTransformer(model_name)

    load_elapsed = time.time() - load_start_time
    print(f"[embedding-generator] Da tai model xong ({load_elapsed:.1f}s).")

    # ------------------------------------------------------------------
    # Bước 4: Encode toàn bộ message → embedding vectors
    # ------------------------------------------------------------------
    # SentenceTransformer.encode() tự động:
    #   - Tokenize từng câu (WordPiece tokenizer của BERT)
    #   - Chạy qua 6 lớp transformer của MiniLM
    #   - Lấy hidden state của token [CLS] → vector 384 chiều
    #   - Tự động normalize nếu dùng normalize_embeddings=True
    #
    # Tham số show_progress_bar=True hiển thị thanh tiến trình.

    print(f"[embedding-generator] Dang encode {total_messages} dong log "
          f"(batch_size={batch_size})...")
    encode_start_time = time.time()

    embedding_matrix = model.encode(
        log_messages,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,   # Chuẩn hóa L2 → ||vector|| = 1
        convert_to_numpy=True,
    )

    encode_elapsed = time.time() - encode_start_time
    print(f"[embedding-generator] Da encode xong ({encode_elapsed:.1f}s, "
          f"{encode_elapsed/total_messages*1000:.1f} ms/dong).")

    # Kiểm tra kích thước ma trận kết quả
    actual_shape = embedding_matrix.shape
    print(f"[embedding-generator] Kich thuoc ma tran embedding: {actual_shape}")
    assert actual_shape == (total_messages, EMBEDDING_DIM), \
        f"Kich thuoc khong dung! Mong doi ({total_messages}, {EMBEDDING_DIM}), " \
        f"nhan duoc {actual_shape}"

    # ------------------------------------------------------------------
    # Bước 5: Kiểm tra L2 normalization
    # ------------------------------------------------------------------
    # Sau normalize, mỗi vector phải có độ dài ~1.0
    vector_norms = np.linalg.norm(embedding_matrix, axis=1)
    min_norm = vector_norms.min()
    max_norm = vector_norms.max()
    print(f"[embedding-generator] Chuan L2 cua vector: min={min_norm:.6f}, "
          f"max={max_norm:.6f} (mong doi ~1.0)")

    # ------------------------------------------------------------------
    # Bước 6: Lưu ma trận embedding ra file .npy
    # ------------------------------------------------------------------
    output_npy_path = Path(output_npy)
    output_npy_path.parent.mkdir(parents=True, exist_ok=True)

    np.save(output_npy_path, embedding_matrix)
    npy_size_mb = output_npy_path.stat().st_size / (1024 * 1024)
    print(f"[embedding-generator] Da luu embeddings vao '{output_npy_path}' "
          f"({npy_size_mb:.2f} MB)")

    # ------------------------------------------------------------------
    # Bước 7: Lưu metadata ra file JSON
    # ------------------------------------------------------------------
    metadata = {
        "model_name": model_name,
        "dimension": EMBEDDING_DIM,
        "total_vectors": total_messages,
        "original_file": str(input_path.resolve()),
        "line_mapping": line_numbers,
        # Lưu thêm vài thông tin hữu ích cho debug
        "encode_time_seconds": round(encode_elapsed, 2),
        "l2_normalized": True,
        "dtype": str(embedding_matrix.dtype),
    }

    output_meta_path = Path(output_meta)
    output_meta_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_meta_path, "w", encoding="utf-8") as meta_handle:
        json.dump(metadata, meta_handle, indent=2, ensure_ascii=False)

    meta_size_kb = output_meta_path.stat().st_size / 1024
    print(f"[embedding-generator] Da luu metadata vao '{output_meta_path}' "
          f"({meta_size_kb:.1f} KB)")

    # ------------------------------------------------------------------
    # Bước 8: In thống kê cuối cùng
    # ------------------------------------------------------------------
    print(f"\n[embedding-generator] Hoan tat!")
    print(f"  Model            : {model_name}")
    print(f"  So dong da encode: {total_messages}")
    print(f"  Kich thuoc vector: {EMBEDDING_DIM} chieu")
    print(f"  Du lieu kieu      : {embedding_matrix.dtype}")
    print(f"  L2 normalized    : True")
    print(f"  Thoi gian encode : {encode_elapsed:.1f}s")
    print(f"  File .npy        : {output_npy_path.resolve()} "
          f"({npy_size_mb:.2f} MB)")
    print(f"  File meta        : {output_meta_path.resolve()} "
          f"({meta_size_kb:.1f} KB)")

    return embedding_matrix


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Embedding generator – vector hoa log message bang Sentence-BERT"
    )
    argument_parser.add_argument(
        "--input-json", type=str, default=DEFAULT_INPUT_JSON,
        help="File JSON tu syslog-parser",
    )
    argument_parser.add_argument(
        "--output-npy", type=str, default=DEFAULT_OUTPUT_NPY,
        help="File .npy de luu ma tran embedding",
    )
    argument_parser.add_argument(
        "--output-meta", type=str, default=DEFAULT_OUTPUT_META,
        help="File JSON metadata mo ta embedding",
    )
    argument_parser.add_argument(
        "--model-name", type=str, default=DEFAULT_MODEL_NAME,
        help="Ten model sentence-transformers",
    )
    argument_parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help="So dong encode cung luc (64-256 la hop ly)",
    )

    cli_args = argument_parser.parse_args()

    generate_embeddings(
        input_json=cli_args.input_json,
        output_npy=cli_args.output_npy,
        output_meta=cli_args.output_meta,
        model_name=cli_args.model_name,
        batch_size=cli_args.batch_size,
    )
