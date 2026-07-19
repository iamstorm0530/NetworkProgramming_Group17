# embedding-agent

## Vai trò
**Embedding Agent** là cầu nối giữa dữ liệu văn bản và các thuật toán học máy. Agent này biến mỗi dòng log message thành một vector số 384 chiều trong không gian embedding, cho phép các detector (Centroid, KNN) thực hiện tính toán khoảng cách và phát hiện bất thường.

## Nhiệm vụ
- Đọc `parsed_logs.json` từ `data/processed/`.
- Trích xuất trường `message` của từng bản ghi.
- Sử dụng model `all-MiniLM-L6-v2` (Sentence-BERT) để encode mỗi message thành vector 384 chiều.
- Chuẩn hóa L2 tất cả vector (độ dài = 1) để tối ưu cho phép tính cosine similarity sau này.
- Lưu ma trận embedding dạng `.npy` và metadata mô tả.

## Input
| Tên | Định dạng | Nguồn | Mô tả |
|---|---|---|---|
| `parsed_logs.json` | JSON | `data/processed/` | Kết quả từ parser-agent, chứa 5000 bản ghi với trường `message` |

## Output
| Tên | Định dạng | Đích | Mô tả |
|---|---|---|---|
| `embeddings.npy` | NumPy binary | `data/processed/` | Ma trận kích thước `(5000, 384)` kiểu `float32`, đã L2-normalized |
| `embeddings_meta.json` | JSON | `data/processed/` | Metadata: `model_name`, `dimension`, `total_vectors`, `line_mapping`, `l2_normalized` |

## Điều kiện hoàn thành
- [x] Tất cả 5000 dòng message được encode thành công (không có dòng nào bị lỗi).
- [x] Ma trận output có kích thước chính xác `(5000, 384)`.
- [x] Tất cả vector có chuẩn L2 = 1.0 (sai số < 1e-5).
- [x] `line_mapping` trong metadata ánh xạ đúng thứ tự index → line_number.
- [x] Model `all-MiniLM-L6-v2` được tải và sử dụng đúng phiên bản.
- [x] File `.npy` có thể load lại bằng `np.load()` và cho ra kết quả giống hệt.
