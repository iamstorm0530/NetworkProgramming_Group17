# syslog-generator

## 1. Mục đích
Sinh dữ liệu syslog giả lập (synthetic) dùng cho huấn luyện và kiểm thử mô hình phát hiện bất thường. Dữ liệu được tạo ra mô phỏng môi trường sản xuất thực tế, bao gồm cả log bình thường và log bất thường có gán nhãn (ground truth) để đánh giá độ chính xác của các detector.

## 2. Vai trò trong Pipeline
Đây là **skill đầu tiên** trong pipeline — nằm trước syslog-parser. Nó cung cấp dữ liệu đầu vào cho toàn bộ hệ thống. Nếu không có skill này, người dùng phải tự chuẩn bị file syslog thật kèm ground truth, vốn rất khó thu thập và gán nhãn thủ công.

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `total_lines` | int | 5000 | Tổng số dòng log cần sinh |
| `anomaly_ratio` | float | 0.10 | Tỷ lệ dòng bất thường (10%) |
| `hostname` | str | `"server-01"` | Tên máy chủ trong log |
| `start_date` | str | `"2026-06-12"` | Ngày bắt đầu sinh log |
| `output_log` | str | `data/raw/syslog_synthetic.log` | Đường dẫn file log |
| `output_truth` | str | `data/raw/syslog_ground_truth.json` | Đường dẫn file ground truth |

## 4. Output
| File | Định dạng | Mô tả |
|---|---|---|
| `syslog_synthetic.log` | Text (syslog RFC 3164) | 5000 dòng log, mỗi dòng gồm: timestamp, hostname, service[pid], message |
| `syslog_ground_truth.json` | JSON | Mảng các object `{line_number, is_anomaly, anomaly_type}` |

## 5. Logic xử lý
1. **Khởi tạo**: Đọc cấu hình (số dòng, tỷ lệ bất thường, hostname, ngày bắt đầu).
2. **Phân bổ**: Chia 5000 dòng thành ~4500 dòng bình thường (8 service, mỗi service ~560 dòng) và ~500 dòng bất thường (9 loại, mỗi loại ~55 dòng).
3. **Sinh log bình thường**: Với mỗi service, chọn ngẫu nhiên từ tập mẫu (template) tin nhắn bình thường, ghép với timestamp tăng dần ngẫu nhiên, hostname, và PID giả ngẫu nhiên.
4. **Sinh log bất thường**: Tương tự nhưng chọn từ tập mẫu bất thường, gán nhãn loại bất thường tương ứng.
5. **Trộn ngẫu nhiên**: Gộp tất cả dòng log, sắp xếp theo timestamp để đảm bảo thứ tự thời gian thực tế.
6. **Xuất file**: Ghi log ra file `.log` và ground truth ra file `.json`.

## 6. Thuật toán sử dụng
- **Phân phối Poisson thời gian**: Mỗi log cách nhau một khoảng thời gian ngẫu nhiên (phân phối mũ) để mô phỏng tần suất log thực tế — lúc dày, lúc thưa.
- **Chọn mẫu ngẫu nhiên có trọng số**: Một số service như `sshd` và `kernel` xuất hiện nhiều hơn `dns` hay `firewall`, phản ánh thực tế.
- **Fisher-Yates shuffle**: Trộn danh sách log để tránh pattern tuần hoàn.

## 7. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `random` | Sinh PID, chọn mẫu, trộn dữ liệu |
| `datetime`, `timedelta` | Tạo timestamp liên tục |
| `json` | Ghi ground truth |
| `pathlib.Path` | Tạo thư mục output |

*(Không cần thư viện ngoài — chỉ dùng Python standard library.)*

## 8. Ví dụ thực thi
```bash
python .pi/skills/syslog-generator/generate_syslog.py \
  --total-lines 5000 \
  --anomaly-ratio 0.10 \
  --hostname "web-prod-01" \
  --start-date "2026-06-12" \
  --output-log data/raw/syslog_synthetic.log \
  --output-truth data/raw/syslog_ground_truth.json
```

Hoặc với cấu hình mặc định:
```bash
python .pi/skills/syslog-generator/generate_syslog.py
```

## 9. Hạn chế
- **Không mô phỏng được sự phụ thuộc giữa các service**: Thực tế, một lỗi `sshd` có thể kéo theo log `systemd`; hiện tại mỗi service hoạt động độc lập.
- **Bất thường đơn giản, dễ phát hiện**: Các mẫu bất thường được chèn rõ ràng (vd: "Failed password for invalid user"), không có các kỹ thuật ẩn giấu tinh vi như log injection hay obfuscation.
- **Không có noise thực tế**: Không có log bị thiếu PID, sai định dạng, hoặc encoding lỗi như syslog thật.
- **Phân phối đều bất thường**: Thực tế bất thường phân bố không đều (có đợt tấn công dồn dập, có lúc yên tĩnh).

## 10. Kết quả mong đợi
| Chỉ số | Giá trị |
|---|---|
| Tổng dòng log | 5,000 |
| Dòng bình thường | ~4,500 (90%) |
| Dòng bất thường | ~500 (10%) |
| Số service bình thường | 8 |
| Số loại bất thường | 9 |
| File output | 2 (`syslog_synthetic.log`, `syslog_ground_truth.json`) |
| Độ dài trung bình mỗi dòng | 80–160 ký tự |
