# centroid-detector

## 1. Mục đích
Phát hiện bất thường trong syslog bằng phương pháp **Per-Service Centroid** — thuật toán unsupervised, không cần dữ liệu gán nhãn để huấn luyện. Mỗi service có một vector trung tâm (centroid) riêng; những dòng log nằm quá xa centroid sẽ bị gắn cờ bất thường.

Ground truth **chỉ dùng để đánh giá** (evaluation) — không tham gia vào quá trình huấn luyện hay xác định ngưỡng.

## 2. Vai trò trong Pipeline
Đây là một trong hai detector chạy song song trong pipeline tổng:

```
embedding-generator  ──┬── centroid-detector  ──┐
                       │                        ├── ensemble-voter ── reporter
                       └── knn-detector      ──┘
```

Có thể chạy độc lập qua chain `centroid-only.yaml`, hoặc chạy song song trong chain `ensemble-parallel.yaml`.

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `--embeddings-npy` | str | `data/processed/embeddings.npy` | Ma trận embedding (5000, 384) |
| `--embeddings-meta` | str | `data/processed/embeddings_meta.json` | Metadata ánh xạ index → line_number |
| `--parsed-logs` | str | `data/processed/parsed_logs.json` | File parsed để lấy thông tin service |
| `--ground-truth` | str | `data/raw/syslog_ground_truth.json` | Ground truth (chỉ để đánh giá) |
| `--output` | str | `logs/centroid_results.json` | File kết quả |
| `--threshold-sigma` | float | 2.0 | Số lần độ lệch chuẩn để tính ngưỡng |
| `--trim-ratio` | float | 0.0 | Tỷ lệ outlier bị loại khi tính centroid (0.0 = không trim) |

## 4. Output
File `logs/centroid_results.json` gồm 3 phần:

```json
{
  "config": {
    "method": "per_service_centroid",
    "distance_metric": "cosine_distance",
    "threshold_sigma": 2.0,
    "trim_ratio": 0.0
  },
  "per_service_stats": {
    "sshd": {
      "sample_count": 1078,
      "centroid_norm": 1.0,
      "mean_distance": 0.080,
      "std_distance": 0.042,
      "threshold": 0.164
    }
  },
  "results": [
    {
      "line_number": 1,
      "service": "sudo",
      "cosine_distance": 0.0512,
      "anomaly_score": 0.0256,
      "is_anomaly": false
    }
  ],
  "evaluation": {
    "accuracy": 0.95,
    "precision": 0.91,
    "recall": 0.84,
    "f1_score": 0.87,
    "true_positives": 420,
    "false_positives": 42,
    "true_negatives": 4458,
    "false_negatives": 80
  }
}
```

| Trường | Mô tả |
|---|---|
| `line_number` | Số dòng trong file gốc |
| `service` | Tên service |
| `cosine_distance` | Khoảng cách cosine đến centroid service đó ∈ [0, 2] |
| `anomaly_score` | Điểm bất thường chuẩn hóa ∈ [0, 1] (= cosine_distance / 2) |
| `is_anomaly` | `true` nếu anomaly_score > threshold của service |

## 5. Logic xử lý
1. **Nạp dữ liệu**: Load embedding, metadata (line_mapping), parsed logs (service), ground truth.
2. **Nhóm theo service**: Gom các embedding có cùng service lại với nhau.
3. **Tính centroid per-service**:
   - Tính trung bình cộng tất cả vector trong service → centroid thô.
   - Chuẩn hóa L2 để centroid có độ dài = 1 (vì bản thân embedding cũng đã L2-normalized).
4. **Tính cosine distance**:
   - Vì cả embedding và centroid đều L2-normalized → `cosine_similarity = embedding · centroid`.
   - `cosine_distance = 1 - cosine_similarity` ∈ [0, 2].
   - `anomaly_score = cosine_distance / 2` ∈ [0, 1].
5. **Xác định ngưỡng per-service**:
   - Với mỗi service, tính `mean_distance` và `std_distance` của tất cả cosine distance trong service đó.
   - `threshold = mean_distance + threshold_sigma × std_distance`.
   - Nếu `cosine_distance > threshold` → bất thường.
6. **Lưu kết quả**: Ghi JSON output.
7. **Đánh giá (evaluation)**: So sánh `is_anomaly` với ground truth, tính accuracy, precision, recall, F1.

## 6. Công thức toán học

### 6.1 Công thức Centroid
Với service `s` có tập embedding `V_s = {v_1, v_2, ..., v_n}`:

```
           1    n
C_s_raw = ─── * Σ  v_i
           n   i=1

C_s = C_s_raw / ||C_s_raw||        (chuẩn hóa L2 về độ dài 1)
```

**Giải thích trực quan**: Centroid là "điểm trung bình" của tất cả log thuộc service đó trong không gian 384 chiều. Một dòng log bình thường sẽ nằm gần centroid; một dòng log bất thường (vd: sshd bị brute force) sẽ có nội dung khác xa → vector lệch khỏi centroid.

