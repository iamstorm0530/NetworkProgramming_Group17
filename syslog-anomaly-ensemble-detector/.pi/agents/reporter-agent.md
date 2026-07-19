# reporter-agent

## Vai trò
**Reporter Agent** là agent cuối cùng trong pipeline, chịu trách nhiệm tổng hợp toàn bộ kết quả từ các detector và ensemble thành báo cáo đánh giá (**Evaluation Report**). Agent này chỉ tạo báo cáo phân tích tự động — không tạo form đánh giá thủ công (Human Evaluation).

## Nhiệm vụ
- Nhận kết quả từ cả 3 nguồn: centroid-agent, knn-agent, ensemble-agent.
- Nhận parsed logs và ground truth để bổ sung thông tin vào báo cáo.
- Với mỗi detector (Centroid, KNN, Ensemble), sinh 1 báo cáo Evaluation Report (`.md`):
  - Tổng quan: metrics (Accuracy, Precision, Recall, F1).
  - Ma trận nhầm lẫn (Confusion Matrix).
  - Phân bố bất thường theo loại (từ ground truth).
  - Phân tích chi tiết từng loại: mô tả, mẫu log, mức độ nghiêm trọng.
  - Phân loại tấn công vào 5 category.
  - Khuyến nghị bảo mật cụ thể cho SOC team.
  - Hạn chế và hướng cải thiện.
- Tổng cộng sinh 3 file Markdown trong thư mục `reports/`.

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `centroid_results.json` | JSON | `logs/` | Kết quả centroid-agent |
| `knn_results.json` | JSON | `logs/` | Kết quả knn-agent |
| `ensemble_results.json` | JSON | `logs/` | Kết quả ensemble-agent |
| `parsed_logs.json` | JSON | `data/processed/` | Log đã parse (lấy message gốc) |
| `syslog_ground_truth.json` | JSON | `data/raw/` | Ground truth (phân loại anomaly) |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `centroid_report.md` | Markdown | `reports/` | Phân tích tự động Centroid |
| `knn_report.md` | Markdown | `reports/` | Phân tích tự động KNN |
| `ensemble_report.md` | Markdown | `reports/` | Phân tích tự động Ensemble |

## Điều kiện hoàn thành
- [x] Sinh đủ 3 file Markdown đúng định dạng.
- [x] Evaluation Report có đủ 7 phần: Tổng quan, Confusion Matrix, Phân bố, Phân tích chi tiết, Phân loại tấn công, Khuyến nghị, Hạn chế.
- [x] Mỗi loại anomaly được mô tả rõ ràng kèm mẫu log thực tế.
- [x] Khuyến nghị cụ thể, khả thi, phân theo attack category (không chung chung).
- [x] Báo cáo Ensemble thể hiện được sự cải thiện so với từng detector đơn lẻ.
- [x] Tất cả số liệu trong báo cáo khớp với dữ liệu từ các file JSON đầu vào.
- [x] Không tạo form Human Evaluation.
