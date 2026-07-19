# parser-agent

## Vai trò
**Parser Agent** là agent đầu tiên trong pipeline, chịu trách nhiệm tiếp nhận file syslog thô (raw) và chuyển đổi thành dữ liệu có cấu trúc để các agent downstream tiêu thụ.

## Nhiệm vụ
- Đọc file syslog thô từ `data/raw/`.
- Tách mỗi dòng log thành các trường: `timestamp`, `host`, `service`, `severity`, `message`.
- Chuẩn hóa timestamp về định dạng ISO 8601 (`YYYY-MM-DDTHH:MM:SS`).
- Suy luận mức độ nghiêm trọng (`severity`) dựa trên từ khóa trong nội dung message: `CRITICAL`, `ERROR`, `WARNING`, `INFO`.
- Xuất kết quả ra file JSON có cấu trúc.

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `syslog_synthetic.log` | Text (RFC 3164) | `data/raw/` | File syslog thô, mỗi dòng định dạng `<timestamp> <host> <service>[pid]: <message>` |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `parsed_logs.json` | JSON | `data/processed/` | Mảng các object gồm 6 trường: `timestamp`, `host`, `service`, `severity`, `message`, `line_number` |

## Điều kiện hoàn thành
- [x] Tất cả dòng trong file input được parse thành công (0 dòng bị bỏ qua).
- [x] Timestamp được chuẩn hóa đúng định dạng ISO 8601.
- [x] Trường `severity` được gán chính xác theo bộ quy tắc từ khóa.
- [x] File JSON output có đúng 6 trường cho mỗi bản ghi.
- [x] `line_number` khớp 1:1 với thứ tự dòng trong file gốc.
- [x] File output tồn tại và có thể đọc được bằng `json.load()`.
