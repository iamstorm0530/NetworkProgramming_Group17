#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — knn-detector skill.

Phát hiện bất thường bằng thuật toán K-Nearest Neighbors (unsupervised).
Với mỗi dòng log, tính khoảng cách cosine trung bình đến k láng giềng
gần nhất trong không gian embedding. Dòng nào có khoảng cách trung bình
lớn hơn ngưỡng → bất thường.

Input:
    data/processed/embeddings.npy         – ma trận (5000, 384)
    data/processed/parsed_logs.json       – thông tin service
    data/raw/syslog_ground_truth.json     – ground truth (chỉ để đánh giá)

Output:
    logs/knn_results.json                 – kết quả detection + evaluation
"""

import json
import argparse
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Cấu hình mặc định
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDINGS_NPY = "data/processed/embeddings.npy"
DEFAULT_PARSED_LOGS = "data/processed/parsed_logs.json"
DEFAULT_GROUND_TRUTH = "data/raw/syslog_ground_truth.json"
DEFAULT_OUTPUT = "logs/knn_results.json"

DEFAULT_K_NEIGHBORS = 5               # Số láng giềng gần nhất
DEFAULT_THRESHOLD_SIGMA = 2.0         # Số lần std cho ngưỡng


# ===================================================================
# Nạp dữ liệu
# ===================================================================

def load_inputs(
    embeddings_path: str,
    parsed_logs_path: str,
    ground_truth_path: str,
) -> tuple[np.ndarray, list[dict], list[dict]]:
    """Nạp embedding, parsed logs, và ground truth.

    Returns:
        embedding_matrix: (n, 384) float32, L2-normalized
        parsed_entries:   danh sách dict {line_number, service, message, ...}
        ground_truth:     danh sách dict {line_number, is_anomaly, anomaly_type}
    """
    if not Path(embeddings_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {embeddings_path}")
    embedding_matrix = np.load(embeddings_path)

    if not Path(parsed_logs_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {parsed_logs_path}")
    with open(parsed_logs_path, "r", encoding="utf-8") as handle:
        parsed_entries = json.load(handle)

    if not Path(ground_truth_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {ground_truth_path}")
    with open(ground_truth_path, "r", encoding="utf-8") as handle:
        ground_truth = json.load(handle)

    total_vectors = embedding_matrix.shape[0]
    assert total_vectors == len(parsed_entries) == len(ground_truth), (
        f"So luong khong khop: embeddings={total_vectors}, "
        f"parsed={len(parsed_entries)}, truth={len(ground_truth)}"
    )

    return embedding_matrix, parsed_entries, ground_truth


# ===================================================================
# Tính KNN distances
# ===================================================================

def compute_knn_distances(
    embedding_matrix: np.ndarray,
    k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Tính khoảng cách cosine trung bình đến k láng giềng gần nhất.

    Thuật toán:
        1. similarity = embeddings @ embeddings.T        → (n, n)
           (dot product = cosine similarity vì đã L2 norm)
        2. distance = 1 - similarity                      → cosine distance
        3. Sắp xếp mỗi hàng, lấy k giá trị nhỏ nhất
           (bỏ qua distance=0 tại đường chéo — chính nó)
        4. knn_distance = mean của k giá trị đó

    Args:
        embedding_matrix: (n, dim) float32, L2-normalized
        k:               số láng giềng

    Returns:
        knn_distances:       (n,) float32 — khoảng cách trung bình đến k NN
        neighbor_indices:    (n, k) int — index của k láng giềng gần nhất
    """
    total_vectors = embedding_matrix.shape[0]

    # ------------------------------------------------------------------
    # Bước 1-2: Tính ma trận cosine distance
    # ------------------------------------------------------------------
    # similarity[i,j] = dot(embedding[i], embedding[j])
    # Vì cả 2 đều L2-normalized → đây chính là cosine similarity
    print(f"  [KNN] Tinh ma tran similarity ({total_vectors}x{total_vectors})...")
    start_matmul = time.time()

    similarity_matrix = embedding_matrix @ embedding_matrix.T     # (n, n)

    matmul_time = time.time() - start_matmul
    print(f"  [KNN] Ma tran similarity: {similarity_matrix.shape}, "
          f"dtype={similarity_matrix.dtype}, "
          f"ram={similarity_matrix.nbytes / (1024**2):.1f} MB "
          f"({matmul_time:.2f}s)")

    # Chuyển similarity → cosine distance
    # distance = 1 - similarity (range [0, 2] cho cosine distance)
    distance_matrix = 1.0 - similarity_matrix

    # Gán distance của mỗi điểm với chính nó = vô cùng
    # (để không chọn chính mình làm láng giềng gần nhất)
    np.fill_diagonal(distance_matrix, np.inf)

    # Giải phóng similarity_matrix để tiết kiệm RAM
    del similarity_matrix

    # ------------------------------------------------------------------
    # Bước 3: Tìm k láng giềng gần nhất cho mỗi điểm
    # ------------------------------------------------------------------
    # argsort trả về index sắp xếp theo distance tăng dần
    # Với 5000 điểm, argsort có thể tốn thời gian nhưng chấp nhận được
    print(f"  [KNN] Tim {k} nearest neighbors cho {total_vectors} diem...")
    start_sort = time.time()

    # Lấy index của k giá trị nhỏ nhất mỗi hàng (bỏ qua cột đầu là chính nó)
    # Cách tối ưu: dùng np.argpartition để tìm top-k nhanh hơn full sort
    #   1. partition để đưa k phần tử nhỏ nhất lên đầu mỗi hàng
    #   2. argsort trên k phần tử đó để có thứ tự chính xác
    partitioned_indices = np.argpartition(distance_matrix, k, axis=1)[:, :k]
    # Lấy distance tương ứng
    top_k_distances = np.take_along_axis(distance_matrix, partitioned_indices, axis=1)
    # Sắp xếp lại k distance và index theo thứ tự tăng dần
    sort_order = np.argsort(top_k_distances, axis=1)
    neighbor_indices = np.take_along_axis(partitioned_indices, sort_order, axis=1)
    top_k_distances_sorted = np.take_along_axis(top_k_distances, sort_order, axis=1)

    sort_time = time.time() - start_sort
    print(f"  [KNN] Tim neighbors xong ({sort_time:.2f}s)")

    # Giải phóng distance_matrix
    del distance_matrix

    # ------------------------------------------------------------------
    # Bước 4: Tính knn_distance = trung bình k khoảng cách
    # ------------------------------------------------------------------
    knn_distances = top_k_distances_sorted.mean(axis=1)          # (n,)

    return knn_distances, neighbor_indices


