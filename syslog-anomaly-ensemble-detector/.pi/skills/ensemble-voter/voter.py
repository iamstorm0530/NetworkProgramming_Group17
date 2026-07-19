#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — ensemble-voter skill.

Ket hop ket qua tu 3 detector thanh quyet dinh cuoi cung bang cac
chien luoc bo phieu:
    1. weighted_average – trung binh co trong so cua anomaly score
    2. majority_and    – tat ca detector cung gan co → bat thuong
    3. majority_2of3   – it nhat 2/3 detector gan co → bat thuong
    4. majority_or     – it nhat 1 detector gan co → bat thuong

Input:
    logs/centroid_results.json
    logs/knn_results.json
    data/processed/isolation_forest_results.json
    data/raw/syslog_ground_truth.json  (danh gia)

Output:
    logs/ensemble_results.json
"""

import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Cau hinh mac dinh
# ---------------------------------------------------------------------------
DEFAULT_CENTROID_RESULTS = "logs/centroid_results.json"
DEFAULT_KNN_RESULTS = "logs/knn_results.json"
DEFAULT_IFOREST_RESULTS = "data/processed/isolation_forest_results.json"
DEFAULT_GROUND_TRUTH = "data/raw/syslog_ground_truth.json"
DEFAULT_OUTPUT = "logs/ensemble_results.json"

DEFAULT_WEIGHT_CENTROID = 1.0
DEFAULT_WEIGHT_KNN = 1.0
DEFAULT_WEIGHT_IFOREST = 1.0
DEFAULT_WEIGHTED_THRESHOLD = 0.5

# Cac chien luoc ensemble
STRATEGY_WEIGHTED = "weighted_average"
STRATEGY_AND = "majority_and"
STRATEGY_2OF3 = "majority_2of3"
STRATEGY_OR = "majority_or"

ALL_STRATEGIES = [STRATEGY_WEIGHTED, STRATEGY_AND, STRATEGY_2OF3, STRATEGY_OR]


# ===================================================================
# Nap du lieu
# ===================================================================

def load_detector_results(
    centroid_path: str,
    knn_path: str,
    iforest_path: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Nap ket qua tu 3 detector.

    Returns:
        centroid_results, knn_results, iforest_results
    """
    results: dict[str, list[dict]] = {}

    for name, path in [
        ("centroid", centroid_path),
        ("knn", knn_path),
        ("iforest", iforest_path),
    ]:
        if not Path(path).exists():
            raise FileNotFoundError(f"Khong tim thay: {path}")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        results[name] = data["results"]

    # Kiem tra so luong khop
    n_centroid = len(results["centroid"])
    n_knn = len(results["knn"])
    n_iforest = len(results["iforest"])
    assert n_centroid == n_knn == n_iforest, (
        f"So luong khong khop: centroid={n_centroid}, "
        f"knn={n_knn}, iforest={n_iforest}"
    )

    return results["centroid"], results["knn"], results["iforest"]


def build_lookup_by_line(results: list[dict]) -> dict[int, dict]:
    """Tao dict tra cuu nhanh theo line_number."""
    return {entry["line_number"]: entry for entry in results}


# ===================================================================
# Chien luoc ensemble
# ===================================================================

def compute_weighted_average(
    centroid_results: list[dict],
    knn_results: list[dict],
    iforest_results: list[dict],
    weight_centroid: float,
    weight_knn: float,
    weight_iforest: float,
    threshold: float,
) -> tuple[list[dict], int]:
    """Tinh weighted average anomaly score tu 3 detector.

    ensemble_score = (w_c*s_c + w_k*s_k + w_if*s_if) / (w_c + w_k + w_if)
    """
    total_weight = weight_centroid + weight_knn + weight_iforest
    if total_weight == 0:
        total_weight = 1.0

    knn_lookup = build_lookup_by_line(knn_results)
    iforest_lookup = build_lookup_by_line(iforest_results)

    results: list[dict] = []
    anomalies_found = 0

    for cent_entry in centroid_results:
        line_num = cent_entry["line_number"]
        centroid_score = cent_entry.get("anomaly_score", 0)
        knn_score = knn_lookup.get(line_num, {}).get("anomaly_score", 0)
        iforest_score = iforest_lookup.get(line_num, {}).get("anomaly_score", 0)

        ensemble_score = (
            weight_centroid * centroid_score
            + weight_knn * knn_score
            + weight_iforest * iforest_score
        ) / total_weight

        is_anomaly = ensemble_score > threshold
        if is_anomaly:
            anomalies_found += 1

        results.append({
            "line_number": line_num,
            "service": cent_entry["service"],
            "centroid_score": centroid_score,
            "knn_score": knn_score,
            "iforest_score": iforest_score,
            "weighted_average_score": round(ensemble_score, 6),
            "weighted_average_is_anomaly": is_anomaly,
        })

    return results, anomalies_found


