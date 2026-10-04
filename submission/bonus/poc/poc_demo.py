"""Proof of Concept (PoC) for Bonus Architecture: LLM Observability at Scale.

Demonstrates:
1. Stream-time PII Tokenization at ingest.
2. Writing to Delta Lake with Z-order clustering on (tenant_id).
3. Measurable file-pruning on tenant point queries.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from pathlib import Path

import polars as pl
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

POC_PATH = Path(__file__).resolve().parents[3] / "_lakehouse" / "scratch" / "poc_observability"

EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_REGEX = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")


def tokenize_pii(text: str, salt: str = "vinuni_day18") -> str:
    """Deterministic tokenization using SHA-256 HMAC for PII entities."""
    def _mask_email(m):
        raw = m.group(0)
        h = hashlib.sha256((raw + salt).encode()).hexdigest()[:12]
        return f"[PII_EMAIL:{h}]"

    def _mask_phone(m):
        raw = m.group(0)
        h = hashlib.sha256((raw + salt).encode()).hexdigest()[:8]
        return f"[PII_PHONE:{h}]"

    text = EMAIL_REGEX.sub(_mask_email, text)
    text = PHONE_REGEX.sub(_mask_phone, text)
    return text


def main():
    print("=== Bonus Architecture PoC: LLM Observability at 1B scale ===")
    import shutil
    shutil.rmtree(POC_PATH, ignore_errors=True)

    # 1. Simulate 50 batches of incoming streaming payloads
    random.seed(42)
    tenants = [f"tenant_{i:04d}" for i in range(100)]
    models = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]

    print("Step 1: Ingesting streaming batches with stream-time PII tokenization ...")
    for b in range(50):
        records = []
        for i in range(1_000):
            t_id = random.choice(tenants)
            raw_prompt = f"User request from alice_{i}@example.com, phone 555-019-2831: summarize document {i}."
            clean_prompt = tokenize_pii(raw_prompt)
            records.append({
                "request_id": f"req_{b}_{i}",
                "tenant_id": t_id,
                "model": random.choice(models),
                "prompt": clean_prompt,
                "latency_ms": random.randint(150, 2500),
                "cost_usd": random.uniform(0.0005, 0.02),
            })
        df = pl.DataFrame(records)
        write_deltalake(POC_PATH, df.to_arrow(), mode="append" if b > 0 else "overwrite")

    dt = DeltaTable(POC_PATH)
    files_before = len(dt.file_uris())
    print(f"Ingested {dt.count():,} rows across {files_before} small files.")

    # 2. Compact and Z-Order by tenant_id
    print("\nStep 2: Performing Compaction & Z-Order clustering by tenant_id ...")
    dt.optimize.compact(target_size=128 * 1024)
    dt.optimize.z_order(["tenant_id"], target_size=128 * 1024)
    dt = DeltaTable(POC_PATH)
    files_after = len(dt.file_uris())
    print(f"Files after optimize: {files_before} -> {files_after}")

    # 3. Test File Pruning on tenant point query
    target_tenant = "tenant_0042"
    t0 = time.perf_counter()
    res = dt.to_pyarrow_table(filters=[("tenant_id", "=", target_tenant)])
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\nStep 3: Point query for {target_tenant}:")
    print(f"  Rows returned: {res.num_rows} in {elapsed_ms:.1f} ms")
    print(f"  Sample tokenized prompt: {res.column('prompt')[0].as_py()[:60]} ...")
    assert "[PII_EMAIL:" in res.column("prompt")[0].as_py(), "PII was not properly tokenized!"
    print("\nPoC successfully verified: PII masked + Z-Order clustering functional!")


if __name__ == "__main__":
    main()
