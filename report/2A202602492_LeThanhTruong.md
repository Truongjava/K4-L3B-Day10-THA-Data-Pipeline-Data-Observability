# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Họ và tên       | Lê Thanh Trường                                                                                                                                                |
| MSSV               | 2A202602492                                                                                                                                                       |
| Khóa/Lớp         | K4                                                                                                                                                                |
| Tên nhóm         | THA                                                                                                                                                               |
| Vai trò chính    | Data Cleaning & Data Observability                                                                                                                                |
| Repository         | [github.com/Truongjava/K4-L3B-Day10-Data-Pipeline-Data-Observability.git](https://github.com/Truongjava/K4-L3B-Day10-Data-Pipeline-Data-Observability.git) |
| Ngày hoàn thành | 2026-09-26                                                                                                                                                        |

## 2. Vai trò và phạm vi công việc

Phạm vi phụ trách: **CP0, CP1, CP2** — từ dữ liệu thô Crossref đến vector index và bộ benchmark.

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| CP0 — Raw ingestion | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref REST API / snapshot `data/raw/crossref_response.json` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 bản ghi) | Hoàn thành |
| CP1 — Cleaning & data modeling | `src/ingestion/cleaning.py`: `build_clean_dataframe` | `list[PaperRecord]` + `run_date` | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` (24 dòng) | Hoàn thành |
| CP1 — Data observability | `src/observability/quality.py`: `run_data_quality_checks`, `build_freshness_report` | cleaned dataframe + `Settings` | `data/quality/*_quality_report.json`, `data/quality/gx/*_gx_result.json`, `data/quality/freshness_report.json` | Hoàn thành |
| CP2 — Evaluation set | `src/evaluation/testset.py`: `build_test_set` | cleaned dataframe | `data/eval/test_set.json` (10 câu hỏi) | Hoàn thành |
| CP2 — Vector index | Gọi `LocalEmbeddingIndex.build` (module `src/retrieval/` đã có sẵn) | cleaned dataframe | ChromaDB collection `papers-baseline` (24 docs) + `data/embeddings/papers_embeddings.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                  | Thành viên/module được hỗ trợ | Kết quả                    |
| ----------------------------- | ------------------------------------ | ---------------------------- |
| Thiết lập môi trường `uv sync` + tạo `.env` từ `.env.example` | Cả nhóm | `uv sync` exit code 0, `.venv` có 325 package; `.env` đã được `.gitignore` chặn |
| Xác minh ghép nối CP2 ↔ CP3 | CP3 (pipeline integrator) | Phát hiện bộ test set phải khớp cách diễn đạt mà `retrieval/qa.py::_extract_answer` nhận diện, nếu không `mean_token_f1` sẽ sụp dù retrieval đúng |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh  |
| --------------------------- | ----------------------------- | ------------------------- | ---------------- |
| Parse payload Crossref, bóc thẻ JATS XML, xử lý 2 dạng ngày, retry 429/5xx, fallback snapshot offline | `src/ingestion/crossref.py` | `data/raw/crossref_records.json` — 24 bản ghi | So từng trường với artifact tham chiếu: **khớp 24/24** |
| Làm sạch, tính `age_days`, sinh `text_for_embedding` 5 phần, khử trùng lặp theo `paper_id` | `src/ingestion/cleaning.py` | `data/clean/papers_clean.json` — 24 dòng, `paper_id` unique | `build_clean_dataframe` trả 24 dòng; `age_days` trong khoảng 66–182 |
| Data Quality Gate theo GX 1.x với 7 expectation | `src/observability/quality.py` | `data/quality/test_quality_report.json` — `success: true` | `gx_version: 1.18.0`, 7/7 check PASS |
| Freshness SLA (ngưỡng 180 ngày, tỷ lệ quá hạn tối đa 25%) | `src/observability/quality.py` | `data/quality/freshness_report.json` | `stale_rows: 1 / 24`, `stale_ratio: 0.0417`, `is_fresh: true` |
| Sinh bộ benchmark 10 câu hỏi qua 4 nhóm nghiệp vụ | `src/evaluation/testset.py` | `data/eval/test_set.json` | 10 câu: 3 `summary`, 3 `authors`, 2 `date`, 2 `categories` |
| Index 24 tài liệu vào ChromaDB, embedding `all-MiniLM-L6-v2`, cosine | `data/chroma/` | Collection `papers-baseline` | `collection.count() == 24` |

**Output cụ thể mà phần việc của tôi tạo ra:** `data/quality/test_quality_report.json` — bằng chứng Data Quality Gate hoạt động đúng ở cả hai chiều. Ở chiều "sạch", cả 7 expectation PASS. Ở chiều "bẩn", tôi dựng một probe mô phỏng 4 dạng lỗi (cắt 5 dòng mới nhất, xoá rỗng 3 summary, cắt cụt 3 tiêu đề, nhân bản 4 dòng) và gate trả `success: false`, bắt đúng 4 lỗi ở 3 nhóm expectation khác nhau. Nếu gate chỉ luôn-xanh thì nó vô nghĩa, nên đây là kiểm chứng bắt buộc.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Biến 24 payload thô từ Crossref thành một corpus sạch, có kiểm dịch chất lượng tự động, và một bộ benchmark đo được chất lượng retrieval — sao cho mọi bước sau (index, đánh giá, corruption, repair) đều dựa được trên cùng một contract dữ liệu ổn định.

### Cách triển khai

**Ingestion (`crossref.py`)**
- Abstract của Crossref bọc trong thẻ JATS XML (`<jats:p>...</jats:p>`). Tôi bóc thẻ bằng `re.sub(r"<[^>]+>", " ", value)` rồi gom khoảng trắng thừa. Không bóc thì vector embedding sẽ học cả nhiễu markup.
- Crossref trả ngày ở hai dạng khác nhau: `published` là `{"date-parts": [[2026, 5, 20]]}` còn `created` là `{"date-time": "..."}`. Hàm `_format_date` xử lý cả hai, mặc định ngày/tháng thiếu là 1.
- **Giữ nguyên thứ tự `message.items`**, không sắp xếp — để `crossref_response.json` và `crossref_records.json` phản ánh đúng thứ tự API trả về, bảo toàn data lineage.
- Retry 3 lần với backoff cho các mã 429/5xx; nếu vẫn thất bại thì fallback đọc snapshot `data/raw/crossref_response.json` đã lưu. Mặc định (`REFRESH_SOURCE` không bật) đọc thẳng snapshot để kết quả chạy lại ổn định, không phụ thuộc mạng.

**Cleaning (`cleaning.py`)**
- `text_for_embedding` gồm 5 phần có nhãn, ghép bằng `\n`: `Title: / Authors: / Categories: / Published: / Abstract:`. Có nhãn giúp mô hình phân biệt được đâu là tiêu đề, đâu là tác giả thay vì trộn thành một khối văn bản.
- `age_days = (run_date - published).days` — mốc thời gian được truyền vào từ pipeline chứ không gọi `now()` bên trong hàm, nhờ vậy cùng một `run_date` sẽ cho ra kết quả tái lập được.
- Bỏ record thiếu `paper_id`/`title`/`summary`, tiêu đề dưới 8 ký tự, summary dưới 40 ký tự, hoặc không đọc được ngày. Ngưỡng đặt thấp hơn nhiều so với dữ liệu thật (tiêu đề ngắn nhất 55 ký tự, summary ngắn nhất 193 ký tự) nên baseline không mất dòng nào nhưng vẫn chặn được dữ liệu rác.
- Khử trùng lặp theo `paper_id` sau khi sắp xếp mới nhất trước, nên bản được giữ là bản mới nhất.

**Data observability (`quality.py`)**
- Dựng GX 1.x ephemeral context theo đúng cú pháp 1.x: `gx.get_context(mode="ephemeral")` → `add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `get_batch(batch_parameters=...)`, rồi `batch.validate(expectation)` cho từng expectation.
- 7 expectation phủ đủ 4 nhóm thiết yếu: `ExpectTableRowCountToBeBetween`, `ExpectColumnValuesToNotBeNull` (paper_id, title, summary), `ExpectColumnValuesToBeUnique` (paper_id), `ExpectColumnValueLengthsToBeBetween` (title, summary).
- Freshness SLA: `is_fresh = (số dòng có age_days > 180) / tổng số dòng <= 0.25`.
- Hàm `_json_safe` chuẩn hoá giá trị GX trả về trước khi ghi report: quy `NaN`/`inf` về `null` — vì `json.dumps` xuất chúng thành `NaN`/`Infinity`, không phải JSON hợp lệ — và chuyển mọi kiểu không phải built-in thành chuỗi. GX 1.18 hiện trả về kiểu Python built-in nên lớp này chưa phải xử lý trường hợp nào trong thực tế; nó là lớp bảo vệ hợp đồng JSON của report ở ranh giới serialize, không phải bản sửa cho một lỗi đã gặp.

**Evaluation set (`testset.py`)**
- Chọn 10 bài trải đều trên corpus bằng công thức nội suy tuyến tính theo chỉ số (`round(i * (n-1) / 9)`), không dùng random — cùng dữ liệu luôn cho cùng bộ câu hỏi.
- Xoay vòng 4 nhóm câu hỏi theo `index % 4` để phủ đủ `summary`, `authors`, `date`, `categories`.
- Mỗi câu hỏi **bắt buộc chứa tiêu đề bài báo trong cặp nháy đơn `'...'`**. Đây là ràng buộc then chốt: `retrieval/qa.py` dùng `re.search(r"'([^']+)'", question)` để tra khớp tiêu đề chính xác và ghim tài liệu đúng lên hạng 1. Đồng thời câu hỏi phải dùng đúng cách diễn đạt mà `_extract_answer` nhận diện (`who authored`, `when was`, `what categories`), nếu không câu trả lời sẽ rơi về mặc định là câu đầu của summary.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | JSON payload Crossref (`message.items`) hoặc snapshot records; cleaned dataframe cho các bước sau |
| Output                         | `list[PaperRecord]` (11 trường); dataframe 16 cột; JSON quality/freshness report; JSON test set |
| Module phụ thuộc             | `core/config.py` (Settings, Paths), `core/utils.py` (normalize_whitespace, compact_join, first_sentence, read/write helpers) |
| Module sử dụng output        | `retrieval/index.py` (đọc `text_for_embedding` + metadata), `evaluation/metrics.py` (đọc test set), `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Mất mạng / HTTP 429 / 503 khi gọi Crossref; abstract rỗng; DOI trùng; ngày thiếu tháng hoặc thiếu ngày; tiêu đề chứa ký tự phá vỡ regex trích tiêu đề |

### Cách xác minh

```bash
# CP0
uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
uv run python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"

# CP1
uv run python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
uv run python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"

# CP2
uv run python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

- **Kết quả mong đợi:** `Môi trường sẵn sàng`; `Đã tải 24 bài báo`; `Clean thành công 24 dòng`; `Quality check status = True`; `Sinh được 10 câu hỏi test`.
- **Kết quả thực tế:** Đúng cả 5 tín hiệu, không sai lệch. Riêng `parse_crossref_payload` được kiểm tra thêm: parse `crossref_response.json` rồi so từng trường với `crossref_records.json` — khớp **24/24 bản ghi**.
- **Artifact/log:** `data/raw/`, `data/clean/`, `data/quality/`, `data/eval/`, `data/chroma/`, `data/embeddings/`.

**Kiểm chứng bổ sung — gate phải biết báo động:** dựng dataframe bẩn (cắt 5 dòng mới nhất → 23 dòng, xoá rỗng 3 summary, cắt cụt 3 tiêu đề còn 3 ký tự, nhân bản 4 dòng) rồi chạy lại gate:

```
rows: 23 | expected: 24
success: False
failed_checks: ['ExpectTableRowCountToBeBetween', 'ExpectColumnValuesToBeUnique',
                'ExpectColumnValueLengthsToBeBetween', 'ExpectColumnValueLengthsToBeBetween']
```

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `ExpectTableRowCountToBeBetween` cần một ngưỡng dưới. Kịch bản corruption "drop latest records" làm mất ~20% bản ghi, và đây là dạng lỗi mà chỉ kiểm tra số dòng mới bắt được — các expectation còn lại (not-null, unique, length) đều không phản ứng với việc mất dòng. Vậy lấy mốc nào làm ngưỡng?

- **Các phương án đã cân nhắc:**
  1. **Hard-code `min_value=24`** — đúng với dữ liệu hiện tại nhưng vỡ ngay nếu Crossref trả về số bản ghi khác. Crossref là nguồn sống, và môi trường có thể được chạy lại với `REFRESH_SOURCE=1`.
  2. **`min_value=1`** — chỉ là guard chống bảng rỗng. An toàn nhưng **không bắt được corruption**, vì 23 dòng vẫn lớn hơn 1. Gate sẽ luôn xanh và trở thành vô nghĩa.
  3. **Đọc số dòng từ `data/raw/crossref_records.json` làm mốc** — so dữ liệu hiện tại với nguồn raw tin cậy chưa bị biến đổi.

- **Phương án đã chọn:** Phương án 3, có fallback về `settings.max_results` nếu file raw chưa tồn tại.

- **Lý do:** Đây là lựa chọn duy nhất vừa **thích ứng** với số bản ghi thực tế của nguồn, vừa **vẫn phát hiện được** việc mất dòng. Phương án 1 đánh đổi khả năng tái lập lấy sự đơn giản; phương án 2 đánh đổi toàn bộ giá trị của gate. Mốc lấy từ raw records là hợp lý về mặt khái niệm vì raw snapshot chính là nguồn tin cậy mà bước repair sẽ quay về — quality gate so với đúng cái nguồn đó.

- **Bằng chứng quyết định phù hợp:** Baseline 24 dòng → `ExpectTableRowCountToBeBetween` PASS. Probe corruption 23 dòng → cùng expectation đó FAIL (`observed_value: 23`, ngưỡng 24). Nếu chọn phương án 2, probe này sẽ cho `success: true` và toàn bộ kịch bản drop-record sẽ lọt qua gate.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Không phải lỗi runtime mà là **lỗi kết quả truy hồi**. Khi probe index vừa build, câu hỏi về bài *"Synthetic Corruption Testing: Stress-Testing Vector Search Robustness"* trả về **tài liệu sai ở hạng 1**: `10.1145/3637528.3671819` — *"Advanced Perspectives on Synthetic Corruption Testing: ..."* — với score 0.6494, còn tài liệu đúng `10.1145/3637528.3671807` chỉ đứng hạng 2 với score 0.6035.

- **Lệnh hoặc bước tái hiện:**
  ```bash
  uv run python -c "... idx = LocalEmbeddingIndex.load(s, s.paths.embeddings_json);
      hits = idx.search(q['question']); in ra top-3 kèm paper_id, title, score ..."
  ```

- **Nguyên nhân gốc:** `text_for_embedding` đặt Title ở dòng đầu, và corpus chứa nhiều cặp tiêu đề gần trùng — cùng một tiêu đề gốc nhưng một bản có tiền tố *"Advanced Perspectives on ..."*. Hai tiêu đề gần trùng chia sẻ gần như toàn bộ token, nên cosine similarity **giữa chúng** cao hơn similarity giữa câu hỏi và tài liệu đúng. Vector search không phân biệt được đâu là bài gốc, đâu là bài mở rộng cùng tên.

- **Cách xử lý:** Ràng buộc mọi câu hỏi trong `build_test_set` phải chứa **tiêu đề đầy đủ trong cặp nháy đơn**. `retrieval/qa.py` dùng `re.search(r"'([^']+)'", question)` để tách tiêu đề, gọi `index.lookup()` tra khớp chính xác, rồi chèn kết quả đó lên hạng 1 trước khi cắt top-k. Bước này biến một phép so khớp mờ thành so khớp chính xác.

  *Ghi chú trung thực về trình tự:* tôi đã lường trước ràng buộc này khi đọc `qa.py` và đặt nó ngay từ đầu, chưa phải sửa lại sau khi hỏng. Probe index ở trên là bước **xác nhận** rằng nếu thiếu ràng buộc đó thì retrieval sẽ thật sự sai — chứ không phải một lỗi tôi gặp rồi mới khắc phục.

- **Cách xác minh sau khi sửa:** Kiểm tra chéo từng câu hỏi: regex trích được tiêu đề và tiêu đề đó tồn tại nguyên vẹn trong corpus → 10/10 câu hợp lệ; đồng thời nhánh `_extract_answer` mà câu hỏi kích hoạt phải khớp với `question_type` khai báo → 10/10 khớp. Chạy evaluation thật trên index: `retrieval_hit_rate = 1.0`, `mean_token_f1 = 1.0`.

- **Điều học được:** Retrieval trong bài lab này **không thuần semantic** — nó là semantic search cộng một bước exact-match ghim kết quả lên đầu. Hiểu nhầm chỗ này sẽ dẫn tới thiết kế test set sai và metric sụp mà không rõ nguyên nhân. Điều này cũng giải thích trước được vì sao kịch bản corruption "truncate title" sẽ tác động mạnh: nó phá đúng bước exact-match đó, đẩy câu hỏi rơi về semantic search thuần và rơi vào chính cái bẫy tiêu đề gần trùng ở trên.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Payload Crossref được parse thành `PaperRecord` (bóc thẻ JATS, xử lý ngày, lọc bản ghi lỗi), lưu lại hai artifact thô để bảo toàn lineage. Từ `PaperRecord`, `build_clean_dataframe` tính `age_days`, ghép `text_for_embedding` 5 phần, khử trùng lặp theo `paper_id`. `LocalEmbeddingIndex.build` biến mỗi dòng thành một document với `record_id = paper_id::index`, sinh vector bằng `all-MiniLM-L6-v2` đã chuẩn hoá, rồi nạp vào ChromaDB với metric cosine. Metadata (title, authors, published, categories, summary, URLs) được lưu kèm để tầng trả lời không cần đọc lại dataframe.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Mỗi câu hỏi mang `ground_truth_doc_ids` — danh sách `paper_id` được coi là nguồn đúng. `evaluate_pipeline` chạy `answer_question` cho từng câu, lấy về `retrieved_doc_ids`, rồi tính `retrieval_hit = any(doc_id in ground_truth_doc_ids for doc_id in retrieved_doc_ids)`. Đây là chỉ số đo **tầng truy hồi**. Chỉ số đo **tầng trả lời** là `token_f1` giữa câu trả lời sinh ra và `ground_truth`, cộng thêm judge chấm điểm 1–5. Hai tầng tách biệt nên khi corruption xảy ra, ta phân biệt được lỗi do không tìm thấy tài liệu hay do tìm thấy mà trả lời sai.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks kiểm tra **cấu trúc và tính toàn vẹn** của tập dữ liệu tại một thời điểm: đủ số dòng không, khoá chính có null/trùng không, độ dài trường có nằm trong khoảng hợp lệ không. Freshness đo một chiều **thời gian**: tỷ lệ bản ghi có `age_days` vượt ngưỡng 180 ngày. Một tập dữ liệu có thể hoàn toàn hợp lệ về cấu trúc nhưng vẫn quá cũ, và ngược lại — nên hai loại tín hiệu này bổ sung chứ không thay thế nhau. Trong code, cả hai đều nằm trong `quality.py` nhưng freshness trả về payload riêng với cờ `is_fresh`, không gộp vào `success` của GX.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Vì mọi phép so sánh chỉ có nghĩa khi biến số được giữ cố định. Nếu mỗi trạng thái dùng một bộ câu hỏi khác nhau, chênh lệch metric có thể đến từ độ khó của câu hỏi chứ không phải từ chất lượng dữ liệu — ta không quy được nhân quả. `data/eval/test_set.json` được sinh một lần ở CP2, và `build_test_set` chỉ chạy lại khi bật `REFRESH_TEST_SET`; cờ mặc định tắt chính là để bảo vệ ràng buộc này.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Dựa trên ba tầng bằng chứng phải khớp nhau. Thứ nhất, **tầng dữ liệu**: `data/clean/papers_clean_repaired.json` phải trùng khớp với `papers_clean.json` của baseline — vì repair tái dẫn xuất từ chính `data/raw/crossref_records.json` bằng cùng một `run_date`, nên kết quả phải giống hệt, không phải "gần giống". Thứ hai, **tầng tín hiệu**: quality gate phải từ `success: false` quay về `true` và freshness về lại `is_fresh: true`. Thứ ba, **tầng metric**: `retrieval_hit_rate` và `mean_token_f1` phải trở về mức baseline. Nếu dữ liệu đã khôi phục đúng mà metric không hồi phục thì vấn đề nằm ở tầng index/agent, không phải ở dữ liệu — đó cũng là một kết luận có giá trị.
   *Lưu ý trung thực:* CP5 (repair) chưa được triển khai tại thời điểm tôi viết báo cáo này, nên phần trên là tiêu chí nghiệm thu mà nhóm đã thống nhất, chưa phải kết quả đã đo.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 | *(chưa có)* | *(chưa có)* | 10/10 câu truy hồi đúng tài liệu. Baseline đạt trần vì mỗi câu hỏi chứa tiêu đề khớp chính xác nên được ghim lên hạng 1 |
| `mean_token_f1`      |     1.00 | *(chưa có)* | *(chưa có)* | Câu trả lời trùng khớp ground truth. Đây là trần lý thuyết, không phải chỉ số còn dư địa cải thiện |
| `judge_accuracy`     |     1.00 | *(chưa có)* | *(chưa có)* | **Chưa có API key LLM** — con số này đến từ nhánh fallback heuristic trong `metrics.py`, không phải judge thật. Xem giải thích bên dưới |
| `mean_judge_score`   |        5 | *(chưa có)* | *(chưa có)* | Cùng lý do trên; thang điểm 1–5 nên 5 là trần |
| Quality checks         |   7/7 PASS | *(chưa có)* | *(chưa có)* | GX 1.18.0; probe corruption cho thấy gate bắt đúng 4 lỗi |
| Freshness status       |  Fresh (4.17% quá hạn) | *(chưa có)* | *(chưa có)* | 1/24 bài cũ hơn 180 ngày; biên an toàn còn rộng so với ngưỡng 25% |

**Giải thích về `judge_accuracy`:** baseline được đo khi nhóm chưa cấu hình `GOOGLE_API_KEY`. `_judge_answer` trong `metrics.py` có nhánh `except` quy về heuristic dựa trên `token_f1` (`>= 0.95` → điểm 5). Vì `token_f1` bằng 1.00 nên judge cho điểm tối đa. **Con số 1.00 này không chứng minh chất lượng câu trả lời là hoàn hảo** — nó chỉ phản ánh rằng dữ liệu sạch và câu hỏi khớp ground truth. Khi nhóm cấu hình LLM provider thật, chỉ số này cần được đo lại và có khả năng sẽ thấp hơn.

Bốn chỉ số của cột Corrupted và Repaired để trống vì CP4 và CP5 chưa được triển khai tại thời điểm viết báo cáo. Tôi không điền số ước lượng vào đây.

### Kết luận từ số liệu

Hai chuỗi nhân quả dưới đây **chưa hoàn thành được** vì chưa có số liệu corrupted/repaired. Thay vào đó tôi nêu cơ chế đã kiểm chứng được ở tầng retrieval — đây là phần tôi có bằng chứng thật:

1. **[Cơ chế đã kiểm chứng, chưa có số đo]** `retrieval_hit` phụ thuộc vào `index.lookup` tra khớp tiêu đề chính xác, không phải vào semantic search. Bằng chứng: với câu `q02`, tài liệu đúng `10.1145/3637528.3671807` chỉ đứng **hạng 2** (score 0.6035), còn tài liệu gần trùng tiêu đề `10.1145/3637528.3671819` đứng hạng 1 (score 0.6494). Câu trả lời vẫn đúng hoàn toàn là nhờ bước lookup ghim tài liệu khớp tiêu đề lên đầu. **Suy ra:** kịch bản corruption "truncate title" sẽ phá vỡ chính bước lookup này, khiến câu hỏi rơi về semantic search thuần và rơi vào đúng cái bẫy gần-trùng-tiêu-đề ở trên. Đây là dự đoán có cơ sở, cần CP4 đo lại để xác nhận.

2. **[Chưa đo được]** Chuỗi repair → tín hiệu phục hồi → metric phục hồi chưa có số liệu vì CP5 chưa chạy.

**Corruption nào ảnh hưởng rõ nhất và vì sao?**
Chưa có số liệu để trả lời dứt khoát. Dự đoán dựa trên cơ chế ở trên: **truncate title** sẽ ảnh hưởng mạnh nhất tới `retrieval_hit_rate` vì nó phá trực tiếp bước lookup — mà lookup là thứ duy nhất giữ cho hit rate ở mức 1.00. Các dạng còn lại tác động gián tiếp hơn: "duplicate rows" và "drop latest" bị quality gate chặn nhưng chỉ ảnh hưởng metric khi tài liệu của câu hỏi bị nhắm trúng; "inject noise" không vi phạm expectation nào nên sẽ lọt qua gate và chỉ lộ ra ở tầng metric.

**Kết quả nào khác với kỳ vọng ban đầu?**
Điểm bất ngờ là **semantic search xếp sai thứ tự** trên corpus này. Tôi kỳ vọng vector search sẽ đưa tài liệu đúng lên đầu, nhưng thực tế nó bị đánh lừa bởi các cặp tiêu đề gần trùng. Đã kiểm tra bằng cách in top-3 kết quả kèm score cho nhiều câu hỏi khác nhau và thấy hiện tượng lặp lại. Giả thuyết: `text_for_embedding` đặt Title ở đầu và các tiêu đề này chia sẻ gần như toàn bộ token, nên cosine similarity giữa chúng cao hơn giữa câu hỏi và tài liệu đúng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Data lineage không chỉ là lưu file thô, mà là lưu **đúng thứ tự và đúng định dạng** của nguồn. `crossref_records.json` giữ nguyên thứ tự `message.items` của API; nếu tôi sắp xếp lại trong bước parse cho "đẹp", artifact thô sẽ lệch khỏi nguồn và mọi so sánh về sau mất tính đối chiếu. Việc sắp xếp là của tầng cleaning, không phải tầng ingestion.

   Bài học kèm theo, cũng thuộc tầng pipeline: **đừng viết code phòng thủ dựa trên giả định về hành vi thư viện mà chưa kiểm chứng.** Tôi từng thêm một lớp ép kiểu `astype(object)` cho hai cột số trong `build_clean_dataframe` với lý do "pandas trả `numpy.int64` nên `json.dumps` sẽ vỡ". Khi kiểm tra thật trên pandas 3.0.3 thì `to_dict(orient="records")` trả Python `int` và `json.dumps` chạy bình thường — lớp ép kiểu đó là thừa, lại còn làm hai cột mất kiểu `int64`. Tôi đã gỡ bỏ và chạy lại toàn bộ nghiệm thu để xác nhận không có gì vỡ.

2. **Về data quality/observability:** Một quality gate chỉ có giá trị nếu nó **có thể thất bại**. Việc viết expectation rất dễ — việc chọn ngưỡng sao cho gate vừa không báo động giả ở dữ liệu sạch, vừa bắt được dữ liệu bẩn mới là phần khó. Ngưỡng `min_value=1` cho row count là ví dụ của một gate trông rất hợp lý nhưng thực chất không bắt được gì. Tôi chỉ phát hiện ra điều này khi chủ động dựng probe corruption và kiểm tra rằng gate thực sự đỏ.

3. **Về ảnh hưởng của data đến RAG agent:** Chất lượng dữ liệu ảnh hưởng đến RAG qua **nhiều đường khác nhau và không đồng đều**. Cùng một mức độ "bẩn" nhưng tác động rất khác nhau tuỳ trường bị bẩn và tuỳ tầng nào đang dùng trường đó. Dữ liệu ở đây còn cho thấy một trường hợp đáng chú ý: một số dạng lỗi bị quality gate chặn (mất dòng, trùng khoá, tiêu đề cụt) nhưng một số khác lọt qua hoàn toàn (chèn nhiễu vào summary) — đó chính là hiện tượng **silent failure** mà bài lab nhắm tới.

### Nếu có thêm thời gian

Bổ sung một expectation phát hiện nhiễu văn bản trong `summary` — ví dụ `ExpectColumnValuesToMatchRegex` với mẫu ký tự hợp lệ, hoặc một custom expectation đo tỷ lệ ký tự phi chữ cái. Lý do: hiện tại kịch bản "inject noise" là dạng corruption duy nhất không vi phạm expectation nào, nên nó đi thẳng vào vector index mà không có cảnh báo. Cách đo cải thiện: chạy probe corruption có chèn nhiễu, kỳ vọng gate chuyển từ `success: true` sang `false`, đồng thời `retrieval_hit_rate` trên dữ liệu đó không đổi — chứng minh gate bắt được lỗi mà metric retrieval bỏ sót.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lê Thanh Trường
**Ngày xác nhận:** 2026-09-26