def compute_majority_votes(
    centroid_results: list[dict],
    knn_results: list[dict],
    iforest_results: list[dict],
) -> tuple[list[dict], int, int, int]:
    """Tinh majority_and, majority_2of3, majority_or.

    - majority_and:  ca 3 cung gan co
    - majority_2of3: it nhat 2/3 gan co
    - majority_or:   it nhat 1/3 gan co
    """
    knn_lookup = build_lookup_by_line(knn_results)
    iforest_lookup = build_lookup_by_line(iforest_results)

    results: list[dict] = []
    and_count = 0
    two_of_three_count = 0
    or_count = 0

    for cent_entry in centroid_results:
        line_num = cent_entry["line_number"]
        cent_flag = cent_entry.get("is_anomaly", False)
        knn_flag = knn_lookup.get(line_num, {}).get("is_anomaly", False)
        iforest_flag = iforest_lookup.get(line_num, {}).get("is_anomaly", False)

        vote_sum = (1 if cent_flag else 0) + (1 if knn_flag else 0) + (1 if iforest_flag else 0)

        and_result = vote_sum == 3
        two_of_three = vote_sum >= 2
        or_result = vote_sum >= 1

        if and_result:       and_count += 1
        if two_of_three:     two_of_three_count += 1
        if or_result:        or_count += 1

        results.append({
            "line_number": line_num,
            "service": cent_entry["service"],
            "centroid_is_anomaly": cent_flag,
            "knn_is_anomaly": knn_flag,
            "iforest_is_anomaly": iforest_flag,
            "majority_and_is_anomaly": and_result,
            "majority_2of3_is_anomaly": two_of_three,
            "majority_or_is_anomaly": or_result,
        })

    return results, and_count, two_of_three_count, or_count


# ===================================================================
# Gop ket qua
# ===================================================================

def merge_all_results(
    weighted_results: list[dict],
    majority_results: list[dict],
) -> list[dict]:
    """Gop weighted_average + majority votes vao mot list."""
    majority_lookup = build_lookup_by_line(majority_results)

    merged: list[dict] = []
    for entry in weighted_results:
        line_num = entry["line_number"]
        maj = majority_lookup.get(line_num, {})

        merged.append({
            "line_number": line_num,
            "service": entry["service"],
            "centroid_score": entry["centroid_score"],
            "knn_score": entry["knn_score"],
            "iforest_score": entry["iforest_score"],
            "weighted_average_score": entry["weighted_average_score"],
            "weighted_average_is_anomaly": entry["weighted_average_is_anomaly"],
            "majority_and_is_anomaly": maj.get("majority_and_is_anomaly", False),
            "majority_2of3_is_anomaly": maj.get("majority_2of3_is_anomaly", False),
            "majority_or_is_anomaly": maj.get("majority_or_is_anomaly", False),
        })

    return merged


# ===================================================================
# Danh gia
# ===================================================================

def evaluate_strategy(
    results: list[dict],
    ground_truth: list[dict],
    anomaly_key: str,
) -> dict:
    """Danh gia mot chien luoc dua tren ground truth."""
    truth_by_line = {e["line_number"]: e["is_anomaly"] for e in ground_truth}

    tp = fp = tn = fn = 0
    for r in results:
        pred = r.get(anomaly_key, False)
        actual = truth_by_line.get(r["line_number"], False)
        if pred and actual:       tp += 1
        elif pred and not actual: fp += 1
        elif not pred and not actual: tn += 1
        else:                     fn += 1

    total = tp + fp + tn + fn
    acc = (tp + tn) / total if total > 0 else 0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    return {
        "total_samples": total,
        "true_positives": tp, "false_positives": fp,
        "true_negatives": tn, "false_negatives": fn,
        "accuracy": round(acc, 4), "precision": round(prec, 4),
        "recall": round(rec, 4), "f1_score": round(f1, 4),
    }


def evaluate_detector_individually(
    centroid_results: list[dict],
    knn_results: list[dict],
    iforest_results: list[dict],
    ground_truth: list[dict],
) -> dict[str, dict]:
    """Danh gia rieng tung detector lam baseline."""
    truth_by_line = {e["line_number"]: e["is_anomaly"] for e in ground_truth}

    def _eval_one(detector_results, flag_key="is_anomaly"):
        tp = fp = tn = fn = 0
        for r in detector_results:
            pred = r.get(flag_key, False)
            actual = truth_by_line.get(r["line_number"], False)
            if pred and actual:       tp += 1
            elif pred and not actual: fp += 1
            elif not pred and not actual: tn += 1
            else:                     fn += 1
        total = tp + fp + tn + fn
        return {
            "accuracy": round((tp+tn)/total, 4) if total else 0,
            "precision": round(tp/(tp+fp), 4) if (tp+fp) else 0,
            "recall": round(tp/(tp+fn), 4) if (tp+fn) else 0,
            "f1_score": round(2*tp/(2*tp+fp+fn), 4) if (2*tp+fp+fn) else 0,
        }

    return {
        "centroid": _eval_one(centroid_results),
        "knn": _eval_one(knn_results),
        "isolation_forest": _eval_one(iforest_results),
    }


