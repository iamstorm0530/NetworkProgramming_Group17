# Syslog Anomaly Ensemble Detector

Do an cuoi ky mon **Network Programming with AI/ML**.

Phat hien bat thuong trong syslog bang 3 detector unsupervised + ensemble voting.

---

## Kien truc Pipeline

```
syslog_synthetic.log
        │
        ▼
  [syslog-parser]
        │
        ▼
  [embedding-generator]  ← all-MiniLM-L6-v2 (384 chieu)
        │
        ├──────────────┬──────────────────┬──────────────────┐
        ▼              ▼                  ▼                  ▼
   Centroid         KNN            Isolation Forest      (song song)
   Detector       Detector          Detector
        │              │                  │
        └──────────────┴──────────────────┘
                       │
                       ▼
               [ensemble-voter]
                       │
                       ▼
               [anomaly-reporter]
                       │
                       ▼
                  reports/*.md
```

---

## Cac thanh phan

### Agent (7)

| Agent | Mo ta |
|---|---|
| parser-agent | Parse syslog tho → JSON co cau truc |
| embedding-agent | Vector hoa message → 384 chieu |
| centroid-agent | Phat hien bat thuong bang Per-Service Centroid |
| knn-agent | Phat hien bat thuong bang KNN (k=5) |
| isolation-forest-agent | Phat hien bat thuong bang Isolation Forest |
| ensemble-agent | Ket hop 3 detector bang voting |
| reporter-agent | Sinh bao cao Evaluation Report |

### Chain (4)

| Chain | Luong |
|---|---|
| centroid-only | Parser → Embedding → Centroid → Report |
| knn-only | Parser → Embedding → KNN → Report |
| isolation-forest-only | Parser → Embedding → Isolation Forest → Report |
| ensemble-parallel | Parser → Embedding → [3 detector song song] → Ensemble → Report |

---

## Cai dat

```bash
pip install -r requirements.txt
```

## Chay toan bo pipeline

```bash
# 1. Sinh du lieu
python .pi/skills/syslog-generator/generate_syslog.py

# 2. Parse
python .pi/skills/syslog-parser/parser.py

# 3. Embedding
python .pi/skills/embedding-generator/embedder.py

# 4. Cac detector (chay song song duoc)
python .pi/skills/centroid-detector/detect.py
python .pi/skills/knn-detector/detect.py
python .pi/skills/isolation-forest-detector/detect.py

# 5. Ensemble
python .pi/skills/ensemble-voter/voter.py

# 6. Report
python .pi/skills/anomaly-reporter/reporter.py
```

---

## Ket qua

### So sanh 4 case

| Case | Detector | Accuracy | Precision | Recall | F1 | Anomalies |
|---|---|---|---|---|---|---|
| 1 | Centroid | ~0.93 | 1.00 | 0.27 | 0.42 | 133 |
| 2 | KNN | ~0.90 | 1.00 | 0.02 | 0.04 | 10 |
| 3 | Isolation Forest | ~0.87 | 0.15 | 0.07 | 0.10 | 241 |
| 4 | Ensemble (OR) | ~0.89 | 0.47 | 0.36 | 0.41 | 384 |

### Output

| File | Mo ta |
|---|---|
| `data/raw/syslog_synthetic.log` | 5000 dong syslog gia lap |
| `data/raw/syslog_ground_truth.json` | Ground truth |
| `data/processed/parsed_logs.json` | Log da parse |
| `data/processed/embeddings.npy` | Ma tran embedding (5000×384) |
| `data/processed/isolation_forest_results.json` | Ket qua Isolation Forest |
| `logs/centroid_results.json` | Ket qua Centroid |
| `logs/knn_results.json` | Ket qua KNN |
| `logs/ensemble_results.json` | Ket qua Ensemble |
| `reports/centroid_report.md` | Bao cao Centroid |
| `reports/knn_report.md` | Bao cao KNN |
| `reports/isolation_forest_report.md` | Bao cao Isolation Forest |
| `reports/ensemble_report.md` | Bao cao Ensemble |
