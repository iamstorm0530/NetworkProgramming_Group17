#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — syslog-parser skill.

Parse file syslog thô (RFC 3164) thành các bản ghi có cấu trúc gồm 6 trường:
    timestamp, host, service, severity, message, line_number.

Input : data/raw/syslog_synthetic.log
Output: data/processed/parsed_logs.json
"""

import re
import json
import argparse
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Cấu hình mặc định
# ---------------------------------------------------------------------------
DEFAULT_INPUT_LOG = "data/raw/syslog_synthetic.log"
DEFAULT_OUTPUT_JSON = "data/processed/parsed_logs.json"
DEFAULT_YEAR = 2026

# ---------------------------------------------------------------------------
# Regex trích xuất syslog RFC 3164
# ---------------------------------------------------------------------------
# Định dạng: Mmm DD HH:MM:SS hostname service[pid]: message
# Hoặc      Mmm DD HH:MM:SS hostname service: message         (không PID)
#
# Nhóm bắt (capture groups):
#   $1 – timestamp     : "Jun 12 00:00:09"
#   $2 – host          : "server-01"
#   $3 – service       : "sshd"
#   $4 – pid (optional): "1234"
#   $5 – message       : toàn bộ phần sau "]: " hoặc ": "
#
SYSLOG_LINE_PATTERN = re.compile(
    r"""
    ^                                           # đầu dòng
    (\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})      # $1: Mmm DD HH:MM:SS
    \s+
    (\S+)                                       # $2: hostname
    \s+
    ([^\s\[\]:]+)                               # $3: service (không chứa space, [, ], :)
    (?:\[(\d+)\])?                              # $4: PID (optional, trong ngoặc vuông)
    :\s+                                        # dấu hai chấm + khoảng trắng
    (.+)                                        # $5: message (phần còn lại)
    $                                           # cuối dòng
    """,
    re.VERBOSE,
)

# ---------------------------------------------------------------------------
# Quy tắc suy luận severity theo từ khóa
# ---------------------------------------------------------------------------
# Duyệt theo thứ tự từ cao xuống thấp. Dừng ở quy tắc đầu tiên khớp.
# Nếu không khớp quy tắc nào → mặc định INFO.

SEVERITY_RULES = [
    # ── CRITICAL ────────────────────────────────────────────────────────
    (
        re.compile(
            r"crash|segfault|segmentation\s*fault|"
            r"kernel\s*oops|null\s*pointer|"
            r"soft\s*lockup|hard\s*lockup|"
            r"kernel\s*panic|BUG:|"
            r"BREAK-IN\s*ATTEMPT|possible\s*break",
            re.IGNORECASE,
        ),
        "CRITICAL",
    ),
    (
        re.compile(
            r"code=killed|code=dumped|status=\d+/(SEGV|ABRT|FPE|ILL|BUS)",
            re.IGNORECASE,
        ),
        "CRITICAL",
    ),
    # ── ERROR ───────────────────────────────────────────────────────────
    (
        re.compile(
            r"failed\s+password|invalid\s+user|authentication\s+failure|"
            r"(?:DROP|UNION|SELECT)(?:\s+|%20)(?:TABLE|SELECT|FROM)|"
            r"(?:%27|')\s*(?:OR|AND)\s*(?:%27|')\s*\d|"
            r"%3B\s*DROP|"
            r"not\s+in\s+sudoers|"
            r"(?:nobody|www-data|guest).*USER=root|"
            r"wget\s+http.*malware|curl\s+.*evil\.com|"
            r"chmod\s+777\s+/etc/shadow",
            re.IGNORECASE,
        ),
        "ERROR",
    ),
    (
        re.compile(
            r"(?:%2e%2e|%2e%2e|(?:\.\./|\..\/){2,})|"
            r"directory\s*traversal|"
            r"/etc/(?:passwd|shadow|hosts)",
            re.IGNORECASE,
        ),
        "ERROR",
    ),
    # ── WARNING ─────────────────────────────────────────────────────────
    (
        re.compile(
            r"reverse\s+.*fail|unable\s+to\s+resolve|"
            r"connection\s+closed|"
            r"disconnect|postponed|"
            r"POSSIBLE\s+BREAK-IN",
            re.IGNORECASE,
        ),
        "WARNING",
    ),
]

# Mặc định nếu không khớp bất kỳ quy tắc nào
DEFAULT_SEVERITY = "INFO"


# ===================================================================
# Hàm tiện ích
# ===================================================================

def normalize_timestamp(raw_timestamp: str, default_year: int) -> str:
    """Chuyển syslog timestamp 'Jun 12 00:00:09' → ISO 8601 '2026-06-12T00:00:09'.

    Syslog RFC 3164 không chứa năm nên phải ghép năm từ tham số default_year.
    """
    # datetime.strptime cần format có năm
    datetime_with_year = f"{default_year} {raw_timestamp}"
    parsed = datetime.strptime(datetime_with_year, "%Y %b %d %H:%M:%S")
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def infer_severity(message: str) -> str:
    """Dựa vào nội dung message để gán severity: CRITICAL > ERROR > WARNING > INFO."""
    for pattern, severity_label in SEVERITY_RULES:
        if pattern.search(message):
            return severity_label
    return DEFAULT_SEVERITY


def parse_single_line(line_text: str, line_number: int,
                      default_year: int) -> dict | None:
    """Parse một dòng syslog, trả về dict hoặc None nếu dòng không hợp lệ."""
    match = SYSLOG_LINE_PATTERN.match(line_text.strip())
    if match is None:
        return None

    raw_timestamp = match.group(1)
    hostname = match.group(2)
    service_name = match.group(3)
    # group(4) là PID — không dùng trong output hiện tại
    raw_message = match.group(5)

    # Chuẩn hóa timestamp
    iso_timestamp = normalize_timestamp(raw_timestamp, default_year)

    # Suy luận severity từ nội dung message
    severity = infer_severity(raw_message)

    return {
        "timestamp":   iso_timestamp,
        "host":        hostname,
        "service":     service_name,
        "severity":    severity,
        "message":     raw_message,
        "line_number": line_number,
    }


# ===================================================================
# Hàm parse chính
# ===================================================================

def parse_syslog_file(
    input_log: str = DEFAULT_INPUT_LOG,
    output_json: str = DEFAULT_OUTPUT_JSON,
    default_year: int = DEFAULT_YEAR,
) -> list[dict]:
    """Đọc file syslog thô, parse từng dòng, xuất JSON.

    Returns:
        parsed_entries: danh sách dict đã parse thành công.
    """
    input_path = Path(input_log)
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file input: {input_path.resolve()}")

    parsed_entries: list[dict] = []
    skipped_lines: list[int] = []

    with open(input_path, "r", encoding="utf-8") as file_handle:
        for line_number, line_text in enumerate(file_handle, start=1):
            parsed_entry = parse_single_line(line_text, line_number, default_year)

            if parsed_entry is None:
                skipped_lines.append(line_number)
                continue

            parsed_entries.append(parsed_entry)

    # ------------------------------------------------------------------
    # Xuất JSON
    # ------------------------------------------------------------------
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as output_handle:
        json.dump(parsed_entries, output_handle, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Thống kê
    # ------------------------------------------------------------------
    severity_counts = _count_by_severity(parsed_entries)
    total_parsed = len(parsed_entries)

    print(f"[syslog-parser] Done!")
    print(f"  Input file     : {input_path.resolve()}")
    print(f"  Lines parsed   : {total_parsed}")
    print(f"  Lines skipped  : {len(skipped_lines)}")
    if skipped_lines:
        print(f"  Skipped lines  : {skipped_lines[:10]}{'...' if len(skipped_lines) > 10 else ''}")
    print(f"  Severity dist  : INFO={severity_counts['INFO']}, "
          f"WARNING={severity_counts['WARNING']}, "
          f"ERROR={severity_counts['ERROR']}, "
          f"CRITICAL={severity_counts['CRITICAL']}")
    print(f"  Output file    : {output_path.resolve()}")

    return parsed_entries


def _count_by_severity(entries: list[dict]) -> dict[str, int]:
    """Đếm số lượng bản ghi theo từng mức severity."""
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    for entry in entries:
        severity = entry.get("severity", DEFAULT_SEVERITY)
        if severity in counts:
            counts[severity] += 1
    return counts


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Syslog parser – parse syslog thô thành JSON có cấu trúc"
    )
    argument_parser.add_argument(
        "--input-log", type=str, default=DEFAULT_INPUT_LOG,
        help="Đường dẫn file syslog thô",
    )
    argument_parser.add_argument(
        "--output-json", type=str, default=DEFAULT_OUTPUT_JSON,
        help="Đường dẫn file JSON kết quả",
    )
    argument_parser.add_argument(
        "--default-year", type=int, default=DEFAULT_YEAR,
        help="Năm mặc định ghép vào timestamp (RFC 3164 không có năm)",
    )

    cli_args = argument_parser.parse_args()

    parse_syslog_file(
        input_log=cli_args.input_log,
        output_json=cli_args.output_json,
        default_year=cli_args.default_year,
    )
