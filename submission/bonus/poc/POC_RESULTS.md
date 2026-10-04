# Local PoC execution evidence

Executed on 04/10/2026 with the repository Python 3.11 environment:

```powershell
$env:PYTHONUTF8 = '1'
$env:LAKEHOUSE_ROOT = (Join-Path (Get-Location).Path '_lakehouse/_completion_poc_20261004').Replace('\', '/')
./.venv/Scripts/python.exe submission/bonus/poc/poc_demo.py
```

```text
Before clustering: 50/50 candidate files
rows: 50000
files_before: 50
candidate_files_before: 50
files_after: 49
candidate_files_after: 1
skip_rate: 0.9795918367346939
pruning_ratio: 49.0
matched_rows: 492
query_ms: 27.04
hmac_verified: true
query_results_preserved: true
PASS: keyed tokens, >=90% file skipping, unchanged rows and query results
```

The script checks HMAC against an independently computed keyed digest, stable tokens for the same key, and different tokens for a different key. It verifies generated email/phone fixtures are masked, 50K rows survive optimization, and the same sorted request IDs match the tenant query before/after.

Candidate counts use active Delta file min/max statistics. This does not measure S3 GET requests, concurrent maintenance, production PII detection, retention safety or throughput at 1B requests/day. Query time varies by machine/cache. A fresh in-memory HMAC key is generated per run unless a test key is supplied through `POC_HMAC_KEY`; no key is saved in the evidence.
