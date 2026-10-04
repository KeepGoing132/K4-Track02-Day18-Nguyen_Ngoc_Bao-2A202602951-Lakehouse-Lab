# Architecture Brief: LLM Observability Lakehouse — 1B Requests/Day

- **Tác giả:** Nguyễn Ngọc Bảo — MSSV 2A202602951
- **Bài:** K4-Track02-Day18, Topic A; thiết kế cá nhân
- **Ngày rà soát:** 04/10/2026

## 1. Problem statement

API sinh 1 tỷ request/ngày, trung bình 11.574 req/s và giả định peak 30.000 req/s. Mỗi prompt/response cùng metadata khoảng 5 KB: **5 TB/ngày raw**. Dashboard theo tenant cần refresh trong 5 phút, query p95 dưới 2 giây. Dữ liệu chi tiết được giữ tối đa 7 ngày; aggregates giữ 365 ngày. PII phải được che trước khi analyst đọc; **storage cap $5.000/tháng**.

Khó khăn chính là cân bằng ingest, số file, retention vật lý và chi phí bảo trì. Thiết kế dưới đây là giả thuyết cần load test, không phải hệ thống production đã triển khai. Quy ước tính toán: TB/GB theo hệ thập phân, tháng 30 ngày cho volume và 730 giờ cho node chạy liên tục. Đơn giá là đầu vào dự toán cho us-east-1, cần báo giá thực tế trước khi triển khai.

## 2. Architecture diagram

```text
Inference API (30K req/s peak)
           |
           v
Kafka: 100 partitions, encrypted, retention <= 1 hour
           |
           v
Flink: regex + PII detector; HMAC key from secret store
10 writer tasks, checkpoint + commit every minute
           |
           v
BRONZE / Delta / S3 Standard
- Partition by UTC ingestion hour; masked prompt/response
- Append batches; schema contract; no raw PII mapping in this table
           |
           v
SILVER / Delta / S3 Standard
- Dedup request_id; typed metrics; partition by UTC ingestion hour
- Z-order tenant_id; compact closed windows every 15 minutes
- Target 256 MB; no more than two rewrite passes per window
           |
           v
GOLD / Delta / S3 Standard then Standard-IA
- 5-minute tenant/model aggregates, latency sketches + token/cost sums
- Daily immutable files for older aggregates; retain 365 days
           |
           v
Trino Delta connector + Hive Metastore --> tenant dashboard
           |
           +--> incident queries on masked Bronze/Silver

Retention controller for detailed tables:
quiesce old partitions -> Delta DELETE -> guarded VACUUM
-> verify physical erasure, orphan sweep and backup expiry
```

Medallion separates raw evidence from dedup and serving. ACID log commits define visible files; schema enforcement catches incompatible writes. File statistics plus clustering reduce tenant-query reads. Catalog registration provides table discovery; retention works through table transactions before physical deletion. Gold stores mergeable sketches so daily p95 is computed by merging distributions, rather than averaging five-minute p95 values.

## 3. Decisions and rejected alternatives

| Decision | Chosen design and tradeoff | Alternative 1 rejected | Alternative 2 rejected |
|---|---|---|---|
| Table format | Delta with append/MERGE, statistics and Z-order. Pin writer/reader versions and validate interoperability before rollout; PoC uses Python `deltalake` 1.x. | Plain Parquet directories require us to build atomic visibility, rollback and schema coordination. | Iceberg is viable for multi-engine governance, but would require changing the demonstrated Delta/CDF path and validating a separate maintenance implementation. |
| Ingest | One-minute commits, 10 writers; roughly 694K requests/minute, 868 MB compressed in total, about 87 MB/file at average load. Compaction runs every 15 minutes on closed windows. | One PUT per request produces 1B files/day: at the assumed $0.005/1K PUT, $5K/day for PUT alone. | Hourly ingestion violates five-minute refresh even if its files are large. |
| Layout | Hourly ingestion partitions bound retention; Z-order by tenant within closed windows. Late event timestamps remain columns rather than reopening expired partitions. | Tenant partitioning creates excessive small partitions for sparse tenants. | Sorting every incoming batch cannot prevent overlapping ranges across independent writers and adds ingest latency. |
| Retention/tiering | Bronze/Silver stay on Standard for their short life; only immutable Gold files older than 30 days move to IA. | Silver archive through day 30 conflicts with the seven-day detailed-data rule. Glacier also bills at least 90 days even if deleted earlier. | Keeping all raw events for a year creates 1.825 PB before compression and changes both the retention contract and budget. |
| PII | Redact before Bronze; keyed HMAC for supported identifiers, restricted access and key rotation. Production adds a validated detector for unstructured PII. | Daily masking leaves readable PII during the batch gap. | Query-time masking can be bypassed by direct object access and repeats detector work on every query. |
| Catalog/query | Hive Metastore registers external Delta tables; Trino reads Gold with tenant access controls and a short cache TTL. Test Delta protocol support in the pinned connector. | Local SQLite catalog is useful for the lab but is not a shared HA production service. | A separately synchronized dashboard database adds another lifecycle and reconciliation pipeline before the MVP establishes the lakehouse contract. |

