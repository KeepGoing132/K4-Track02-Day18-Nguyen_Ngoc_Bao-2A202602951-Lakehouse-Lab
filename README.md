# K4-Track02-Day18-Lakehouse-Lab

Lab cho **Khóa 4 · Track 02 · Day 18 · Data Lakehouse Architecture**.

**Hình thức làm bài: cá nhân cho cả phần bắt buộc và bonus.** Mỗi học viên tự chạy,
giải thích kết quả và nộp repo riêng theo [SUBMISSION.md](docs/SUBMISSION.md).

## Mục tiêu học tập

Sau bài lab, bạn có thể tạo bảng Delta có transaction log và schema enforcement;
đo tác dụng của compaction/Z-order; dùng MERGE, time travel và RESTORE;
xây dựng pipeline Bronze → Silver → Gold; quản lý bảng Iceberg qua catalog;
đo các job maintenance; và giải thích vòng đời embeddings, version dữ liệu và provenance.

**Thời lượng dự kiến:** 3–4 giờ cho phần bắt buộc, tùy cấu hình máy và thời gian phân tích kết quả.
Bonus là phần tùy chọn, dự kiến thêm 4–8 giờ.

| Tài liệu | Nội dung |
|---|---|
| [SUBMISSION.md](docs/SUBMISSION.md) | Tên repo, bài phải nộp, nơi nộp, deadline và kiểm tra trước khi nộp |
| [RUBRIC.md](docs/RUBRIC.md) | Thang điểm phần bắt buộc và bonus, bằng chứng và điều kiện mất điểm |
| [CHECKPOINTS.md](docs/CHECKPOINTS.md) | Các bước thực hiện, sản phẩm và cách tự kiểm tra |
| [RULES.md](docs/RULES.md) | Sử dụng AI, hợp tác, nộp muộn, sửa bài và bảo mật |

Tám notebook, hai nửa:

* **NB1–NB4 — nền tảng.** Delta Lake ACID, OPTIMIZE/Z-ORDER, time travel, medallion Bronze→Silver→Gold.
* **NB5–NB8 — lakehouse cho AI.** Iceberg và **catalog như control plane**, maintenance, multimodal + vector trong bảng, agent trajectory và provenance minh họa.

Đường lightweight chạy **offline sau khi cài dependencies**: không API key, không Docker,
không JVM, không tải model, không tải DuckDB extension. Setup lần đầu cần mạng để cài gói;
đường Spark tùy chọn còn cần tải container image và Maven JARs.

---

## Quick Start

