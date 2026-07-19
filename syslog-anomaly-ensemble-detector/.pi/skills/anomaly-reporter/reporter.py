#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — anomaly-reporter skill.

Sinh 4 file Evaluation Report Markdown trong thu muc reports/:
    - centroid_report.md
    - knn_report.md
    - isolation_forest_report.md
    - ensemble_report.md

Skill nay chi chiu trach nhiem bao cao danh gia. Khong tao form danh gia thu cong.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# ---------------------------------------------------------------------------
# Cấu hình mặc định
# ---------------------------------------------------------------------------
DEFAULT_CENTROID_RESULTS = "logs/centroid_results.json"
DEFAULT_KNN_RESULTS = "logs/knn_results.json"
DEFAULT_ENSEMBLE_RESULTS = "logs/ensemble_results.json"
DEFAULT_IFOREST_RESULTS = "data/processed/isolation_forest_results.json"
DEFAULT_PARSED_LOGS = "data/processed/parsed_logs.json"
DEFAULT_GROUND_TRUTH = "data/raw/syslog_ground_truth.json"
DEFAULT_OUTPUT_DIR = "reports"

# ---------------------------------------------------------------------------
# Ánh xạ anomaly type → attack category
# ---------------------------------------------------------------------------
ANOMALY_TO_ATTACK_CATEGORY = {
    "failed_password":       "Brute Force / Credential Attack",
    "invalid_user":          "Brute Force / Credential Attack",
    "brute_force":           "Brute Force / Credential Attack",
    "reverse_lookup_failure":"Reconnaissance",
    "suspicious_sudo":       "Privilege Escalation",
    "port_scan":             "Reconnaissance / Network Scan",
    "sql_injection":         "Web Application Attack / Injection",
    "directory_traversal":   "Web Application Attack / Path Traversal",
    "service_crash":         "Denial of Service / System Failure",
}

# Mô tả ngắn cho từng loại anomaly (dùng trong báo cáo)
ANOMALY_DESCRIPTIONS = {
    "failed_password": (
        "Đăng nhập SSH thất bại với password sai. Có thể là người dùng "
        "hợp lệ quên mật khẩu, hoặc kẻ tấn công đang thử đoán mật khẩu."
    ),
    "invalid_user": (
        "Cố gắng đăng nhập SSH với tài khoản không tồn tại. Dấu hiệu rõ ràng "
        "của tấn công dò quét tài khoản (user enumeration)."
    ),
    "brute_force": (
        "Nhiều lần đăng nhập thất bại liên tiếp từ cùng một IP — tấn công "
        "brute force điển hình nhằm đoán mật khẩu root hoặc admin."
    ),
    "reverse_lookup_failure": (
        "Không thể phân giải ngược DNS cho IP kết nối đến. Có thể là dấu hiệu "
        "của IP giả mạo hoặc máy chủ C&C không có PTR record."
    ),
    "suspicious_sudo": (
        "Lệnh sudo đáng ngờ — người dùng không có quyền (nobody, www-data) "
        "cố gắng chạy lệnh với quyền root, hoặc thực thi script từ URL độc hại."
    ),
    "port_scan": (
        "Quét cổng (port scan) — một IP gửi gói SYN đến nhiều cổng khác nhau. "
        "Dấu hiệu của reconnaissance trước khi tấn công."
    ),
    "sql_injection": (
        "SQL Injection — URL chứa cú pháp SQL (' OR '1'='1, UNION SELECT, "
        "DROP TABLE). Kẻ tấn công cố gắng khai thác lỗ hổng SQL injection."
    ),
    "directory_traversal": (
        "Directory Traversal — URL chứa '../' hoặc '%2e%2e/' để truy cập file "
        "hệ thống (/etc/passwd, /etc/shadow)."
    ),
    "service_crash": (
        "Dịch vụ bị crash — segfault, kernel oops, NULL pointer dereference, "
        "soft lockup. Có thể do lỗi phần mềm hoặc tấn công DoS."
    ),
}

