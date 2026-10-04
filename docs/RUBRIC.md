# K4-Track02-Day18 — Grading Rubric

Phần bắt buộc: **100 điểm**. Bonus: **tối đa 10 điểm cộng**, chấm riêng.
Điểm lab cuối cùng = `min(100, điểm bắt buộc + điểm bonus)`, trước khi áp dụng
điều chỉnh nộp muộn theo thông báo của key coach. Bonus là điểm của bài lab,
không phải điểm phát biểu, giơ tay hay pitching.

`make test` and `make run-all` check library behaviours and assertions in the
eight lightweight notebooks. Run the commands below from the repository root.
The grader also checks the preserved outputs,
screenshots and explanations against the criteria below. A successful run alone
does not prove every criterion: inspect the actual schema-enforcement error,
commit JSON and Gold outputs; NB4 does not assert every Gold requirement.

```bash
make setup && make smoke && make data && make data-ai && make test && make run-all
```

Two paths are supported for NB1–NB4 (lightweight `deltalake` vs Spark/Docker).
Both write the **same on-disk Delta format**, so evidence from either counts:

* *MinIO `_delta_log/` visible* ↔ *`_lakehouse/.../_delta_log/` on local disk*
* *Spark `OPTIMIZE … ZORDER BY`* ↔ *`dt.optimize.compact()` + `dt.optimize.z_order(...)`*
* *Spark `MERGE INTO`* ↔ *`dt.merge(...).when_matched_update_all().execute()`*

NB5–NB8 use the lightweight path (Python APIs; no JVM required).

---

## Part A — Foundations (44 pts)

| # | Notebook | Criterion | Pts |
|---|---|---|---:|
| 1 | `01_delta_basics` | Delta table created; `_delta_log/` JSON commits visible | 4 |
| 1 | `01_delta_basics` | Schema enforcement blocks the `age=str` write | 2 |
| 1 | `01_delta_basics` | `schema_mode="merge"` adds the `tier` column (opt-in evolution) | 2 |
| 2 | `02_optimize_zorder` | Small-file problem reproduced (≥ 100 files before OPTIMIZE) | 3 |
| 2 | `02_optimize_zorder` | Speedup ≥ 3× **or** files-pruned ratio ≥ 10× | 6 |
| 2 | `02_optimize_zorder` | `numFiles` drops meaningfully after OPTIMIZE | 3 |
| 3 | `03_time_travel` | `history()` shows ≥ 5 versions **including the RESTORE row** | 4 |
| 3 | `03_time_travel` | MERGE upsert 100K rows succeeds | 4 |
| 3 | `03_time_travel` | RESTORE rolls back bad data; `score < 0` count = 0 | 4 |
| 4 | `04_medallion` | Bronze, Silver, Gold all present on the storage layer | 4 |
| 4 | `04_medallion` | Silver dedup measurably drops rows (Silver < Bronze) | 4 |
| 4 | `04_medallion` | Gold correct (p50/p95, cost_usd, error_rate) for ≥ 7 dates × 3 models | 4 |
|   | | **Part A subtotal** | **44** |

## Part B — Lakehouse 2026 (50 pts)

| # | Notebook | Criterion | Pts |
|---|---|---|---:|
| 5 | `05_iceberg_catalog` | Table created **through the catalog**; partition spec uses `day(ts)` | 3 |
| 5 | `05_iceberg_catalog` | Hidden-partition pruning ≥ 5× measured via `plan_files()`, filtering on `ts` (not `ts_day`) | 5 |
| 5 | `05_iceberg_catalog` | Three-tier metadata walked; metadata:data byte ratio reported | 1 |
| 5 | `05_iceberg_catalog` | Rename keeps `field_id` (metadata-only); ≥ 2 partition specs coexist and the table still reads | 4 |
| 6 | `06_maintenance` | **Job 1** Compaction: ≥ 10× fewer files, before/after reported | 4 |
| 6 | `06_maintenance` | **Job 2** Clustering: ≥ 50% of files skippable for a point query, proven from min/max stats | 3 |
| 6 | `06_maintenance` | **Job 3** Expiry: Delta vacuum reclaims bytes; Iceberg drops to 3 snapshots | 3 |
| 6 | `06_maintenance` | **Job 4** Orphans: 3 planted Delta orphans found + removed; stranded Iceberg manifest lists swept | 2 |
| 6 | `06_maintenance` | **Job 5** Checkpoint written (`*.checkpoint.parquet` + `_last_checkpoint`) | 1 |
| 7 | `07_vectors_multimodal` | Random-access amplification measured (≥ 5×) and explained via row-group granularity | 4 |
| 7 | `07_vectors_multimodal` | int8 quantization ≥ 3× smaller on disk; recall@10 ≥ 0.80 and topic fidelity ≥ 0.95, both reported | 4 |
| 7 | `07_vectors_multimodal` | Semantic search runs as SQL and returns on-topic neighbours | 1 |
| 7 | `07_vectors_multimodal` | **Lifecycle bug reproduced**: 0 hits in-table, > 0 hits in the stale external index | 4 |
| 8 | `08_agents_provenance` | Trajectories through medallion; Silver partitioned by `agent_version`; Gold covers both policies | 3 |
| 8 | `08_agents_provenance` | Training run pins the table version; replay at that version matches the recorded step count | 3 |
| 8 | `08_agents_provenance` | Offline MCP-inspired surface: cached `list_tables` calls (5 turns → 1 catalog read), `input_required` before the simulated destructive call, task poll completes | 3 |
| 8 | `08_agents_provenance` | All **four illustrative provenance buckets** exist as partitions; UNCLASSIFIED rows excluded from the lab's trainable set | 2 |
|   | | **Part B subtotal** | **50** |

