"""PlantSpec Quickviewer demo — Cloud Run service for Alchemy iframe proxy."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "demo_results"
DEMO_HTML = ROOT / "static" / "demo.html"
SUMMARY_CSV = DATA_DIR / "summary_results.csv"
MANIFEST_JSON = DATA_DIR / "manifest.json"
PLOTS_DIR = DATA_DIR / "plots"
STEPWISE_DIR = DATA_DIR / "stepwise"

app = FastAPI(title="PlantSpec Quickviewer Demo", version="1.0.0")


def _load_summary_rows() -> list[dict]:
    if not SUMMARY_CSV.exists():
        return []
    with SUMMARY_CSV.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "ds-plantspec-quickviewer"}


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
async def demo_ui() -> HTMLResponse:
    if not DEMO_HTML.is_file():
        raise HTTPException(status_code=500, detail="Demo UI missing")
    return HTMLResponse(
        content=DEMO_HTML.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/summary")
async def demo_summary() -> dict:
    rows = _load_summary_rows()
    if not rows:
        raise HTTPException(status_code=404, detail="Demo results not found")

    manifest = {}
    if MANIFEST_JSON.exists():
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

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

    return {
        "title": "PlantSpec Quickviewer — Demo Analysis",
        "description": "Bundled Cabbage control vs test multispectral demo captures.",
        "manifest": manifest,
        "groups": by_group,
        "plots": sorted(p.name for p in PLOTS_DIR.glob("*.png")) if PLOTS_DIR.exists() else [],
        "stepwise": sorted(p.name for p in STEPWISE_DIR.glob("*.png")) if STEPWISE_DIR.exists() else [],
    }


@app.get("/api/plots/{filename}")
async def demo_plot(filename: str):
    path = PLOTS_DIR / filename
    if not path.is_file() or path.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/stepwise/{filename}")
async def demo_stepwise(filename: str):
    path = STEPWISE_DIR / filename
    if not path.is_file() or path.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail="Stepwise image not found")
    return FileResponse(path, media_type="image/png")
