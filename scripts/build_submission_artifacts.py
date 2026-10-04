"""Build submission notebooks and generate high-fidelity result screenshots.

1. Converts notebooks/[0-9]*.py to notebooks/[0-9]*.ipynb using jupytext.
2. Executes each notebook using nbconvert with the day18 kernel.
3. Saves the executed notebooks with all outputs preserved into submission/notebooks/.
4. Generates terminal/notebook output cards and screenshots in submission/screenshots/.
"""
from __future__ import annotations

import json
import argparse
import os
import re
import subprocess
import sys
import time
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parents[1]
NB_SRC_DIR = ROOT / "notebooks"
SUB_NB_DIR = ROOT / "submission" / "notebooks"
SUB_IMG_DIR = ROOT / "submission" / "screenshots"

SUB_NB_DIR.mkdir(parents=True, exist_ok=True)
SUB_IMG_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = sys.executable

def convert_and_execute(nb_path: Path) -> Path:
    stem = nb_path.stem
    target_ipynb = NB_SRC_DIR / f"{stem}.ipynb"
    dest_ipynb = SUB_NB_DIR / f"{stem}.ipynb"

    print(f"\n=======================================================")
    print(f"Processing {stem} ...")
    print(f"=======================================================")

    # 1. Convert via jupytext
    cmd_jupytext = [PYTHON_EXE, "-m", "jupytext", "--to", "notebook", str(nb_path)]
    subprocess.run(cmd_jupytext, check=True, cwd=str(ROOT))

    # 2. Execute via nbconvert
    cmd_execute = [
        PYTHON_EXE, "-m", "jupyter", "nbconvert",
        "--to", "notebook",
        "--execute",
        "--ExecutePreprocessor.kernel_name=day18",
        "--ExecutePreprocessor.timeout=600",
        str(target_ipynb),
        "--output", dest_ipynb.name,
        "--output-dir", str(SUB_NB_DIR),
    ]
    print(f"Executing {target_ipynb.name} ...")
    t0 = time.perf_counter()
    res = subprocess.run(cmd_execute, capture_output=True, text=True, cwd=str(ROOT))
    dt = time.perf_counter() - t0
    if res.returncode != 0:
        print(f"FAILED executing {stem} after {dt:.1f}s!")
        print("STDOUT:\n", res.stdout[-2000:])
        print("STDERR:\n", res.stderr[-2000:])
        raise RuntimeError(f"Failed to execute {stem}")
    print(f"Successfully executed and saved to {dest_ipynb} in {dt:.1f}s")
    return dest_ipynb


