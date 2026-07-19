# knn-detector

## 1. Mục đích
Phát hiện bất thường trong syslog bằng thuật toán **K-Nearest Neighbors (KNN)** — phương pháp unsupervised dựa trên mật độ cục bộ. Mỗi dòng log được đánh giá bằng khoảng cách trung bình đến k láng giềng gần nhất của nó trong không gian embedding. Dòng log nào "cô đơn" (xa tất cả các dòng khác) sẽ bị gắn cờ bất thường.

Ground truth **chỉ dùng để đánh giá** — không tham gia huấn luyện.

## 2. Vai trò trong Pipeline
KNN-detector là một trong hai detector trong pipeline tổng, chạy song song với centroid-detector:

```
embedding-generator  ──┬── centroid-detector  ──┐
                       │                        ├── ensemble-voter ── reporter
                       └── knn-detector      ──┘
```

Có thể chạy độc lập qua chain `knn-only.yaml`, hoặc song song trong `ensemble-parallel.yaml`.

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `--embeddings-npy` | str | `data/processed/embeddings.npy` | Ma trận embedding (5000, 384) |
| `--embeddings-meta` | str | `data/processed/embeddings_meta.json` | Metadata ánh xạ index → line_number |
| `--parsed-logs` | str | `data/processed/parsed_logs.json` | File parsed để lấy thông tin service |
| `--ground-truth` | str | `data/raw/syslog_ground_truth.json` | Ground truth (chỉ để đánh giá) |
| `--output` | str | `logs/knn_results.json` | File kết quả |
| `--k-neighbors` | int | 5 | Số láng giềng gần nhất (k) |
| `--threshold-sigma` | float | 2.0 | Số lần std để tính ngưỡng toàn cục |

## 4. Output
File `logs/knn_results.json`:

```json
{
  "config": {
    "method": "knn",
    "k": 5,
    "distance_metric": "cosine_distance",
    "threshold_sigma": 2.0
  },
  "global_stats": {
    "mean_knn_distance": 0.1523,
    "std_knn_distance": 0.0456,
    "threshold": 0.2435
  },
  "results": [
    {
      "line_number": 1,
      "service": "sudo",
      "knn_distance": 0.0712,
      "anomaly_score": 0.0356,
      "is_anomaly": false,
      "neighbor_line_numbers": [24, 67, 102, 189, 301]
    }
  ],
  "evaluation": {
    "accuracy": 0.93,
    "precision": 0.88,
    "recall": 0.78,
    "f1_score": 0.83
  }
}
```

| Trường | Mô tả |
|---|---|
| `knn_distance` | Khoảng cách cosine trung bình đến k láng giềng gần nhất ∈ [0, 2] |
| `anomaly_score` | knn_distance / 2 ∈ [0, 1] |
| `neighbor_line_numbers` | Số dòng của k láng giềng gần nhất (để truy vết) |

## 5. Logic xử lý
1. **Nạp dữ liệu**: Load embedding, parsed logs (service), ground truth.
2. **Tính ma trận tương đồng**: `similarity_matrix = embeddings @ embeddings.T` → (5000, 5000). Vì embedding đã L2-normalized, đây chính là cosine similarity giữa mọi cặp.
3. **Tính ma trận khoảng cách**: `distance_matrix = 1 - similarity_matrix` → cosine distance ∈ [0, 2].
4. **Tìm k láng giềng gần nhất**: Với mỗi dòng, sắp xếp khoảng cách tăng dần, lấy k giá trị nhỏ nhất (bỏ qua chính nó — distance = 0).
5. **Tính anomaly score**: `knn_distance = mean(top_k_distances)`, `anomaly_score = knn_distance / 2`.
6. **Xác định ngưỡng toàn cục**: `threshold = mean(knn_distances) + sigma × std(knn_distances)`.
7. **Gắn cờ**: `is_anomaly = knn_distance > threshold`.
8. **Đánh giá**: So sánh với ground truth.

## 6. Thuật toán và khái niệm

### 6.1 KNN là gì?
**K-Nearest Neighbors (KNN)** là thuật toán dựa trên ý tưởng: *"Hãy nhìn vào những người hàng xóm gần nhất của bạn để biết bạn là ai"*.

Trong phát hiện bất thường:
- Mỗi dòng log là một điểm trong không gian 384 chiều.
- Tìm k điểm gần nhất với nó (khoảng cách nhỏ nhất).
- Nếu khoảng cách trung bình đến k láng giềng **lớn** → điểm này "cô đơn", không giống ai → **bất thường**.
- Nếu khoảng cách trung bình đến k láng giềng **nhỏ** → điểm này nằm trong đám đông → **bình thường**.

**Trực quan hóa** (không gian 2D thay vì 384D):
```
        ● ← bất thường (xa mọi điểm khác)

  ● ●
 ● ● ● ●     ← cụm bình thường (gần nhau)
  ● ● ●
   ● ●
```

### 6.2 Vì sao chọn k = 5?
| k | Ưu điểm | Nhược điểm |
|---|---|---|
| k = 1 | Cực nhạy, phát hiện mọi outlier | Quá nhạy với nhiễu — một điểm lạc cũng bị gắn cờ |
| **k = 5** | **Cân bằng tốt** giữa độ nhạy và độ ổn định | — |
| k = 20 | Ổn định, ít false positive | Có thể bỏ sót anomaly cục bộ (local outlier) |

