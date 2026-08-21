"""Upload → discover captures → headless ROI analysis pipeline."""

from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from api.headless import ROOT, pq

JOBS_ROOT = ROOT / "api" / "job_runs"
MAX_UPLOAD_BYTES = int(__import__("os").getenv("PLANTSPEC_MAX_UPLOAD_MB", "250")) * 1024 * 1024


def _configure_workspace(job_root: Path) -> None:
    output = job_root / "output"
    pq.WORKSPACE = job_root
    pq.APP_OUT = output
    pq.RGB_DIR = output / "aligned_rgb_full"
    pq.CACHE_DIR = output / "band_cache"
    pq.MASK_CACHE_DIR = output / "plant_mask_cache"
    pq.STEP_DIR = output / "stepwise"
    pq.PLOT_DIR = output / "results_plot"
    pq.CSV_DIR = output / "results_csv"
    pq.SAMPLES_JSON = output / "samples.json"
    pq.ensure_dirs()


def _build_samples(input_dir: Path) -> list[dict]:
    captures = pq.discover_captures(input_dir)
    if not captures:
        raise ValueError(
            "No valid multispectral captures found. Each folder needs "
            "blue/green/red/nir/rededge/thermal bands (or MicaSense IMG_*_1..7 files)."
        )

    samples: list[dict] = []
    sample_numbers: dict[tuple[str, str], int] = {}
    full_roi = {"type": "rect", "coords": [0.0, 0.0, 1.0, 1.0]}

    for cap in sorted(captures, key=lambda c: (c["source_crop"], c["source_group"], c["capture_id"])):
        key = (cap["source_crop"], cap["source_group"])
        sample_numbers[key] = sample_numbers.get(key, 0) + 1
        samples.append(
            {
                "plant": cap["source_crop"],
                "group": cap["source_group"],
                "sample_number": str(sample_numbers[key]),
                "capture_id": cap["capture_id"],
                "source_crop": cap["source_crop"],
                "source_group": cap["source_group"],
                "roi": full_roi,
                "mode": "plant_area",
                "grid_rows": 3,
                "grid_cols": 3,
                "mask_method": "green_exg_auto",
                "mask_threshold": 0.45,
                "mask_workflow": "full_image_mask_then_roi_intersection",
                "files": cap["files"],
            }
        )
    return samples


def _write_status(job_dir: Path, payload: dict) -> None:
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    (job_dir / "status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def create_job() -> str:
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    (job_dir / "input").mkdir()
    _write_status(
        job_dir,
        {
            "job_id": job_id,
            "status": "queued",
            "message": "Waiting for upload",
        },
    )
    return job_id


def job_dir(job_id: str) -> Path:
    path = JOBS_ROOT / job_id
    if not path.is_dir():
        raise FileNotFoundError(f"Job not found: {job_id}")
    return path


def read_status(job_id: str) -> dict:
    status_path = job_dir(job_id) / "status.json"
    if not status_path.is_file():
        raise FileNotFoundError(f"Job not found: {job_id}")
    return json.loads(status_path.read_text(encoding="utf-8"))


def save_upload_zip(job_id: str, data: bytes) -> None:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")

    path = job_dir(job_id)
    zip_path = path / "upload.zip"
    zip_path.write_bytes(data)

    input_dir = path / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir()

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(input_dir)
    except zipfile.BadZipFile as exc:
        raise ValueError("Upload must be a valid ZIP archive") from exc

    _write_status(
        path,
        {
            "job_id": job_id,
            "status": "uploaded",
            "message": "ZIP extracted; ready to analyze",
            "bytes": len(data),
        },
    )


def run_job_analysis(job_id: str) -> None:
    path = job_dir(job_id)
    input_dir = path / "input"

    _write_status(
        path,
        {"job_id": job_id, "status": "running", "message": "Discovering captures"},
    )

    try:
        _configure_workspace(path)
        samples = _build_samples(input_dir)
        pq.write_samples(samples)

        def progress(msg: str) -> None:
            _write_status(
                path,
                {
                    "job_id": job_id,
                    "status": "running",
                    "message": msg,
                    "samples": len(samples),
                },
            )

        run_out = pq.analyze_samples(samples, stepwise=True, progress=progress)
        summary_csv = run_out / "results_csv" / "summary_results.csv"
        if not summary_csv.is_file():
            raise RuntimeError("Analysis finished but summary_results.csv was not created")

        result_dir = path / "results"
        if result_dir.exists():
            shutil.rmtree(result_dir)
        shutil.copytree(run_out, result_dir)

        _write_status(
            path,
            {
                "job_id": job_id,
                "status": "complete",
                "message": f"Analyzed {len(samples)} capture(s)",
                "samples": len(samples),
                "groups": sorted({f"{s['plant']} / {s['group']}" for s in samples}),
                "result_dir": str(result_dir),
            },
        )
    except Exception as exc:
        _write_status(
            path,
            {
                "job_id": job_id,
                "status": "failed",
                "message": str(exc),
            },
        )
        raise


def result_paths(job_id: str) -> tuple[Path, Path, Path]:
    base = job_dir(job_id) / "results"
    return (
        base / "results_csv" / "summary_results.csv",
        base / "results_plot",
        base / "stepwise",
    )
