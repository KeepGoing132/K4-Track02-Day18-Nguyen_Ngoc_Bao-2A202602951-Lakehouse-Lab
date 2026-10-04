# Architecture Brief: LLM Observability Lakehouse at 1B Requests/Day Scale

- **Tác giả:** Nguyễn Ngọc Bảo (MSSV: 2A202602951)
- **Mã bài lab:** `K4-Track02-Day18`
- **Topic lựa chọn:** **Topic A — LLM Observability ở quy mô 1B requests/ngày**
- **Vai trò:** Lead Lakehouse Architect (Design Review Defense)

---

## 1. Problem Statement

Hệ thống phục vụ foundation-model API ghi nhận **1.000.000.000 (1 tỷ) requests/ngày** (~11.574 req/giây trung bình, đỉnh điểm 30.000 req/giây). Mỗi bản ghi payload (prompt, completion, metadata, token usage, latency) có kích thước trung bình **~5 KB**, sinh ra **5 TB raw data mỗi ngày** (150 TB/tháng raw uncompressed). 

**Các ràng buộc cốt lõi:**
1. **Real-time Tenant Observability:** Dashboard chi phí, lỗi và latency phân tích theo từng `tenant_id` phải làm mới tối đa mỗi **5 phút**; độ trễ truy vấn p95 < 2 giây.
2. **Lifecycle & Retention:** Dữ liệu chi tiết (full prompt/response) chỉ được lưu trữ trong **7 ngày** phục vụ incident triage / debugging, sau đó phải tự động chuyển sang lưu dạng aggregates (Gold rollups) trong vòng **1 năm**.
3. **Data Privacy & Compliance:** Mọi thông tin nhận dạng cá nhân (PII như email, số điện thoại, API keys) phải được **redact/tokenize ngay tại tầng Bronze** trước khi bất kỳ ai (analyst, dashboard, model auditor) có thể đọc.
4. **Hard FinOps Budget Cap:** Tổng chi phí lưu trữ hạ tầng cloud storage phải duy trì nghiêm ngặt **≤ $5.000/tháng**.

**Vì sao bài toán này khó?**
Ở quy mô 11.5K writes/giây, nếu ghi trực tiếp vào cloud object storage (S3), hệ thống sẽ gặp thảm họa **Small-File Problem** (1 tỷ file/ngày = $5.000/ngày chỉ riêng phí API S3 PUT/GET). Hơn nữa, lưu trữ 1.825 PB thô trong 1 năm trên S3 Standard sẽ tiêu tốn hơn **$41.000/tháng**, phá vỡ hoàn toàn ngân sách nếu không có chiến lược Medallion, micro-batch compaction, Z-order clustering và tiered lifecycle quyết liệt.

---

## 2. Architecture Diagram

Kiến trúc triển khai theo mô hình Medallion với Open Table Format (Delta Lake / Apache Iceberg), kết hợp streaming micro-batching và vòng đời lưu trữ tối ưu chi phí:

