# RUNBOOK – Syslog Anomaly Ensemble Detector

## 1. Mo ta he thong
He thong phat hien bat thuong trong syslog su dung 3 detector unsupervised (Centroid, KNN, Isolation Forest) va ket hop bang ensemble voting. Toan bo pipeline tu dong tu du lieu gia lap → bao cao danh gia.

## 2. Cau truc thu muc

```
.
├── data/
│   ├── raw/           Du lieu syslog tho + ground truth
│   └── processed/     Du lieu da xu ly (parse, embedding, IF results)
├── logs/              Ket qua cac detector
├── reports/           Bao cao Evaluation Report (.md)
├── .pi/
│   ├── agents/        Dinh nghia 7 agent
│   ├── skills/        Ma nguon 8 skill
│   └── chain/         4 chain pipeline
└── requirements.txt   Thu vien Python
```

## 3. Thu vien yeu cau

```
numpy
sentence-transformers
scikit-learn
```

Cai dat: `pip install -r requirements.txt`

## 4. Cach chay

### 4.1 Chay toan bo pipeline

```bash
# Step 1: Sinh du lieu
python .pi/skills/syslog-generator/generate_syslog.py

# Step 2: Parse syslog
python .pi/skills/syslog-parser/parser.py

# Step 3: Tao embedding
python .pi/skills/embedding-generator/embedder.py

# Step 4: Chay 3 detector
python .pi/skills/centroid-detector/detect.py
python .pi/skills/knn-detector/detect.py
python .pi/skills/isolation-forest-detector/detect.py

# Step 5: Ensemble
python .pi/skills/ensemble-voter/voter.py

# Step 6: Sinh bao cao
python .pi/skills/anomaly-reporter/reporter.py
```

### 4.2 Chay tung case rieng le

```bash
# Case 1: Centroid
python .pi/skills/centroid-detector/detect.py

# Case 2: KNN
python .pi/skills/knn-detector/detect.py

# Case 3: Isolation Forest
python .pi/skills/isolation-forest-detector/detect.py

# Case 4: Ensemble
python .pi/skills/ensemble-voter/voter.py
```

## 5. Cac chiến lược Ensemble

| Chiến lược | Dieu kien | Phu hop khi |
|---|---|---|
| weighted_average | (s_c + s_k + s_if) / 3 > threshold | Can score lien tuc |
| majority_and | Ca 3 cung gan co | Can precision tuyet doi |
| majority_2of3 | It nhat 2/3 gan co | Can bang P/R |
| **majority_or** | It nhat 1/3 gan co | Can recall cao nhat |

## 6. Thong so mac dinh

| Tham so | Gia tri |
|---|---|
| Tong so dong log | 5000 |
| Ty le bat thuong | 10% |
| Model embedding | all-MiniLM-L6-v2 |
| Kich thuoc vector | 384 |
| Centroid sigma | 2.0 |
| KNN k | 5 |
| KNN sigma | 2.0 |
| IF contamination | 0.05 |
| IF n_estimators | 100 |
| Trong so ensemble | 1:1:1 |

## 7. Output

| File | Mo ta |
|---|---|
| `data/raw/syslog_synthetic.log` | Syslog gia lap |
| `data/raw/syslog_ground_truth.json` | Nhan ground truth |
| `data/processed/parsed_logs.json` | Log da parse |
| `data/processed/embeddings.npy` | Ma tran embedding |
| `data/processed/isolation_forest_results.json` | IF ket qua |
| `logs/centroid_results.json` | Centroid ket qua |
| `logs/knn_results.json` | KNN ket qua |
| `logs/ensemble_results.json` | Ensemble ket qua |
| `reports/*.md` | 4 bao cao danh gia |