# ===================================================================
# Gắn cờ bất thường
# ===================================================================

def flag_anomalies(
    knn_distances: np.ndarray,
    neighbor_indices: np.ndarray,
    parsed_entries: list[dict],
    threshold_sigma: float,
) -> tuple[list[dict], dict]:
    """Dựa vào knn_distance để gắn cờ bất thường.

    Ngưỡng toàn cục: threshold = mean(knn_distances) + sigma * std(knn_distances)

    Args:
        knn_distances:    (n,) float32
        neighbor_indices: (n, k) int
        parsed_entries:   danh sách parsed logs
        threshold_sigma:  số lần std

    Returns:
        results:       list[dict] kết quả từng dòng
        global_stats:  dict thống kê toàn cục
    """
    total_vectors = len(knn_distances)
    line_numbers = [entry["line_number"] for entry in parsed_entries]
    services = [entry["service"] for entry in parsed_entries]

    # ---- Thống kê toàn cục ----
    mean_knn = float(knn_distances.mean())
    std_knn = float(knn_distances.std())
    threshold = mean_knn + threshold_sigma * std_knn

    global_stats = {
        "total_vectors": total_vectors,
        "mean_knn_distance": round(mean_knn, 6),
        "std_knn_distance": round(std_knn, 6),
        "threshold": round(threshold, 6),
    }

    # ---- Gắn cờ ----
    anomaly_flags = knn_distances > threshold
    total_anomalies = int(anomaly_flags.sum())

    global_stats["anomalies_found"] = total_anomalies
    global_stats["anomaly_ratio"] = round(total_anomalies / total_vectors, 4)

    # ---- Đóng gói kết quả ----
    results: list[dict] = []
    for idx in range(total_vectors):
        # Chuyển neighbor indices → neighbor line_numbers
        neighbor_line_nums = [line_numbers[nidx] for nidx in neighbor_indices[idx]]

        results.append({
            "line_number": line_numbers[idx],
            "service": services[idx],
            "knn_distance": round(float(knn_distances[idx]), 6),
            "anomaly_score": round(float(knn_distances[idx]) / 2.0, 6),
            "is_anomaly": bool(anomaly_flags[idx]),
            "neighbor_line_numbers": neighbor_line_nums,
        })

    return results, global_stats


# ===================================================================
# Đánh giá
# ===================================================================

def evaluate_results(
    detection_results: list[dict],
    ground_truth: list[dict],
) -> dict:
    """So sánh kết quả KNN với ground truth.

    Returns:
        dict: accuracy, precision, recall, f1, confusion matrix.
    """
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
        else:
            false_negatives += 1

    total = true_positives + false_positives + true_negatives + false_negatives

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