```
[Inference API Gateway (30K req/s peak)]
                   │
                   ▼  (Kafka / Redpanda: 100 partitions, 5-min retention)
         [Flink Streaming Workers]
                   │
       ┌───────────┴────────────────────────────────────────┐
       │ (1) Stream Tokenization / PII Redactor (Regex+NER) │
       │ (2) Asymmetric Vault KMS (Encrypted PII Map)       │
       │ (3) In-Memory Micro-batch Commit (1-minute window) │
       └───────────────────┬────────────────────────────────┘
                           ▼
 ═══════════════════════════════════════════════════════════════════════════
                      STORAGE LAYER (AWS S3 + Delta Lake)
 ═══════════════════════════════════════════════════════════════════════════
   ┌────────────────────────────────────────────────────────────────────┐
   │ BRONZE TABLE: raw_llm_events                                       │
   │  - Layout: Append-only, partitioned by [date, hour]                │
   │  - Payload: Zstandard-compressed Parquet (4:1 ratio -> 1.25 TB/day)│
   │  - Security: PII replaced with token IDs, raw payload in tombstone │
   │  - Lifecycle: AWS S3 Lifecycle Rule -> EXPIRE at Day 7             │
   └──────────────────────────────────┬─────────────────────────────────┘
                                      │ (Flink / Spark Streaming Engine:
                                      │  Deduplication by request_id,
                                      │  Schema Validation & Extraction)
                                      ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │ SILVER TABLE: llm_requests_cleaned                                 │
   │  - Layout: Partitioned by [date], Z-ORDER / Liquid Cluster on:     │
   │            (tenant_id, model, status)                              │
   │  - Features: Delta Change Data Feed (CDF), Deletion Vectors (DV)   │
   │  - Target File Size: 256 MB–512 MB (Async Compaction Cron 15 mins) │
   │  - Lifecycle: S3 Standard (Days 1–7) -> S3 Glacier Instant (Day 8) │
   │               -> EXPIRE at Day 30                                  │
   └──────────────────────────────────┬─────────────────────────────────┘
                                      │ (Continuous Micro-Aggregator:
                                      │  5-min tumbling windows)
                                      ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │ GOLD TABLE: tenant_observability_5min                              │
   │  - Layout: Partitioned by [year_month], Z-ORDER by [tenant_id]     │
   │  - Metrics: p50/p95/p99 latency, prompt/completion tokens, cost,   │
   │             error_rate grouped by (window_ts, tenant_id, model)    │
   │  - Volume: ~2.5 GB/ngày (giảm 99.95% so với raw)                  │
   │  - Lifecycle: S3 Standard (30 days) -> S3 Standard-IA (335 days)   │
   │               Total Retention: 365 Days                            │
   └──────────────────────────────────┬─────────────────────────────────┘
                                      │
 ═════════════════════════════════════╪═════════════════════════════════════
                         QUERY & CONSUMPTION LAYER
 ═════════════════════════════════════╪═════════════════════════════════════
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
        [Trino / StarRocks Engine]               [Jupyter / Ad-hoc]
      (Catalog Cache + Stats Pruning)          (Incident Investigation)
                   │                                     │
                   ▼                                     ▼
     [Tenant Dashboard (Grafana)]              [Deep Trace Inspection]
        - Refresh: Every 5 mins                  - Filter by tenant_id
        - Latency p95 < 500 ms                   - 90% File Pruning
```

---

## 3. Quyết Định Thiết Kế Chính & Các Alternatives Đã Loại

### Quyết định 1: Table Format — Chọn Delta Lake 1.x với Deletion Vectors & Liquid Clustering
* **Tôi chọn:** **Delta Lake (với Liquid Clustering / Z-Order trên `tenant_id`)** làm định dạng bảng nền tảng.
* **Tôi loại Apache Hive:** Vì Hive không hỗ trợ ACID transactions, dựa vào cấu trúc thư mục tĩnh để phân vùng. Nếu người dùng quên filter ngày (`WHERE dt=...`), engine sẽ thực hiện full-scan toàn bộ petabytes dữ liệu, gây nghẽn băng thông I/O và phát sinh chi phí hàng nghìn USD cho mỗi câu truy vấn bất cẩn. Hive cũng không hỗ trợ min/max statistics-based file pruning cho các cột không phải partition key.
* **Tôi loại Raw Parquet Files trên Object Storage:** Không có transaction log nguyên tử (`_delta_log`). Khi hàng chục writer stream liên tục, reader sẽ gặp lỗi đọc dở dang (dirty reads / missing partial files) và không thể thực hiện rollback hoặc time travel khi có sự cố dữ liệu.