### 6.2 Công thức Cosine Distance
```
cosine_similarity(v, C) = (v · C) / (||v|| × ||C||)

Vì ||v|| = ||C|| = 1 (đã L2-normalized):
cosine_similarity(v, C) = v · C = Σ(v_j × C_j) với j = 1..384

cosine_distance(v, C) = 1 - cosine_similarity(v, C)
```

**Ý nghĩa**:
- `cosine_distance = 0` → vector trùng hướng centroid → log hoàn toàn bình thường
- `cosine_distance = 1` → vector vuông góc centroid → log không liên quan (nghi ngờ)
- `cosine_distance = 2` → vector ngược hướng centroid → log cực kỳ bất thường

### 6.3 Cách tính Anomaly Score
```
anomaly_score = cosine_distance / 2         ∈ [0, 1]
```

Chia cho 2 để chuẩn hóa về [0, 1], dễ diễn giải: 0 = bình thường, 1 = cực kỳ bất thường.

### 6.4 Cách tính ngưỡng (Threshold)
Với mỗi service `s`:
```
μ_s = mean({d_i | i ∈ service s})           // khoảng cách trung bình
σ_s = std({d_i | i ∈ service s})            // độ lệch chuẩn

threshold_s = μ_s + k × σ_s                  // k = threshold_sigma (mặc định 2.0)
```

Dùng quy tắc 2-sigma: nếu phân phối khoảng cách gần chuẩn, ~95% dữ liệu nằm dưới ngưỡng, ~5% bị gắn cờ.

## 7. Ưu điểm
| Ưu điểm | Giải thích |
|---|---|
| **Unsupervised** | Không cần dữ liệu gán nhãn — phù hợp với môi trường thực tế nơi không có sẵn ground truth |
| **Per-Service** | Mỗi service có centroid riêng → sshd và nginx có "hành vi bình thường" khác nhau → centroid cũng khác nhau → chính xác hơn |
| **Đơn giản, nhanh** | Chỉ cần 1 phép tính trung bình và 5000 phép dot product — O(n) |
| **Dễ giải thích** | "Dòng này cách xa hành vi bình thường của sshd một khoảng 0.85" → trực quan cho người vận hành |
| **Cosine distance** | Không bị ảnh hưởng bởi độ dài vector (vì đã L2-normalized), chỉ quan tâm đến hướng (ngữ nghĩa) |

## 8. Nhược điểm
| Nhược điểm | Giải thích |
|---|---|
| **Centroid bị kéo lệch bởi anomaly** | Nếu service có quá nhiều bất thường (>20%), centroid sẽ bị "nhiễm" và dịch về phía anomaly → giảm độ nhạy. Khắc phục: dùng `--trim-ratio` để loại bỏ top-K% outlier trước khi tính centroid |
| **Giả định phân phối chuẩn** | Ngưỡng dùng mean + k*std chỉ chính xác nếu cosine distance phân phối gần chuẩn. Nếu phân phối lệch (skewed) → threshold không tối ưu |
| **Không phát hiện được bất thường tập thể** | Nếu tất cả log trong service đều bất thường giống nhau (vd: toàn bộ nginx bị SQL injection), centroid sẽ nằm ngay giữa đám bất thường đó → không phát hiện được |
| **Nhạy với service ít mẫu** | Service như `dns` (312 dòng) hoặc `firewall` (332 dòng) có ít mẫu → centroid kém ổn định → nhiễu cao hơn |
| **Chỉ dùng ngữ nghĩa message** | Bỏ qua thông tin thời gian, tần suất, mối liên hệ giữa các service → không phát hiện được anomaly dạng chuỗi thời gian (vd: đột biến lúc 3h sáng) |

## 9. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `numpy` | Tính centroid, dot product, mean/std |
| `json` | Đọc/ghi file JSON |
| `argparse` | CLI |
| `pathlib.Path` | Kiểm tra file tồn tại |

*(Chỉ dùng Python standard library + numpy.)*

## 10. Ví dụ thực thi
```bash
# Mặc định
python .pi/skills/centroid-detector/detect.py

# Tùy chỉnh ngưỡng
python .pi/skills/centroid-detector/detect.py \
  --threshold-sigma 1.5 \
  --trim-ratio 0.1

# Chain centroid-only
python .pi/skills/centroid-detector/detect.py \
  --embeddings-npy data/processed/embeddings.npy \
  --output logs/centroid_results.json
```

## 11. Kết quả mong đợi
| Chỉ số | Giá trị kỳ vọng |
|---|---|
| Accuracy | 0.90 – 0.95 |
| Precision | 0.80 – 0.92 |
| Recall | 0.70 – 0.88 |
| F1 Score | 0.78 – 0.90 |
| Số anomaly phát hiện | 300 – 600 (trên 5000 dòng, 10% thực sự bất thường) |
| Thời gian chạy | < 0.5 giây |
