# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4/H201              |
| Tên nhóm         | THA     |
| Repository         | https://github.com/Truongjava/K4-L3B-Day10-THA-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Lê Thanh Trường | 2A202602492 | Trưởng nhóm | Data Foundation & Retrieval (`crossref.py`, `cleaning.py`, `index.py`) |
| 2 | Trần Hoàng Duy Anh | 2A202602558 | Thành viên | Observability & Evaluation (`quality.py`, `testset.py`, `metrics.py`) |
| 3 | Nguyễn Quang Huy | 2A202602461 | Thành viên | Data Recovery & Reporting (`corruption_flow.py`, `reporting.py`) |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thiện toàn bộ luồng Data Pipeline từ bước Ingestion dữ liệu thô (từ Crossref API), Cleaning, tính toán embedding cho đến Evaluation và Quality Checks. Baseline pipeline đã sinh ra 24 records, bộ test set 10 câu hỏi, cùng ChromaDB collections và báo cáo Quality Checks (GX 1.x PASS 100%).

Trong kịch bản Corruption, lỗi "truncate title" gây thiệt hại nặng nề nhất đến RAG Agent do cơ chế exact-match của Retrieval phụ thuộc vào Title. Kết quả là `retrieval_hit_rate` giảm mạnh (từ 1.000 xuống 0.800) và Quality Gate chuyển sang FAIL (báo lỗi độ dài).

