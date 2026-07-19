# isolation-forest-detector

## 1. Mục đích
Phát hiện bất thường trong syslog bằng thuật toán **Isolation Forest** — phương pháp unsupervised dựa trên cây quyết định ngẫu nhiên. Không giống Centroid (so với tâm) hay KNN (so với láng giềng), Isolation Forest khai thác nguyên lý: *điểm bất thường dễ bị cô lập hơn điểm bình thường*. Bằng cách xây dựng nhiều cây ngẫu nhiên, thuật toán đo độ sâu trung bình cần thiết để cô lập mỗi điểm — điểm càng nông (dễ cô lập) thì càng bất thường.

Ground truth **chỉ dùng để đánh giá** — không tham gia huấn luyện.

## 2. Vai trò trong Pipeline
Isolation Forest là detector thứ ba, chạy song song với Centroid và KNN:

```
embedding-generator  ──┬── centroid-detector       ──┐
                       ├── knn-detector            ──┤
                       └── isolation-forest-detector ─┘
                                                       ├── ensemble-voter ── reporter
```

Có thể chạy độc lập qua chain `isolation-forest-only.yaml`.

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `--embeddings-npy` | str | `data/processed/embeddings.npy` | Ma trận embedding (5000, 384) |
| `--parsed-logs` | str | `data/processed/parsed_logs.json` | File parsed để lấy service, line_number |
| `--ground-truth` | str | `data/raw/syslog_ground_truth.json` | Ground truth (chỉ để đánh giá) |
| `--output` | str | `data/processed/isolation_forest_results.json` | File kết quả |
| `--contamination` | float | 0.05 | Tỷ lệ anomaly ước tính (5%) |
| `--random-state` | int | 42 | Seed cho tính tái lập |
| `--n-estimators` | int | 100 | Số lượng cây trong rừng |

## 4. Output
File `data/processed/isolation_forest_results.json`:

```json
{
  "config": {
    "method": "isolation_forest",
    "contamination": 0.05,
    "n_estimators": 100,
    "random_state": 42
  },
  "global_stats": {
    "total_vectors": 5000,
    "anomalies_found": 250,
    "anomaly_ratio": 0.05
  },
  "results": [
    {
      "line_number": 1,
      "service": "sudo",
      "anomaly_score": 0.42,
      "is_anomaly": false
    }
  ],
  "evaluation": {
    "accuracy": 0.92,
    "precision": 0.75,
    "recall": 0.38,
    "f1_score": 0.50,
    "true_positives": 188,
    "false_positives": 62,
    "true_negatives": 4438,
    "false_negatives": 312
  }
}
```

| Trường | Mô tả |
|---|---|
| `anomaly_score` | Điểm bất thường ∈ [0, 1] (0 = bình thường, 1 = rất bất thường) |
| `is_anomaly` | `true` nếu bị Isolation Forest gắn cờ |

## 5. Thuật toán sử dụng
**Isolation Forest** (Liu, Ting, Zhou — 2008) thuộc họ ensemble tree-based anomaly detection.

### 5.1 Nguyên lý hoạt động
1. **Xây dựng cây**: Với mỗi cây, chọn ngẫu nhiên một chiều (feature) và một ngưỡng cắt (split value) trong khoảng [min, max] của chiều đó. Phân chia dữ liệu thành 2 nhánh. Lặp lại đệ quy đến khi mỗi nút lá chỉ chứa 1 điểm hoặc đạt độ sâu tối đa.
2. **Đo độ sâu**: `path_length(x)` = số lần phân nhánh cần thiết để cô lập điểm `x` trong cây.
3. **Tính anomaly score**:
   ```
   E(h(x)) = độ sâu trung bình của x trên tất cả các cây
   c(n)    = độ sâu trung bình kỳ vọng cho n điểm (hằng số chuẩn hóa)

   score(x) = 2^(-E(h(x)) / c(n))
   ```
   - `score ≈ 1` → độ sâu rất nhỏ → dễ cô lập → bất thường
   - `score ≈ 0.5` → độ sâu trung bình → không rõ ràng
   - `score ≈ 0` → độ sâu lớn → khó cô lập → bình thường

### 5.2 Tại sao điểm bất thường dễ bị cô lập?
Trong không gian embedding 384 chiều:
- **Điểm bình thường**: Nằm trong cụm dày đặc → cần nhiều lần phân nhánh để tách riêng từng điểm.
- **Điểm bất thường**: Nằm ở vùng thưa thớt, xa đám đông → chỉ cần vài lần cắt ngẫu nhiên là bị cô lập.

## 6. Công thức hoặc nguyên lý hoạt động

### 6.1 Hàm decision_function (sklearn)
Isolation Forest trong sklearn trả về `decision_function(x)`:
- Giá trị âm → bất thường
- Giá trị dương → bình thường

### 6.2 Chuẩn hóa anomaly_score
Để đồng bộ với Centroid và KNN (cùng thang [0, 1]):

```python
raw_score = -clf.decision_function(embeddings)      # âm = bất thường → đảo dấu
anomaly_score = (raw_score - raw_score.min()) / (raw_score.max() - raw_score.min())
```

Kết quả: 0 = bình thường nhất, 1 = bất thường nhất.

