# ensemble-voter

## 1. Mục đích
Kết hợp (ensemble) kết quả từ **ba detector** — **Centroid Detector**, **KNN Detector**, và **Isolation Forest Detector** — thành một quyết định cuối cùng. Ensemble giúp tận dụng thế mạnh riêng của từng detector, giảm false positive và tăng độ tin cậy của hệ thống.

Hỗ trợ 4 chiến lược bỏ phiếu:
- **weighted_average**: Trung bình có trọng số của anomaly score từ 3 detector
- **majority_and**: Cả ba detector cùng gắn cờ → mới kết luận bất thường
- **majority_2of3**: Ít nhất 2/3 detector gắn cờ → kết luận bất thường
- **majority_or**: Một trong ba detector gắn cờ → kết luận bất thường

## 2. Vai trò trong Pipeline
Đây là **skill thứ bảy** — nằm sau ba detector và trước reporter:

```
centroid-detector        ──┐
knn-detector             ──┤
isolation-forest-detector ─┘
                              ├── ensemble-voter ── reporter
```

Ensemble-voter nhận output của cả ba detector, kết hợp lại, và xuất ra quyết định ensemble cuối cùng.

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `--centroid-results` | str | `logs/centroid_results.json` | Kết quả từ centroid-detector |
| `--knn-results` | str | `logs/knn_results.json` | Kết quả từ knn-detector |
| `--iforest-results` | str | `data/processed/isolation_forest_results.json` | Kết quả từ isolation-forest-detector |
| `--ground-truth` | str | `data/raw/syslog_ground_truth.json` | Ground truth (đánh giá) |
| `--output` | str | `logs/ensemble_results.json` | File kết quả ensemble |
| `--weight-centroid` | float | 1.0 | Trọng số cho centroid |
| `--weight-knn` | float | 1.0 | Trọng số cho KNN |
| `--weight-iforest` | float | 1.0 | Trọng số cho Isolation Forest |
| `--weighted-threshold` | float | 0.5 | Ngưỡng cho weighted_average |

## 4. Output
File `logs/ensemble_results.json`:

```json
{
  "config": {
    "strategies": ["weighted_average", "majority_and", "majority_2of3", "majority_or"],
    "weight_centroid": 1.0,
    "weight_knn": 1.0,
    "weight_iforest": 1.0,
    "weighted_threshold": 0.5
  },
  "input_stats": {
    "centroid_anomalies": 133,
    "knn_anomalies": 10,
    "iforest_anomalies": 241,
    "all_three_agree": 0,
    "centroid_knn": 0,
    "centroid_iforest": 0,
    "knn_iforest": 0
  },
  "ensemble_stats": { ... },
  "results": [
    {
      "line_number": 1,
      "service": "sudo",
      "centroid_score": 0.166,
      "knn_score": 0.000,
      "iforest_score": 0.423,
      "weighted_average_score": 0.196,
      "weighted_average_is_anomaly": false,
      "majority_and_is_anomaly": false,
      "majority_2of3_is_anomaly": false,
      "majority_or_is_anomaly": false
    }
  ],
  "evaluation": {
    "centroid_baseline": { ... },
    "knn_baseline": { ... },
    "isolation_forest_baseline": { ... },
    "weighted_average": { ... },
    "majority_and": { ... },
    "majority_2of3": { ... },
    "majority_or": { ... }
  }
}
```

### Các detector tham gia voting

| Detector | Vai trò |
|---|---|
| Centroid | Phát hiện log xa tâm |
| KNN | Phát hiện log cô lập cục bộ |
| Isolation Forest | Phát hiện điểm dễ bị cô lập bằng cây ngẫu nhiên |

## 5. Logic xử lý
1. **Nạp kết quả**: Load `centroid_results.json`, `knn_results.json`, `isolation_forest_results.json`.
2. **Đồng bộ theo line_number**: Join ba danh sách kết quả theo `line_number`.
3. **Phân tích overlap**: Đếm all_three_agree, centroid_knn, centroid_iforest, knn_iforest.
4. **Tính weighted_average**:
   - `ensemble_score = (1.0×s_c + 1.0×s_k + 1.0×s_if) / 3.0`
   - Hoặc với trọng số tùy chỉnh: `(w_c×s_c + w_k×s_k + w_if×s_if) / (w_c + w_k + w_if)`
   - `is_anomaly = ensemble_score > weighted_threshold`
