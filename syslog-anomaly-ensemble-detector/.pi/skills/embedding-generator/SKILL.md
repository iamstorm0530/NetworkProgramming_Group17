# embedding-generator

## 1. Mục đích
Chuyển đổi các dòng log dạng văn bản (text) thành vector số học (numerical vectors) trong không gian embedding 384 chiều. Vector hóa là bước trung gian bắt buộc: các thuật toán phát hiện bất thường như Centroid Detector hay KNN Detector **chỉ làm việc với số**, không thể tính toán trên text thô.

## 2. Vai trò trong Pipeline
Đây là **skill thứ ba** — nằm giữa syslog-parser và các detector (centroid-detector, knn-detector). Nó nhận JSON đã parse, biến mỗi dòng `message` thành 1 vector 384 chiều, xuất ra file `.npy` để detector tiêu thụ.

```
parsed_logs.json  →  [embedding-generator]  →  embeddings.npy + embeddings_meta.json
                                                      ↓
                                          centroid-detector / knn-detector
```

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `input_json` | str | `data/processed/parsed_logs.json` | File JSON từ syslog-parser |
| `output_npy` | str | `data/processed/embeddings.npy` | File numpy chứa ma trận embedding |
| `output_meta` | str | `data/processed/embeddings_meta.json` | File metadata mô tả embedding |
| `model_name` | str | `all-MiniLM-L6-v2` | Tên model sentence-transformers |
| `batch_size` | int | 64 | Số dòng encode cùng lúc để tối ưu GPU/CPU |

## 4. Output

| File | Định dạng | Mô tả |
|---|---|---|
| `embeddings.npy` | NumPy binary | Ma trận kích thước `(5000, 384)` — mỗi hàng là 1 vector tương ứng với 1 dòng log |
| `embeddings_meta.json` | JSON | Object chứa: `model_name`, `dimension`, `total_vectors`, `original_file`, `line_mapping` (ánh xạ index → line_number) |

**Cấu trúc `embeddings_meta.json`:**
```json
{
  "model_name": "all-MiniLM-L6-v2",
  "dimension": 384,
  "total_vectors": 5000,
  "original_file": "data/processed/parsed_logs.json",
  "line_mapping": [1, 2, 3, ..., 5000]
}
```

## 5. Logic xử lý
1. **Đọc input**: Load file `parsed_logs.json` → danh sách 5000 object.
2. **Trích xuất message**: Lấy trường `message` từ mỗi object. Đây là toàn bộ nội dung sau dấu `:` trong syslog (vd: `"Failed password for root from 10.0.0.99 port 40004 ssh2"`).
3. **Load model**: Tải `all-MiniLM-L6-v2` từ sentence-transformers. Model này tự động cache sau lần tải đầu tiên.
4. **Encode theo batch**: Chia 5000 message thành các batch 64 dòng, encode tuần tự để tránh tràn RAM GPU.
5. **Chuẩn hóa L2**: Mỗi vector được normalize về độ dài = 1. Việc này giúp cosine similarity giữa 2 vector bất kỳ chỉ còn là dot product (A·B), tăng tốc đáng kể khi tính toán hàng loạt sau này.
6. **Lưu embedding**: Ghi toàn bộ ma trận `(5000, 384)` ra file `.npy` (NumPy binary format — nhanh, nhẹ, load trực tiếp không cần parse).
7. **Lưu metadata**: Ghi file JSON chứa thông tin model, kích thước, ánh xạ index → line_number.

## 6. Thuật toán & khái niệm sử dụng

### 6.1 Embedding là gì?
**Embedding** (vector nhúng) là phép biến đổi một đoạn văn bản thành một vector số trong không gian nhiều chiều. Mỗi chiều mã hóa một khía cạnh ngữ nghĩa khác nhau. Hai câu có ý nghĩa tương tự sẽ có vector nằm gần nhau.

Ví dụ trực quan:
```
"Accepted password for admin"        →  [0.12, -0.34,  0.89, ...,  0.05] (384 số)
"Failed password for root"           →  [0.09,  0.41, -0.12, ..., -0.67] (384 số)
"GET /index.html HTTP/1.1 200 612"  →  [-0.78, 0.22,  0.45, ...,  0.31] (384 số)
```