# Khuyến nghị cho từng attack category
ATTACK_RECOMMENDATIONS = {
    "Brute Force / Credential Attack": [
        "Kích hoạt fail2ban để tự động chặn IP sau N lần đăng nhập thất bại.",
        "Vô hiệu hóa đăng nhập root qua SSH (`PermitRootLogin no`).",
        "Triển khai xác thực khóa công khai (public key) thay vì password.",
        "Giới hạn số lần thử đăng nhập (`MaxAuthTries 3`).",
        "Giám sát số lượng failed password theo IP để phát hiện bất thường.",
    ],
    "Reconnaissance": [
        "Chặn các IP thực hiện port scan bằng iptables/nftables rules.",
        "Giới hạn tốc độ gói SYN (`--limit` trong iptables).",
        "Triển khai IDS/IPS (Snort, Suricata) để phát hiện scan pattern.",
        "Kiểm tra DNS PTR record — IP không có reverse DNS nên bị nghi ngờ.",
    ],
    "Reconnaissance / Network Scan": [
        "Chặn các IP thực hiện port scan bằng iptables/nftables rules.",
        "Giới hạn tốc độ gói SYN (`--limit` trong iptables).",
        "Triển khai IDS/IPS (Snort, Suricata) để phát hiện scan pattern.",
    ],
    "Privilege Escalation": [
        "Rà soát file `/etc/sudoers` — loại bỏ quyền sudo không cần thiết.",
        "Không cho phép user `nobody`, `www-data` chạy sudo.",
        "Giám sát tất cả lệnh sudo được thực thi, đặc biệt từ user bất thường.",
        "Triển khai SELinux/AppArmor để giới hạn quyền process.",
        "Kiểm tra xem có backdoor nào được cài qua `wget`/`curl` không.",
    ],
    "Web Application Attack / Injection": [
        "Triển khai Web Application Firewall (WAF) — ModSecurity, Cloudflare.",
        "Sử dụng prepared statements / parameterized queries cho database.",
        "Validate và sanitize tất cả user input.",
        "Chặn URL chứa ký tự đặc biệt (' OR, UNION, DROP, ../).",
        "Thực hiện penetration testing định kỳ cho web application.",
    ],
    "Web Application Attack / Path Traversal": [
        "Validate và sanitize đường dẫn file — không cho phép '../' trong input.",
        "Chroot jail cho web server để giới hạn truy cập file system.",
        "Triển khai WAF để chặn path traversal pattern.",
        "Kiểm tra cấu hình web server — disable directory listing.",
    ],
    "Denial of Service / System Failure": [
        "Điều tra nguyên nhân root cause của crash (kernel log, core dump).",
        "Cập nhật kernel và phần mềm lên phiên bản mới nhất.",
        "Triển khai giám sát service (systemd watchdog, monit).",
        "Cấu hình tự động restart service khi crash (`Restart=always`).",
        "Kiểm tra phần cứng — soft lockup có thể do lỗi CPU/RAM.",
    ],
}


# ===================================================================
# Tiện ích
# ===================================================================