### Quyết định 2: Ingestion & Compaction — Flink Streaming Ingest 1-phút kết hợp Asynchronous Compaction Cron
* **Tôi chọn:** Flink gom buffer trong bộ nhớ và ghi commit theo **micro-batch 1 phút** (~700.000 records/file ~100 MB), kết hợp với một job bảo trì định kỳ chạy ngầm (mỗi 15 phút) chạy `OPTIMIZE ... COMPACT` gộp thành các file chuẩn 256 MB – 512 MB.
* **Tôi loại Direct Ingestion per Request:** Ghi file ngay khi request kết thúc sẽ tạo ra 1 tỷ file/ngày. Riêng tiền gọi API `PUT` của S3 ($0.005/1.000 requests) đã tốn **$5.000/ngày ($150.000/tháng)** — vượt trần ngân sách gấp 30 lần chỉ vì request API.
* **Tôi loại Batch Ingestion 1 giờ (Hourly Batch):** Mặc dù tạo ra kích thước file lý tưởng ngay lập tức, cách này vi phạm nghiêm trọng ràng buộc vận hành (SLA làm mới dashboard tenant mỗi 5 phút).

### Quyết định 3: FinOps Storage Tiering — Multi-tier S3 Lifecycle với Hard Expiry
* **Tôi chọn:** Bronze & Silver lưu ở **S3 Standard trong 7 ngày đầu**, sau đó kích hoạt **AWS S3 Lifecycle Rule tự động xóa (EXPIRE) sau ngày thứ 7** (giữ lại Silver đến ngày 30 trên Glacier Instant Retrieval để backup audit). Bảng Gold tổng hợp (dung lượng nhỏ) chuyển sang S3 Standard-IA sau 30 ngày và giữ trọn 365 ngày.
* **Tôi loại S3 Standard cho toàn bộ dữ liệu trong 1 năm:** Lưu 5 TB/ngày × 365 ngày = 1.825 PB trên S3 Standard ($0.023/GB-tháng) tiêu tốn **$41.975/tháng**, phá sản mục tiêu FinOps $5K/tháng.
* **Tôi loại S3 Glacier Flexible Archive / Deep Archive cho full raw logs:** Mặc dù phí lưu trữ chỉ $0.0036/GB, nhưng phí transition ($0.05/1.000 objects) và thời gian chờ giải nén từ 3–5 giờ phá vỡ hoàn toàn khả năng ứng cứu sự cố (incident triage) đòi hỏi phản hồi trong 15 phút của đội ngũ on-call.

### Quyết định 4: PII Redaction Pattern — Stream-Time Tokenization tại Flink Ingestion
* **Tôi chọn:** Thực hiện nhận diện thực thể (NER/Regex) và **Tokenize/Mask PII ngay trên bộ nhớ của Flink worker** trước khi commit xuống Bronze. Giá trị PII thật được mã hóa bất đối xứng và lưu vào Secure Vault chuyên dụng tách biệt khỏi Lakehouse.
* **Tôi loại Batch PII Masking hàng ngày:** Để dữ liệu raw PII nằm trên Bronze trong 24 giờ vi phạm nghiêm trọng các quy chuẩn bảo mật (GDPR / Nghị định 13/2023/NĐ-CP); nếu nhân viên phân tích truy cập trong khoảng thời gian này, rủi ro rò rỉ dữ liệu là 100%.
* **Tôi loại Dynamic Data Masking (DDM) on query-time:** Che dấu PII lúc truy vấn gây tốn kém CPU vô ích cho mọi câu query lặp đi lặp lại của dashboard, làm chậm p95 latency và có nguy cơ bypass nếu analyst sử dụng direct file read qua DuckDB/PyArrow.

