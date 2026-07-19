# anomaly-reporter

## 1. Mục đích
Tạo báo cáo đánh giá (**Evaluation Report**) cho từng detector (Centroid, KNN, Isolation Forest) và ensemble. Báo cáo phân tích tự động — thống kê, phân loại tấn công, giải thích, khuyến nghị bảo mật.

**Skill này chỉ chịu trách nhiệm báo cáo đánh giá. Không tạo form đánh giá thủ công (Human Evaluation).**

## 2. Vai trò trong Pipeline
Đây là **skill cuối cùng** trong pipeline — nằm sau ensemble-voter.

```
... centroid-detector ────────────┐
... knn-detector ─────────────────┤
... isolation-forest-detector ────┤
                                  ├─ ensemble-voter ──┐
                                  │                    ├─ anomaly-reporter → reports/*.md
             ground truth ────────┘                    │
             parsed logs  ─────────────────────────────┘
```

## 3. Input
| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `--centroid-results` | str | `logs/centroid_results.json` | Kết quả centroid |
| `--knn-results` | str | `logs/knn_results.json` | Kết quả KNN |
| `--iforest-results` | str | `data/processed/isolation_forest_results.json` | Kết quả Isolation Forest |
| `--ensemble-results` | str | `logs/ensemble_results.json` | Kết quả ensemble |
| `--parsed-logs` | str | `data/processed/parsed_logs.json` | Log đã parse |
| `--ground-truth` | str | `data/raw/syslog_ground_truth.json` | Ground truth |
| `--output-dir` | str | `reports/` | Thư mục output |

## 4. Các loại báo cáo được sinh

| File | Detector |
|---|---|
| `reports/centroid_report.md` | Centroid Detector |
| `reports/knn_report.md` | KNN Detector |
| `reports/isolation_forest_report.md` | Isolation Forest Detector |
| `reports/ensemble_report.md` | Ensemble (3 detector) |

## 5. Cấu trúc mỗi báo cáo

Mỗi báo cáo Evaluation Report gồm 12 phần:

```
# Evaluation Report: [Tên Detector]

## 1. Tổng quan detector
## 2. Cấu hình thực nghiệm
## 3. Kết quả phát hiện
## 4. Top anomaly
## 5. Confusion Matrix
## 6. Accuracy
## 7. Precision
## 8. Recall
## 9. F1-score
## 10. Điểm mạnh
## 11. Điểm yếu
## 12. Khuyến nghị
```

Phần 4 (Top anomaly) hiển thị các dòng có anomaly score cao nhất kèm mẫu log thực tế.

Phần 5–9 hiển thị confusion matrix và các metrics từ ground truth.

Phần 10–11 phân tích ưu/nhược điểm dựa trên kết quả thực tế của detector đó.

Phần 12 đưa ra khuyến nghị bảo mật cụ thể, phân theo attack category.

## 6. Logic xử lý
1. **Nạp toàn bộ dữ liệu**: detector results, ensemble results, parsed logs, ground truth.
2. **Với mỗi detector (Centroid, KNN, Isolation Forest, Ensemble)**:
   a. Tính thống kê tổng quan
   b. Đối chiếu với ground truth → confusion matrix, metrics
   c. Phân tích từng loại anomaly: đếm detected / total, lấy mẫu log
   d. Gom nhóm anomaly type → attack category
   e. Sinh khuyến nghị dựa trên loại tấn công phát hiện được
   f. Ghi ra file `reports/{detector}_report.md`

## 7. Thư viện Python
| Thư viện | Mục đích |
|---|---|
| `json` | Đọc dữ liệu |
| `argparse` | CLI |
| `pathlib.Path` | Tạo thư mục, ghi file |
| `datetime` | Timestamp trong báo cáo |
| `collections.Counter` | Đếm phân bố |

*(Chỉ dùng Python standard library.)*

## 8. Ví dụ thực thi
```bash
python .pi/skills/anomaly-reporter/reporter.py
```

## 9. Kết quả mong đợi
| Chỉ số | Giá trị |
|---|---|
| Số file sinh ra | 4 |
| Dung lượng mỗi report | 4–8 KB |
| Tổng thời gian | < 1 giây |
| Định dạng | Markdown (GitHub-flavored) |