def load_all_data(
    centroid_path: str,
    knn_path: str,
    ensemble_path: str,
    iforest_path: str,
    parsed_path: str,
    truth_path: str,
) -> dict:
    """Nạp tất cả dữ liệu cần thiết.

    Returns:
        dict với keys: centroid, knn, ensemble, parsed, ground_truth, truth_map,
                       messages_by_line
    """
    data: dict = {}

    # Detector results
    for key, path in [
        ("centroid", centroid_path),
        ("knn", knn_path),
        ("ensemble", ensemble_path),
        ("iforest", iforest_path),
    ]:
        if not Path(path).exists():
            raise FileNotFoundError(f"Khong tim thay: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            data[key] = json.load(fh)

    # Parsed logs
    if not Path(parsed_path).exists():
        raise FileNotFoundError(f"Khong tim thay: {parsed_path}")
    with open(parsed_path, "r", encoding="utf-8") as fh:
        data["parsed"] = json.load(fh)

    # Ground truth
    if not Path(truth_path).exists():
        raise FileNotFoundError(f"Khong tim thay: {truth_path}")
    with open(truth_path, "r", encoding="utf-8") as fh:
        data["ground_truth"] = json.load(fh)

    # Tạo lookup nhanh: line_number → message, anomaly_type, is_anomaly
    data["messages_by_line"] = {
        entry["line_number"]: entry["message"]
        for entry in data["parsed"]
    }
    data["truth_map"] = {
        entry["line_number"]: entry
        for entry in data["ground_truth"]
    }

    return data


# ===================================================================
# Sinh Evaluation Report
# ===================================================================

def generate_evaluation_report(
    detector_name: str,
    detector_data: dict,
    data: dict,
    output_path: Path,
) -> None:
    """Sinh bao cao Evaluation Report cho mot detector.

    Args:
        detector_name: "Centroid", "KNN", hoặc "Ensemble"
        detector_data: dict chứa "results", "evaluation" (từ file JSON detector)
        data:          dict chứa parsed logs, ground truth, messages
        output_path:   đường dẫn file .md output
    """
    results = detector_data["results"]
    evaluation = detector_data.get("evaluation", {})

    # Với Ensemble, evaluation có nhiều sub-key
    # Lấy evaluation cho majority_or làm đại diện chính
    if detector_name == "Ensemble":
        main_eval = evaluation.get("majority_or", {})
    else:
        main_eval = evaluation

    total_entries = len(results)
    detected_anomalies = [r for r in results if _get_is_anomaly(r, detector_name)]
    total_detected = len(detected_anomalies)

    # ------------------------------------------------------------------
    # Gom nhóm anomaly theo loại (dùng ground truth)
    # ------------------------------------------------------------------
    anomaly_by_type: dict[str, dict] = {}
    for r in detected_anomalies:
        line_num = r["line_number"]
        truth_entry = data["truth_map"].get(line_num, {})
        anomaly_type = truth_entry.get("anomaly_type", "unknown")

        if anomaly_type not in anomaly_by_type:
            anomaly_by_type[anomaly_type] = {
                "count": 0,
                "samples": [],
                "category": ANOMALY_TO_ATTACK_CATEGORY.get(anomaly_type, "Unknown"),
            }
        anomaly_by_type[anomaly_type]["count"] += 1
        if len(anomaly_by_type[anomaly_type]["samples"]) < 3:
            message = data["messages_by_line"].get(line_num, "N/A")
            anomaly_by_type[anomaly_type]["samples"].append({
                "line": line_num,
                "message": message,
            })

    # Đếm tổng số mỗi loại trong ground truth
    total_by_type: dict[str, int] = {}
    for entry in data["ground_truth"]:
        atype = entry.get("anomaly_type")
        if atype:
            total_by_type[atype] = total_by_type.get(atype, 0) + 1

    # Sắp xếp anomaly type theo số lượng phát hiện giảm dần
    sorted_types = sorted(
        anomaly_by_type.keys(),
        key=lambda t: anomaly_by_type[t]["count"],
        reverse=True,
    )

    # ------------------------------------------------------------------
    # Gom attack category
    # ------------------------------------------------------------------
    category_counts: dict[str, int] = {}
    for atype, info in anomaly_by_type.items():
        cat = info["category"]
        category_counts[cat] = category_counts.get(cat, 0) + info["count"]

    # ------------------------------------------------------------------
    # Viết báo cáo Markdown
    # ------------------------------------------------------------------
    report_lines: list[str] = []
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines.append(f"# Evaluation Report: {detector_name} Detector\n")
    report_lines.append(f"> Sinh tự động: {report_time}\n")

    # ── 1. Tổng quan ──
    report_lines.append("## 1. Tổng quan (Overview)\n")
    report_lines.append("| Chỉ số | Giá trị |")
    report_lines.append("|---|---|")
    report_lines.append(f"| Tổng số dòng log | {total_entries} |")
    report_lines.append(f"| Số bất thường phát hiện | {total_detected} |")
    report_lines.append(f"| Tỷ lệ phát hiện | {total_detected/total_entries*100:.1f}% |")
    report_lines.append(f"| Accuracy | {main_eval.get('accuracy', 'N/A')} |")
    report_lines.append(f"| Precision | {main_eval.get('precision', 'N/A')} |")
    report_lines.append(f"| Recall | {main_eval.get('recall', 'N/A')} |")
    report_lines.append(f"| F1 Score | {main_eval.get('f1_score', 'N/A')} |\n")

    # ── 2. Ma trận nhầm lẫn ──
    report_lines.append("## 2. Ma trận nhầm lẫn (Confusion Matrix)\n")
    report_lines.append("| | Dự đoán Bình thường | Dự đoán Bất thường |")
    report_lines.append("|---|---|---|")
    report_lines.append(
        f"| **Thực tế Bình thường** | TN = {main_eval.get('true_negatives', '?')} | "
        f"FP = {main_eval.get('false_positives', '?')} |"
    )
    report_lines.append(
        f"| **Thực tế Bất thường** | FN = {main_eval.get('false_negatives', '?')} | "
        f"TP = {main_eval.get('true_positives', '?')} |"
    )
    report_lines.append("")

    # ── 3. Phân bố theo loại ──
    report_lines.append("## 3. Phân bố bất thường theo loại (Anomaly Breakdown)\n")
    report_lines.append(
        "| Loại bất thường | Phát hiện | Tổng trong GT | Tỷ lệ | Attack Category |"
    )
    report_lines.append("|---|---|---|---|---|")
    for atype in sorted_types:
        info = anomaly_by_type[atype]
        total_in_gt = total_by_type.get(atype, 0)
        detection_rate = info["count"] / total_in_gt * 100 if total_in_gt > 0 else 0
        report_lines.append(
            f"| `{atype}` | {info['count']} | {total_in_gt} | "
            f"{detection_rate:.1f}% | {info['category']} |"
        )
    report_lines.append("")

    # ── 4. Phân tích chi tiết ──
    report_lines.append("## 4. Phân tích chi tiết (Detailed Analysis)\n")
    for atype in sorted_types:
        info = anomaly_by_type[atype]
        desc = ANOMALY_DESCRIPTIONS.get(atype, "Không có mô tả.")
        total_in_gt = total_by_type.get(atype, 0)

        report_lines.append(f"### 4.{sorted_types.index(atype)+1}. `{atype}`\n")
        report_lines.append(f"**Mô tả**: {desc}\n")
        report_lines.append(
            f"**Phát hiện**: {info['count']}/{total_in_gt} "
            f"({info['count']/total_in_gt*100:.1f}%)\n" if total_in_gt > 0
            else f"**Phát hiện**: {info['count']}\n"
        )
        report_lines.append(f"**Attack Category**: {info['category']}\n")
        report_lines.append("**Mẫu log**:\n")
        report_lines.append("```")
        for sample in info["samples"]:
            report_lines.append(f"  [Line {sample['line']}] {sample['message'][:150]}")
        report_lines.append("```\n")

    # ── 5. Phân loại tấn công ──
    report_lines.append("## 5. Phân loại tấn công (Attack Classification)\n")
    report_lines.append("| Attack Category | Số lượng | Tỷ lệ |")
    report_lines.append("|---|---|")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        report_lines.append(
            f"| {cat} | {count} | {count/total_detected*100:.1f}% |"
            if total_detected > 0 else f"| {cat} | {count} | N/A |"
        )
    report_lines.append("")

    # ── 6. Khuyến nghị ──
    report_lines.append("## 6. Khuyến nghị (Recommendations)\n")

    if total_detected == 0:
        report_lines.append(
            "> Không có bất thường nào được phát hiện. Kiểm tra lại ngưỡng "
            "(threshold) hoặc cấu hình detector.\n"
        )
    else:
        # Gom khuyến nghị theo attack category (tránh trùng lặp)
        seen_categories: set[str] = set()
        for atype in sorted_types:
            cat = anomaly_by_type[atype]["category"]
            if cat in seen_categories:
                continue
            seen_categories.add(cat)
            recommendations = ATTACK_RECOMMENDATIONS.get(cat, [])
            if recommendations:
                report_lines.append(f"### Với {cat}\n")
                for rec in recommendations:
                    report_lines.append(f"- {rec}")
                report_lines.append("")

    # ── 7. Hạn chế ──
    report_lines.append("## 7. Hạn chế (Limitations)\n")

    # Tính những loại bị bỏ sót
    missed_types = []
    for atype, total in total_by_type.items():
        detected = anomaly_by_type.get(atype, {}).get("count", 0)
        if detected < total:
            missed_types.append((atype, detected, total))

    if missed_types:
        report_lines.append("### Các loại bất thường bị bỏ sót hoặc phát hiện một phần\n")
        report_lines.append("| Loại | Phát hiện | Tổng | Tỷ lệ bỏ sót |")
        report_lines.append("|---|---|---|---|")
        for atype, detected, total in missed_types:
            missed_rate = (total - detected) / total * 100
            report_lines.append(
                f"| `{atype}` | {detected} | {total} | {missed_rate:.1f}% |"
            )
        report_lines.append("")

    report_lines.append("### Nguyên nhân\n")
    if detector_name == "Centroid":
        report_lines.append(
            "- Các anomaly có ngữ nghĩa gần với log bình thường (vd: "
            "`failed_password` vẫn cùng chủ đề SSH authentication với "
            "`Accepted password`) nên nằm gần centroid và không bị phát hiện.\n"
            "- Centroid bị ảnh hưởng bởi số lượng lớn log bình thường trong "
            "cùng service.\n"
        )
    elif detector_name == "KNN":
        report_lines.append(
            "- KNN chỉ phát hiện các điểm cực kỳ cô lập (global outlier). "
            "Anomaly xuất hiện lặp lại nhiều lần (brute force, failed password) "
            "tự tạo thành mini-cluster → không bị coi là outlier.\n"
            "- Ngưỡng sigma=2.0 rất bảo thủ, chỉ bắt ~0.2% dữ liệu.\n"
        )
    else:
        report_lines.append(
            "- Ensemble majority_or kết hợp cả hai detector, nhưng KNN đóng góp "
            "rất ít (10 detection) nên kết quả gần như giống Centroid.\n"
            "- Cần cải thiện KNN detector (hạ ngưỡng, tăng k) để ensemble có ý nghĩa hơn.\n"
        )

    report_lines.append("### Hướng cải thiện\n")
    report_lines.append("- Thử nghiệm với threshold thấp hơn để tăng recall.")
    report_lines.append("- Kết hợp thêm đặc trưng thời gian (temporal features).")
    report_lines.append(
        "- Sử dụng model embedding chuyên biệt cho syslog thay vì MiniLM đa dụng."
    )
    report_lines.append(
        "- Thêm detector thứ ba (Isolation Forest, LOF) để tăng diversity."
    )
    report_lines.append("")

    # Ghi file
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report_lines))