### Quyết định 5: Query Engine cho Dashboard 5 Phút — StarRocks / Trino với Iceberg/Delta Catalog Caching
* **Tôi chọn:** **StarRocks / Trino** kết hợp metadata caching ở tầng Catalog, truy vấn trực tiếp bảng Gold được Z-Order theo `tenant_id`.
* **Tôi loại Spark SQL cho Dashboard:** Khởi động JVM và Spark driver overhead mất 10–20 giây cho mỗi lượt query, không thể đáp ứng dashboard tương tác sub-second cho hàng nghìn tenants đồng thời.
* **Tôi loại Standalone External Database (PostgreSQL/ClickHouse sync song song):** Tái diễn Anti-Pattern "The Stale External Index". Việc duy trì một cụm RDBMS/ClickHouse riêng lẻ để chứa bản sao dữ liệu sẽ nhân đôi chi phí hạ tầng và phát sinh lỗi mất đồng bộ dữ liệu (skew).

---

## 4. Failure Modes (Kịch Bản 3 Giờ Sáng)

### Failure Mode 1: Compaction Job bị OOM/Crash khiến Small Files tích tụ làm sập Dashboard
* **Triệu chứng lúc 3h sáng:** Dashboard của khách hàng bị timeout (> 30s). Alert CloudWatch báo số lượng S3 GET request tăng đột biến gấp 50 lần; query engine bị nghẽn I/O do mở hàng chục nghìn file Parquet vài MB.
* **Cơ chế phát hiện:** Prometheus alert giám sát metric `delta.table.num_files` trên partition ngày hiện tại vượt quá ngưỡng an toàn (500 files/partition).
* **Kế hoạch Rollback & Khắc phục:**
  1. Tự động kích hoạt job compaction khẩn cấp với cấu hình phân bổ bộ nhớ cao hơn và giới hạn batch size (`dt.optimize.compact(target_size=256*1024*1024)`).
  2. Áp dụng thuật toán **Orphan Removal** đã học ở NB6: Chạy script so sánh tập hợp giữa danh sách file thực tế trên S3 và danh sách file trong transaction log `_delta_log` để dọn dẹp các file rác dở dang do writer bị crash để lại, ngăn chặn việc tính phí dung lượng vô hình.

### Failure Mode 2: Ingestion Payload Schema Mismatch làm ngắt quãng pipeline Silver
* **Triệu chứng lúc 3h sáng:** Khách hàng mới gửi metadata chứa trường dữ liệu lạ hoặc sai kiểu dữ liệu (ví dụ: `latency_ms` là string `"120ms"` thay vì integer), khiến job ghi vào Silver bị fail do **Schema Enforcement**.
* **Cơ chế phát hiện:** Flink taskmanager phát sinh exception, stream tự động định tuyến bản ghi lỗi sang Dead-Letter Queue (DLQ) S3 partition `quarantine/` và gửi alert PagerDuty.
* **Kế hoạch Rollback & Khắc phục:**
  1. Hệ thống tiếp tục xử lý các bản ghi hợp lệ bình thường; dashboard không bị gián đoạn toàn bộ mà chỉ thiếu các bản ghi lỗi.
  2. Nếu cần khôi phục bảng về trạng thái lành mạnh trước sự cố ghi lỗi, sử dụng ngay **Delta RESTORE** (khái niệm Day 18 NB3): `DeltaTable(silver_path).restore(safe_version)` trong < 30 giây mà không làm mất lịch sử commit kiểm toán.
  3. Sau khi xác nhận trường mới hợp lệ, kích hoạt an toàn **Schema Evolution** có chủ đích: `write_deltalake(..., schema_mode="merge")` để thêm cột mà không làm hỏng dữ liệu cũ.

### Failure Mode 3: Rò rỉ chi phí (Storage Budget Spike) do quên dọn Tombstone/Snapshots
* **Triệu chứng lúc 3h sáng:** CFO nhận cảnh báo chi phí AWS vọt lên $8.000/tháng dù dung lượng hữu ích của bảng không tăng.
* **Cơ chế phát hiện:** FinOps CloudWatch Budget Alarm kích hoạt khi dung lượng bucket vượt 30 TB.
* **Kế hoạch Rollback & Khắc phục:**
  1. Nguyên nhân do tính năng Time-Travel giữ lại toàn bộ các file đã bị compaction thay thế (tombstoned files) mà không có lịch dọn dẹp định kỳ.
  2. Thực thi **Job 3 (Snapshot Expiry & VACUUM)** của Day 18:
     - Chạy `dt.vacuum(retention_hours=168)` (giữ đúng 7 ngày cho time travel).
     - Đối với Iceberg: Chạy `expire_snapshots` kết hợp dọn dẹp các stranded manifest lists như đã đo lường trong NB6 để ép giải phóng dung lượng vật lý thực tế trên S3 ngay trong đêm.

