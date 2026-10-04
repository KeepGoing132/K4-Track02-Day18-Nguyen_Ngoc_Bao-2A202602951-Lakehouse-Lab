"""Local PoC: HMAC pseudonymization and file pruning from Delta min/max stats.

Run: .venv/Scripts/python.exe submission/bonus/poc/poc_demo.py
POC_HMAC_KEY supplies an optional test key; otherwise a fresh key is created
in memory. The regex demo covers emails and phones, not all PII. It does not
verify production throughput or legal compliance.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import re
import secrets
import shutil
import time
from pathlib import Path

import polars as pl
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get("LAKEHOUSE_ROOT", REPO_ROOT / "_lakehouse"))
POC_PATH = DATA_ROOT / "scratch" / "poc_observability"
KEY = os.environ.get("POC_HMAC_KEY", "").encode() or secrets.token_bytes(32)
EMAIL_REGEX = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")


def tokenize_pii(text: str, key: bytes = KEY) -> str:
    """Keyed HMAC-SHA256 tokens, stable for the same entity and key."""
    def replace(match, kind):
        digest = hmac.new(key, match.group(0).encode(), hashlib.sha256).hexdigest()[:32]
        return f"[PII_{kind}:{digest}]"
    text = EMAIL_REGEX.sub(lambda match: replace(match, "EMAIL"), text)
    return PHONE_REGEX.sub(lambda match: replace(match, "PHONE"), text)


def candidates(table: DeltaTable, tenant: str) -> tuple[int, int]:
    """Count active files whose recorded min/max ranges include the tenant."""
    stats = pa.table(table.get_add_actions(flatten=True)).to_pylist()
    for row in stats:
        assert row.get("min.tenant_id") is not None and row.get("max.tenant_id") is not None
    return len(stats), sum(row["min.tenant_id"] <= tenant <= row["max.tenant_id"]
                           for row in stats)


def main() -> None:
    # Clear only this demo's generated table below the repository's data root.
    POC_PATH.resolve().relative_to((REPO_ROOT / "_lakehouse").resolve())
    shutil.rmtree(POC_PATH, ignore_errors=True)
    rng = random.Random(42)
    tenants = [f"tenant_{i:04d}" for i in range(100)]
    models = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]
    sample = "alice@example.com phone 555-019-2831"
    masked = tokenize_pii(sample)
    expected_email = hmac.new(KEY, b"alice@example.com", hashlib.sha256).hexdigest()[:32]
    assert f"[PII_EMAIL:{expected_email}]" in masked
    assert masked == tokenize_pii(sample) and masked != tokenize_pii(sample, b"other-test-key")
    assert not EMAIL_REGEX.search(masked) and not PHONE_REGEX.search(masked)

    print("Step 1: HMAC-SHA256 pseudonymization and 50 streaming batches")
    for batch in range(50):
        records = []
        for i in range(1_000):
            raw = f"alice_{i}@example.com phone 555-019-2831: summarize document {i}"
            records.append({
                "request_id": f"req_{batch}_{i}", "tenant_id": rng.choice(tenants),
                "model": rng.choice(models), "prompt": tokenize_pii(raw),
                "latency_ms": rng.randint(150, 2500), "cost_usd": rng.uniform(0.0005, 0.02),
            })
        write_deltalake(POC_PATH, pl.DataFrame(records).to_arrow(),
                        mode="append" if batch else "overwrite")

    tenant = "tenant_0042"
    before = DeltaTable(POC_PATH)
    files_before, candidates_before = candidates(before, tenant)
    expected_ids = sorted(before.to_pyarrow_table(filters=[("tenant_id", "=", tenant)])
                          .column("request_id").to_pylist())
    print(f"Before clustering: {candidates_before}/{files_before} candidate files")
    # Small target for this small dataset; production uses 256 MB.
    before.optimize.compact(target_size=32 * 1024)
    before.optimize.z_order(["tenant_id"], target_size=32 * 1024)
    after = DeltaTable(POC_PATH)
    files_after, candidates_after = candidates(after, tenant)
    skip_rate = 1 - candidates_after / files_after
    start = time.perf_counter()
    result = after.to_pyarrow_table(filters=[("tenant_id", "=", tenant)])
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert sorted(result.column("request_id").to_pylist()) == expected_ids
    assert after.count() == 50_000
    assert candidates_before == files_before and candidates_after > 0
    assert skip_rate >= 0.90, f"File skipping {skip_rate:.1%} is below 90%"
    assert all(not EMAIL_REGEX.search(p) and not PHONE_REGEX.search(p)
               for p in after.to_pyarrow_table(columns=["prompt"]).column("prompt").to_pylist())
    metrics = {
        "rows": after.count(), "target_tenant": tenant,
        "files_before": files_before, "candidate_files_before": candidates_before,
        "files_after": files_after, "candidate_files_after": candidates_after,
        "skip_rate": skip_rate, "pruning_ratio": files_after / candidates_after,
        "matched_rows": result.num_rows, "query_ms": round(elapsed_ms, 2),
        "hmac_verified": True, "query_results_preserved": True,
        "measurement": "active-file min/max stats; not observed S3 GET requests",
    }
    print(json.dumps(metrics, indent=2))
    print("PASS: keyed tokens, >=90% file skipping, unchanged rows and query results")


if __name__ == "__main__":
    main()