def _get_is_anomaly(result: dict, detector_name: str) -> bool:
    """Lấy trường is_anomaly phù hợp với từng detector."""
    if detector_name == "Ensemble":
        # Dùng majority_or làm đại diện
        return result.get("majority_or_is_anomaly", False)
    return result.get("is_anomaly", False)





def _get_score(result: dict, detector_name: str) -> float:
    """Lấy anomaly score phù hợp với detector."""
    if detector_name == "Centroid":
        return result.get("anomaly_score", 0)
    elif detector_name == "KNN":
        return result.get("anomaly_score", 0)
    else:
        return result.get("weighted_average_score", 0)


# ===================================================================
# Hàm chính
# ===================================================================

def generate_all_reports(
    centroid_results_path: str = DEFAULT_CENTROID_RESULTS,
    knn_results_path: str = DEFAULT_KNN_RESULTS,
    ensemble_results_path: str = DEFAULT_ENSEMBLE_RESULTS,
    iforest_results_path: str = DEFAULT_IFOREST_RESULTS,
    parsed_logs_path: str = DEFAULT_PARSED_LOGS,
    ground_truth_path: str = DEFAULT_GROUND_TRUTH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """Sinh toan bo 4 bao cao.

    Returns:
        Danh sach duong dan cac file da tao.
    """
    print("=" * 60)
    print("[anomaly-reporter] Bat dau sinh bao cao...\n")

    # Nap du lieu
    data = load_all_data(
        centroid_results_path,
        knn_results_path,
        ensemble_results_path,
        iforest_results_path,
        parsed_logs_path,
        ground_truth_path,
    )

    # Tạo thư mục output
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Danh sách detector cần sinh báo cáo
    detectors = [
        ("Centroid", data["centroid"], "centroid"),
        ("KNN", data["knn"], "knn"),
        ("Isolation Forest", data["iforest"], "isolation_forest"),
        ("Ensemble", data["ensemble"], "ensemble"),
    ]

    generated_files: list[Path] = []

    for detector_name, detector_data, file_prefix in detectors:
        # ── Evaluation Report ──
        ai_path = output_path / f"{file_prefix}_report.md"
        generate_evaluation_report(detector_name, detector_data, data, ai_path)
        ai_size = ai_path.stat().st_size / 1024
        print(f"  [AI]  {ai_path.name:<40} ({ai_size:.1f} KB)")

        generated_files.append(ai_path)

    # Tổng kết
    total_size = sum(f.stat().st_size for f in generated_files) / 1024
    print(f"\n[anomaly-reporter] Hoan tat!")
    print(f"  So file da sinh : {len(generated_files)}")
    print(f"  Tong dung luong  : {total_size:.1f} KB")
    print(f"  Thu muc output   : {output_path.resolve()}")
    print(f"  (Evaluation Report only — khong tao Human Evaluation)")

    return generated_files


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Anomaly reporter – sinh bao cao Evaluation Report (khong tao Human Evaluation)"
    )
    argument_parser.add_argument(
        "--centroid-results", type=str, default=DEFAULT_CENTROID_RESULTS,
        help="File ket qua centroid-detector",
    )
    argument_parser.add_argument(
        "--knn-results", type=str, default=DEFAULT_KNN_RESULTS,
        help="File ket qua knn-detector",
    )
    argument_parser.add_argument(
        "--ensemble-results", type=str, default=DEFAULT_ENSEMBLE_RESULTS,
        help="File ket qua ensemble-voter",
    )
    argument_parser.add_argument(
        "--iforest-results", type=str, default=DEFAULT_IFOREST_RESULTS,
        help="File ket qua isolation-forest-detector",
    )
    argument_parser.add_argument(
        "--parsed-logs", type=str, default=DEFAULT_PARSED_LOGS,
        help="File parsed_logs.json",
    )
    argument_parser.add_argument(
        "--ground-truth", type=str, default=DEFAULT_GROUND_TRUTH,
        help="File ground truth",
    )
    argument_parser.add_argument(
        "--output-dir", type=str, default=DEFAULT_OUTPUT_DIR,
        help="Thu muc output cho bao cao",
    )

    cli_args = argument_parser.parse_args()

    generate_all_reports(
        centroid_results_path=cli_args.centroid_results,
        knn_results_path=cli_args.knn_results,
        ensemble_results_path=cli_args.ensemble_results,
        iforest_results_path=cli_args.iforest_results,
        parsed_logs_path=cli_args.parsed_logs,
        ground_truth_path=cli_args.ground_truth,
        output_dir=cli_args.output_dir,
    )
