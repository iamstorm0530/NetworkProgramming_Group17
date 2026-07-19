# centroid-agent

## Vai trò
**Centroid Agent** là detector thứ nhất trong pipeline, thực hiện phát hiện bất thường bằng phương pháp Per-Service Centroid (unsupervised). Agent này tính vector trung tâm cho từng service và gắn cờ những dòng log có khoảng cách cosine đến centroid vượt ngưỡng cho phép.

## Nhiệm vụ
- Nhận ma trận embedding từ embedding-agent.
- Nhóm các embedding theo service (dựa trên `parsed_logs.json`).
- Tính centroid cho mỗi service bằng trung bình cộng các vector trong service đó.
- Tính cosine distance từ mỗi embedding đến centroid của service tương ứng.
- Xác định ngưỡng bất thường per-service: `threshold = mean + k × std`.
- Gắn cờ `is_anomaly = True` cho các dòng có cosine distance vượt ngưỡng.
- Đối chiếu với ground truth để đánh giá accuracy, precision, recall, F1.
- **Lưu ý**: Ground truth chỉ dùng để đánh giá, không tham gia vào quá trình huấn luyện hay xác định ngưỡng.

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `embeddings.npy` | NumPy binary | `data/processed/` | Ma trận (5000, 384) đã L2-normalized |
| `parsed_logs.json` | JSON | `data/processed/` | Chứa thông tin `service` và `line_number` |
| `syslog_ground_truth.json` | JSON | `data/raw/` | Ground truth (chỉ để đánh giá) |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `centroid_results.json` | JSON | `logs/` | Kết quả gồm: `config`, `per_service_stats`, `results` (mỗi dòng: cosine_distance, anomaly_score, is_anomaly), `evaluation` |

## Điều kiện hoàn thành
- [x] Centroid được tính riêng cho từng service (8 service).
- [x] Centroid sau khi tính có chuẩn L2 = 1.0.
- [x] Cosine distance được tính chính xác: `distance = 1 - dot(embedding, centroid)`.
- [x] Ngưỡng per-service = mean_distance + threshold_sigma × std_distance.
- [x] Ground truth không được dùng để huấn luyện hay xác định ngưỡng.
- [x] Tất cả 5000 dòng đều có kết quả detection.
- [x] Evaluation metrics (accuracy, precision, recall, F1) được tính đúng.
- [x] File output JSON hợp lệ và chứa đầy đủ 4 phần: config, per_service_stats, results, evaluation.
