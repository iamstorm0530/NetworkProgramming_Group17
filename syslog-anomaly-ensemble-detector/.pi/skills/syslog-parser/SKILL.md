# syslog-parser

## 1. Mục đích
Phân tích cú pháp (parse) file syslog thô thành các bản ghi có cấu trúc, chuẩn hóa và làm sạch dữ liệu để các skill downstream (embedding-generator, centroid-detector, knn-detector) có thể tiêu thụ trực tiếp mà không cần xử lý lại định dạng.

## 2. Vai trò trong Pipeline
Đây là **skill thứ hai** trong pipeline, đứng ngay sau syslog-generator. Nó nhận file `.log` thô, trích xuất các trường quan trọng, suy luận mức độ nghiêm trọng (severity), và xuất ra JSON có cấu trúc. Nếu không có skill này, mọi detector phải tự viết logic parse — dẫn đến trùng lặp code và sai khác định dạng giữa các detector.

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `input_log` | str | `data/raw/syslog_synthetic.log` | Đường dẫn file syslog thô |
| `output_json` | str | `data/processed/parsed_logs.json` | Đường dẫn file JSON kết quả |
| `default_year` | int | 2026 | Năm mặc định (syslog RFC 3164 không chứa năm) |

## 4. Output
File `data/processed/parsed_logs.json` — một mảng JSON gồm các object với 6 trường:

| Trường | Kiểu | Mô tả |
|---|---|---|
| `timestamp` | str (ISO 8601) | Ví dụ: `"2026-06-12T00:00:09"` |
| `host` | str | Hostname, ví dụ: `"server-01"` |
| `service` | str | Tên service, ví dụ: `"sshd"`, `"kernel"` |
| `severity` | str | Một trong: `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `message` | str | Nội dung thông điệp gốc (sau dấu `:`) |
| `line_number` | int | Số thứ tự dòng trong file gốc (đánh từ 1) |

## 5. Logic xử lý
1. **Đọc file**: Mở file syslog, đọc từng dòng, giữ nguyên `line_number`.
2. **Trích xuất bằng regex**: Với mỗi dòng, dùng regex RFC 3164 để tách:
   - `timestamp`: `Mmm DD HH:MM:SS`
   - `host`: hostname (token ngay sau timestamp)
   - `service`: tên service (token trước `[` hoặc `:`)
   - `message`: phần còn lại sau `service[pid]:` hoặc `service:`
3. **Chuẩn hóa timestamp**: Ghép năm mặc định vào, chuyển sang ISO 8601 (`YYYY-MM-DDTHH:MM:SS`).
4. **Suy luận severity**: Dùng danh sách quy tắc từ khóa (keyword rules) để gán severity dựa trên nội dung `message`. Ưu tiên khớp từ cao xuống thấp: CRITICAL → ERROR → WARNING. Nếu không khớp, mặc định là `INFO`.
5. **Xuất JSON**: Ghi toàn bộ mảng object ra file, indent 2, UTF-8.

## 6. Thuật toán sử dụng
- **Regex capture groups**: Trích xuất các trường syslog chỉ bằng 1 lần duyệt regex, không cần split thủ công.
- **Rule-based severity classification**: Danh sách quy tắc sắp xếp theo độ nghiêm trọng giảm dần. Duyệt tuần tự, dừng ở quy tắc đầu tiên khớp.
- **Stream processing**: Đọc file từng dòng, không load toàn bộ vào RAM (phù hợp với file hàng triệu dòng).

## 7. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `re` | Regex trích xuất trường syslog |
| `json` | Ghi file JSON output |
| `datetime` | Chuẩn hóa timestamp |
| `argparse` | CLI |
| `pathlib.Path` | Tạo thư mục output |

*(Chỉ dùng Python standard library.)*

## 8. Ví dụ thực thi
```bash
python .pi/skills/syslog-parser/parser.py \
  --input-log data/raw/syslog_synthetic.log \
  --output-json data/processed/parsed_logs.json \
  --default-year 2026
```

```bash
# Với cấu hình mặc định
python .pi/skills/syslog-parser/parser.py
```

## 9. Hạn chế
- **RFC 3164 chỉ hỗ trợ timestamp không năm**: Phải cấu hình `--default-year`; nếu log kéo dài qua giao thừa, parser sẽ gán sai năm.
- **Regex không xử lý được syslog dị dạng**: Nếu dòng không khớp regex, dòng đó bị bỏ qua và ghi cảnh báo ra stderr.
- **Severity suy luận theo từ khóa, không phải giá trị thật**: Syslog thật có trường `PRI` (facility * 8 + severity) nhưng generator hiện tại không sinh PRI, nên phải dùng keyword rules.
- **Không trích xuất PID**: PID bị loại bỏ trong quá trình parse (theo yêu cầu output 6 trường). Nếu cần PID cho phân tích sau này, cần mở rộng output schema.

## 10. Kết quả mong đợi
| Chỉ số | Giá trị |
|---|---|
| Tổng dòng parse thành công | 5,000 |
| Dòng bị bỏ qua (parse lỗi) | 0 |
| Trường output | 6 (`timestamp`, `host`, `service`, `severity`, `message`, `line_number`) |
| Phân bố severity | ~90% INFO, ~5% WARNING, ~3% ERROR, ~2% CRITICAL (xấp xỉ) |
| Kích thước file output | ~1.2–1.8 MB |