# ===================================================================
# Ham chinh
# ===================================================================

def run_ensemble_voter(
    centroid_results_path: str = DEFAULT_CENTROID_RESULTS,
    knn_results_path: str = DEFAULT_KNN_RESULTS,
    iforest_results_path: str = DEFAULT_IFOREST_RESULTS,
    ground_truth_path: str = DEFAULT_GROUND_TRUTH,
    output: str = DEFAULT_OUTPUT,
    weight_centroid: float = DEFAULT_WEIGHT_CENTROID,
    weight_knn: float = DEFAULT_WEIGHT_KNN,
    weight_iforest: float = DEFAULT_WEIGHT_IFOREST,
    weighted_threshold: float = DEFAULT_WEIGHTED_THRESHOLD,
) -> dict:
    """Chay toan bo pipeline ensemble voting + evaluation."""
    print("=" * 60)
    print("[ensemble-voter] Bat dau (3 detectors)...")
    print(f"  Weights: centroid={weight_centroid}, "
          f"knn={weight_knn}, iforest={weight_iforest}")
    print(f"  Weighted threshold: {weighted_threshold}")

    # Buoc 1: Nap ket qua
    centroid_res, knn_res, iforest_res = load_detector_results(
        centroid_results_path, knn_results_path, iforest_results_path
    )
    total_lines = len(centroid_res)

    cent_anom = sum(1 for r in centroid_res if r.get("is_anomaly"))
    knn_anom = sum(1 for r in knn_res if r.get("is_anomaly"))
    ifo_anom = sum(1 for r in iforest_res if r.get("is_anomaly"))

    print(f"\n[ensemble-voter] Da nap {total_lines} dong ket qua")
    print(f"  Centroid        : {cent_anom} ({cent_anom/total_lines*100:.1f}%)")
    print(f"  KNN             : {knn_anom} ({knn_anom/total_lines*100:.1f}%)")
    print(f"  Isolation Forest: {ifo_anom} ({ifo_anom/total_lines*100:.1f}%)")

    # Overlap analysis
    knn_lu = build_lookup_by_line(knn_res)
    ifo_lu = build_lookup_by_line(iforest_res)
    all_three = 0; cent_knn = 0; cent_ifo = 0; knn_ifo = 0
    for r in centroid_res:
        c = r.get("is_anomaly", False)
        k = knn_lu.get(r["line_number"], {}).get("is_anomaly", False)
        i = ifo_lu.get(r["line_number"], {}).get("is_anomaly", False)
        if c and k and i: all_three += 1
        elif c and k:     cent_knn += 1
        elif c and i:     cent_ifo += 1
        elif k and i:     knn_ifo += 1

    print(f"  All 3 agree     : {all_three}")
    print(f"  Centroid+KNN    : {cent_knn}")
    print(f"  Centroid+IF     : {cent_ifo}")
    print(f"  KNN+IF          : {knn_ifo}")

    # Buoc 2: Weighted average
    print(f"\n[ensemble-voter] Tinh weighted_average...")
    w_res, w_anom = compute_weighted_average(
        centroid_res, knn_res, iforest_res,
        weight_centroid, weight_knn, weight_iforest, weighted_threshold,
    )
    print(f"  Weighted avg anomalies: {w_anom} ({w_anom/total_lines*100:.1f}%)")

    # Buoc 3: Majority votes
    print(f"\n[ensemble-voter] Tinh majority_and / 2of3 / or...")
    m_res, and_cnt, two3_cnt, or_cnt = compute_majority_votes(
        centroid_res, knn_res, iforest_res,
    )
    print(f"  Majority AND   : {and_cnt} ({and_cnt/total_lines*100:.1f}%)")
    print(f"  Majority 2of3  : {two3_cnt} ({two3_cnt/total_lines*100:.1f}%)")
    print(f"  Majority OR    : {or_cnt} ({or_cnt/total_lines*100:.1f}%)")

    # Buoc 4: Gop ket qua
    all_results = merge_all_results(w_res, m_res)

    # Buoc 5: Danh gia
    print(f"\n[ensemble-voter] Dang danh gia...")
    if not Path(ground_truth_path).exists():
        raise FileNotFoundError(f"Khong tim thay: {ground_truth_path}")
    with open(ground_truth_path, "r", encoding="utf-8") as fh:
        ground_truth = json.load(fh)

    eval_detectors = evaluate_detector_individually(
        centroid_res, knn_res, iforest_res, ground_truth
    )
    eval_w = evaluate_strategy(all_results, ground_truth, "weighted_average_is_anomaly")
    eval_and = evaluate_strategy(all_results, ground_truth, "majority_and_is_anomaly")
    eval_2of3 = evaluate_strategy(all_results, ground_truth, "majority_2of3_is_anomaly")
    eval_or = evaluate_strategy(all_results, ground_truth, "majority_or_is_anomaly")

    # In bang so sanh
    print(f"\n  {'Strategy':<22} {'Accuracy':>8} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print(f"  {'-'*22} {'-'*8} {'-'*10} {'-'*8} {'-'*8}")
    for name, ev in [
        ("Centroid (baseline)", eval_detectors["centroid"]),
        ("KNN (baseline)", eval_detectors["knn"]),
        ("IsolationForest (base)", eval_detectors["isolation_forest"]),
        ("weighted_average", eval_w),
        ("majority_and", eval_and),
        ("majority_2of3", eval_2of3),
        ("majority_or", eval_or),
    ]:
        print(f"  {name:<22} {ev['accuracy']:>8.4f} {ev['precision']:>10.4f} "
              f"{ev['recall']:>8.4f} {ev['f1_score']:>8.4f}")

    # Buoc 6: Luu
    output_data = {
        "config": {
            "strategies": ALL_STRATEGIES,
            "weight_centroid": weight_centroid,
            "weight_knn": weight_knn,
            "weight_iforest": weight_iforest,
            "weighted_threshold": weighted_threshold,
        },
        "input_stats": {
            "total_lines": total_lines,
            "centroid_anomalies": cent_anom,
            "knn_anomalies": knn_anom,
            "iforest_anomalies": ifo_anom,
            "all_three_agree": all_three,
            "centroid_knn": cent_knn,
            "centroid_iforest": cent_ifo,
            "knn_iforest": knn_ifo,
        },
        "ensemble_stats": {
            STRATEGY_WEIGHTED: {"anomalies_found": w_anom, "anomaly_ratio": round(w_anom/total_lines, 4)},
            STRATEGY_AND: {"anomalies_found": and_cnt, "anomaly_ratio": round(and_cnt/total_lines, 4)},
            STRATEGY_2OF3: {"anomalies_found": two3_cnt, "anomaly_ratio": round(two3_cnt/total_lines, 4)},
            STRATEGY_OR: {"anomalies_found": or_cnt, "anomaly_ratio": round(or_cnt/total_lines, 4)},
        },
        "results": all_results,
        "evaluation": {
            "centroid_baseline": eval_detectors["centroid"],
            "knn_baseline": eval_detectors["knn"],
            "isolation_forest_baseline": eval_detectors["isolation_forest"],
            STRATEGY_WEIGHTED: eval_w,
            STRATEGY_AND: eval_and,
            STRATEGY_2OF3: eval_2of3,
            STRATEGY_OR: eval_or,
        },
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output_data, fh, indent=2, ensure_ascii=False)

    print(f"\n[ensemble-voter] Da luu vao '{output_path.resolve()}'")
    print(f"[ensemble-voter] Hoan tat!")

    return output_data


# ===================================================================
# CLI
# ===================================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Ensemble voter – ket hop 3 detector (Centroid + KNN + IsolationForest)"
    )
    ap.add_argument("--centroid-results", type=str, default=DEFAULT_CENTROID_RESULTS)
    ap.add_argument("--knn-results", type=str, default=DEFAULT_KNN_RESULTS)
    ap.add_argument("--iforest-results", type=str, default=DEFAULT_IFOREST_RESULTS)
    ap.add_argument("--ground-truth", type=str, default=DEFAULT_GROUND_TRUTH)
    ap.add_argument("--output", type=str, default=DEFAULT_OUTPUT)
    ap.add_argument("--weight-centroid", type=float, default=DEFAULT_WEIGHT_CENTROID)
    ap.add_argument("--weight-knn", type=float, default=DEFAULT_WEIGHT_KNN)
    ap.add_argument("--weight-iforest", type=float, default=DEFAULT_WEIGHT_IFOREST)
    ap.add_argument("--weighted-threshold", type=float, default=DEFAULT_WEIGHTED_THRESHOLD)

    args = ap.parse_args()
    run_ensemble_voter(
        centroid_results_path=args.centroid_results,
        knn_results_path=args.knn_results,
        iforest_results_path=args.iforest_results,
        ground_truth_path=args.ground_truth,
        output=args.output,
        weight_centroid=args.weight_centroid,
        weight_knn=args.weight_knn,
        weight_iforest=args.weight_iforest,
        weighted_threshold=args.weighted_threshold,
    )
