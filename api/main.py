"""PlantSpec Quickviewer — demo viewer + upload analysis pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from api.pipeline import create_job, job_dir, read_status, result_paths, run_job_analysis, save_upload_zip
from api.summary import build_summary_payload, load_manifest

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "demo_results"
DEMO_HTML = ROOT / "static" / "demo.html"
SUMMARY_CSV = DATA_DIR / "summary_results.csv"
MANIFEST_JSON = DATA_DIR / "manifest.json"
PLOTS_DIR = DATA_DIR / "plots"
STEPWISE_DIR = DATA_DIR / "stepwise"

app = FastAPI(title="PlantSpec Quickviewer", version="1.1.0")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "ds-plantspec-quickviewer", "features": ["demo", "upload"]}


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
    try:
        return build_summary_payload(
            title="PlantSpec Quickviewer — Demo Analysis",
            description="Bundled Cabbage control vs test multispectral demo captures.",
            summary_csv=SUMMARY_CSV,
            plots_dir=PLOTS_DIR if PLOTS_DIR.exists() else None,
            stepwise_dir=STEPWISE_DIR if STEPWISE_DIR.exists() else None,
            manifest=load_manifest(MANIFEST_JSON),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@app.post("/api/jobs/upload")
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict:
    """Upload a ZIP of multispectral capture folders and start headless analysis."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip file of capture folders")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    job_id = create_job()
    try:
        save_upload_zip(job_id, data)
    except ValueError as exc:
        shutil_rmtree_safe(job_dir(job_id))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(_run_job_safe, job_id)
    return {"job_id": job_id, "status": "running", "message": "Analysis started"}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str) -> dict:
    try:
        return read_status(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}/summary")
async def job_summary(job_id: str) -> dict:
    status = read_status(job_id)
    if status.get("status") != "complete":
        raise HTTPException(
            status_code=409,
            detail={"status": status.get("status"), "message": status.get("message", "Not ready")},
        )

    summary_csv, plots_dir, stepwise_dir = result_paths(job_id)
    try:
        return build_summary_payload(
            title="PlantSpec Quickviewer — Custom Analysis",
            description="ROI-based multispectral analysis for uploaded capture folders.",
            summary_csv=summary_csv,
            plots_dir=plots_dir,
            stepwise_dir=stepwise_dir,
            manifest={"job_id": job_id, "groups": status.get("groups", [])},
            job_id=job_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}/plots/{filename}")
async def job_plot(job_id: str, filename: str):
    _ensure_job_complete(job_id)
    _, plots_dir, _ = result_paths(job_id)
    path = plots_dir / filename
    if not path.is_file() or path.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/jobs/{job_id}/stepwise/{filename}")
async def job_stepwise(job_id: str, filename: str):
    _ensure_job_complete(job_id)
    _, _, stepwise_dir = result_paths(job_id)
    path = stepwise_dir / filename
    if not path.is_file() or path.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail="Stepwise image not found")
    return FileResponse(path, media_type="image/png")


def _ensure_job_complete(job_id: str) -> None:
    status = read_status(job_id)
    if status.get("status") != "complete":
        raise HTTPException(status_code=409, detail="Analysis not complete")


def _run_job_safe(job_id: str) -> None:
    try:
        run_job_analysis(job_id)
    except Exception:
        logger.exception("PlantSpec job %s failed", job_id)


def shutil_rmtree_safe(path: Path) -> None:
    import shutil

    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
