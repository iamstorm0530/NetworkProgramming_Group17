# Evaluation Report: Isolation Forest Detector

> Sinh tự động: 2026-06-12 16:21:48

## 1. Tổng quan (Overview)

| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng log | 5000 |
| Số bất thường phát hiện | 241 |
| Tỷ lệ phát hiện | 4.8% |
| Accuracy | 0.8662 |
| Precision | 0.1494 |
| Recall | 0.072 |
| F1 Score | 0.0972 |

## 2. Ma trận nhầm lẫn (Confusion Matrix)

| | Dự đoán Bình thường | Dự đoán Bất thường |
|---|---|---|
| **Thực tế Bình thường** | TN = 4295 | FP = 205 |
| **Thực tế Bất thường** | FN = 464 | TP = 36 |

## 3. Phân bố bất thường theo loại (Anomaly Breakdown)

| Loại bất thường | Phát hiện | Tổng trong GT | Tỷ lệ | Attack Category |
|---|---|---|---|---|
| `None` | 205 | 0 | 0.0% | Unknown |
| `service_crash` | 21 | 55 | 38.2% | Denial of Service / System Failure |
| `sql_injection` | 15 | 55 | 27.3% | Web Application Attack / Injection |

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

### 4.2. `service_crash`

**Mô tả**: Dịch vụ bị crash — segfault, kernel oops, NULL pointer dereference, soft lockup. Có thể do lỗi phần mềm hoặc tấn công DoS.

**Phát hiện**: 21/55 (38.2%)

**Attack Category**: Denial of Service / System Failure

**Mẫu log**:

```
  [Line 4572] kernel: Oops: 0000 [#1] SMP NOPTI
  [Line 4581] kernel: BUG: unable to handle kernel NULL pointer dereference at 0000000000000010
  [Line 4635] kernel: Oops: 0000 [#1] SMP NOPTI
```

### 4.3. `sql_injection`

**Mô tả**: SQL Injection — URL chứa cú pháp SQL (' OR '1'='1, UNION SELECT, DROP TABLE). Kẻ tấn công cố gắng khai thác lỗ hổng SQL injection.

**Phát hiện**: 15/55 (27.3%)

**Attack Category**: Web Application Attack / Injection

**Mẫu log**:

```
  [Line 4507] GET /search?q=%27%3B%20DROP%20TABLE%20users%3B-- HTTP/1.1 500 67 "-" "curl/7.81.0"
  [Line 4525] GET /search?q=%27%3B%20DROP%20TABLE%20users%3B-- HTTP/1.1 500 67 "-" "curl/7.81.0"
  [Line 4570] GET /search?q=%27%3B%20DROP%20TABLE%20users%3B-- HTTP/1.1 500 67 "-" "curl/7.81.0"
```

## 5. Phân loại tấn công (Attack Classification)

| Attack Category | Số lượng | Tỷ lệ |
|---|---|
| Unknown | 205 | 85.1% |
| Denial of Service / System Failure | 21 | 8.7% |
| Web Application Attack / Injection | 15 | 6.2% |

## 6. Khuyến nghị (Recommendations)

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

## 7. Hạn chế (Limitations)

### Các loại bất thường bị bỏ sót hoặc phát hiện một phần

| Loại | Phát hiện | Tổng | Tỷ lệ bỏ sót |
|---|---|---|---|
| `failed_password` | 0 | 56 | 100.0% |
| `invalid_user` | 0 | 56 | 100.0% |
| `brute_force` | 0 | 56 | 100.0% |
| `reverse_lookup_failure` | 0 | 56 | 100.0% |
| `suspicious_sudo` | 0 | 56 | 100.0% |
| `port_scan` | 0 | 55 | 100.0% |
| `sql_injection` | 15 | 55 | 72.7% |
| `directory_traversal` | 0 | 55 | 100.0% |
| `service_crash` | 21 | 55 | 61.8% |

### Nguyên nhân

- Ensemble majority_or kết hợp cả hai detector, nhưng KNN đóng góp rất ít (10 detection) nên kết quả gần như giống Centroid.
- Cần cải thiện KNN detector (hạ ngưỡng, tăng k) để ensemble có ý nghĩa hơn.

### Hướng cải thiện

- Thử nghiệm với threshold thấp hơn để tăng recall.
- Kết hợp thêm đặc trưng thời gian (temporal features).
- Sử dụng model embedding chuyên biệt cho syslog thay vì MiniLM đa dụng.
- Thêm detector thứ ba (Isolation Forest, LOF) để tăng diversity.