`deltalake` package version is not the Delta table-format version. Liquid clustering and deletion vectors are outside this MVP; feature support must be tested across the actual engines before enabling them. HMAC tokens are pseudonymous and retain linkability, so they remain governed data. The local regex PoC covers email and phone fixtures only; it neither detects all PII nor proves legal compliance.

**Detailed retention:** The design uses a conservative six-day logical visibility window and reserves the last day for physical cleanup, ensuring the maximum is seven days. A controller stops writes/reads on each expiring ingestion-hour partition, commits DELETE, and VACUUMs tombstoned files after a validated 12-hour safety interval. Hourly scheduling, cleanup time and reader lifetime must fit the remaining margin; admission control bounds transaction/reader lifetime to one hour. The shortened VACUUM retention requires an explicit production safety review and an erasure drill. If seven complete days of queryability are required, this tradeoff must be renegotiated.

Replay/time travel for detailed tables is limited by that cleanup policy. No detailed backup or Kafka copy may outlive the same seven-day maximum; S3 versioning is disabled for detailed buckets, or noncurrent objects must be included in erasure verification. Object lifecycle must not delete live Delta files directly. Orphan removal checks active and retained log references, excludes CDF/checkpoints, and requires an age guard beyond the longest writer transaction. Gold expiration also uses table-aware deletion; transitions apply only to immutable files.

## 4. Failure modes

| Failure | Detection | Recovery / rollback |
|---|---|---|
| Compaction crashes or races a writer | File-count/average-size alert; commit conflicts; query p95; unfinished-task age. | Keep streaming append available, retry bounded maintenance on closed partitions; pause jobs that exceed the 15-minute slot. Sweep uncommitted files only after the age guard and retained-version checks. |
| New payload has incompatible schema | Schema rejection count and DLQ lag; contract test on a canary batch. | Quarantine already-masked bad records, preserve the source checkpoint, approve opt-in schema evolution, then replay. RESTORE is used only after quiescing writers and identifying good commits; otherwise replay affected records to avoid losing concurrent valid data. |
| Retention worker stops or deletes needed files | Erasure deadline per partition; inventory joined with retained logs; missing-file read checks. | Stop old-detail queries at the logical deadline; escalate physical cleanup before the seven-day limit. Fix the controller and verify all copies. An expired physical object cannot be recovered by RESTORE; do not promise rollback after erasure. |
| Detector misses PII or dashboard is stale | Seeded PII canaries, restricted-access audit, ingest-to-Gold watermark age >5 minutes. | Quarantine the affected partition and revoke analyst access; repair masking and rebuild while within retention. On watermark lag, invalidate the cache and backfill from pinned Silver versions still available. |

Storage alerts compare live bytes, obsolete bytes, orphan age and daily budget projection. A $4K projected storage alert leaves intervention margin below the $5K cap. The delta-rs and PyIceberg behaviors measured in NB6 are lab-specific: the production engine must pass the same deletion checks rather than inheriting those conclusions.

## 5. Storage and compute math

Compression of 4:1 is an assumption to test on masked payload samples: 5 TB/day / 4 = **1.25 TB/day Bronze**. Silver is assumed 1 TB/day. Maximum detailed-file residence of seven days gives conservative volume ceilings of **8.75 TB Bronze** and **7 TB Silver**, including the physical-erasure interval.

Gold: 10K active tenants x 3 models x 288 windows/day = **8.64M rows/day**. At assumed 2.5 GB/day compressed (about 289 B/row), one year is **912.5 GB**: 75 GB on Standard and 837.5 GB on IA. This allowance includes latency sketches; sample serialization must validate its size. Catalog, transaction logs, CDF, and transient rewrite files are budgeted separately.

| Storage item | Calculation / assumption | USD/month |
|---|---|---:|
| Bronze Standard | 8,750 GB x $0.023 | 201.25 |
| Silver Standard | 7,000 GB x $0.023 | 161.00 |
| Rewrite/obsolete reserve | Two passes/day x 2.25 TB/day x one-day residence = 4,500 GB x $0.023 | 103.50 |
| Gold Standard + IA | 75 x $0.023 + 837.5 x $0.0125 | 12.19 |
| PUT/COPY/LIST reserve | 5M calls x assumed $0.005/1K | 25.00 |
| Standard GET reserve | 20M calls x assumed $0.0004/1K | 8.00 |
| Gold transition + IA reads | 30K transitions x $0.01/1K + 100 GB retrieval x $0.01/GB | 1.30 |
| Logs, CDF, catalog and inventory reserve | Budget allowance; measure separately | 20.00 |
| **Storage planning total** | | **532.24** |