### 6.2 Vì sao phải dùng embedding?
Các thuật toán phát hiện bất thường (centroid distance, k-NN) hoạt động trên **khoảng cách** giữa các điểm dữ liệu. Nhưng text thô không có khái niệm "khoảng cách" — không thể tính `"Failed password" - "Accepted password"`. Embedding biến text thành tọa độ trong không gian vector, cho phép:
- Tính **khoảng cách Euclidean** giữa 2 dòng log
- Tính **cosine similarity** để đo mức độ giống nhau
- Nhóm các log cùng loại vào cụm (cluster)
- Phát hiện log "lạc" ra ngoài cụm → **bất thường**

### 6.3 Cosine similarity là gì?
Cosine similarity đo **góc** giữa hai vector, không phải độ dài. Công thức:

```
cos(θ) = (A · B) / (||A|| × ||B||)
```

Trong đó:
- `A · B` là tích vô hướng (dot product) của 2 vector
- `||A||` là độ dài Euclidean của vector A
- Giá trị ∈ [-1, 1]: 1 = cùng hướng (giống hệt), 0 = vuông góc (không liên quan), -1 = ngược hướng

**Khi đã normalize L2 (||A|| = ||B|| = 1)**, cosine similarity rút gọn thành dot product:
```
cos(θ) = A · B
```

→ Tăng tốc hàng nghìn lần khi duyệt 5000 dòng log.

### 6.4 Kích thước vector 384 chiều
Model `all-MiniLM-L6-v2` nén toàn bộ ngữ nghĩa của một câu thành **384 con số**. Đây là con số được chọn qua nghiên cứu: đủ lớn để phân biệt hàng triệu câu khác nhau, nhưng đủ nhỏ để tính toán nhanh trên CPU (384 float32 = 1.5 KB/vector, 5000 vector ≈ 7.5 MB).

### 6.5 Về model all-MiniLM-L6-v2
- **Kiến trúc**: MiniLM (distilled từ BERT), 6 layers transformer
- **Đầu ra**: 384 chiều, đã được huấn luyện trên 1 tỷ cặp câu
- **Tại sao chọn model này**: Nhẹ (80 MB), nhanh (vài ms/câu), chất lượng đủ tốt để phân biệt các loại log khác nhau. Không cần GPU, chạy tốt trên CPU.

## 7. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `sentence-transformers` | Load model, encode văn bản → vector |
| `numpy` | Lưu/đọc ma trận embedding |
| `json` | Đọc input JSON, ghi metadata |
| `argparse` | CLI |
| `pathlib.Path` | Tạo thư mục output |

Cài đặt:
```bash
pip install sentence-transformers numpy
```

## 8. Ví dụ thực thi
```bash
python .pi/skills/embedding-generator/embedder.py \
  --input-json data/processed/parsed_logs.json \
  --output-npy data/processed/embeddings.npy \
  --output-meta data/processed/embeddings_meta.json \
  --model-name all-MiniLM-L6-v2 \
  --batch-size 64
```

```bash
# Với cấu hình mặc định
python .pi/skills/embedding-generator/embedder.py
```

## 9. Hạn chế
- **Model đa ngôn ngữ nhưng không chuyên cho syslog**: MiniLM được huấn luyện trên văn bản tự nhiên (Wikipedia, tin tức, hội thoại), không chuyên cho log kỹ thuật. Các log như `IN=eth0 OUT= SRC=... PROTO=TCP` có thể không được biểu diễn tốt bằng văn bản thông thường.
- **Mất thông tin cấu trúc**: Chỉ encode trường `message`, bỏ qua `timestamp`, `host`, `service`. Các detector sẽ không biết "cùng một service" hay "cùng một thời điểm" — chỉ dựa vào ngữ nghĩa message.
- **Chi phí inference**: 5000 dòng mất ~10-30 giây trên CPU, ~2-5 giây trên GPU. Với dataset lớn hơn (hàng triệu dòng), cần chiến lược batch và caching.
- **Không cập nhật online**: Embedding được sinh một lần, không tự động cập nhật khi có log mới. Trong production cần pipeline streaming.

## 10. Kết quả mong đợi
| Chỉ số | Giá trị |
|---|---|
| Số dòng encode | 5,000 |
| Kích thước vector | 384 |
| Kích thước file `.npy` | ~7.7 MB (5000 × 384 × 4 bytes float32) |
| Kích thước file meta | ~30 KB |
| Thời gian encode (CPU) | ~15-30 giây |
| Thời gian encode (GPU) | ~2-5 giây |
| Tỷ lệ lỗi encode | 0 (tất cả message đều encode được) |