Cơ chế Idempotent Repair sau đó đã tái tạo dữ liệu từ snapshot local (`raw_records.json`), sửa chữa toàn bộ bảng dữ liệu và khôi phục `retrieval_hit_rate`, `mean_token_f1` về mốc 1.000. Giới hạn hiện tại là cơ chế Judge Evaluation đang sử dụng heuristic (vì thiếu LLM) nên chưa đo lường triệt để năng lực sinh câu trả lời tự nhiên của mô hình.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref API | Fetch, parse JATS XML, xử lý date | `data/raw/` | Lê Thanh Trường |
| Cleaning          | Raw records | Xoá rác, sinh text_for_embedding | `data/clean/` | Lê Thanh Trường |
| Embedding/index   | Cleaned data | all-MiniLM-L6-v2 | `data/chroma/`, `data/embeddings/` | Lê Thanh Trường |
| Evaluation        | Cleaned data | Sinh câu hỏi QA, tính metric | `data/eval/`, `data/results/` | Trần Hoàng Duy Anh |
| Observability     | Cleaned data | GX 1.x rules, độ trễ | `data/quality/` | Trần Hoàng Duy Anh |
| Corruption/repair | Cleaned data | Chèn noise, tái khôi phục | `data/clean/`, `data/results/` | Nguyễn Quang Huy |
| Orchestration     | Toàn bộ flows| Chạy pipeline tổng hợp | `data/reports/` | Nguyễn Quang Huy |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | openrouter         |
| `LLM_MODEL`                | gemini-2.5-flash         |
| Embedding model              | all-MiniLM-L6-v2         |
| Số lượng Crossref records | 24         |
| Retrieval `top_k`           | 3         |
| Freshness threshold          | 180 days         |

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất |
| ----------------- | ----------------------------------------------- | ----------------------------- |
| Baseline pipeline | Thành công | 2026-09-26 11:20:00                  |
| Corruption flow   | Thành công | 2026-09-26 11:21:00                  |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref API (`works` endpoint) |
| Query/filter                | query=data engineering, data pipeline |
| Thời điểm lấy dữ liệu | 2026-09-26                           |
| Số record nhận được    | 24                         |
| Cơ chế retry/backoff      | Thử 3 lần với Tenacity, fallback offline snapshot |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| paper_id | string | Có | Mã DOI bài báo | Loại bỏ |
| title | string | Có | Tiêu đề bài báo | Bỏ nếu < 8 ký tự |
| summary | string | Có | Tóm tắt nội dung | Bỏ nếu rỗng hoặc < 40 ký tự |
| published | datetime | Có | Ngày xuất bản | Lấy default mùng 1 nếu thiếu ngày tháng |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động |
| ---------------------------------------- | ---------------------------- | -------------------------: | 
| Loại title < 8 ký tự | Completeness, Validity  |              0 |
| Khử trùng DOI | Uniqueness                  |              0 |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:
- `text_for_embedding`: Nối Title, Authors, Categories, Published, Abstract bằng `\n`.
- Document ID: Sinh từ `paper_id` cộng index để tránh trùng lặp.
- `age_days`: Đo thời gian lệch giữa `run_date` và `published`.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10                 |
| Các `question_type`                    | summary, authors, date, categories                  |
| Ground-truth document ID                 | Từ dataset (exact match title)     |
| Embedding model                          | all-MiniLM-L6-v2                  |
| Vector store/collection                  | ChromaDB (`papers-baseline`)                 |
| Retrieval `top_k`                       | 3                   |
| LLM provider/model                       | openrouter / gemini-2.5-flash                   |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái |
| ------------------------ | -------------------------------------- | ------------ |
| Raw response/records     | `data/raw/`                          | Có |
| Cleaned dataset          | `data/clean/`                        | Có |
| Embedding manifest/index | `data/embeddings/`                   | Có |
| Evaluation set           | `data/eval/`                         | Có |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có |
| Quality/freshness        | `data/quality/`                      | Có |
| Baseline report          | `data/reports/phase1_report.md`      | Có |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.00 | Tìm thấy đúng 100% paper  |
| `mean_token_f1`      |     1.00 | Khớp chữ hoàn toàn với label                           |
| `judge_accuracy`     |     1.00 | Chấm theo token_f1 (Heuristic) vì chưa config LLM                           |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | 
| ------------ | ----------------- | ------------------ | ----------------------- |
| Row count | Completeness | Tối thiểu bằng Raw data | Pass: 24 | 
| Title length | Validity | > 8 ký tự | Pass |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/papers_clean.csv`            |
| Ngưỡng freshness         | 180 ngày                         |
| Trạng thái baseline      | FRESH (4.17% quá hạn, đạt yêu cầu < 25%)               |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Drop latest | Xóa dòng cũ | 5 | FAIL Row Count | Gate bắt được lỗi | Đọc lại từ raw_records |
| Truncate title | Sửa Title thành BROKEN | 3 | FAIL Title length | Giảm Hit Rate | Đọc lại từ raw_records |
| Inject noise | Chèn rác | 3 | PASS (Không check) | Suy giảm F1 | Đọc lại từ raw_records |
| Stale date | Lùi 365 ngày | 10 | FAIL Freshness | Freshness báo lỗi STALE | Đọc lại từ raw_records |

Cách repair đảm bảo khôi phục từ nguồn đáng tin cậy bằng cách bypass hoàn toàn API call, trỏ trực tiếp module ingestion vào file `data/raw/crossref_records.json`.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: |
| `retrieval_hit_rate`   |      1.0 |       0.8 |      1.0 |                      -0.2 |             100% | 
| `mean_token_f1`        |      1.0 |       0.696 |      1.0 |                      -0.304 |             100% | 
| Quality checks pass/fail |      PASS |       FAIL |      PASS |                      FAIL |             PASS | 
| Freshness status         |      FRESH |       STALE |      FRESH |                      STALE |             FRESH | 

Kết luận:
1. Lỗi truncate_title -> Vi phạm Quality Checks -> Suy giảm mạnh Retrieval Hit Rate (vì ghim tài liệu không còn khớp regex).
2. Xử lý Idempotent Repair -> Đưa Quality/Freshness hồi phục 100% -> Khôi phục Agent Metric (Hit Rate và F1) về mốc 1.0 ban đầu.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Pipeline bị vỡ `ModuleNotFoundError: No module named 'pandas'` khi chạy ở thư mục ngoài.
- **Nguyên nhân:** Thư mục `src` không nằm trong PATH môi trường.
- **Cách xử lý:** Nhóm đã tự chèn `sys.path.append('src')` vào các file `run_*.py` trong thư mục script.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Judge Heuristic          | Điểm số đánh giá tự động chưa phản ánh đúng năng lực sinh ngôn ngữ tự nhiên. | Thay thế bằng mô hình GenAI với prompt chấm thi (LLM-as-a-judge). |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
