# Evaluation Report: KNN Detector

> Sinh tự động: 2026-06-12 16:21:48

## 1. Tổng quan (Overview)

| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng log | 5000 |
| Số bất thường phát hiện | 10 |
| Tỷ lệ phát hiện | 0.2% |
| Accuracy | 0.902 |
| Precision | 1.0 |
| Recall | 0.02 |
| F1 Score | 0.0392 |

## 2. Ma trận nhầm lẫn (Confusion Matrix)

| | Dự đoán Bình thường | Dự đoán Bất thường |
|---|---|---|
| **Thực tế Bình thường** | TN = 4500 | FP = 0 |
| **Thực tế Bất thường** | FN = 490 | TP = 10 |

## 3. Phân bố bất thường theo loại (Anomaly Breakdown)

| Loại bất thường | Phát hiện | Tổng trong GT | Tỷ lệ | Attack Category |
|---|---|---|---|---|
| `service_crash` | 5 | 55 | 9.1% | Denial of Service / System Failure |
| `invalid_user` | 5 | 56 | 8.9% | Brute Force / Credential Attack |

## 4. Phân tích chi tiết (Detailed Analysis)

### 4.1. `service_crash`

**Mô tả**: Dịch vụ bị crash — segfault, kernel oops, NULL pointer dereference, soft lockup. Có thể do lỗi phần mềm hoặc tấn công DoS.

**Phát hiện**: 5/55 (9.1%)

**Attack Category**: Denial of Service / System Failure

**Mẫu log**:

```
  [Line 4527] kernel: NMI watchdog: BUG: soft lockup - CPU#2 stuck for 22s! [nginx:1620]
  [Line 4554] kernel: NMI watchdog: BUG: soft lockup - CPU#2 stuck for 22s! [nginx:1620]
  [Line 4608] kernel: NMI watchdog: BUG: soft lockup - CPU#2 stuck for 22s! [nginx:1620]
```

### 4.2. `invalid_user`

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
| Denial of Service / System Failure | 5 | 50.0% |
| Brute Force / Credential Attack | 5 | 50.0% |

## 6. Khuyến nghị (Recommendations)

### Với Denial of Service / System Failure

- Điều tra nguyên nhân root cause của crash (kernel log, core dump).
- Cập nhật kernel và phần mềm lên phiên bản mới nhất.
- Triển khai giám sát service (systemd watchdog, monit).
- Cấu hình tự động restart service khi crash (`Restart=always`).
- Kiểm tra phần cứng — soft lockup có thể do lỗi CPU/RAM.

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
| `reverse_lookup_failure` | 0 | 56 | 100.0% |
| `suspicious_sudo` | 0 | 56 | 100.0% |
| `port_scan` | 0 | 55 | 100.0% |
| `sql_injection` | 0 | 55 | 100.0% |
| `directory_traversal` | 0 | 55 | 100.0% |
| `service_crash` | 5 | 55 | 90.9% |

### Nguyên nhân

- KNN chỉ phát hiện các điểm cực kỳ cô lập (global outlier). Anomaly xuất hiện lặp lại nhiều lần (brute force, failed password) tự tạo thành mini-cluster → không bị coi là outlier.
- Ngưỡng sigma=2.0 rất bảo thủ, chỉ bắt ~0.2% dữ liệu.

### Hướng cải thiện

- Thử nghiệm với threshold thấp hơn để tăng recall.
- Kết hợp thêm đặc trưng thời gian (temporal features).
- Sử dụng model embedding chuyên biệt cho syslog thay vì MiniLM đa dụng.
- Thêm detector thứ ba (Isolation Forest, LOF) để tăng diversity.
