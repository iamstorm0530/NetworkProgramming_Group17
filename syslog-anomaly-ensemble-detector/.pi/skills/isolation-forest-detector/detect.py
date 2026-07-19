#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — isolation-forest-detector skill.

Phat hien bat thuong bang thuat toan Isolation Forest (unsupervised).
Su dung sklearn.ensemble.IsolationForest. Diem nao de bi co lap
(it lan phan nhanh) → bat thuong.

Input:
    data/processed/embeddings.npy         – ma tran (5000, 384)
    data/processed/parsed_logs.json       – thong tin service
    data/raw/syslog_ground_truth.json     – ground truth (chi de danh gia)

Output:
    data/processed/isolation_forest_results.json    – ket qua detection + evaluation
"""

import json
import argparse
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest

# ---------------------------------------------------------------------------
# Cau hinh mac dinh
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDINGS_NPY = "data/processed/embeddings.npy"
DEFAULT_PARSED_LOGS = "data/processed/parsed_logs.json"
DEFAULT_GROUND_TRUTH = "data/raw/syslog_ground_truth.json"
DEFAULT_OUTPUT = "data/processed/isolation_forest_results.json"

DEFAULT_CONTAMINATION = 0.05          # Ty le anomaly uoc tinh
DEFAULT_RANDOM_STATE = 42
DEFAULT_N_ESTIMATORS = 100            # So cay trong rung


# ===================================================================
# Nap du lieu
# ===================================================================

def load_inputs(
    embeddings_path: str,
    parsed_logs_path: str,
    ground_truth_path: str | None,
) -> tuple[np.ndarray, list[dict], list[dict] | None]:
    """Nap embedding, parsed logs, va ground truth.

    Returns:
        embedding_matrix: (n, 384) float32
        parsed_entries:   danh sach dict {line_number, service, message, ...}
        ground_truth:     danh sach dict hoac None
    """
    if not Path(embeddings_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {embeddings_path}")
    embedding_matrix = np.load(embeddings_path)

    if not Path(parsed_logs_path).exists():
        raise FileNotFoundError(f"Khong tim thay file: {parsed_logs_path}")
    with open(parsed_logs_path, "r", encoding="utf-8") as handle:
        parsed_entries = json.load(handle)

    # Ground truth la optional
    ground_truth = None
    if ground_truth_path and Path(ground_truth_path).exists():
        with open(ground_truth_path, "r", encoding="utf-8") as handle:
            ground_truth = json.load(handle)

    total_vectors = embedding_matrix.shape[0]
    assert total_vectors == len(parsed_entries), (
        f"So luong khong khop: embeddings={total_vectors}, "
        f"parsed={len(parsed_entries)}"
    )

    return embedding_matrix, parsed_entries, ground_truth


# ===================================================================
# Phat hien bang Isolation Forest
# ===================================================================

def detect_with_isolation_forest(
    embedding_matrix: np.ndarray,
    parsed_entries: list[dict],
    contamination: float,
    random_state: int,
    n_estimators: int,
) -> tuple[list[dict], dict]:
    """Chay Isolation Forest de phat hien bat thuong.

    Args:
        embedding_matrix: (n, dim) float32
        parsed_entries:   danh sach parsed logs
        contamination:    ty le anomaly uoc tinh
        random_state:     seed
        n_estimators:     so cay

    Returns:
        results:       list[dict] ket qua tung dong
        global_stats:  dict thong ke toan cuc
    """
    total_vectors = embedding_matrix.shape[0]
    line_numbers = [entry["line_number"] for entry in parsed_entries]
    services = [entry["service"] for entry in parsed_entries]

    # ------------------------------------------------------------------
    # Huan luyen Isolation Forest
    # ------------------------------------------------------------------
    print(f"  [IF] Huan luyen IsolationForest "
          f"(n_estimators={n_estimators}, contamination={contamination})...")
    train_start = time.time()

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,            # Dung tat ca CPU cores
    )
    predictions = model.fit_predict(embedding_matrix)     # -1=anomaly, 1=normal

    train_time = time.time() - train_start
    print(f"  [IF] Huan luyen xong ({train_time:.2f}s)")

    # ------------------------------------------------------------------
    # Tinh anomaly_score tu decision_function
    # ------------------------------------------------------------------
    # decision_function: am = bat thuong, duong = binh thuong
    decision_scores = model.decision_function(embedding_matrix)

    # Dao dau de: duong = bat thuong
    raw_scores = -decision_scores

    # Chuan hoa ve [0, 1]
    score_min = raw_scores.min()
    score_max = raw_scores.max()
    if score_max - score_min > 1e-10:
        anomaly_scores = (raw_scores - score_min) / (score_max - score_min)
    else:
        anomaly_scores = np.zeros_like(raw_scores)

    # Gán co anomaly
    anomaly_flags = predictions == -1
    total_anomalies = int(anomaly_flags.sum())

    # ------------------------------------------------------------------
    # Thong ke toan cuc
    # ------------------------------------------------------------------
    global_stats = {
        "total_vectors": total_vectors,
        "anomalies_found": total_anomalies,
        "anomaly_ratio": round(total_anomalies / total_vectors, 4),
        "train_time_seconds": round(train_time, 2),
    }

    # Phan bo theo service
    service_counts: dict[str, int] = {}
    for idx in range(total_vectors):
        if anomaly_flags[idx]:
            svc = services[idx]
            service_counts[svc] = service_counts.get(svc, 0) + 1

    global_stats["anomalies_per_service"] = service_counts

    # ------------------------------------------------------------------
    # Dong goi ket qua
    # ------------------------------------------------------------------
    results: list[dict] = []
    for idx in range(total_vectors):
        results.append({
            "line_number": line_numbers[idx],
            "service": services[idx],
            "anomaly_score": round(float(anomaly_scores[idx]), 6),
            "is_anomaly": bool(anomaly_flags[idx]),
        })

    return results, global_stats


# ===================================================================
# Danh gia
# ===================================================================

def evaluate_results(
    detection_results: list[dict],
    ground_truth: list[dict],
) -> dict:
    """So sanh ket qua Isolation Forest voi ground truth."""
    truth_by_line: dict[int, bool] = {}
    for entry in ground_truth:
        truth_by_line[entry["line_number"]] = entry["is_anomaly"]

    tp = fp = tn = fn = 0
    for result in detection_results:
        predicted = result["is_anomaly"]
        actual = truth_by_line.get(result["line_number"], False)

        if predicted and actual:      tp += 1
        elif predicted and not actual: fp += 1
        elif not predicted and not actual: tn += 1
        else:                          fn += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = 2 * precision * recall / (precision + recall) \
        if (precision + recall) > 0 else 0.0

    return {
        "total_samples": total,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
    }


# ===================================================================
# Ham chinh
# ===================================================================

def run_isolation_forest_detector(
    embeddings_npy: str = DEFAULT_EMBEDDINGS_NPY,
    parsed_logs: str = DEFAULT_PARSED_LOGS,
    ground_truth: str = DEFAULT_GROUND_TRUTH,
    output: str = DEFAULT_OUTPUT,
    contamination: float = DEFAULT_CONTAMINATION,
    random_state: int = DEFAULT_RANDOM_STATE,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
) -> dict:
    """Chay toan bo pipeline Isolation Forest detection + evaluation.

    Returns:
        output_data: dict gom config, global_stats, results, evaluation.
    """
    print("=" * 60)
    print("[isolation-forest-detector] Bat dau...")
    print(f"  Contamination   : {contamination}")
    print(f"  N estimators    : {n_estimators}")
    print(f"  Random state    : {random_state}")

    # ------------------------------------------------------------------
    # Buoc 1: Nap du lieu
    # ------------------------------------------------------------------
    embedding_matrix, parsed_entries, truth_data = load_inputs(
        embeddings_npy, parsed_logs, ground_truth
    )
    total_vectors = embedding_matrix.shape[0]
    embedding_dim = embedding_matrix.shape[1]
    print(f"\n[IF] Da nap {total_vectors} vectors ({embedding_dim} chieu)")

    # ------------------------------------------------------------------
    # Buoc 2: Detection
    # ------------------------------------------------------------------
    detection_results, global_stats = detect_with_isolation_forest(
        embedding_matrix, parsed_entries, contamination, random_state,
        n_estimators,
    )

    total_anomalies = global_stats["anomalies_found"]
    print(f"\n[IF] Phat hien {total_anomalies}/{total_vectors} "
          f"bat thuong ({total_anomalies/total_vectors*100:.1f}%)")

    # In phan bo theo service
    per_svc = global_stats.get("anomalies_per_service", {})
    if per_svc:
        print(f"\n  Anomalies per service:")
        total_by_svc = {}
        for entry in parsed_entries:
            svc = entry["service"]
            total_by_svc[svc] = total_by_svc.get(svc, 0) + 1
        for svc in sorted(per_svc.keys()):
            total_svc = total_by_svc.get(svc, 0)
            print(f"    {svc:<12}: {per_svc[svc]:>4}/{total_svc:<4} "
                  f"({per_svc[svc]/total_svc*100:.1f}%)")

    # ------------------------------------------------------------------
    # Buoc 3: Danh gia
    # ------------------------------------------------------------------
    evaluation = None
    if truth_data is not None:
        print(f"\n[IF] Dang danh gia voi ground truth...")
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
    # Buoc 4: Luu ket qua
    # ------------------------------------------------------------------
    output_data: dict = {
        "config": {
            "method": "isolation_forest",
            "contamination": contamination,
            "n_estimators": n_estimators,
            "random_state": random_state,
        },
        "global_stats": global_stats,
        "results": detection_results,
    }
    if evaluation is not None:
        output_data["evaluation"] = evaluation

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output_data, handle, indent=2, ensure_ascii=False)

    print(f"\n[IF] Da luu ket qua vao '{output_path.resolve()}'")
    print(f"[IF] Hoan tat!")

    return output_data


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Isolation Forest detector – phat hien bat thuong bang IsolationForest"
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
        "--contamination", type=float, default=DEFAULT_CONTAMINATION,
        help="Ty le anomaly uoc tinh (mac dinh 0.05)",
    )
    argument_parser.add_argument(
        "--random-state", type=int, default=DEFAULT_RANDOM_STATE,
        help="Seed cho reproducible",
    )
    argument_parser.add_argument(
        "--n-estimators", type=int, default=DEFAULT_N_ESTIMATORS,
        help="So cay trong rung (mac dinh 100)",
    )

    cli_args = argument_parser.parse_args()

    run_isolation_forest_detector(
        embeddings_npy=cli_args.embeddings_npy,
        parsed_logs=cli_args.parsed_logs,
        ground_truth=cli_args.ground_truth,
        output=cli_args.output,
        contamination=cli_args.contamination,
        random_state=cli_args.random_state,
        n_estimators=cli_args.n_estimators,
    )