def extract_cell_outputs(ipynb_path: Path) -> list[str]:
    with open(ipynb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    outputs = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            cell_out = []
            for out in cell.get("outputs", []):
                if out.get("output_type") == "stream":
                    text = out.get("text", "")
                    if isinstance(text, list):
                        text = "".join(text)
                    cell_out.append(text)
                elif out.get("output_type") in ("execute_result", "display_data"):
                    data = out.get("data", {})
                    text = data.get("text/plain", "")
                    if isinstance(text, list):
                        text = "".join(text)
                    cell_out.append(text)
            if cell_out:
                outputs.append("".join(cell_out))
    return outputs


def render_terminal_screenshot(
    title: str,
    subtitle: str,
    content_lines: list[str],
    output_png: Path,
    width_px: int = 1200,
    height_px: int = 800,
):
    fig = plt.figure(figsize=(width_px / 100, height_px / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    # Dark background
    ax.fill([0, 1, 1, 0], [0, 0, 1, 1], color="#0f172a", transform=ax.transAxes)

    # Window titlebar
    title_height = 0.07
    title_rect = patches.Rectangle((0, 1 - title_height), 1, title_height,
                                   facecolor="#1e293b", edgecolor="#334155",
                                   linewidth=1, transform=ax.transAxes)
    ax.add_patch(title_rect)

    # Window dots
    ax.scatter([0.025, 0.045, 0.065], [1 - title_height/2, 1 - title_height/2, 1 - title_height/2],
               color=["#ef4444", "#f59e0b", "#10b981"], s=100, transform=ax.transAxes)

    # Title text
    ax.text(0.5, 1 - title_height/2, title,
            color="#e2e8f0", fontsize=13, fontweight="bold", fontfamily="sans-serif",
            ha="center", va="center", transform=ax.transAxes)

    # Subtitle bar
    sub_height = 0.05
    sub_rect = patches.Rectangle((0.02, 1 - title_height - sub_height), 0.96, sub_height,
                                 facecolor="#1e1e38", edgecolor="#475569",
                                 linewidth=0.5, transform=ax.transAxes)
    ax.add_patch(sub_rect)
    ax.text(0.04, 1 - title_height - sub_height/2, subtitle,
            color="#38bdf8", fontsize=11, fontweight="semibold", fontfamily="sans-serif",
            ha="left", va="center", transform=ax.transAxes)

    # Terminal output box
    y_start = 1 - title_height - sub_height - 0.03
    rendered_lines = [wrapped for line in content_lines
                      for wrapped in (textwrap.wrap(line, width=110,
                          replace_whitespace=False, drop_whitespace=False) or [""])]
    required_height = 160 + 19 * len(rendered_lines)
    if required_height > height_px:
        fig.set_size_inches(width_px / 100, required_height / 100)
    line_spacing = 0.79 / max(len(rendered_lines), 32)
    for i, line in enumerate(rendered_lines):
        y = y_start - (i * line_spacing)
        if y < 0.03:
            break

        # Color coding based on content
        color = "#cbd5e1"  # default light gray
        weight = "normal"
        if "[PASS]" in line or "✓" in line or "complete" in line.lower() or "success" in line.lower():
            color = "#4ade80"  # green
            weight = "bold"
        elif "[FAIL]" in line or "✗" in line or "error" in line.lower():
            color = "#f87171"  # red
            weight = "bold"
        elif "BLOCKED" in line or "expected" in line.lower():
            color = "#fbbf24"  # amber
            weight = "bold"
        elif line.startswith("#") or line.startswith("===") or line.startswith("---") or line.startswith("──"):
            color = "#94a3b8"  # slate
        elif "speedup" in line.lower() or "pruning" in line.lower() or "ratio" in line.lower():
            color = "#38bdf8"  # sky blue
            weight = "semibold"
        elif "files" in line.lower() or "rows" in line.lower() or "version" in line.lower():
            color = "#e2e8f0"

        # clean non-ascii / box chars safely if font doesn't have them
        clean_line = line.replace("\t", "    ")
        ax.text(0.035, y, clean_line,
                color=color, fontsize=9.5, fontweight=weight, fontfamily="monospace",
                ha="left", va="top", transform=ax.transAxes)

    plt.savefig(output_png, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"Generated screenshot: {output_png.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=[p.stem for p in NB_SRC_DIR.glob("[0-9]*.py")])
    args = parser.parse_args()
    py_notebooks = sorted(p for p in NB_SRC_DIR.glob("[0-9]*.py")
                          if args.only is None or p.stem == args.only)
    print(f"Found {len(py_notebooks)} notebooks to execute and package.")

    all_outputs = {}
    for nb in py_notebooks:
        ipynb = convert_and_execute(nb)
        all_outputs[nb.stem] = extract_cell_outputs(ipynb)

    if args.only:
        if args.only != "01_delta_basics":
            print("Notebook updated; run without --only to rebuild its overview image.")
            return
        nb1_lines = []
        for block in all_outputs[args.only]:
            if "Transaction log:" in block:
                nb1_lines.extend(block.splitlines())
            else:
                nb1_lines.extend(line for line in block.splitlines()
                                 if "BLOCKED" in line or "[PASS]" in line or "NB1 complete" in line)
        render_terminal_screenshot("NB1: Actual Delta Commit JSON & Schema Enforcement",
            "Executed notebook output | Complete initial commit | Wrapped for readability",
            nb1_lines, SUB_IMG_DIR / "nb01_delta_log.png", width_px=1400)
        return

    print("\nGenerating Rubric-compliant screenshots ...")

    # NB1 screenshot: delta_log, schema enforcement, evolution, duckdb
    nb1_lines = []
    nb1_lines.append("# Delta Table Initial Write & History Inspection")
    for block in all_outputs["01_delta_basics"]:
        if "Transaction log:" in block:
            nb1_lines.extend(block.splitlines())
            continue
        for line in block.splitlines():
            if any(k in line for k in ("shape:", "v0", "v1", "v2", "BLOCKED", "tier", "[PASS]", "NB1 complete")):
                nb1_lines.append(line)
    render_terminal_screenshot(
        "NB1: Delta Lake Basics — Schema Enforcement & Evolution",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Engine: deltalake 1.6.6",
        nb1_lines,
        SUB_IMG_DIR / "nb01_delta_log.png",
        height_px=820,
    )

    # NB2 screenshot: Small files, OPTIMIZE + Z-ORDER
    nb2_lines = []
    for block in all_outputs["02_optimize_zorder"]:
        for line in block.splitlines():
            if any(k in line for k in ("Files before", "BEFORE OPTIMIZE", "Files after", "AFTER OPTIMIZE", "Speedup", "File reduction", "Z-order deliverable", "[PASS]", "NB2 complete", "coverage", "contains target")):
                nb2_lines.append(line)
    render_terminal_screenshot(
        "NB2: Small-File Problem & OPTIMIZE + Z-ORDER",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Target User: 4242",
        nb2_lines,
        SUB_IMG_DIR / "nb02_optimize.png",
        height_px=820,
    )

    # NB3 screenshot: Time Travel + MERGE Upsert
    nb3_lines = []
    for block in all_outputs["03_time_travel"]:
        for line in block.splitlines():
            if any(k in line for k in ("MERGE 100K", "v0 row count", "v1 schema", "RESTORE", "Rows with score", "Total versions", "[PASS]", "NB3 complete", "v0", "v1", "v2", "v3", "v4")):
                nb3_lines.append(line)
    render_terminal_screenshot(
        "NB3: Time Travel & MERGE Upsert + RESTORE Rollback",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Audit Trail & Rollback",
        nb3_lines,
        SUB_IMG_DIR / "nb03_time_travel.png",
        height_px=820,
    )

    # NB4 screenshot: Medallion Architecture (Bronze -> Silver -> Gold)
    nb4_lines = []
    for block in all_outputs["04_medallion"]:
        for line in block.splitlines():
            if any(k in line for k in ("Bronze rows:", "Silver rows:", "shape:", "date", "claude-", "Distinct dates", "Distinct models", "Total Gold rows")):
                nb4_lines.append(line)
    render_terminal_screenshot(
        "NB4: Medallion Architecture (Bronze -> Silver -> Gold)",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | LLM Observability Metrics",
        nb4_lines,
        SUB_IMG_DIR / "nb04_medallion.png",
        height_px=850,
    )

    # NB5 screenshot: Iceberg & Catalog as Control Plane
    nb5_lines = []
    for block in all_outputs["05_iceberg_catalog"]:
        for line in block.splitlines():
            if any(k in line for k in ("Created lake.", "Partition spec:", "Rows:", "Snapshots:", "Files to read", "Pruning ratio:", "Tier 1", "Tier 2", "Tier 3", "metadata is", "latency_ms ->", "Partition specs in use", "[PASS]", "NB5 complete")):
                nb5_lines.append(line)
    render_terminal_screenshot(
        "NB5: Apache Iceberg & Catalog Control Plane",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Hidden Partitioning & Metadata Tree",
        nb5_lines,
        SUB_IMG_DIR / "nb05_iceberg_catalog.png",
        height_px=850,
    )

    # NB6 screenshot: Table Maintenance (4 mandatory jobs + checkpoint)
    nb6_lines = []
    for block in all_outputs["06_maintenance"]:
        for line in block.splitlines():
            if any(k in line for k in ("BASELINE", "AFTER compaction", "File reduction", "Point query user_id", "skip rate", "VACUUM", "Reclaimed", "Orphans found", "JSON log entries", "Checkpoint written", "snapshots:", "Stranded manifest", "[PASS]", "NB6 complete")):
                nb6_lines.append(line)
    render_terminal_screenshot(
        "NB6: Table Maintenance — 4 Mandatory Jobs & Checkpoint",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Compaction, Clustering, Expiry, Orphans",
        nb6_lines,
        SUB_IMG_DIR / "nb06_maintenance.png",
        height_px=850,
    )

    # NB7 screenshot: Multimodal & Vectors, Lifecycle Bug
    nb7_lines = []
    for block in all_outputs["07_vectors_multimodal"]:
        for line in block.splitlines():
            if any(k in line for k in ("Corpus:", "inline table", "pointer table", "amplification:", "recall@10", "topic fidelity", "storage saved", "Erased docs still", "CDF rows", "[PASS]", "NB7 complete", "VIOLATION")):
                nb7_lines.append(line)
    render_terminal_screenshot(
        "NB7: Multimodal Vectors & Lifecycle Skew Reproduction",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Quantization, SQL Search & CDF",
        nb7_lines,
        SUB_IMG_DIR / "nb07_vectors_multimodal.png",
        height_px=850,
    )

    # NB8 screenshot: Agents, MCP simulation & Provenance
    nb8_lines = []
    for block in all_outputs["08_agents_provenance"]:
        for line in block.splitlines():
            if any(k in line for k in ("Bronze trajectory", "Silver:", "policy-v2", "policy-v3", "run_id", "Replay at pinned", "Matches what training", "Actual catalog round-trips", "resultType: input_required", "submit_scan", "UNCLASSIFIED rows:", "Rows selected by", "Erasure request", "[PASS]", "NB8 complete")):
                nb8_lines.append(line)
    render_terminal_screenshot(
        "NB8: Agents as Consumers & Data Provenance Governance",
        "Repository: K4-Track02-Day18-Nguyen_Ngoc_Bao-2A202602951 | Trajectories, MCP Sim & Provenance",
        nb8_lines,
        SUB_IMG_DIR / "nb08_agents_provenance.png",
        height_px=850,
    )

    print("\nAll submission notebooks and screenshots generated successfully!")


if __name__ == "__main__":
    main()
