# ensemble-agent

## Vai trò
**Ensemble Agent** là bộ kết hợp (voter) trong pipeline, nhận kết quả từ **3 detector** — Centroid Agent, KNN Agent, và Isolation Forest Agent — sau đó tổng hợp thành một quyết định cuối cùng. Agent này triển khai 4 chiến lược bỏ phiếu khác nhau, cho phép người dùng lựa chọn giữa độ chính xác cao (precision) và độ phủ cao (recall).

## Nhiệm vụ
- Nhận `centroid_results.json`, `knn_results.json`, và `isolation_forest_results.json`.
- Đồng bộ ba kết quả theo `line_number`.
- Phân tích mức độ đồng thuận (overlap) giữa ba detector.
- Tính 4 chiến lược ensemble:
  1. **weighted_average**: `score = (w_c×s_c + w_k×s_k + w_if×s_if) / (w_c + w_k + w_if)`, gắn cờ nếu `score > threshold`.
  2. **majority_and**: gắn cờ nếu **cả ba** detector cùng gắn cờ.
  3. **majority_2of3**: gắn cờ nếu **ít nhất 2/3** detector gắn cờ.
  4. **majority_or**: gắn cờ nếu **ít nhất một** detector gắn cờ.
- Đối chiếu với ground truth để đánh giá từng chiến lược.

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `centroid_results.json` | JSON | `logs/` | Kết quả từ centroid-agent |
| `knn_results.json` | JSON | `logs/` | Kết quả từ knn-agent |
| `isolation_forest_results.json` | JSON | `logs/` | Kết quả từ isolation-forest-agent |
| `syslog_ground_truth.json` | JSON | `data/raw/` | Ground truth (chỉ để đánh giá) |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `ensemble_results.json` | JSON | `logs/` | Kết quả gồm: `config`, `input_stats` (overlap 3 detector), `ensemble_stats`, `results`, `evaluation` (7 bộ metrics) |

## Điều kiện hoàn thành
- [x] Kết quả từ 3 detector được đồng bộ chính xác theo `line_number`.
- [x] Cả 4 chiến lược (weighted_average, majority_and, majority_2of3, majority_or) đều được tính.
- [x] Weighted average sử dụng đúng công thức trung bình có trọng số với 3 detector.
- [x] Overlap analysis: tính được all_three_agree, centroid_knn, centroid_iforest, knn_iforest.
- [x] Evaluation bao gồm: 3 baseline + 4 chiến lược ensemble = 7 bộ metrics.
- [x] Mỗi dòng kết quả có đầy đủ: centroid_score, knn_score, iforest_score, weighted_average_score, và 4 cờ is_anomaly.
- [x] File output JSON hợp lệ và chứa đầy đủ các phần.
