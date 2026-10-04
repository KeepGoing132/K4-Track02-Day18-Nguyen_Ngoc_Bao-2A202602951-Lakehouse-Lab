# Verification — 04/10/2026

Python 3.11.9, Windows, lightweight path; commands executed with this repository's `.venv`.

| Check | Actual result |
|---|---|
| `scripts/verify_lite.py` | 9/9 checks PASS |
| `python -m pytest -o addopts='' -q --basetemp=./.pytest_tmp/c` | 24 passed in 6.41s |
| `scripts/run_all.py` with `LAKEHOUSE_ROOT=<repo>/_lakehouse/c` | 8/8 PASS in 58.7s |
| `scripts/build_submission_artifacts.py --only 01_delta_basics` | Executed notebook saved; full initial commit JSON and actual schema failure retained |
| `submission/bonus/poc/poc_demo.py` | 50K rows; candidate files 50/50 before, 1/49 after; 97.96% skipping; identical 492 matching request IDs |
| Submission audit | 8 notebooks; every nonempty code cell executed; no error outputs; 8 result images |
| Bonus export | `ARCHITECTURE.pdf` has 6 A4 pages; all six rendered pages visually inspected |
| Reflection | 184 whitespace-separated words, within the 200-word limit |

## Reproduction on Windows PowerShell

Run from the repository root. The short generated-data path avoids legacy path-length limits in the Windows Arrow/Iceberg I/O stack.

```powershell
$env:PYTHONUTF8 = '1'
$env:LAKEHOUSE_ROOT = (Join-Path (Get-Location).Path '_lakehouse/c').Replace('\', '/')
./.venv/Scripts/python.exe scripts/verify_lite.py
./.venv/Scripts/python.exe -m pytest -o addopts='' -q --basetemp=./.pytest_tmp/c
./.venv/Scripts/python.exe scripts/run_all.py
```

Two earlier verification attempts used longer temporary paths and hit `WinError 3` when PyArrow created Iceberg metadata/data files. Shortening `--basetemp` and `LAKEHOUSE_ROOT` resolved those failures. No assertions were removed or thresholds lowered. The successful final notebook run started with a separate generated-data root; NB4/NB7 generated missing input data through their normal self-healing paths.

The notebook source and submission output for NB1 now include complete commit JSON. Its schema-enforcement flag records the actual exception and verifies that no new table version was committed. The NB1 image renders that executed output, with wrapping for readability; it is not a capture of a live terminal window.

The optional PDF exporter requires `requirements-artifacts.txt` and Windows Arial fonts; this export was run using the bundled document runtime. The PoC is local and does not establish production PII coverage, throughput, concurrency safety or legal compliance. Measured PoC details are in [POC_RESULTS.md](bonus/poc/POC_RESULTS.md).

Spark/Docker and Apple container paths were not rerun. The submitted path is lightweight for all eight notebooks. Classroom submission and deadline status must be confirmed through the coach's official channel; a GitHub PR by itself does not establish classroom receipt.