### 6.3 Ngưỡng contamination
Với `contamination=0.05`, Isolation Forest tự động gán 5% điểm có score cao nhất là bất thường. Đây là ngưỡng **tự động**, không cần cấu hình `threshold_sigma` như Centroid hay KNN.

## 7. Logic xử lý
1. **Nạp embedding**: Load `embeddings.npy` (5000, 384).
2. **Huấn luyện**: `IsolationForest(contamination=0.05, random_state=42).fit(embeddings)`.
3. **Dự đoán**: `predict()` → -1 (bất thường) hoặc 1 (bình thường).
4. **Tính anomaly_score**: Chuẩn hóa `decision_function` về [0, 1].
5. **Đóng gói kết quả**: Mỗi dòng có `line_number`, `service`, `anomaly_score`, `is_anomaly`.
6. **Đánh giá** (nếu có ground truth): Tính confusion matrix, accuracy, precision, recall, F1.
7. **Lưu JSON**.

## 8. Các tham số cấu hình
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `contamination` | 0.05 | Tỷ lệ anomaly kỳ vọng. Càng cao → càng nhiều detection, càng nhiều FP |
| `n_estimators` | 100 | Số cây. Càng nhiều → càng ổn định, chậm hơn |
| `random_state` | 42 | Seed cố định để reproducible |
| `max_samples` | auto (256) | Số mẫu mỗi cây. Mặc định 256, đủ cho hầu hết dataset |

## 9. Thư viện Python sử dụng
| Thư viện | Mục đích |
|---|---|
| `numpy` | Đọc ma trận embedding |
| `sklearn.ensemble.IsolationForest` | Thuật toán chính |
| `json` | Đọc/ghi file |
| `argparse` | CLI |
| `pathlib.Path` | Kiểm tra file |

Cài đặt: `pip install scikit-learn numpy`

## 10. Ưu điểm
| Ưu điểm | Giải thích |
|---|---|
| **Không giả định phân phối** | Không yêu cầu dữ liệu chuẩn, không cần tính centroid hay khoảng cách |
| **Phát hiện global outlier tốt** | Điểm nằm ngoài rìa phân phối bị cô lập nhanh |
| **Tuyến tính theo thời gian** | O(n) với số cây cố định — nhanh hơn KNN (O(n²)) |
| **Không bị ảnh hưởng bởi curse of dimensionality** | Chọn feature ngẫu nhiên → hiệu quả cả trong không gian 384 chiều |
| **Tự động xác định ngưỡng** | `contamination` kiểm soát tỷ lệ anomaly thay vì cần threshold thủ công |

## 11. Nhược điểm
| Nhược điểm | Giải thích |
|---|---|
| **Cần ước lượng contamination** | Phải biết trước ~% anomaly. Nếu đoán sai → kết quả sai lệch |
| **Không phát hiện local outlier** | Điểm nằm trong cụm nhỏ nhưng khác biệt vẫn có thể bị bỏ qua |
| **Ngẫu nhiên** | Kết quả thay đổi theo seed nếu không đặt `random_state` |
| **Không giải thích được** | Khó trả lời "tại sao điểm này bất thường" — khác với Centroid (khoảng cách đến tâm) hay KNN (hàng xóm) |
| **Nhạy với contamination** | Quá cao → nhiều FP; quá thấp → bỏ sót anomaly |

## 12. Tiêu chí đánh giá
| Chỉ số | Mô tả |
|---|---|
| Accuracy | (TP + TN) / Total |
| Precision | TP / (TP + FP) — bao nhiêu % flag là đúng? |
| Recall | TP / (TP + FN) — bao nhiêu % anomaly thực sự bị bắt? |
| F1-score | 2 × P × R / (P + R) — cân bằng precision và recall |
| False Positive Rate | FP / (FP + TN) — tỷ lệ báo động giả |

## 13. Kết quả mong đợi
| Chỉ số | Giá trị kỳ vọng |
|---|---|
| Số anomaly phát hiện | ~250 (5% của 5000) |
| Accuracy | 0.89 – 0.93 |
| Precision | 0.65 – 0.85 |
| Recall | 0.30 – 0.45 |
| F1 Score | 0.45 – 0.60 |
| Thời gian huấn luyện | < 1 giây |

## 14. Ví dụ thực thi
```bash
# Mặc định
python .pi/skills/isolation-forest-detector/detect.py

# Tùy chỉnh contamination
python .pi/skills/isolation-forest-detector/detect.py --contamination 0.08

# Chain riêng
python .pi/skills/isolation-forest-detector/detect.py \
  --embeddings-npy data/processed/embeddings.npy \
  --output data/processed/isolation_forest_results.json
```

## 15. So sánh với các Detector khác

| Tiêu chí | Centroid | KNN | Isolation Forest |
|---|---|---|---|
| Loại phương pháp | Distance-based | Density-based | Tree-based |
| Cần dữ liệu normal | Có | Không | Không |
| Giải thích kết quả | Dễ | Trung bình | Khó |
| Tốc độ | Nhanh | Trung bình | Nhanh |
| Local anomaly | Kém | Tốt | Trung bình |
| Global anomaly | Tốt | Trung bình | Rất tốt |