---

## 5. Ước Tính Chi Phí Back-of-the-Envelope (Show the Math)

### A. Phân tích dung lượng dữ liệu (Data Math)
* **Khối lượng Raw Input:** $1.000.000.000 \text{ req/ngày} \times 5 \text{ KB} = 5.000.000 \text{ MB} = 5 \text{ TB/ngày}$.
* **Dung lượng sau nén Parquet Zstandard (tỉ lệ nén trung bình 4:1):**
  $$\text{Dung lượng nén} = \frac{5 \text{ TB}}{4} = 1.25 \text{ TB/ngày} \approx 37.5 \text{ TB/tháng}.$$
* **Lưu trữ Bronze (Retention 7 ngày trên S3 Standard):**
  $$\text{Dung lượng Bronze} = 1.25 \text{ TB/ngày} \times 7 \text{ ngày} = 8.75 \text{ TB}.$$
* **Lưu trữ Silver (Retention 7 ngày trên S3 Standard, trích xuất typed columns gọn gàng):**
  $$\text{Dung lượng Silver} = 1.0 \text{ TB/ngày} \times 7 \text{ ngày} = 7.0 \text{ TB}.$$
* **Lưu trữ Gold (Dữ liệu tổng hợp 5 phút × 365 ngày):**
  - Giả định $10.000$ active tenants $\times 3$ models $\times 288$ chu kỳ 5-phút/ngày = $8.640.000$ dòng rollup/ngày.
  - Dung lượng Parquet Gold nén: $\approx 2.5 \text{ GB/ngày} = 0.075 \text{ TB/tháng}$.
  - Tổng lưu trữ Gold 1 năm (365 ngày): $2.5 \text{ GB} \times 365 \approx 912 \text{ GB} \approx 0.91 \text{ TB}$.

---

### B. Bảng tính chi phí lưu trữ chi tiết ($/tháng)

| Hạng mục lưu trữ | Dung lượng lưu | Đơn giá AWS S3 (us-east-1) | Thành tiền ($/tháng) |
|---|---|---|---:|
| **Bronze Layer** (S3 Standard, 7 days retention) | 8.75 TB | $0.023 / GB = $23.00 / TB | **$201.25** |
| **Silver Layer** (S3 Standard, 7 days hot) | 7.00 TB | $0.023 / GB = $23.00 / TB | **$161.00** |
| **Silver Backup** (S3 Glacier Instant, days 8–30) | ~23.00 TB | $0.004 / GB = $4.00 / TB | **$92.00** |
| **Gold Layer** (S3 Standard 30 days + S3 IA 335 days) | ~0.91 TB | ~$0.0125 / GB trung bình | **$11.38** |
| **S3 API Requests (PUT/POST/LIST/GET):** | | | |
| - *PUT Requests:* 1.440 micro-batches/ngày × 3 layers = 4.320 PUT/ngày = 129.600 PUT/tháng | 130K calls | $0.005 / 1.000 requests | **$0.65** |
| - *GET Requests (Dashboard queries có Z-order skipping):* ~2.000.000 GET/tháng | 2M calls | $0.0004 / 1.000 requests | **$0.80** |
| - *Lifecycle Transition Requests:* ~50.000 objects/tháng | 50K calls | $0.01 / 1.000 requests | **$0.50** |
| **Tổng chi phí Storage:** | | | **$467.58 / tháng** |

---