1. **Fork** [repo đề bài](https://github.com/VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab)
   về tài khoản GitHub cá nhân.
2. **Bắt buộc đổi tên fork** thành `K4-Track02-Day18-HoVaTen-MSSV-Lakehouse-Lab`.
   Họ tên viết không dấu, không khoảng trắng; dùng MSSV của chính bạn.
   Ví dụ: `K4-Track02-Day18-NguyenVanAn-20260001-Lakehouse-Lab`.
   Nếu đã fork với tên gốc, đổi tên repository trên GitHub trước khi clone.
3. Clone fork đã đổi tên. Thay `TEN_GITHUB`, `HoVaTen` và `MSSV` bằng thông tin của bạn:

```bash
git clone https://github.com/TEN_GITHUB/K4-Track02-Day18-HoVaTen-MSSV-Lakehouse-Lab.git
cd K4-Track02-Day18-HoVaTen-MSSV-Lakehouse-Lab
git remote -v
```

**Kiểm tra:** `origin` phải trỏ tới fork cá nhân có tên đúng mẫu trên.
Đổi tên thư mục trên máy không thay thế việc đổi tên repository trên GitHub.
Nếu đã clone trước khi đổi tên, cập nhật `origin` theo [SUBMISSION.md](docs/SUBMISSION.md#1-fork-và-đặt-tên-repo).
Chạy các lệnh cài đặt sau từ thư mục gốc fork:

```bash
make setup      # tạo venv và cài dependencies; lần đầu có thể mất vài phút
make smoke      # 9 checks, offline sau khi cài dependencies
make data       # Bronze cho NB4
make data-ai    # corpus multimodal + agent traces cho NB7/NB8
make lab        # http://localhost:8888
```

Chuẩn bị **Python 3.10–3.14**, Git và mạng cho lần cài đặt đầu tiên; khuyến nghị Python 3.11
để dùng phiên bản đã kiểm tra trong lần rà soát này. Các lệnh `make` cần GNU Make,
công cụ shell Unix và cấu trúc venv của Linux/macOS; trên Windows có thể dùng WSL
hoặc chạy Python trực tiếp bằng PowerShell theo hướng dẫn sau.

### Chạy lightweight trên Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/verify_lite.py
.\.venv\Scripts\python.exe scripts/generate_data_lite.py
.\.venv\Scripts\python.exe scripts/generate_ai_data.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/run_all.py
# Chuyển riêng 8 notebook, bỏ helper _setup.py
Get-ChildItem notebooks/[0-9]*.py | ForEach-Object {
    .\.venv\Scripts\python.exe -m jupytext --to notebook $_.FullName
}
.\.venv\Scripts\python.exe -m jupyter lab --notebook-dir=notebooks --no-browser
```

Nếu gặp lỗi encoding khi in ký tự Unicode trên Windows, đặt `$env:PYTHONUTF8 = '1'`
trước khi chạy scripts. Smoke test, 24 tests và cả 8 notebook lightweight đã được
kiểm tra trên Windows với Python 3.11. WSL phù hợp nếu muốn dùng nguyên các lệnh `make`.

Nếu PyArrow báo `WinError 3` ở đường dẫn Iceberg rất dài, giữ đường dẫn dữ liệu
và `pytest --basetemp` ngắn. Ví dụ dùng
`$env:LAKEHOUSE_ROOT = (Join-Path (Get-Location).Path '_lakehouse/c').Replace('\', '/')`
và `--basetemp=./.pytest_tmp/c`.
Đây là thư mục dữ liệu riêng trong repo, không dùng để thay đổi ngưỡng assertion.

Để tạo lại bằng chứng NB1 và PDF bonus trên Windows:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-artifacts.txt
./.venv/Scripts/python.exe scripts/build_submission_artifacts.py --only 01_delta_basics
./.venv/Scripts/python.exe scripts/render_bonus_brief.py
./.venv/Scripts/python.exe submission/bonus/poc/poc_demo.py
```

Script PDF đọc `submission/bonus/ARCHITECTURE.md`, dùng font Arial của Windows,
và xuất `submission/bonus/ARCHITECTURE.pdf`. Ảnh NB1 là bản render từ output thực
thi, giữ đầy đủ commit JSON và chỉ xuống dòng để dễ đọc.

Khoảng phiên bản Python được cấu hình là 3.10–3.14. Lần rà soát hiện tại kiểm tra
Python 3.11 trên Windows; chưa chạy lại toàn bộ khoảng phiên bản này.

Kiểm tra mọi thứ chạy được trước khi nộp:

```bash
make test       # 24 pytest; thời gian tùy máy
make run-all    # chạy cả 8 notebook headless; thời gian tùy máy
```

---

## Tám notebook

| NB | Chủ đề | Bạn **đo** được gì | Slide |
|---|---|---|---|
| `01_delta_basics` | Transaction log, schema enforcement + evolution | `_delta_log/` JSON; bad write bị chặn; `tier` thêm khi opt-in | §2 |
| `02_optimize_zorder` | Small files, OPTIMIZE + Z-ORDER | speedup ≥ 3× **hoặc** files-pruned ≥ 10× | §6 |
| `03_time_travel` | `versionAsOf`, MERGE, RESTORE | `history()` ≥ 5 version kể cả RESTORE | §3 |
| `04_medallion` | Bronze→Silver→Gold cho LLM observability | Silver < Bronze (dedup); Gold p50/p95/cost ≥ 7 ngày | §8 |
| `05_iceberg_catalog` | **Iceberg + catalog là control plane** | hidden-partition pruning ≥ 5×; field-ID bền qua rename; 2 partition spec cùng tồn tại | §4, §12 |
| `06_maintenance` | **4 job bắt buộc** + job thứ 5 | compaction ≥ 10× ít file; clustering skip ≥ 50%; orphan + snapshot expiry | §6, §12 |
| `07_vectors_multimodal` | Blob inline vs pointer; embedding trong bảng | amplification khi random-read; int8 nhỏ ≥ 3×; **lifecycle bug** tái hiện được | §11 |
| `08_agents_provenance` | Trajectory, lớp MCP mô phỏng, provenance | pin version; kiểm tra số bước replay; 4 bucket minh họa thành partition | §11, §12 |

`make run-all` chạy cả 8 notebook và kiểm tra các `assert` có trong mã.
Bạn vẫn cần đối chiếu output với [RUBRIC.md](docs/RUBRIC.md): chạy thành công chưa tự động chứng minh
mọi tiêu chí chấm, đặc biệt chất lượng Gold, bằng chứng schema enforcement và phần giải thích kết quả.

---

## Ba điều notebook đo được mà slide chưa nói

Lab này không chỉ minh hoạ slide. Ba kết quả dưới đây là **đo thật trên máy bạn**, và đều là bẫy production:

1. **`VACUUM` không dọn orphan chưa từng commit.** `deltalake` (Rust/Python) chỉ thu hồi file đã bị *tombstone* trong log. File do job crash để lại chưa từng vào log → vô hình với vacuum ở mọi retention. NB6 đo, rồi bắt bạn tự viết phép hiệu tập hợp.
2. **Snapshot expiry trong đường PyIceberg của NB6 chưa xóa file vật lý.** Notebook đo số snapshot giảm 20 → 3 nhưng manifest lists vẫn còn trên đĩa, rồi dọn các file không còn được tham chiếu. Đây là hành vi của API và phiên bản thư viện trong lab, không phải kết luận cho mọi engine Iceberg.
3. **Đường Delta của NB7 không giữ kiểu vector cố định chiều.** `fixed_size_list<float>[256]` ghi xuống rồi đọc lên thành `list<float>`; notebook cast về kiểu mảng cố định khi query DuckDB.

Hai điều đầu được "ghim" bằng test canary trong `tests/` — nếu thư viện đổi hành vi, test đỏ và notebook phải sửa theo.

---

## Lệnh `make`

```
make setup     Tạo venv + cài dependencies
make smoke     9 check offline sau khi cài dependencies
make test      24 pytest (thời gian tùy máy)
make data      Bronze 200K dòng cho NB4
make data-ai   Corpus multimodal + agent traces cho NB7/NB8
make run-all   Chạy cả 8 notebook headless và các assertion có trong mã
make simulate  Mô phỏng 12 kịch bản học viên (SIM_FAST=1 để bỏ 2 kịch bản dựng venv)
make lab       Mở Jupyter Lab
make clean     Xoá venv + _lakehouse/

make spark-up / spark-smoke / spark-data / spark-down / spark-clean
               Đường Spark/Docker tuỳ chọn (chỉ phủ NB1–NB4)
```

**Notebook lưu dạng Jupytext `.py`** (nhẹ, dễ review). `make setup` / `make lab` sinh `.ipynb`.
Nếu chỉnh sửa notebook, cần lưu/đồng bộ lại mã nguồn phù hợp; khi nộp, giữ `.ipynb` đã chạy
trong `submission/notebooks/` để output được đưa vào Git. Xem [SUBMISSION.md](docs/SUBMISSION.md).

---

## Hai đường chạy

| Path | Stack | Setup | RAM | Phủ |
|---|---|---|---|---|
| **Lightweight (mặc định)** | `deltalake` 1.x + `pyiceberg` + DuckDB + Polars | `make setup`; tùy mạng/cache | ~600 MB | **cả 8 NB** |
| **Spark (Docker Compose)** | PySpark 3.5 + delta-spark + MinIO | `make spark-up`, ~3–8 phút | ~6 GB | 4 NB PySpark **+ cả 8 NB lightweight** |
| **Spark (Apple `container`)** | y hệt trên, chạy bằng `container run` | `make apple-up`, ~3–8 phút | ~6 GB | y hệt trên |

Các con số RAM và thời gian Spark là ước lượng, tùy máy và cache tải xuống.
Cả hai dùng định dạng Delta, nhưng khả năng đọc chéo còn phụ thuộc protocol,
table features và phiên bản engine. Lightweight lưu cục bộ, Spark dùng MinIO;
không tự chia sẻ cùng bảng chỉ bằng việc đổi đường chạy.
Container Spark được cấu hình cài cả stack lightweight để phục vụ 4 bản PySpark
ở `notebooks-spark/` và 8 bản lightweight ở `notebooks/`. Lần rà soát hiện tại
chỉ kiểm tra cấu hình Compose và cú pháp shell, chưa chạy lại container đầu-cuối.

---

### Chạy Spark bằng Apple `container` (macOS 15+, Apple silicon)

Đường [`apple/container`](https://github.com/apple/container) dùng
`infra/apple_container.sh` để dựng MinIO, khởi tạo buckets và Spark/Jupyter bằng
`container run`. Các target `apple-*` gọi script này; các target `spark-*` dùng Docker Compose:

```bash
brew install container
container system kernel set --recommended   # bắt buộc: `system start` sẽ hỏi và treo nếu không có TTY
container system start

make apple-up       # MinIO + buckets + Spark/Jupyter
make apple-smoke    # scripts/verify.py trong container
make apple-data     # sinh Bronze 1 triệu dòng bằng Spark
make apple-status   # xem container + IP của MinIO
make apple-down     # dừng (giữ dữ liệu MinIO)  ·  apple-clean = xoá luôn
```

Script đọc IP của MinIO bằng `container inspect` rồi truyền vào `MINIO_ENDPOINT`.
`scripts/spark_session.py` đọc biến này và mặc định là `http://minio:9000`
cho đường Compose. Đường Apple chưa được chạy lại trong lần rà soát hiện tại.

---

## Deliverable

Nộp 8 notebook đã chạy (giữ output), bằng chứng và reflection theo [SUBMISSION.md](docs/SUBMISSION.md).
Phần bắt buộc chấm trên **100 điểm**, bonus cộng tối đa **10 điểm**; điểm lab cuối cùng tối đa 100.
Chi tiết tại [RUBRIC.md](docs/RUBRIC.md).

1. **NB1** — `_delta_log/` JSON; bad-schema write bị chặn; `schema_mode="merge"` thêm cột `tier`
2. **NB2** — speedup ≥ 3× **hoặc** files-pruned ≥ 10×
3. **NB3** — MERGE 100K + RESTORE; `history()` ≥ 5 version *sau* restore
4. **NB4** — Bronze/Silver/Gold trên đĩa; Silver < Bronze; Gold ≥ 7 ngày × 3 model
5. **NB5** — pruning ratio ≥ 5× khi lọc trên `ts`; `latency_millis` giữ nguyên `field_id`; ≥ 2 `spec_id`
6. **NB6** — 4 job chạy đủ, kèm số trước/sau; 3 orphan tìm và xoá được
7. **NB7** — amplification random-read; int8 nhỏ ≥ 3×; **tái hiện lifecycle bug** (external index còn trả dữ liệu đã xoá)
8. **NB8** — Silver partition theo `agent_version`; replay có số bước khớp version đã pin;
   4 bucket provenance minh họa thành partition. Xem giới hạn mô phỏng trong [CHECKPOINTS.md](docs/CHECKPOINTS.md).

Ngoài ra: `submission/REFLECTION.md` (≤ 200 từ) — trong "Top 5 Lakehouse Anti-Patterns",
dữ liệu hoặc hệ thống bạn quan tâm dễ vướng cái nào nhất, vì sao?

---

## Bonus Challenge (tùy chọn, cộng tối đa 10 điểm)

Một **architecture brief** mở: chọn một tình huống dữ liệu khó (LLM observability 1B req/ngày, CDC với yêu cầu bảo vệ dữ liệu cá nhân, corpus nghìn tỷ token, multimodal RAG, tiering theo ngân sách FinOps, migration catalog…) và thiết kế chiến lược lưu trữ bạn có thể bảo vệ trong design review.

Tài liệu là deliverable; code tùy chọn. Bonus được chấm riêng theo [RUBRIC.md](docs/RUBRIC.md),
tập trung vào quyết định kiến trúc, alternatives, failure modes và phép tính chi phí.
Xem [BONUS-CHALLENGE.md](docs/bonus/BONUS-CHALLENGE.md) (VI) · [BONUS-CHALLENGE-EN.md](docs/bonus/BONUS-CHALLENGE-EN.md) (EN).

---

## Cấu trúc repo

```
.
├── README.md · Makefile · pytest.ini
├── requirements.txt          # lightweight: deltalake 1.x, pyiceberg, duckdb, polars, numpy
├── docs/                     # hướng dẫn học và nộp bài
│   ├── SUBMISSION.md · RUBRIC.md · CHECKPOINTS.md · RULES.md
│   └── bonus/
│       └── BONUS-CHALLENGE.md · BONUS-CHALLENGE-EN.md
├── infra/                    # container và script khởi động
│   ├── docker-compose.yml
│   ├── setup_spark.sh
│   └── apple_container.sh
├── notebooks/                # ← đường lightweight (mặc định)
│   ├── 01_delta_basics.py        05_iceberg_catalog.py
│   ├── 02_optimize_zorder.py     06_maintenance.py
│   ├── 03_time_travel.py         07_vectors_multimodal.py
│   └── 04_medallion.py           08_agents_provenance.py
├── notebooks-spark/          # NB1–NB4 bản PySpark
├── scripts/
│   ├── lakehouse.py              # path/catalog/đo đạc helper
│   ├── generate_data_lite.py     # Bronze LLM-observability (NB4)
│   ├── generate_ai_data.py       # corpus multimodal + trajectory (NB7/NB8)
│   ├── verify_lite.py            # make smoke
│   ├── run_all.py                # make run-all
│   └── spark_session.py · generate_data.py · verify.py
└── tests/                    # kiểm thử và mô phỏng cách học viên sử dụng lab
    ├── test_lab18.py
    └── simulate_students.py
```

`scripts/` chứa helper Python, sinh dữ liệu và lệnh kiểm tra/chạy notebook.
`infra/` chứa cấu hình Docker và script shell: nếu không dùng `make`, chạy
`bash infra/setup_spark.sh` để dựng đường Spark, hoặc `bash infra/apple_container.sh up`
trên macOS có Apple `container`.

---

## Troubleshooting

| Triệu chứng | Fix |
|---|---|
| `make setup` báo `python3: command not found` | Cài Python 3.10–3.14 hoặc `uv` |
| `AttributeError: 'DeltaTable' object has no attribute 'files'` | Bạn đang ở `deltalake` 0.x. `make clean && make setup` (lab dùng 1.x, `file_uris()`) |
| `No function matches array_cosine_similarity(FLOAT[], …)` | Thiếu cast: `emb::FLOAT[256]`. Delta trả về list biến chiều — xem ghi chú trong NB7 |
| NB2 speedup < 3× | Bình thường khi RAM thấp; tiêu chí cho phép dùng files-pruned ≥ 10× thay thế |
| Quên `make data` / `make data-ai` | Không sao — NB4/NB7/NB8 tự sinh dữ liệu thiếu khi chạy |
| Mở nhiều notebook cùng lúc trong Jupyter | NB5/NB6/NB8 và smoke dùng catalog Iceberg riêng. Sinh dữ liệu dùng chung trước; tránh chạy đồng thời hai bản của cùng notebook hoặc `make clean` khi đang chạy |
| Máy chặn mạng hoàn toàn | Lightweight chạy offline sau khi cài đủ dependencies. Lab dùng Arrow, không cần tải extension cho `delta_scan()` |

---

## Submission

Repo đề bài: [K4-Track02-Day18-Lakehouse-Lab](https://github.com/VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab).
Tên repo bài nộp, cấu trúc file, nơi nộp và deadline được quy định tại [SUBMISSION.md](docs/SUBMISSION.md).

---

## Đã kiểm thử như thế nào

Lần kiểm tra ngày 03/10/2026 trên Windows, Python 3.11:

- Smoke test: **9/9 PASS**.
- Pytest: **24/24 PASS**.
- Lightweight notebooks: **8/8 PASS**, khoảng 29 giây trên máy kiểm tra.
- Docker Compose: cấu hình hợp lệ và bind mount trỏ đúng repo; các script shell qua kiểm tra cú pháp.

Chưa chạy lại Spark/Apple container đầu-cuối hoặc bộ mô phỏng 12 kịch bản trong
lần kiểm tra này. Không dùng các kết quả lightweight để suy ra các đường đó đã PASS.

`make simulate` chạy bộ mô phỏng gồm thứ tự notebook, chạy lại, thiếu dữ liệu,
thư mục làm việc, chạy đồng thời, offline, tải CPU, thực thi `.ipynb`, clean,
Python 3.10 và pip. Bộ này cần môi trường Unix/WSL, `rsync` và `uv`;
`SIM_FAST=1 make simulate` bỏ hai kịch bản dựng venv.

---

© VinUniversity AICB program. Tài liệu được điều chỉnh cho K4-Track02-Day18.