## Part C — Reproducibility (6 pts)

| Criterion | Pts |
|---|---:|
| Pytest suite green (24 tests), via `make test` or the PowerShell equivalent in README | 2 |
| All 8 lightweight notebooks green from a clean setup, via `make run-all` or its PowerShell equivalent | 4 |
| | **6** |

**Required work total: 100 points**

## Bonus — Architecture brief (up to 10 additional points)

Submit `submission/bonus/ARCHITECTURE.md` using the
[Vietnamese brief](bonus/BONUS-CHALLENGE.md) or [English brief](bonus/BONUS-CHALLENGE-EN.md).
Code is optional; the document must contain enough evidence to assess feasibility.

| Criterion | Evidence | Pts |
|---|---|---:|
| Key decisions and rejected alternatives | At least 5 decisions, each with at least 2 alternatives and concrete tradeoffs | 2 |
| Realistic constraints and cost calculation | Scale, latency and budget used consistently; storage and compute math shown | 2 |
| Day18 concepts applied in the architecture | One diagram; at least 4 concepts applied to actual design choices | 2 |
| Failure modes | At least 3 specific failures with detection and rollback; at least one tied to a Day18 concept | 2 |
| One-week MVP and feasibility | A testable slice, acceptance criteria and a way to verify the hardest mechanism; PoC optional | 2 |
| | **Bonus maximum** | **10** |

For each 2-point bonus criterion: **2** = all requested evidence is clear and
consistent; **1** = partially supported or missing a material detail;
**0** = absent, unverifiable or only generic claims. Omitting bonus does not
reduce the required-work score.

---

## What earns the top band

Full marks on a criterion require the number **and** the reading of it. Two
submissions can both print `pruning ratio: 10×` and only one has done the lab:

* *Adequate:* "Pruning ratio was 10×."
* *Strong:* "10× because the filter is on `ts` and Iceberg derived `ts_day`
  from the stored transform — a Hive user who forgot the partition predicate
  would have read all 10 files, ~$220/day at 10K queries."

NB6 measures two library behaviours: Delta vacuum misses uncommitted orphans,
and the PyIceberg snapshot-expiry path leaves physical files for a separate sweep.
Explain the measured behaviour in the lab's engine/version context.

NB8 is an offline simulation, not an MCP server or a legal-compliance test.
Its cache demonstration calls `list_tables`, not `tools/list`. Its confirmation
flag is caller-controlled, and version replay checks row count, not content equality.
The provenance mapping is illustrative and has known limitations described in
[CHECKPOINTS.md](CHECKPOINTS.md).

## Submission

Fork the assignment repository into your personal GitHub account and **rename the fork**
to `K4-Track02-Day18-HoVaTen-MSSV-Lakehouse-Lab` before cloning.
Follow [SUBMISSION.md](SUBMISSION.md) for the naming details, executed notebooks,
screenshots and individual reflection. Both required work and bonus are individual. Each notebook criterion
needs output showing the required measurement and an explanation of what it means.

## Điều kiện mất điểm và chấm lại

- Không có output/bằng chứng để kiểm tra một tiêu chí: không nhận điểm tiêu chí đó.
- Số liệu không đạt ngưỡng hoặc giải thích sai cơ chế: không nhận đủ điểm tiêu chí.
  Riêng NB2 chấp nhận **một trong hai** ngưỡng speedup hoặc pruning; không bắt buộc đạt cả hai.
- Thiếu notebook: các tiêu chí thuộc notebook đó không được chấm điểm.
- `make test` hoặc `make run-all` thất bại: mất phần điểm reproducibility tương ứng;
  các tiêu chí khác vẫn được xét theo bằng chứng thực tế.
- Output giả, bỏ kiểm tra để báo PASS, hoặc sao chép không khai báo: xử lý theo [RULES.md](RULES.md).
- Thiếu reflection, sai tên repo hoặc thiếu thông tin người nộp:
  bài nộp chưa đầy đủ; cần bổ sung theo yêu cầu của key coach. Không tự gán một mức trừ
  điểm ngoài các tiêu chí đã công bố.
- Nộp muộn và sửa bài sau deadline: áp dụng [RULES.md](RULES.md) và thông báo chính thức
  của key coach. Khi xin chấm lại, gửi liên kết PR/repo, commit đã nộp và tiêu chí cần xem xét.
