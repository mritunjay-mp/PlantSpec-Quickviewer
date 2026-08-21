"""Build API summary payloads from CSV + artifact folders."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_summary_rows(summary_csv: Path) -> list[dict]:
    if not summary_csv.is_file():
        return []
    with summary_csv.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def build_summary_payload(
    *,
    title: str,
    description: str,
    summary_csv: Path,
    plots_dir: Path | None = None,
    stepwise_dir: Path | None = None,
    manifest: dict | None = None,
    job_id: str | None = None,
    api_prefix: str = "/api",
) -> dict:
    rows = load_summary_rows(summary_csv)
    if not rows:
        raise FileNotFoundError("Summary results not found")

    by_group: dict[str, list[dict]] = {}
    for row in rows:
        key = f"{row['plant']} / {row['group']}"
        by_group.setdefault(key, []).append(
            {
                "index": row["index"],
                "mean": float(row["mean"]) if row.get("mean") else None,
                "median": float(row["median"]) if row.get("median") else None,
                "samples": int(float(row["samples"])) if row.get("samples") else None,
            }
        )

    plots: list[str] = []
    stepwise: list[str] = []
    if plots_dir and plots_dir.is_dir():
        plots = sorted(p.name for p in plots_dir.glob("*.png"))
    if stepwise_dir and stepwise_dir.is_dir():
        stepwise = sorted(p.name for p in stepwise_dir.glob("*.png"))

    if job_id:
        plot_base = f"{api_prefix}/jobs/{job_id}/plots"
        stepwise_base = f"{api_prefix}/jobs/{job_id}/stepwise"
    else:
        plot_base = f"{api_prefix}/plots"
        stepwise_base = f"{api_prefix}/stepwise"

    return {
        "title": title,
        "description": description,
        "manifest": manifest or {},
        "job_id": job_id,
        "groups": by_group,
        "plots": plots,
        "stepwise": stepwise,
        "plot_urls": [f"{plot_base}/{name}" for name in plots],
        "stepwise_urls": [f"{stepwise_base}/{name}" for name in stepwise],
    }


def load_manifest(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