def run_knn_detector(
    embeddings_npy: str = DEFAULT_EMBEDDINGS_NPY,
    parsed_logs: str = DEFAULT_PARSED_LOGS,
    ground_truth: str = DEFAULT_GROUND_TRUTH,
    output: str = DEFAULT_OUTPUT,
    k_neighbors: int = DEFAULT_K_NEIGHBORS,
    threshold_sigma: float = DEFAULT_THRESHOLD_SIGMA,
) -> dict:
    """Chạy toàn bộ pipeline KNN detection + evaluation.

    Returns:
        output_data: dict gồm config, global_stats, results, evaluation.
    """
    print("=" * 60)
    print("[knn-detector] Bat dau...")
    print(f"  k               : {k_neighbors}")
    print(f"  Threshold sigma : {threshold_sigma}")

    # ------------------------------------------------------------------
    # Bước 1: Nạp dữ liệu
    # ------------------------------------------------------------------
    embedding_matrix, parsed_entries, truth_data = load_inputs(
        embeddings_npy, parsed_logs, ground_truth
    )
    total_vectors = embedding_matrix.shape[0]
    embedding_dim = embedding_matrix.shape[1]
    print(f"\n[knn-detector] Da nap {total_vectors} vectors "
          f"({embedding_dim} chieu)")

    # ------------------------------------------------------------------
    # Bước 2: Tính KNN distances
    # ------------------------------------------------------------------
    overall_start = time.time()

    knn_distances, neighbor_indices = compute_knn_distances(
        embedding_matrix, k_neighbors
    )

    # ------------------------------------------------------------------
    # Bước 3: Gắn cờ bất thường
    # ------------------------------------------------------------------
    detection_results, global_stats = flag_anomalies(
        knn_distances, neighbor_indices, parsed_entries, threshold_sigma
    )

    total_anomalies = global_stats["anomalies_found"]
    print(f"\n[knn-detector] Phat hien {total_anomalies}/{total_vectors} "
          f"bat thuong ({total_anomalies/total_vectors*100:.1f}%)")
    print(f"  Mean KNN distance : {global_stats['mean_knn_distance']:.4f}")
    print(f"  Std KNN distance  : {global_stats['std_knn_distance']:.4f}")
    print(f"  Threshold         : {global_stats['threshold']:.4f}")

    # Phân bố theo service
    service_anomalies: dict[str, int] = {}
    for r in detection_results:
        if r["is_anomaly"]:
            svc = r["service"]
            service_anomalies[svc] = service_anomalies.get(svc, 0) + 1

    print(f"\n  Anomalies per service:")
    for svc in sorted(service_anomalies.keys()):
        total_svc = sum(1 for r in detection_results if r["service"] == svc)
        print(f"    {svc:<12}: {service_anomalies[svc]:>4}/{total_svc:<4} "
              f"({service_anomalies[svc]/total_svc*100:.1f}%)")

    # ------------------------------------------------------------------
    # Bước 4: Đánh giá
    # ------------------------------------------------------------------
    print(f"\n[knn-detector] Dang danh gia voi ground truth...")
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
    # Bước 5: Lưu kết quả
    # ------------------------------------------------------------------
    total_time = time.time() - overall_start

    output_data = {
        "config": {
            "method": "knn",
            "k": k_neighbors,
            "distance_metric": "cosine_distance",
            "threshold_sigma": threshold_sigma,
        },
        "global_stats": global_stats,
        "results": detection_results,
        "evaluation": evaluation,
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output_data, handle, indent=2, ensure_ascii=False)

    print(f"\n[knn-detector] Da luu ket qua vao '{output_path.resolve()}'")
    print(f"[knn-detector] Hoan tat! (tong thoi gian: {total_time:.2f}s)")

    return output_data


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="KNN detector – phat hien bat thuong bang K-Nearest Neighbors"
    )
    argument_parser.add_argument(
        "--embeddings-npy", type=str, default=DEFAULT_EMBEDDINGS_NPY,
        help="File ma tran embedding .npy",
    )
    argument_parser.add_argument(
        "--parsed-logs", type=str, default=DEFAULT_PARSED_LOGS,
        help="File parsed_logs.json",
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
        "--k-neighbors", type=int, default=DEFAULT_K_NEIGHBORS,
        help="So lang gieng gan nhat (mac dinh 5)",
    )
    argument_parser.add_argument(
        "--threshold-sigma", type=float, default=DEFAULT_THRESHOLD_SIGMA,
        help="So lan std de tinh nguong (mac dinh 2.0)",
    )

    cli_args = argument_parser.parse_args()

    run_knn_detector(
        embeddings_npy=cli_args.embeddings_npy,
        parsed_logs=cli_args.parsed_logs,
        ground_truth=cli_args.ground_truth,
        output=cli_args.output,
        k_neighbors=cli_args.k_neighbors,
        threshold_sigma=cli_args.threshold_sigma,
    )