5. **Tính majority_and**: `is_anomaly = c AND k AND if`
6. **Tính majority_2of3**: `is_anomaly = (c+k+if) >= 2`
7. **Tính majority_or**: `is_anomaly = c OR k OR if`
8. **Đánh giá**: Tính accuracy, precision, recall, F1 cho từng chiến lược.
9. **Xuất JSON**.

## 6. Công thức toán học

### 6.1 Weighted Average (3 detector)
```
        w_c × s_c + w_k × s_k + w_if × s_if
score = ──────────────────────────────────────
                w_c + w_k + w_if
```

Với trọng số mặc định bằng nhau (mỗi detector 1/3):
```
score = (s_centroid + s_knn + s_iforest) / 3
```

### 6.2 Majority AND (3 detector)
```
is_anomaly = flag_centroid AND flag_knn AND flag_iforest
```

### 6.3 Majority 2-of-3
```
is_anomaly = (flag_centroid + flag_knn + flag_iforest) >= 2
```

### 6.4 Majority OR (3 detector)
```
is_anomaly = flag_centroid OR flag_knn OR flag_iforest
```

## 7. Lý do kết hợp nhiều detector

| Lý do | Giải thích |
|---|---|
| **Góc nhìn bổ sung** | Centroid nhìn từ "tâm", KNN nhìn từ "hàng xóm", Isolation Forest nhìn từ "cây cô lập". Ba nguyên lý khác nhau → phát hiện loại anomaly khác nhau |
| **Giảm blind spot** | Mỗi detector có blind spot riêng → ensemble lấp đầy khoảng trống |
| **Tăng recall** | majority_or với 3 detector phát hiện nhiều hơn bất kỳ detector đơn lẻ nào |
| **Linh hoạt** | 4 chiến lược để chọn: precision cao (majority_and), cân bằng (2of3), recall cao (majority_or) |

## 8. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `json` | Đọc/ghi file JSON |
| `argparse` | CLI |
| `pathlib.Path` | Kiểm tra file |

*(Chỉ dùng Python standard library.)*

## 9. Ví dụ thực thi
```bash
# Mặc định (trọng số bằng nhau cho 3 detector)
python .pi/skills/ensemble-voter/voter.py

# Tùy chỉnh trọng số
python .pi/skills/ensemble-voter/voter.py \
  --weight-centroid 1.0 --weight-knn 0.5 --weight-iforest 0.5

# Chain ensemble-parallel
python .pi/skills/ensemble-voter/voter.py \
  --centroid-results logs/centroid_results.json \
  --knn-results logs/knn_results.json \
  --iforest-results data/processed/isolation_forest_results.json \
  --output logs/ensemble_results.json
```

## 10. Kết quả mong đợi
| Chiến lược | Precision | Recall | F1 | Ghi chú |
|---|---|---|---|---|
| Centroid (đơn lẻ) | ~1.00 | ~0.27 | ~0.42 | Baseline |
| KNN (đơn lẻ) | ~1.00 | ~0.02 | ~0.04 | Baseline |
| Isolation Forest (đơn lẻ) | ~0.15 | ~0.07 | ~0.10 | Baseline |
| **majority_or** | ~0.47 | ~0.36 | ~0.41 | Recall cao nhất |
| **majority_2of3** | ~0.00 | ~0.00 | ~0.00 | 3 detector không overlap |
| **majority_and** | ~0.00 | ~0.00 | ~0.00 | 3 detector không overlap |

> **Ghi chú**: Trên tập dữ liệu này, 3 detector có zero overlap — mỗi detector phát hiện tập anomaly hoàn toàn khác nhau. majority_or kết hợp được cả 3 tập, tăng recall 35% so với centroid đơn lẻ nhưng precision giảm do Isolation Forest có nhiều false positive.
