# knn-agent

## Vai trò
**KNN Agent** là detector thứ hai trong pipeline, thực hiện phát hiện bất thường bằng thuật toán K-Nearest Neighbors (unsupervised). Agent này đánh giá mức độ "cô lập" của mỗi dòng log dựa trên khoảng cách trung bình đến k láng giềng gần nhất trong không gian embedding.

## Nhiệm vụ
- Nhận ma trận embedding từ embedding-agent.
- Tính ma trận cosine distance toàn cục: `distance_matrix = 1 - embeddings @ embeddings.T`.
- Với mỗi dòng log, tìm k = 5 láng giềng có cosine distance nhỏ nhất (bỏ qua chính nó).
- Tính `knn_distance` = trung bình cosine distance đến k láng giềng.
- Chuẩn hóa thành `anomaly_score` ∈ [0, 1].
- Xác định ngưỡng toàn cục: `threshold = mean + k × std`.
- Gắn cờ `is_anomaly = True` cho các dòng có `knn_distance > threshold`.
- Đối chiếu với ground truth để đánh giá (ground truth không tham gia huấn luyện).

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `embeddings.npy` | NumPy binary | `data/processed/` | Ma trận (5000, 384) đã L2-normalized |
| `parsed_logs.json` | JSON | `data/processed/` | Chứa thông tin `service` và `line_number` |
| `syslog_ground_truth.json` | JSON | `data/raw/` | Ground truth (chỉ để đánh giá) |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `knn_results.json` | JSON | `logs/` | Kết quả gồm: `config`, `global_stats`, `results` (mỗi dòng: knn_distance, anomaly_score, is_anomaly, neighbor_line_numbers), `evaluation` |

## Điều kiện hoàn thành
- [x] Ma trận similarity được tính chính xác bằng phép nhân ma trận `embeddings @ embeddings.T`.
- [x] Đường chéo của ma trận distance được gán `inf` để không chọn chính nó làm láng giềng.
- [x] Sử dụng `argpartition` để tìm top-k nhanh (O(n²·log k) thay vì O(n²·log n)).
- [x] k = 5 láng giềng được chọn chính xác cho mỗi điểm.
- [x] `knn_distance` = trung bình cosine distance đến k láng giềng.
- [x] Ground truth không được dùng để huấn luyện hay xác định ngưỡng.
- [x] Tất cả 5000 dòng đều có kết quả detection.
- [x] `neighbor_line_numbers` lưu đúng line_number (không phải index) của k láng giềng.
- [x] File output JSON hợp lệ và chứa đầy đủ các phần.
