# isolation-forest-agent

## Vai trò
**Isolation Forest Agent** là detector thứ ba trong pipeline, thực hiện phát hiện bất thường bằng thuật toán Isolation Forest (unsupervised). Agent này sử dụng cây ngẫu nhiên để cô lập các điểm dữ liệu — những điểm càng dễ bị cô lập (cần ít lần phân nhánh) thì càng có khả năng là bất thường.

## Mục đích
Bổ sung góc nhìn thứ ba vào hệ thống ensemble. Trong khi Centroid phát hiện "lệch chuẩn" và KNN phát hiện "cô lập cục bộ", Isolation Forest phát hiện "dễ bị cô lập" — những điểm nằm ở vùng thưa thớt, khác biệt rõ rệt với phần còn lại của dữ liệu. Ba detector với ba nguyên lý khác nhau tạo nên ensemble mạnh mẽ, giảm thiểu blind spot.

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `embeddings.npy` | NumPy binary | `data/processed/` | Ma trận (5000, 384) đã L2-normalized |
| `embeddings_meta.json` | JSON | `data/processed/` | Metadata ánh xạ index → line_number |
| `parsed_logs.json` | JSON | `data/processed/` | Chứa thông tin `service` và `line_number` |
| `syslog_ground_truth.json` | JSON | `data/raw/` | Ground truth (chỉ để đánh giá) |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `isolation_forest_results.json` | JSON | `logs/` | Kết quả gồm: `config`, `global_stats`, `results` (mỗi dòng: anomaly_score, is_anomaly), `evaluation` |

## Nhiệm vụ
- Nhận ma trận embedding từ embedding-agent.
- Huấn luyện mô hình `IsolationForest` từ `sklearn.ensemble` với `contamination=0.05`.
- Dự đoán: `-1` = bất thường, `1` = bình thường.
- Chuyển đổi decision function thành `anomaly_score` ∈ [0, 1] (0 = bình thường, 1 = bất thường).
- Đối chiếu với ground truth (nếu có) để tính Precision, Recall, F1.
- **Lưu ý**: Ground truth chỉ dùng để đánh giá, không tham gia huấn luyện.

## Điều kiện hoàn thành
- [x] Mô hình Isolation Forest được huấn luyện trên toàn bộ embedding (unsupervised).
- [x] `contamination=0.05` được áp dụng đúng — kỳ vọng ~250 anomaly.
- [x] `random_state=42` đảm bảo kết quả reproducible.
- [x] `anomaly_score` được chuẩn hóa về [0, 1] từ `decision_function`.
- [x] Tất cả 5000 dòng đều có kết quả detection.
- [x] Evaluation metrics được tính chính xác nếu có ground truth.
- [x] File output JSON hợp lệ, chứa đầy đủ config, stats, results, evaluation.

## Mối liên hệ với các agent khác
| Agent | Mối quan hệ |
|---|---|
| **embedding-agent** | Nhận `embeddings.npy` làm input |
| **parser-agent** | Nhận `parsed_logs.json` để lấy service và line_number |
| **centroid-agent** | Chạy song song trong ensemble-parallel chain |
| **knn-agent** | Chạy song song trong ensemble-parallel chain |
| **ensemble-agent** | Cung cấp kết quả cho ensemble voting (3 detector) |
| **reporter-agent** | Cung cấp kết quả để sinh `isolation_forest_report.md` |
