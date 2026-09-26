# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Họ và tên       | Nguyễn Quang Huy                                                                                                                                                |
| MSSV               | 2A202602461                                                                                                                                                       |
| Khóa/Lớp         | K4/H201                                                                                                                                                                |
| Tên nhóm         | THA                                                                                                                                                               |
| Vai trò chính    | Idempotent Repair & Observability Reporting (CP5, CP6)                                                                                                                                |
| Repository         | [github.com/Truongjava/K4-L3B-Day10-THA-Data-Pipeline-Data-Observability.git](https://github.com/Truongjava/K4-L3B-Day10-THA-Data-Pipeline-Data-Observability.git) |
| Ngày hoàn thành | 2026-09-26                                                                                                                                                        |

## 2. Vai trò và phạm vi công việc

Phạm vi phụ trách: **CP5, CP6** — Phục hồi dữ liệu (Idempotent Repair) và Báo cáo đối chiếu 3 trạng thái.

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| CP5 — Idempotent Repair | `src/pipelines/corruption_flow.py` | `data/raw/crossref_records.json` | `data/clean/papers_clean_repaired.csv`, JSON, index | Hoàn thành |
| CP5 — Reporting | `src/observability/reporting.py`: `generate_corruption_report` | Các JSON metrics, quality | `data/reports/corruption_report.md` | Hoàn thành |

## 3. Kết quả theo vai trò

- **Idempotent Repair**: Đã tự động hóa quá trình đọc lại dữ liệu raw và chạy toàn bộ quy trình làm sạch để xuất ra dữ liệu Repaired sạch sẽ.
- **Reporting**: Đã xây dựng script tự động render báo cáo đối chiếu giữa 3 trạng thái (Baseline, Corrupted, Repaired).

## 4. Giải thích phần kỹ thuật đã thực hiện

**Idempotent Repair:** 
Tôi đọc lại `crossref_records.json` thay vì gọi lại API để đảm bảo luồng repair luôn nhất quán và không sinh ra hiệu ứng phụ. Việc sử dụng raw layer như một "single source of truth" đã chứng minh sức mạnh của Data Lake architecture.

**Reporting:**
Hàm `generate_corruption_report` tổng hợp nhiều file `.json` riêng lẻ thành một markdown report duy nhất với format bảng, giúp người đọc dễ dàng thấy sự phục hồi từ mức 0.800 (Corrupted) trở lại mức 1.000 (Repaired) của chỉ số Retrieval Hit Rate.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi thực thi repair, cần quyết định gọi lại API (refresh) hay dùng local cache.
- **Quyết định:** Tôi quyết định tái tạo dữ liệu từ snapshot local `raw_records.json` đã lưu. 
- **Lý do:** Điều này giúp đảm bảo nguyên tắc Idempotent: chạy bao nhiêu lần cũng cho ra đúng kết quả đó, không bị phụ thuộc vào tính khả dụng của API Crossref ở thời điểm repair.

## 6. Một lỗi hoặc blocker đã xử lý

- Lỗi đường dẫn tương đối (sys.path) khi chạy script `run_corruption_flow.py` từ ngoài thư mục `src`.
- Cách xử lý: Đã thêm code logic chèn thư mục `src` vào `sys.path` tự động ở đầu script. Từ đó script có thể chạy dễ dàng hơn ở bất cứ đâu.

## 7. Hiểu biết về luồng end-to-end
(Đã nắm chắc theo như mô tả ở các CP trước).

## 8. Phân tích kết quả
| Metric/signal          | Baseline | Corrupted | Repaired |
| ---------------------- | -------: | --------: | -------: |
| `retrieval_hit_rate` |     1.000 | 0.800 | 1.000 |
| `mean_token_f1`      |     1.000 | 0.696 | 1.000 |
| Quality checks         |   PASS | FAIL | PASS |
| Freshness status       |  FRESH | STALE | FRESH |

Dữ liệu cho thấy repair đã kéo lại toàn bộ metrics bị tụt giảm.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.

**Họ và tên:** Nguyễn Quang Huy
**Ngày xác nhận:** 2026-09-26