PUT counts cannot equal batch counts: ten writers already produce 14,400 Bronze data files/day; Silver, rewrite files, transaction logs, multipart uploads and Gold add more calls. Five million calls/month is a planning reserve, not a measured workload. With no Glacier tier there is no Glacier minimum-duration charge. Gold IA objects must live at least 30 days after transition; expiring objects incur any remaining minimum charge. The $0.023 and $0.0125 rates are explicit planning inputs; AWS region, retrieval, tax and invoice units must be checked in a calculator quote [S1, S2].

| Compute and operations | Planning rate / quantity (not an AWS quote) | USD/month |
|---|---|---:|
| Flink ingest + detector | 4 worker nodes x $0.30/h x 730h | 876.00 |
| Kafka | 3 nodes x $0.20/h x 730h | 438.00 |
| Broker volumes | 600 GB x $0.08/GB-month | 48.00 |
| Trino | 3 nodes x $0.20/h x 730h | 438.00 |
| Catalog service | 1 node x $0.10/h x 730h | 73.00 |
| Maintenance | Dedicated node x $0.30/h x 730h; scheduler every 15 minutes | 219.00 |
| Secret store, KMS, monitoring | Planning allowance | 100.00 |
| **Compute/operations total** | | **2,192.00** |

Baseline storage plus operations = **$2,724.24/month**; adding 30% contingency gives **$3,541.51/month**. The assignment cap applies to storage, whose estimate is $532.24; this does not establish measured throughput or an all-inclusive production quote. LLM inference, staff, cross-region replication, public egress and disaster recovery are outside this estimate and must be quoted if required. Same-region transfer and intra-region service charges require measurement within the contingency.

If compression falls to 2:1 and Silver/rewrite volume also doubles, those three storage rows rise from $465.75 to $931.50: storage becomes **$997.99/month**, before any extra compute. Rewriting entire historical partitions every 15 minutes is prohibited by the pass budget; inventory should verify this assumption daily. Detector throughput and high query concurrency may require more nodes than the provisional configuration.

## 6. One-week MVP and evidence

**Slice:** 10M synthetic masked events over one hour, 100 tenants, plus a short 30K req/s burst. This is a scale sample, not fifteen minutes of production: at 30K req/s, ten million requests take about 333 seconds.

- Day 1: pin engine/connector versions, schema and keys; validate tokenization with seeded PII cases.
- Day 2: checkpointed ingest, dedup and Gold; compare request IDs, costs and merged quantiles against an independent batch calculation.
- Day 3: closed-window Z-order and concurrent append; measure file candidates from min/max before/after and audit real query I/O.
- Day 4: accelerate the retention clock; hold a reader open, crash a writer and leave an orphan. Verify that retained reads survive and that all detailed copies meet the erasure deadline.
- Day 5: load test and publish measured throughput, refresh watermark, p95 and cost projection; revise sizing if targets fail.

**Acceptance:** sustain 15K req/s for ten minutes without growing backlog; Gold freshness <=5 minutes and query p95 <2 seconds; dedup matches an independent request-ID set; tenant file skipping >=90%; correct costs and quantiles; no unhandled concurrent-commit errors; erasure within the seven-day-equivalent test clock. These are targets, not results already demonstrated.

**Hardest mechanism:** Retention-safe concurrent maintenance. Continuously append while clustering only closed partitions, then expire an old partition during a bounded reader. Check retained-version references before cleanup and confirm no file-missing errors. After quiescing writers, inject a bad commit and verify RESTORE preserves the chosen good version; explicitly test that erased versions are unavailable.

**Local PoC actually run:** `poc/poc_demo.py`, 50K rows and 100 tenants. HMAC-SHA256 was checked against the keyed digest; all generated prompts passed the fixture regex checks. Before clustering, 50/50 files were candidates. After Z-order, 1/49 files was a candidate: **97.96% skipped, pruning 49x**, with the same 492 matching request IDs. These are active-file statistics, not observed S3 GET counts. The local query took 27.04 ms in this run and is not a production SLA. See [POC_RESULTS.md](poc/POC_RESULTS.md). The PoC does not implement Flink, production PII detection or concurrency/retention acceptance tests.

## Sources

Checked 04/10/2026. Prices in the tables remain declared planning assumptions.

- [S1 — AWS S3 pricing: storage, requests and minimum-duration billing](https://aws.amazon.com/s3/pricing/).
- [S2 — AWS S3 storage classes: IA 30 days, Glacier Instant 90 days](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html).
- [S3 — Delta maintenance: VACUUM safety, RESTORE and retained files](https://docs.delta.io/delta-utility/).
- [S4 — Delta liquid clustering: feature requirements and compatibility](https://docs.delta.io/delta-clustering/).
- [S5 — Python HMAC](https://docs.python.org/3/library/hmac.html).
- [S6 — Trino Delta Lake connector](https://trino.io/docs/current/connector/delta-lake.html).