**Lý do chọn k = 5:**
- Trong tập 5000 dòng, 5 láng giềng đại diện cho ~0.1% dữ liệu — đủ nhỏ để phát hiện local outlier.
- Theo kinh nghiệm thực nghiệm, k = √n ≈ √5000 ≈ 70 là quá lớn cho anomaly detection; k = 5-20 là phổ biến.
- k lẻ (5) tránh hòa trong bài toán phân loại (dù ở đây ta chỉ dùng khoảng cách, không bỏ phiếu).

### 6.3 Cách tính Anomaly Score
```
Với mỗi vector v_i:

1. Tính cosine distance đến tất cả vector khác:
   distance(v_i, v_j) = 1 - (v_i · v_j)           (vì đã L2-normalized)

2. Sắp xếp tăng dần, lấy k giá trị nhỏ nhất (bỏ distance=0 với chính nó):
   top_k_distances = {d_1, d_2, ..., d_k}

3. Tính trung bình:
   knn_distance_i = (1/k) × Σ d_j                 ∈ [0, 2]

4. Chuẩn hóa:
   anomaly_score_i = knn_distance_i / 2            ∈ [0, 1]
```

**Ý nghĩa**:
- `anomaly_score ≈ 0`: log này có nhiều "hàng xóm" rất gần → giống với nhiều log khác → bình thường.
- `anomaly_score ≈ 0.5`: log này cách xa đám đông → đáng nghi ngờ.
- `anomaly_score ≈ 1.0`: log này cực kỳ cô lập → gần như chắc chắn bất thường.

### 6.4 Ngưỡng (Threshold)
Dùng ngưỡng toàn cục (không per-service như centroid):
```
μ = mean({knn_distance_i | i = 1..n})
σ = std({knn_distance_i | i = 1..n})

threshold = μ + sigma × σ
```
Dùng ngưỡng toàn cục vì KNN đã tự động xử lý sự khác biệt giữa các service — mỗi điểm được so với **tất cả** điểm khác, không giới hạn trong service.

## 7. Ưu điểm
| Ưu điểm | Giải thích |
|---|---|
| **Unsupervised** | Không cần nhãn, chỉ dựa vào cấu trúc dữ liệu |
| **Phát hiện local outlier** | Không giống centroid (chỉ so với 1 điểm trung tâm), KNN so với k điểm gần nhất → phát hiện được bất thường cục bộ |
| **Không giả định phân phối** | Không yêu cầu dữ liệu phân phối chuẩn |
| **Đơn giản, dễ hiểu** | "Log này không giống bất kỳ log nào khác" → trực quan |
| **Tự động cross-service** | Mỗi dòng được so với tất cả service khác → nếu một dòng sshd giống nginx hơn là giống sshd, nó sẽ bị phát hiện |
| **Có thể truy vết** | Lưu `neighbor_line_numbers` → biết được log nào "bình thường" gần nhất để đối chiếu |

## 8. Nhược điểm
| Nhược điểm | Giải thích |
|---|---|
| **Độ phức tạp O(n²)** | Cần tính 25 triệu cặp khoảng cách cho 5000 dòng. Với 100K dòng → 10 tỷ cặp → cần tối ưu (KD-tree, LSH, FAISS) |
| **Nhạy với k** | k quá nhỏ → nhạy nhiễu; k quá lớn → bỏ sót anomaly. Cần thử nghiệm để chọn k tối ưu |
| **Không phân biệt được anomaly tập thể** | Nếu có 100 dòng cùng loại bất thường, chúng sẽ là "hàng xóm" của nhau → khoảng cách nhỏ → không bị phát hiện |
| **Ngưỡng toàn cục** | Một ngưỡng cho tất cả service có thể không tối ưu — service có phân tán cao (vd: systemd) dễ bị gắn cờ hơn service tập trung (vd: firewall) |
| **Tốn RAM** | Ma trận 5000×5000 float32 = 100 MB. Với 50K dòng → 10 GB |

## 9. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `numpy` | Tính ma trận similarity, sắp xếp, mean/std |
| `json` | Đọc/ghi file |
| `argparse` | CLI |
| `pathlib.Path` | Kiểm tra file |

*(Chỉ dùng Python standard library + numpy.)*

## 10. Ví dụ thực thi
```bash
# Mặc định (k=5, sigma=2.0)
python .pi/skills/knn-detector/detect.py

# Tùy chỉnh
python .pi/skills/knn-detector/detect.py --k-neighbors 7 --threshold-sigma 1.8

# Chain knn-only
python .pi/skills/knn-detector/detect.py \
  --embeddings-npy data/processed/embeddings.npy \
  --output logs/knn_results.json
```

## 11. Kết quả mong đợi
| Chỉ số | Giá trị kỳ vọng |
|---|---|
| Accuracy | 0.90 – 0.94 |
| Precision | 0.60 – 0.85 |
| Recall | 0.40 – 0.75 |
| F1 Score | 0.50 – 0.78 |
| Số anomaly phát hiện | 200 – 600 |
| Thời gian chạy (5000 dòng) | 1 – 3 giây |