### C. Ước tính chi phí Compute phục vụ Streaming & Query ($/tháng)

| Hạng mục Compute | Cấu hình đề xuất | Đơn vị & Thời gian | Thành tiền ($/tháng) |
|---|---|---|---:|
| **Flink Streaming Workers (Ingest & PII)** | 4 nodes `c6g.2xlarge` (8 vCPU, 16GB) Reserved/Spot | $0.136/giờ × 730h × 4 | **$397.12** |
| **Delta Compaction & Maintenance Cron (NB6)** | 1 node `r6g.xlarge` chạy 15 phút mỗi 2 giờ | 90 giờ compute / tháng | **$22.68** |
| **Trino / StarRocks Query Cluster (Dashboard)** | 3 nodes `m6g.xlarge` phục vụ ad-hoc + 5-min caching | $0.154/giờ × 730h × 3 | **$337.26** |
| **Tổng chi phí Compute:** | | | **$757.06 / tháng** |

$$\mathbf{\text{TỔNG TOÀN BỘ HỆ THỐNG}} = \$467.58 \text{ (Storage)} + \$757.06 \text{ (Compute)} = \mathbf{\$1.224.64 / \text{tháng}}.$$

**Kết luận:** Mức chi phí **~$1.225/tháng** đáp ứng xuất sắc giới hạn ngân sách nghiêm ngặt **≤ $5.000/tháng** (tiết kiệm hơn 75% ngân sách dự kiến, dư biên độ an toàn cực lớn cho các đợt bùng nổ traffic đột biến).

---

## 6. Kế Hoạch Triển Khai MVP 1 Tuần (One-Week MVP Slice)

Để chứng minh tính khả thi của kiến trúc trước ban lãnh đạo mà không cần dựng toàn bộ hệ thống đồ sộ, đội ngũ sẽ thực thi một **Vertical Slice** nhỏ nhất trong 5 ngày làm việc:

* **Phạm vi Slice:** Pipeline hoàn chỉnh cho **10.000.000 requests** (tương đương 15 phút peak traffic của production).
* **Tiêu chí nghiệm thu (Acceptance Criteria):**
  1. *Throughput & Ingest:* Pipeline Flink ingest đạt tối thiểu **15.000 req/giây** mà không bị backpressure; hoàn tất tokenize PII trên memory.
  2. *Deduplication:* Tầng Silver deduplicate triệt để các requests trùng lặp do network retry (`Silver row count < Bronze row count`), lưu trữ bảng theo chuẩn Medallion.
  3. *Query Performance & Pruning:* Câu truy vấn tenant dashboard trên Gold trả về kết quả trong **< 200 ms**. Trên Silver, câu truy vấn chi tiết với bộ lọc `WHERE tenant_id = 't_123'` kích hoạt Z-order skipping, chứng minh loại bỏ **≥ 90% số lượng file Parquet** cần đọc.
  4. *Audit Trail & Rollback:* Mô phỏng 1 đợt ghi dữ liệu lỗi vào Silver và thực hiện lệnh `RESTORE` thành công trong **< 5 giây**, đưa bảng về trạng thái hoàn hảo.
* **Cách xác minh cơ chế khó nhất (Hardest Mechanism Verification):**
  - **Cơ chế khó nhất:** Đảm bảo việc Auto-Compaction chạy liên tục 15 phút/lần không gây xung đột khóa (write conflict) với các Flink streaming appends đang diễn ra đồng thời.
  - **Cách test:** Sử dụng công cụ load generator bắn liên tục 20.000 writes/giây trong khi kích hoạt script `dt.optimize.compact()`. Đo đạc tỉ lệ commit failure (yêu cầu = 0% lỗi unhandled nhờ cơ chế Optimistic Concurrency Control của Delta Lake).

---

*(Mã nguồn Proof-of-Concept minh họa cơ chế PII Tokenization & Delta Z-order Pruning được lưu tại `submission/bonus/poc/poc_demo.py`)*.
