#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — centroid-detector skill.

Phát hiện bất thường bằng phương pháp Per-Service Centroid (unsupervised).
Mỗi service có một vector trung tâm riêng. Dòng log nào nằm quá xa centroid
của service tương ứng sẽ bị gắn cờ bất thường.

Input:
    data/processed/embeddings.npy         – ma trận (5000, 384)
    data/processed/embeddings_meta.json   – line_mapping
    data/processed/parsed_logs.json       – thông tin service từng dòng
    data/raw/syslog_ground_truth.json     – ground truth (chỉ để đánh giá)

Output:
    logs/centroid_results.json            – kết quả detection + evaluation
"""

import json
import argparse
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Cấu hình mặc định
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDINGS_NPY = "data/processed/embeddings.npy"
DEFAULT_EMBEDDINGS_META = "data/processed/embeddings_meta.json"
DEFAULT_PARSED_LOGS = "data/processed/parsed_logs.json"
DEFAULT_GROUND_TRUTH = "data/raw/syslog_ground_truth.json"
DEFAULT_OUTPUT = "logs/centroid_results.json"

DEFAULT_THRESHOLD_SIGMA = 2.0        # Số lần std để tính ngưỡng
DEFAULT_TRIM_RATIO = 0.0             # Tỷ lệ outlier bị loại khi tính centroid


# ===================================================================
# Hàm phụ trợ
# ===================================================================

def load_inputs(
    embeddings_path: str,
    parsed_logs_path: str,
    ground_truth_path: str,
) -> tuple[np.ndarray, list[dict], list[dict]]:
    """Nạp toàn bộ dữ liệu đầu vào.

    Returns:
        embedding_matrix: (5000, 384) float32
        parsed_entries:   danh sách 5000 dict từ parsed_logs.json
        ground_truth:     danh sách 5000 dict từ ground_truth.json
    """
    # Load ma trận embedding
    if not Path(embeddings_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {embeddings_path}")
    embedding_matrix = np.load(embeddings_path)

    # Load parsed logs (để lấy service)
    if not Path(parsed_logs_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {parsed_logs_path}")
    with open(parsed_logs_path, "r", encoding="utf-8") as handle:
        parsed_entries = json.load(handle)

    # Load ground truth (chỉ để đánh giá)
    if not Path(ground_truth_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {ground_truth_path}")
    with open(ground_truth_path, "r", encoding="utf-8") as handle:
        ground_truth = json.load(handle)

    # Kiểm tra khớp số lượng
    total_vectors = embedding_matrix.shape[0]
    assert total_vectors == len(parsed_entries) == len(ground_truth), (
        f"So luong khong khop: embeddings={total_vectors}, "
        f"parsed={len(parsed_entries)}, ground_truth={len(ground_truth)}"
    )

    return embedding_matrix, parsed_entries, ground_truth


def group_embeddings_by_service(
    embedding_matrix: np.ndarray,
    parsed_entries: list[dict],
) -> dict[str, np.ndarray]:
    """Nhóm các embedding vector theo service.

    Returns:
        service_embeddings: dict {tên_service: ma_trận_con (n_service, 384)}
    """
    # Bước 1: Gom index theo service
    service_indices: dict[str, list[int]] = {}

    for idx, entry in enumerate(parsed_entries):
        service_name = entry["service"]
        if service_name not in service_indices:
            service_indices[service_name] = []
        service_indices[service_name].append(idx)

    # Bước 2: Tạo ma trận con cho từng service
    service_embeddings: dict[str, np.ndarray] = {}

    for service_name, indices in service_indices.items():
        service_embeddings[service_name] = embedding_matrix[indices]

    return service_embeddings


def compute_centroid(vectors: np.ndarray, trim_ratio: float = 0.0) -> np.ndarray:
    """Tính centroid từ tập vector, có tùy chọn trim outlier.

    Nếu trim_ratio > 0:
        1. Tính centroid tạm từ toàn bộ vector
        2. Tính cosine distance từng vector đến centroid tạm
        3. Loại bỏ top (trim_ratio * 100)% vector xa nhất
        4. Tính centroid cuối cùng từ tập đã trim

    Args:
        vectors:    (n, 384) float32, đã L2-normalized
        trim_ratio: tỷ lệ outlier bị loại [0, 1)

    Returns:
        centroid: (384,) float32, L2-normalized
    """
    if vectors.shape[0] == 0:
        # Service không có mẫu nào → trả về vector 0
        return np.zeros(vectors.shape[1], dtype=np.float32)

    if trim_ratio <= 0.0:
        # Không trim → centroid = mean trực tiếp
        centroid_raw = vectors.mean(axis=0)
    else:
        # Có trim → loại bỏ outlier trước khi tính mean
        # Bước 1: Centroid tạm từ toàn bộ
        temp_centroid = vectors.mean(axis=0)
        temp_centroid = temp_centroid / (np.linalg.norm(temp_centroid) + 1e-10)

        # Bước 2: Cosine distance đến centroid tạm
        similarities = vectors @ temp_centroid          # dot product (đã L2 norm)
        distances = 1.0 - similarities                   # cosine distance

        # Bước 3: Giữ lại (1 - trim_ratio) vector gần centroid nhất
        keep_count = max(1, int(vectors.shape[0] * (1.0 - trim_ratio)))
        keep_indices = np.argsort(distances)[:keep_count]  # sort tăng dần, lấy đầu

        # Bước 4: Centroid từ tập đã trim
        centroid_raw = vectors[keep_indices].mean(axis=0)

    # Chuẩn hóa L2 để centroid có độ dài = 1
    centroid_norm = np.linalg.norm(centroid_raw)
    if centroid_norm < 1e-10:
        # Tránh chia cho 0
        return centroid_raw
    return centroid_raw / centroid_norm


def detect_anomalies_per_service(
    service_embeddings: dict[str, np.ndarray],
    parsed_entries: list[dict],
    threshold_sigma: float,
    trim_ratio: float,
) -> tuple[list[dict], dict[str, dict]]:
    """Thực hiện detection per-service centroid.

    Args:
        service_embeddings: dict service → ma trận embedding
        parsed_entries:     danh sách parsed logs (để lấy service, line_number)
        threshold_sigma:    số lần std để tính ngưỡng
        trim_ratio:         tỷ lệ outlier bị loại khi tính centroid

    Returns:
        all_results:        danh sách kết quả từng dòng (đã sắp xếp theo line_number)
        per_service_stats:  dict thống kê từng service
    """
    # Tạo mapping từ index → (line_number, service)
    line_numbers = [entry["line_number"] for entry in parsed_entries]
    services = [entry["service"] for entry in parsed_entries]

    # Mảng lưu kết quả tạm (theo index embedding)
    cosine_distances = np.zeros(len(parsed_entries), dtype=np.float32)
    anomaly_flags = np.zeros(len(parsed_entries), dtype=bool)
    per_service_stats: dict[str, dict] = {}

    # Duyệt từng service
    for service_name, vectors in service_embeddings.items():
        sample_count = vectors.shape[0]

        # ---- Tính centroid ----
        centroid = compute_centroid(vectors, trim_ratio=trim_ratio)

        # ---- Tính cosine distance ----
        # Vì cả embedding và centroid đều L2-normalized:
        #   cosine_similarity = embedding @ centroid
        #   cosine_distance   = 1 - cosine_similarity
        similarities = vectors @ centroid
        distances = 1.0 - similarities                     # shape (n_service,)

        # ---- Tính ngưỡng per-service ----
        mean_dist = float(distances.mean())
        std_dist = float(distances.std())
        threshold = mean_dist + threshold_sigma * std_dist

        # ---- Gắn cờ bất thường ----
        is_anomaly = distances > threshold

        # ---- Lưu thống kê ----
        per_service_stats[service_name] = {
            "sample_count": sample_count,
            "centroid_norm": float(np.linalg.norm(centroid)),
            "mean_distance": round(mean_dist, 6),
            "std_distance": round(std_dist, 6),
            "threshold": round(threshold, 6),
            "anomalies_found": int(is_anomaly.sum()),
            "anomaly_ratio": round(float(is_anomaly.sum()) / sample_count, 4),
        }

        # ---- Gán kết quả về đúng vị trí trong mảng tổng ----
        # Cần tìm các index của service này trong parsed_entries
        service_indices_in_full = [
            idx for idx, svc in enumerate(services) if svc == service_name
        ]

        for local_idx, global_idx in enumerate(service_indices_in_full):
            cosine_distances[global_idx] = distances[local_idx]
            anomaly_flags[global_idx] = is_anomaly[local_idx]

    # ---- Đóng gói kết quả thành list dict, sắp xếp theo line_number ----
    all_results: list[dict] = []
    for idx in range(len(parsed_entries)):
        all_results.append({
            "line_number": line_numbers[idx],
            "service": services[idx],
            "cosine_distance": round(float(cosine_distances[idx]), 6),
            "anomaly_score": round(float(cosine_distances[idx]) / 2.0, 6),
            "is_anomaly": bool(anomaly_flags[idx]),
        })

    return all_results, per_service_stats


# ===================================================================
# Đánh giá (evaluation)
# ===================================================================

def evaluate_results(
    detection_results: list[dict],
    ground_truth: list[dict],
) -> dict:
    """So sánh kết quả detection với ground truth.

    Returns:
        dict chứa accuracy, precision, recall, f1, confusion matrix.
    """
    # Tạo dict tra cứu ground truth theo line_number
    truth_by_line: dict[int, bool] = {}
    for entry in ground_truth:
        truth_by_line[entry["line_number"]] = entry["is_anomaly"]

    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0

    for result in detection_results:
        predicted = result["is_anomaly"]
        actual = truth_by_line.get(result["line_number"], False)

        if predicted and actual:
            true_positives += 1
        elif predicted and not actual:
            false_positives += 1
        elif not predicted and not actual:
            true_negatives += 1
        else:   # not predicted and actual → missed anomaly
            false_negatives += 1

    total = true_positives + false_positives + true_negatives + false_negatives

    # Tính các metric
    accuracy = (true_positives + true_negatives) / total if total > 0 else 0.0
    precision = true_positives / (true_positives + false_positives) \
        if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) \
        if (true_positives + false_negatives) > 0 else 0.0
    f1_score = 2 * precision * recall / (precision + recall) \
        if (precision + recall) > 0 else 0.0

    return {
        "total_samples": total,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
    }


# ===================================================================
# Hàm chính
# ===================================================================

def run_centroid_detector(
    embeddings_npy: str = DEFAULT_EMBEDDINGS_NPY,
    parsed_logs: str = DEFAULT_PARSED_LOGS,
    ground_truth: str = DEFAULT_GROUND_TRUTH,
    output: str = DEFAULT_OUTPUT,
    threshold_sigma: float = DEFAULT_THRESHOLD_SIGMA,
    trim_ratio: float = DEFAULT_TRIM_RATIO,
) -> dict:
    """Chạy toàn bộ pipeline centroid detection + evaluation.

    Returns:
        output_data: dict gồm config, per_service_stats, results, evaluation.
    """
    print("=" * 60)
    print("[centroid-detector] Bat dau...")
    print(f"  Threshold sigma : {threshold_sigma}")
    print(f"  Trim ratio      : {trim_ratio}")

    # ------------------------------------------------------------------
    # Bước 1: Nạp dữ liệu
    # ------------------------------------------------------------------
    embedding_matrix, parsed_entries, truth_data = load_inputs(
        embeddings_npy, parsed_logs, ground_truth
    )
    total_vectors = embedding_matrix.shape[0]
    embedding_dim = embedding_matrix.shape[1]
    print(f"\n[centroid-detector] Da nap {total_vectors} vectors "
          f"({embedding_dim} chieu)")

    # ------------------------------------------------------------------
    # Bước 2: Nhóm theo service
    # ------------------------------------------------------------------
    service_embeddings = group_embeddings_by_service(
        embedding_matrix, parsed_entries
    )
    service_names = sorted(service_embeddings.keys())
    print(f"[centroid-detector] {len(service_names)} services: "
          f"{', '.join(service_names)}")

    # ------------------------------------------------------------------
    # Bước 3-4: Tính centroid, cosine distance, ngưỡng, gắn cờ
    # ------------------------------------------------------------------
    detection_results, per_service_stats = detect_anomalies_per_service(
        service_embeddings, parsed_entries, threshold_sigma, trim_ratio
    )

    total_anomalies = sum(1 for r in detection_results if r["is_anomaly"])
    print(f"\n[centroid-detector] Phat hien {total_anomalies}/{total_vectors} "
          f"bat thuong ({total_anomalies/total_vectors*100:.1f}%)")

    # In chi tiết từng service
    print("\n  Per-service stats:")
    print(f"  {'Service':<12} {'Samples':>8} {'Mean':>8} {'Std':>8} "
          f"{'Thresh':>8} {'Anom':>6} {'Rate':>7}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*7}")
    for svc in service_names:
        s = per_service_stats[svc]
        print(f"  {svc:<12} {s['sample_count']:>8} {s['mean_distance']:>8.4f} "
              f"{s['std_distance']:>8.4f} {s['threshold']:>8.4f} "
              f"{s['anomalies_found']:>6} {s['anomaly_ratio']:>7.2%}")

    # ------------------------------------------------------------------
    # Bước 5: Đánh giá với ground truth
    # ------------------------------------------------------------------
    print(f"\n[centroid-detector] Dang danh gia voi ground truth...")
    evaluation = evaluate_results(detection_results, truth_data)

    print(f"\n  Evaluation results:")
    print(f"  Accuracy : {evaluation['accuracy']:.4f}")
    print(f"  Precision: {evaluation['precision']:.4f}")
    print(f"  Recall   : {evaluation['recall']:.4f}")
    print(f"  F1 Score : {evaluation['f1_score']:.4f}")
    print(f"  TP={evaluation['true_positives']}  "
          f"FP={evaluation['false_positives']}  "
          f"TN={evaluation['true_negatives']}  "
          f"FN={evaluation['false_negatives']}")

    # ------------------------------------------------------------------
    # Bước 6: Lưu kết quả
    # ------------------------------------------------------------------
    output_data = {
        "config": {
            "method": "per_service_centroid",
            "distance_metric": "cosine_distance",
            "threshold_sigma": threshold_sigma,
            "trim_ratio": trim_ratio,
        },
        "per_service_stats": per_service_stats,
        "results": detection_results,
        "evaluation": evaluation,
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output_data, handle, indent=2, ensure_ascii=False)

    print(f"\n[centroid-detector] Da luu ket qua vao '{output_path.resolve()}'")
    print(f"[centroid-detector] Hoan tat!")

    return output_data


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Centroid detector – phat hien bat thuong bang Per-Service Centroid"
    )
    argument_parser.add_argument(
        "--embeddings-npy", type=str, default=DEFAULT_EMBEDDINGS_NPY,
        help="File ma tran embedding .npy",
    )
    argument_parser.add_argument(
        "--parsed-logs", type=str, default=DEFAULT_PARSED_LOGS,
        help="File parsed_logs.json (de lay service)",
    )
    argument_parser.add_argument(
        "--ground-truth", type=str, default=DEFAULT_GROUND_TRUTH,
        help="File ground truth (chi de danh gia)",
    )
    argument_parser.add_argument(
        "--output", type=str, default=DEFAULT_OUTPUT,
        help="File JSON ket qua",
    )
    argument_parser.add_argument(
        "--threshold-sigma", type=float, default=DEFAULT_THRESHOLD_SIGMA,
        help="So lan std de tinh nguong (mac dinh 2.0)",
    )
    argument_parser.add_argument(
        "--trim-ratio", type=float, default=DEFAULT_TRIM_RATIO,
        help="Ty le outlier loai bo khi tinh centroid (0.0 - 0.3)",
    )

    cli_args = argument_parser.parse_args()

    run_centroid_detector(
        embeddings_npy=cli_args.embeddings_npy,
        parsed_logs=cli_args.parsed_logs,
        ground_truth=cli_args.ground_truth,
        output=cli_args.output,
        threshold_sigma=cli_args.threshold_sigma,
        trim_ratio=cli_args.trim_ratio,
    )
