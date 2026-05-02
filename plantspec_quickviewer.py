import json
import os
import re
import shutil
import time
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd
MPL_CONFIG_DIR = Path.cwd() / "paper_figure_outputs" / "plantspec_quickviewer" / "mpl_config"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont, ImageTk

import analyze_labeled_multispectral as base


WORKSPACE = Path.cwd()
APP_OUT = WORKSPACE / "paper_figure_outputs" / "plantspec_quickviewer"
RGB_DIR = APP_OUT / "aligned_rgb_full"
CACHE_DIR = APP_OUT / "band_cache"
MASK_CACHE_DIR = APP_OUT / "plant_mask_cache"
STEP_DIR = APP_OUT / "stepwise"
PLOT_DIR = APP_OUT / "results_plot"
CSV_DIR = APP_OUT / "results_csv"
SAMPLES_JSON = APP_OUT / "samples.json"
SAMPLE_REGION_CSV = CSV_DIR / "sample_region_metrics.csv"
SAMPLE_THERMAL_CSV = CSV_DIR / "sample_thermal_pixels.csv"
CONFIG_JSON = APP_OUT / "beginner_app_config.json"
ANALYSIS_VERSION = "matplotlib_plots_v3"
PLOT_INDICES = ["ExG", "NDVI", "GNDVI", "NDRE", "SAVI", "OSAVI", "CWSI", "Thermal_C"]
SUPPORTED_IMAGE_EXTS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}
SUPPORTED_ARRAY_EXTS = {".npy", ".npz"}
SUPPORTED_BAND_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_ARRAY_EXTS


def ensure_dirs():
    for path in (APP_OUT, RGB_DIR, CACHE_DIR, MASK_CACHE_DIR, STEP_DIR, PLOT_DIR, CSV_DIR):
        path.mkdir(parents=True, exist_ok=True)


BAND_ALIASES = {
    "blue": "1",
    "b": "1",
    "green": "2",
    "g": "2",
    "red": "3",
    "r": "3",
    "nir": "4",
    "nir1": "4",
    "rededge": "5",
    "red_edge": "5",
    "red-edge": "5",
    "re": "5",
    "thermal": "7",
    "lwir": "7",
    "temp": "7",
}
NPZ_BAND_ALIASES = BAND_ALIASES
REQUIRED_BANDS = {"1", "2", "3", "4", "5", "7"}


def capture_sets(label_dir):
    files = sorted([p for p in label_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_BAND_EXTS])
    caps = {}
    for file in files:
        m = re.match(r"(IMG_\d+)_([1-7])\.(tif|tiff|png|jpg|jpeg|bmp|npy)$", file.name, flags=re.IGNORECASE)
        if m:
            caps.setdefault(m.group(1), {})[m.group(2)] = file
    return {cid: group for cid, group in caps.items() if REQUIRED_BANDS.issubset(group)}


def npz_band_set(file):
    try:
        with np.load(file) as data:
            files = {}
            for key in data.files:
                band = NPZ_BAND_ALIASES.get(key.lower().replace(" ", "_"))
                if band:
                    files[band] = f"{file}::{key}"
            return files if REQUIRED_BANDS.issubset(files) else None
    except Exception:
        return None


def named_band_set(folder):
    files = {}
    for file in sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_BAND_EXTS]):
        if file.suffix.lower() == ".npz":
            bundled = npz_band_set(file)
            if bundled:
                return bundled
        key = BAND_ALIASES.get(file.stem.lower().replace(" ", "_"))
        if key:
            files[key] = file
    return files if REQUIRED_BANDS.issubset(files) else None


def infer_numbered_metadata(label_dir, root, capture_id):
    parts = label_dir.relative_to(root).parts
    if len(parts) >= 3 and parts[-2] == "000":
        return parts[-3], parts[-1], capture_id
    if len(parts) >= 2:
        return parts[-2], parts[-1], capture_id
    return label_dir.parent.name or "Plant", label_dir.name or "Group", capture_id


def infer_named_metadata(folder, root):
    name = folder.name
    match = re.match(r"(.+)_([^_]+)_(IMG_\d+)$", name, flags=re.IGNORECASE)
    if match:
        return match.group(1), match.group(2), match.group(3)
    parts = folder.relative_to(root).parts
    if len(parts) >= 3:
        return parts[-3], parts[-2], parts[-1]
    if len(parts) >= 2:
        return parts[-2], "Group", parts[-1]
    return "Plant", "Group", name


def discover_captures(root):
    captures = []
    root = Path(root)
    if not root.exists():
        return captures
    seen = set()
    folders = [root] if root.is_dir() and not root.name.startswith("_") else []
    folders.extend([p for p in root.rglob("*") if p.is_dir() and not p.name.startswith("_")])
    for folder in sorted(folders):
        named_files = named_band_set(folder)
        if named_files:
            crop, group, capture_id = infer_named_metadata(folder, root)
            key = (crop, group, capture_id, str(folder))
            if key not in seen:
                seen.add(key)
                captures.append(
                    {
                        "source_crop": crop,
                        "source_group": group,
                        "capture_id": capture_id,
                        "files": {str(k): str(v) for k, v in named_files.items()},
                        "display": f"{crop} | {group} | {capture_id}",
                    }
                )
        for capture_id, files in sorted(capture_sets(folder).items()):
            crop, group, capture_id = infer_numbered_metadata(folder, root, capture_id)
            key = (crop, group, capture_id, str(folder))
            if key in seen:
                continue
            seen.add(key)
            captures.append(
                {
                    "source_crop": crop,
                    "source_group": group,
                    "capture_id": capture_id,
                    "files": {str(k): str(v) for k, v in files.items()},
                    "display": f"{crop} | {group} | {capture_id}",
                }
            )
    return captures


def discover_captures_from_roots(roots):
    captures = []
    seen = set()
    for root in roots:
        for cap in discover_captures(root):
            key = (cap["source_crop"], cap["source_group"], cap["capture_id"], tuple(sorted(cap["files"].items())))
            if key in seen:
                continue
            seen.add(key)
            captures.append(cap)
    return captures


def dataset_report(roots):
    roots = [Path(r) for r in roots]
    valid = discover_captures_from_roots(roots)
    skipped = []
    for root in roots:
        folders = [root] if root.is_dir() else []
        folders.extend([p for p in root.rglob("*") if p.is_dir() and not p.name.startswith("_")])
        for folder in sorted(set(folders)):
            if named_band_set(folder) or capture_sets(folder):
                continue
            band_files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_BAND_EXTS])
            if not band_files:
                continue
            named_present = set()
            for f in band_files:
                if f.suffix.lower() == ".npz":
                    bundled = npz_band_set(f)
                    if bundled:
                        named_present.update(bundled.keys())
                named_present.add(BAND_ALIASES.get(f.stem.lower().replace(" ", "_")))
            numbered_present = set()
            for file in band_files:
                m = re.match(r"(IMG_\d+)_([1-7])\.(tif|tiff|png|jpg|jpeg|bmp|npy)$", file.name, flags=re.IGNORECASE)
                if m:
                    numbered_present.add(m.group(2))
            present = {x for x in named_present if x} | numbered_present
            missing = sorted(REQUIRED_BANDS - present)
            if missing:
                skipped.append({"folder": str(folder), "missing": ", ".join(missing)})
    return valid, skipped


def format_dataset_report(captures, skipped):
    lines = [f"Valid captures found: {len(captures)}"]
    if captures:
        groups = {}
        for cap in captures:
            key = f"{cap['source_crop']} / {cap['source_group']}"
            groups[key] = groups.get(key, 0) + 1
        lines.append("")
        lines.append("Capture groups:")
        lines.extend(f"- {key}: {count}" for key, count in sorted(groups.items()))
    if skipped:
        lines.append("")
        lines.append("Skipped folders with missing required bands:")
        for item in skipped[:20]:
            lines.append(f"- {item['folder']}: missing bands {item['missing']}")
        if len(skipped) > 20:
            lines.append(f"- ... {len(skipped) - 20} more")
    return "\n".join(lines)


def load_band(path, target_shape=None):
    path = str(path)
    npz_key = None
    if "::" in path:
        path, npz_key = path.split("::", 1)
    file = Path(path)
    suffix = file.suffix.lower()
    if suffix == ".npy":
        arr = np.asarray(np.load(file), dtype=np.float32)
    elif suffix == ".npz":
        with np.load(file) as data:
            key = npz_key or data.files[0]
            arr = np.asarray(data[key], dtype=np.float32)
    else:
        arr = np.asarray(Image.open(file), dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[..., 0]
    if target_shape and arr.shape != target_shape:
        img = Image.fromarray(arr)
        img = img.resize((target_shape[1], target_shape[0]), Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.float32).copy()
    arr[arr <= 0] = np.nan
    return arr


def align_full_bands(files):
    green = load_band(files["2"])
    aligned = {"green": green}
    raw = {"green": green}
    shifts = {"green": (0, 0)}
    mapping = {"1": "blue", "3": "red", "4": "nir", "5": "red_edge", "7": "thermal"}
    for key, name in mapping.items():
        arr = load_band(files[key], target_shape=green.shape)
        raw[name] = arr
        shift = base.estimate_shift(green, arr, max_shift=80 if name != "thermal" else 120)
        aligned[name] = base.shift_with_nan(arr, *shift)
        shifts[name] = shift
    return raw, aligned, shifts


def capture_cache_key(sample_or_capture):
    if all(k in sample_or_capture for k in ("source_crop", "source_group", "capture_id")):
        stem = f"{sample_or_capture['source_crop']}_{sample_or_capture['source_group']}_{sample_or_capture['capture_id']}"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)
    files = sample_or_capture["files"]
    first = Path(files["1"])
    stem = f"{first.parent.parent.parent.name}_{first.parent.name}_{Path(files['1']).stem.rsplit('_', 1)[0]}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)


def load_or_create_aligned_bands(sample_or_capture, progress=None):
    ensure_dirs()
    key = capture_cache_key(sample_or_capture)
    cache_path = CACHE_DIR / f"{key}_aligned_bands.npz"
    if cache_path.exists():
        data = np.load(cache_path)
        aligned = {name: data[name] for name in ["blue", "green", "red", "nir", "red_edge", "thermal"]}
        if progress:
            progress(f"Loaded cached aligned bands: {key}")
        return aligned
    if progress:
        progress(f"Creating aligned band cache: {key}")
    _, aligned, _shifts = align_full_bands(sample_or_capture["files"])
    np.savez_compressed(cache_path, **aligned)
    return aligned


def rgb_from_bands(bands):
    rgb = np.dstack([base.stretch(bands["red"]), base.stretch(bands["green"]), base.stretch(bands["blue"])])
    return Image.fromarray(rgb, "RGB")


def make_full_rgb(capture):
    out = RGB_DIR / f"{capture['source_crop']}_{capture['source_group']}_{capture['capture_id']}_full_aligned_rgb.png"
    if not out.exists():
        aligned = load_or_create_aligned_bands(capture)
        rgb_from_bands(aligned).save(out)
    return out


def read_samples():
    if SAMPLES_JSON.exists():
        return json.loads(SAMPLES_JSON.read_text(encoding="utf-8"))
    return []


def write_samples(samples):
    SAMPLES_JSON.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")


def read_config():
    if CONFIG_JSON.exists():
        try:
            return json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def write_config(config):
    ensure_dirs()
    CONFIG_JSON.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_key(sample):
    return f"{sample.get('plant')}||{sample.get('group')}||{sample.get('sample_number')}||{sample.get('capture_id')}"


def sample_signature(sample):
    data = {
        "analysis_version": ANALYSIS_VERSION,
        "sample_key": sample_key(sample),
        "roi": sample.get("roi"),
        "mode": sample.get("mode"),
        "grid_rows": sample.get("grid_rows"),
        "grid_cols": sample.get("grid_cols"),
        "mask_method": sample.get("mask_method"),
        "mask_threshold": sample.get("mask_threshold"),
        "files": {str(k): str(v) for k, v in sample.get("files", {}).items()},
    }
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def sample_metrics_current(sample):
    if not SAMPLE_REGION_CSV.exists() or not SAMPLE_THERMAL_CSV.exists():
        return False
    try:
        df = pd.read_csv(SAMPLE_REGION_CSV, usecols=lambda col: col in {"sample_key", "sample_signature"})
    except Exception:
        return False
    if "sample_key" not in df.columns or "sample_signature" not in df.columns:
        return False
    rows = df[df["sample_key"] == sample_key(sample)]
    return bool(len(rows)) and rows["sample_signature"].eq(sample_signature(sample)).all()


def remove_existing_sample_rows(csv_path, sample):
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if "sample_key" not in df.columns:
        return df
    return df[df["sample_key"] != sample_key(sample)].copy()


def update_sample_csv(csv_path, rows, sample):
    old = remove_existing_sample_rows(csv_path, sample)
    new = pd.DataFrame(rows)
    out = pd.concat([old, new], ignore_index=True) if not old.empty else new
    out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return out


def sample_prefix(sample):
    return f"{sample['plant']}_{sample['group']}_S{sample['sample_number']}_{sample['capture_id']}"


def stepwise_png_path(sample):
    return STEP_DIR / f"{sample_prefix(sample)}_stepwise.png"


def delete_sample_csv_rows(sample):
    for csv_path in [SAMPLE_REGION_CSV, SAMPLE_THERMAL_CSV]:
        if not csv_path.exists():
            continue
        df = remove_existing_sample_rows(csv_path, sample)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")


def clear_sample_metric_csvs():
    for csv_path in [SAMPLE_REGION_CSV, SAMPLE_THERMAL_CSV]:
        if csv_path.exists():
            csv_path.unlink()


def shape_mask(spec, shape):
    h, w = shape
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    if spec["type"] == "rect":
        x0, y0, x1, y1 = spec["coords"]
        draw.rectangle([x0 * (w - 1), y0 * (h - 1), x1 * (w - 1), y1 * (h - 1)], fill=255)
    elif spec["type"] == "polygon":
        pts = [(x * (w - 1), y * (h - 1)) for x, y in spec["coords"]]
        draw.polygon(pts, fill=255)
    return np.asarray(img) > 0


def normalized_threshold(values, roi_mask, threshold):
    valid = roi_mask & np.isfinite(values)
    if valid.sum() == 0:
        return np.zeros_like(roi_mask, dtype=bool)
    vals = values[valid]
    lo, hi = np.nanpercentile(vals, [2, 98])
    if hi <= lo:
        hi = lo + 1
    norm = np.clip((values - lo) / (hi - lo), 0, 1)
    return valid & (norm >= threshold)


def remove_isolated_fast(mask, min_neighbors=2):
    padded = np.pad(mask.astype(np.uint8), 1, mode="constant")
    neighbors = (
        padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
        + padded[1:-1, :-2] + padded[1:-1, 2:]
        + padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
    )
    return mask & (neighbors >= min_neighbors)


def fast_green_mask(blue, green, red):
    b = base.normalize_for_alignment(blue)
    g = base.normalize_for_alignment(green)
    r = base.normalize_for_alignment(red)
    exg = 2 * g - r - b
    threshold = base.otsu_threshold(exg)
    finite = np.isfinite(blue) & np.isfinite(green) & np.isfinite(red)
    valid_g = g[np.isfinite(g)]
    g_floor = np.nanpercentile(valid_g, 35) if valid_g.size else 0
    mask = finite & (exg > threshold) & (g > g_floor) & (g >= r * 0.92) & (g >= b * 0.92)
    return remove_isolated_fast(mask, min_neighbors=2)


def plant_mask_cache_key(sample_or_capture, method, threshold):
    stem = f"{capture_cache_key(sample_or_capture)}_{method}_{float(threshold):.3f}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)


def load_or_create_full_plant_mask(sample_or_capture, bands, method="green_exg_auto", threshold=0.45, progress=None):
    ensure_dirs()
    key = plant_mask_cache_key(sample_or_capture, method, threshold)
    cache_path = MASK_CACHE_DIR / f"{key}_plant_mask.npy"
    if cache_path.exists():
        if progress:
            progress(f"Loaded cached plant mask: {key}")
        return np.load(cache_path).astype(bool)
    if progress:
        progress(f"Creating plant mask cache: {key}")
    full_area = np.ones_like(bands["green"], dtype=bool)
    mask = plant_mask_roi(bands, full_area, method, threshold)
    np.save(cache_path, mask.astype(np.uint8))
    return mask


def plant_mask_roi(bands, roi_mask, method="green_exg_auto", threshold=0.45):
    if method == "green_norm":
        return normalized_threshold(bands["green"], roi_mask, threshold)
    if method == "exg_norm":
        blue = base.normalize_for_alignment(bands["blue"])
        green = base.normalize_for_alignment(bands["green"])
        red = base.normalize_for_alignment(bands["red"])
        exg = 2 * green - red - blue
        return normalized_threshold(exg, roi_mask, threshold)
    if method == "ndvi_norm":
        ndvi = base.safe_index(bands["nir"] - bands["red"], bands["nir"] + bands["red"])
        return normalized_threshold(ndvi, roi_mask, threshold)
    mask = fast_green_mask(bands["blue"], bands["green"], bands["red"])
    return mask & roi_mask


def green_mask_roi(bands, roi_mask):
    return plant_mask_roi(bands, roi_mask)


def thermal_to_celsius(raw):
    return raw / 100.0 - 273.15


def index_maps(bands):
    nir = bands["nir"]
    red = bands["red"]
    green = bands["green"]
    blue = bands["blue"]
    re = bands["red_edge"]
    thermal_c = thermal_to_celsius(bands["thermal"])
    exg = 2 * base.normalize_for_alignment(green) - base.normalize_for_alignment(red) - base.normalize_for_alignment(blue)
    return {
        "ExG": exg,
        "NDVI": base.safe_index(nir - red, nir + red),
        "GNDVI": base.safe_index(nir - green, nir + green),
        "NDRE": base.safe_index(nir - re, nir + re),
        "SAVI": 1.5 * base.safe_index(nir - red, nir + red + 0.5),
        "OSAVI": 1.16 * base.safe_index(nir - red, nir + red + 0.16),
        "Thermal_C": thermal_c,
    }


def region_masks(mask, mode, grid_rows=3, grid_cols=3):
    if mode == "plant_area":
        return [("plant_area", mask)]
    if mode == "object":
        labels, comps = base.connected_components(mask, min_area=max(60, int(mask.size * 0.0005)))
        regions = []
        for comp in comps:
            rid = int(comp["region_id"].split("_")[-1])
            regions.append((comp["region_id"], labels == rid))
        return regions or [("plant_area", mask)]
    if mode == "grid":
        h, w = mask.shape
        regions = []
        for gy in range(grid_rows):
            for gx in range(grid_cols):
                y0, y1 = int(h * gy / grid_rows), int(h * (gy + 1) / grid_rows)
                x0, x1 = int(w * gx / grid_cols), int(w * (gx + 1) / grid_cols)
                region = np.zeros_like(mask, dtype=bool)
                region[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
                if region.sum() > 0:
                    regions.append((f"grid_{gy + 1}_{gx + 1}", region))
        return regions
    return [("plant_area", mask)]


def compute_sample_rows(sample, stepwise=True, progress=None):
    if progress:
        progress(f"Computing sample {sample.get('group')}S{sample.get('sample_number')} {sample.get('capture_id')}")
    sig = sample_signature(sample)
    aligned = load_or_create_aligned_bands(sample, progress=progress)
    rgb = rgb_from_bands(aligned)
    roi_mask = shape_mask(sample["roi"], aligned["green"].shape)
    full_plant_mask = load_or_create_full_plant_mask(
        sample,
        aligned,
        sample.get("mask_method", "green_exg_auto"),
        float(sample.get("mask_threshold", 0.45)),
        progress=progress,
    )
    plant_mask = full_plant_mask & roi_mask
    maps = index_maps(aligned)
    thermal_vals = maps["Thermal_C"][plant_mask & np.isfinite(maps["Thermal_C"])]
    thermal_rows = [
        {
            "sample_key": sample_key(sample),
            "sample_signature": sig,
            "plant": sample["plant"],
            "group": sample["group"],
            "sample_number": sample["sample_number"],
            "capture_id": sample["capture_id"],
            "thermal_c": float(v),
        }
        for v in thermal_vals[:: max(1, int(len(thermal_vals) / 5000))]
    ]
    rows = []
    regions = region_masks(plant_mask, sample.get("mode", "plant_area"), sample.get("grid_rows", 3), sample.get("grid_cols", 3))
    for region_id, region_mask in regions:
        for index_name, arr in maps.items():
            st = base.stats(arr, region_mask)
            rows.append(
                {
                    "sample_key": sample_key(sample),
                    "sample_signature": sig,
                    "plant": sample["plant"],
                    "group": sample["group"],
                    "sample_number": sample["sample_number"],
                    "capture_id": sample["capture_id"],
                    "mode": sample.get("mode", "plant_area"),
                    "region_id": region_id,
                    "index": index_name,
                    "roi_area_px": int(roi_mask.sum()),
                    "plant_area_px": int(plant_mask.sum()),
                    "mask_method": sample.get("mask_method", "green_exg_auto"),
                    "mask_threshold": float(sample.get("mask_threshold", 0.45)),
                    **st,
                }
            )
    return rows, thermal_rows


def wetdry_refs_from_thermal_csv():
    thermal_df = pd.read_csv(SAMPLE_THERMAL_CSV) if SAMPLE_THERMAL_CSV.exists() else pd.DataFrame()
    refs = {}
    temp_limits = {}
    if thermal_df.empty:
        return refs, temp_limits
    for plant, vals in thermal_df.groupby("plant")["thermal_c"]:
        vals = vals.dropna()
        refs[plant] = {
            "wet_ref_c": float(np.nanpercentile(vals, 5)) if len(vals) else np.nan,
            "dry_ref_c": float(np.nanpercentile(vals, 95)) if len(vals) else np.nan,
        }
        temp_limits[plant] = (
            float(np.nanpercentile(vals, 2)) if len(vals) else np.nan,
            float(np.nanpercentile(vals, 98)) if len(vals) else np.nan,
        )
    return refs, temp_limits


def wetdry_refs_from_samples(samples, progress=None):
    refs = {}
    temp_limits = {}
    grouped = {}
    for sample in samples:
        if progress:
            progress(f"Collecting thermal refs: {sample.get('plant')} / {sample.get('group')}S{sample.get('sample_number')}")
        aligned = load_or_create_aligned_bands(sample, progress=progress)
        roi_mask = shape_mask(sample["roi"], aligned["green"].shape)
        full_plant_mask = load_or_create_full_plant_mask(
            sample,
            aligned,
            sample.get("mask_method", "green_exg_auto"),
            float(sample.get("mask_threshold", 0.45)),
            progress=progress,
        )
        plant_mask = full_plant_mask & roi_mask
        thermal = thermal_to_celsius(aligned["thermal"])
        vals = thermal[plant_mask & np.isfinite(thermal)]
        if vals.size:
            grouped.setdefault(sample["plant"], []).append(vals)
    for plant, chunks in grouped.items():
        vals = np.concatenate(chunks)
        refs[plant] = {
            "wet_ref_c": float(np.nanpercentile(vals, 5)),
            "dry_ref_c": float(np.nanpercentile(vals, 95)),
        }
        temp_limits[plant] = (
            float(np.nanpercentile(vals, 2)),
            float(np.nanpercentile(vals, 98)),
        )
    return refs, temp_limits


def exact_cwsi_rows_from_samples(samples, refs, progress=None):
    rows = []
    for sample in samples:
        if progress:
            progress(f"Calculating pixelwise CWSI: {sample.get('plant')} / {sample.get('group')}S{sample.get('sample_number')}")
        aligned = load_or_create_aligned_bands(sample, progress=progress)
        roi_mask = shape_mask(sample["roi"], aligned["green"].shape)
        full_plant_mask = load_or_create_full_plant_mask(
            sample,
            aligned,
            sample.get("mask_method", "green_exg_auto"),
            float(sample.get("mask_threshold", 0.45)),
            progress=progress,
        )
        plant_mask = full_plant_mask & roi_mask
        maps = index_maps(aligned)
        ref = refs.get(sample["plant"], {"wet_ref_c": np.nan, "dry_ref_c": np.nan})
        wet, dry = ref["wet_ref_c"], ref["dry_ref_c"]
        cwsi = np.clip((maps["Thermal_C"] - wet) / (dry - wet), 0, 1) if np.isfinite(wet) and dry > wet else maps["Thermal_C"] * np.nan
        regions = region_masks(plant_mask, sample.get("mode", "plant_area"), sample.get("grid_rows", 3), sample.get("grid_cols", 3))
        for region_id, region_mask in regions:
            rows.append(
                {
                    "sample_key": sample_key(sample),
                    "sample_signature": sample_signature(sample),
                    "plant": sample["plant"],
                    "group": sample["group"],
                    "sample_number": sample["sample_number"],
                    "capture_id": sample["capture_id"],
                    "mode": sample.get("mode", "plant_area"),
                    "region_id": region_id,
                    "index": "CWSI",
                    "roi_area_px": int(roi_mask.sum()),
                    "plant_area_px": int(plant_mask.sum()),
                    "mask_method": sample.get("mask_method", "green_exg_auto"),
                    "mask_threshold": float(sample.get("mask_threshold", 0.45)),
                    "wet_ref_c": wet,
                    "dry_ref_c": dry,
                    **base.stats(cwsi, region_mask),
                }
            )
    return rows


def build_summary_from_incremental_csv(run_out=None, samples=None, refs=None, progress=None):
    if not SAMPLE_REGION_CSV.exists():
        raise ValueError("No sample metrics CSV found. Save at least one sample first.")
    region_df = pd.read_csv(SAMPLE_REGION_CSV)
    if refs is None:
        refs, _temp_limits = wetdry_refs_from_thermal_csv()
    cwsi_rows = exact_cwsi_rows_from_samples(samples, refs, progress=progress) if samples else []
    combined = pd.concat([region_df, pd.DataFrame(cwsi_rows)], ignore_index=True)
    summary = (
        combined.groupby(["plant", "group", "index"], as_index=False)
        .agg(samples=("sample_number", "nunique"), mean=("mean", "mean"), sd=("mean", "std"), median=("median", "median"))
    )
    if run_out:
        run_out = Path(run_out)
        out_csv_dir = run_out / "results_csv"
        out_csv_dir.mkdir(parents=True, exist_ok=True)
        combined.to_csv(out_csv_dir / "region_level_results.csv", index=False, encoding="utf-8-sig")
        summary.to_csv(out_csv_dir / "summary_results.csv", index=False, encoding="utf-8-sig")
        with pd.ExcelWriter(out_csv_dir / "full_roi_analysis_results.xlsx", engine="openpyxl") as writer:
            combined.to_excel(writer, sheet_name="region_level", index=False)
            summary.to_excel(writer, sheet_name="summary", index=False)
            pd.DataFrame([{**{"plant": k}, **v} for k, v in refs.items()]).to_excel(writer, sheet_name="wetdry_refs", index=False)
    return combined, summary


def mask_outside(img, mask, fill=(245, 245, 245)):
    arr = np.asarray(img).copy()
    arr[~mask] = fill
    return Image.fromarray(arr, "RGB")


def masked_heatmap(arr, mask, vmin=None, vmax=None):
    vals = arr[mask & np.isfinite(arr)]
    if vmin is None or vmax is None:
        if vals.size:
            vmin = float(np.nanpercentile(vals, 2)) if vmin is None else vmin
            vmax = float(np.nanpercentile(vals, 98)) if vmax is None else vmax
        else:
            vmin = 0 if vmin is None else vmin
            vmax = 1 if vmax is None else vmax
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmin, vmax = 0, 1
    masked = np.where(mask, arr, np.nan)
    img = base.heatmap(masked, vmin, vmax)
    return mask_outside(img, mask), float(vmin), float(vmax)


def make_step_panel(title, img, colorbar=None, size=(420, 315)):
    width, height = size
    title_h = 24
    bar_h = 34 if colorbar else 0
    body_h = height - title_h - bar_h
    body = img.resize((width, body_h))
    panel = Image.new("RGB", size, "white")
    panel.paste(body, (0, title_h))
    draw = ImageDraw.Draw(panel)
    draw.rectangle([0, 0, width, title_h], fill=(255, 255, 255))
    draw.text((6, 7), title, fill=(0, 0, 0), font=ImageFont.load_default())
    if colorbar:
        vmin, vmax = colorbar
        bar_y = title_h + body_h + 7
        bar_x0, bar_x1 = 55, width - 45
        grad = np.linspace(vmin, vmax, max(2, bar_x1 - bar_x0), dtype=np.float32)[None, :]
        grad_img = base.heatmap(np.repeat(grad, 12, axis=0), vmin, vmax)
        panel.paste(grad_img, (bar_x0, bar_y))
        draw.rectangle([bar_x0, bar_y, bar_x1 - 1, bar_y + 11], outline=(0, 0, 0))
        draw.text((6, bar_y - 1), f"{vmin:.2f}", fill=(0, 0, 0), font=ImageFont.load_default())
        draw.text((bar_x1 + 5, bar_y - 1), f"{vmax:.2f}", fill=(0, 0, 0), font=ImageFont.load_default())
    return panel


def save_stepwise(sample, rgb, roi_mask, full_plant_mask, plant_mask, maps, cwsi, temp_limits):
    rgb_arr = np.asarray(rgb).copy()
    plant_overlay = np.zeros_like(rgb_arr)
    plant_overlay[full_plant_mask] = rgb_arr[full_plant_mask]
    roi_overlay = np.zeros_like(rgb_arr)
    roi_overlay[roi_mask] = rgb_arr[roi_mask]
    roi_overlay[plant_mask] = (0.45 * roi_overlay[plant_mask] + 0.55 * np.array([30, 220, 80])).astype(np.uint8)
    roi_outline = Image.fromarray(roi_overlay, "RGB")
    d = ImageDraw.Draw(roi_outline)
    if sample["roi"]["type"] == "rect":
        h, w = roi_mask.shape
        x0, y0, x1, y1 = sample["roi"]["coords"]
        d.rectangle([x0 * (w - 1), y0 * (h - 1), x1 * (w - 1), y1 * (h - 1)], outline=(255, 210, 0), width=5)
    panels = [
        ("01 RGB", rgb, None),
        ("02 Plant Mask", Image.fromarray(plant_overlay, "RGB"), None),
        ("03 ROI + analyzed plant", roi_outline, None),
    ]
    for title, result in [
        ("04 ExG", masked_heatmap(maps["ExG"], plant_mask)),
        ("05 NDVI", masked_heatmap(maps["NDVI"], plant_mask, -0.2, 1.0)),
        ("06 GNDVI", masked_heatmap(maps["GNDVI"], plant_mask, -0.2, 1.0)),
        ("07 NDRE", masked_heatmap(maps["NDRE"], plant_mask, -0.2, 1.0)),
        ("08 SAVI", masked_heatmap(maps["SAVI"], plant_mask, -0.2, 1.0)),
        ("09 OSAVI", masked_heatmap(maps["OSAVI"], plant_mask, -0.2, 1.0)),
        ("10 CWSI", masked_heatmap(cwsi, plant_mask, 0, 1)),
        ("11 Thermal C", masked_heatmap(maps["Thermal_C"], plant_mask, temp_limits[0], temp_limits[1])),
    ]:
        img, vmin, vmax = result
        panels.append((title, img, (vmin, vmax)))
    thumbs = []
    for title, img, colorbar in panels:
        thumbs.append(make_step_panel(title, img, colorbar=colorbar))
    cols = 3
    rows = int(np.ceil(len(thumbs) / cols))
    canvas = Image.new("RGB", (cols * 420, rows * 315), "white")
    for i, im in enumerate(thumbs):
        canvas.paste(im, ((i % cols) * 420, (i // cols) * 315))
    out = stepwise_png_path(sample)
    canvas.save(out)
    return out


def save_final_stepwise(sample, refs, temp_limits, progress=None):
    if progress:
        progress(f"Creating final stepwise PNG: {sample.get('group')}S{sample.get('sample_number')}")
    aligned = load_or_create_aligned_bands(sample, progress=progress)
    rgb = rgb_from_bands(aligned)
    roi_mask = shape_mask(sample["roi"], aligned["green"].shape)
    full_plant_mask = load_or_create_full_plant_mask(
        sample,
        aligned,
        sample.get("mask_method", "green_exg_auto"),
        float(sample.get("mask_threshold", 0.45)),
        progress=progress,
    )
    plant_mask = full_plant_mask & roi_mask
    maps = index_maps(aligned)
    ref = refs.get(sample["plant"], {"wet_ref_c": np.nan, "dry_ref_c": np.nan})
    wet, dry = ref["wet_ref_c"], ref["dry_ref_c"]
    cwsi = np.clip((maps["Thermal_C"] - wet) / (dry - wet), 0, 1) if np.isfinite(wet) and dry > wet else maps["Thermal_C"] * np.nan
    limits = temp_limits.get(sample["plant"], (np.nan, np.nan))
    return save_stepwise(sample, rgb, roi_mask, full_plant_mask, plant_mask, maps, cwsi, limits)


def draw_barplot(summary, index_name, save_vector=False):
    data = summary[summary["index"] == index_name].copy()
    plants = list(data["plant"].dropna().drop_duplicates())
    groups = list(data["group"].dropna().drop_duplicates())
    out = PLOT_DIR / f"{index_name}_barplot.png"
    palette = ["#6F6F6F", "#2E8B57", "#3B6FB6", "#C47A2C", "#8D559C", "#BF4D4D"]
    label_map = {
        "ExG": "Excess Green (ExG)",
        "NDVI": "NDVI",
        "GNDVI": "GNDVI",
        "NDRE": "NDRE",
        "SAVI": "SAVI",
        "OSAVI": "OSAVI",
        "CWSI": "CWSI",
        "Thermal_C": "Thermal temperature (C)",
    }

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "axes.linewidth": 0.9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig_w = max(4.8, 1.05 * max(len(plants), 1) + 1.8)
    fig, ax = plt.subplots(figsize=(fig_w, 3.7))

    if data.empty or not plants or not groups:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()
    else:
        x = np.arange(len(plants), dtype=float)
        bar_width = min(0.36 / max(len(groups), 1), 0.16)
        for gi, group in enumerate(groups):
            means, sds = [], []
            for plant in plants:
                row = data[(data["plant"] == plant) & (data["group"] == group)]
                if row.empty:
                    means.append(np.nan)
                    sds.append(0.0)
                    continue
                rec = row.iloc[0]
                means.append(float(rec["mean"]) if pd.notna(rec["mean"]) else np.nan)
                sds.append(float(rec["sd"]) if pd.notna(rec["sd"]) else 0.0)
            offset = (gi - (len(groups) - 1) / 2) * bar_width * 1.25
            ax.bar(
                x + offset,
                means,
                width=bar_width,
                yerr=sds,
                capsize=3,
                color=palette[gi % len(palette)],
                edgecolor="black",
                linewidth=0.6,
                error_kw={"elinewidth": 0.8, "capthick": 0.8},
                label=str(group),
            )
        ax.set_xticks(x)
        ax.set_xticklabels(plants, rotation=0)
        ax.set_ylabel(label_map.get(index_name, index_name))
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if index_name == "CWSI":
            ax.set_ylim(0, 1)
        else:
            ax.margins(y=0.08)
        ax.set_xlim(-0.7, max(len(plants) - 1, 0) + 0.7)
        ax.legend(frameon=False, ncol=min(len(groups), 3), loc="upper center", bbox_to_anchor=(0.5, 1.04))

    fig.tight_layout(pad=0.8)
    fig.savefig(out, dpi=300)
    if save_vector:
        fig.savefig(PLOT_DIR / f"{index_name}_barplot.pdf")
        fig.savefig(PLOT_DIR / f"{index_name}_barplot.svg")
    plt.close(fig)
    return out


def make_plot_contact_sheet(paths):
    thumbs = []
    for path in paths:
        if not Path(path).exists():
            continue
        im = Image.open(path).convert("RGB")
        im.thumbnail((460, 270))
        canvas = Image.new("RGB", (460, 270), "white")
        canvas.paste(im, ((460 - im.width) // 2, (270 - im.height) // 2))
        thumbs.append(canvas)
    if not thumbs:
        return None
    cols = 2
    rows = int(np.ceil(len(thumbs) / cols))
    sheet = Image.new("RGB", (cols * 460, rows * 270), "white")
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * 460, (i // cols) * 270))
    out = PLOT_DIR / "all_indices_barplots.png"
    sheet.save(out)
    return out


def sample_preflight_text(samples):
    lines = [f"Samples to analyze: {len(samples)}"]
    group_counts = {}
    methods = {}
    modes = {}
    for sample in samples:
        group = str(sample.get("group", "Group"))
        group_counts[group] = group_counts.get(group, 0) + 1
        method = f"{sample.get('mask_method')} @ {float(sample.get('mask_threshold', 0)):.2f}"
        methods[method] = methods.get(method, 0) + 1
        mode = str(sample.get("mode", "plant_area"))
        modes[mode] = modes.get(mode, 0) + 1
    lines.append("")
    lines.append("By group:")
    lines.extend(f"- {k}: {v}" for k, v in sorted(group_counts.items()))
    lines.append("")
    lines.append("Mask methods:")
    lines.extend(f"- {k}: {v}" for k, v in sorted(methods.items()))
    lines.append("")
    lines.append("Modes:")
    lines.extend(f"- {k}: {v}" for k, v in sorted(modes.items()))
    lines.append("")
    lines.append("Continue?")
    return "\n".join(lines)


def write_result_helpers(out, samples, refs):
    out = Path(out)
    csv_dir = out / "results_csv"
    plot_dir = out / "results_plot"
    csv_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)
    readme = csv_dir / "README_results.txt"
    readme.write_text(
        "\n".join(
            [
                "ROI Multispectral Analysis Results",
                "",
                "Analysis target:",
                "- Each metric is calculated only from pixels that are both inside the saved ROI and inside the plant mask.",
                "- Plant mask is calculated on the full aligned image, then intersected with the ROI.",
                "",
                "CWSI:",
                "- Thermal_C = raw thermal pixel / 100 - 273.15",
                "- wet_ref_c = plant-level 5th percentile of ROI plant-pixel temperature",
                "- dry_ref_c = plant-level 95th percentile of ROI plant-pixel temperature",
                "- CWSI_pixel = clip((Thermal_C_pixel - wet_ref_c) / (dry_ref_c - wet_ref_c), 0, 1)",
                "",
                "Folders:",
                "- results_plot: Matplotlib bar plots as PNG plus all_indices_barplots.png",
                "- results_csv: CSV/XLSX outputs and method notes",
                "- stepwise: RGB, plant mask, ROI, index maps with colorbars",
                "",
                "Wet/dry references:",
            ]
            + [f"- {plant}: wet={vals.get('wet_ref_c'):.3f} C, dry={vals.get('dry_ref_c'):.3f} C" for plant, vals in sorted(refs.items())]
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            ["plant", "Plant/crop label saved for the ROI."],
            ["group", "Treatment/group label such as control or test."],
            ["sample_number", "User-entered sample number within each group."],
            ["capture_id", "Image capture identifier."],
            ["region_id", "plant_area, grid row/column, or object id depending on analysis mode."],
            ["index", "ExG, NDVI, GNDVI, NDRE, SAVI, OSAVI, Thermal_C, or CWSI."],
            ["n_px", "Number of ROI plant pixels used for the statistic."],
            ["mean", "Mean over ROI plant pixels."],
            ["sd", "Standard deviation over ROI plant pixels."],
            ["median", "Median over ROI plant pixels."],
            ["p10", "10th percentile over ROI plant pixels."],
            ["p90", "90th percentile over ROI plant pixels."],
            ["wet_ref_c", "Wet reference temperature for CWSI."],
            ["dry_ref_c", "Dry reference temperature for CWSI."],
        ],
        columns=["column", "description"],
    ).to_csv(csv_dir / "columns_description.csv", index=False, encoding="utf-8-sig")


def analyze_samples(samples, stepwise=True, progress=None):
    global APP_OUT, STEP_DIR, PLOT_DIR, CSV_DIR
    base_out = APP_OUT
    run_out = base_out / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    old_dirs = (APP_OUT, STEP_DIR, PLOT_DIR, CSV_DIR)
    APP_OUT = run_out
    STEP_DIR = run_out / "stepwise"
    PLOT_DIR = run_out / "results_plot"
    CSV_DIR = run_out / "results_csv"
    ensure_dirs()
    if progress:
        progress("0% Starting analysis. Cached captures will skip band alignment.")
    cache = {}
    prepared = []
    total_steps = max(1, len(samples) * 2 + 3)
    done_steps = 0
    for idx, sample in enumerate(samples, start=1):
        done_steps += 1
        if progress:
            pct = int(done_steps / total_steps * 100)
            progress(f"{pct}% [{idx}/{len(samples)}] Preparing {sample['plant']} / {sample['group']} / S{sample['sample_number']} / {sample['capture_id']}")
        key = json.dumps(sample["files"], sort_keys=True)
        if key not in cache:
            aligned = load_or_create_aligned_bands(sample, progress=progress)
            cache[key] = (aligned, rgb_from_bands(aligned))
        aligned, rgb = cache[key]
        roi_mask = shape_mask(sample["roi"], aligned["green"].shape)
        full_plant_mask = load_or_create_full_plant_mask(
            sample,
            aligned,
            sample.get("mask_method", "green_exg_auto"),
            float(sample.get("mask_threshold", 0.45)),
            progress=progress,
        )
        plant_mask = full_plant_mask & roi_mask
        maps = index_maps(aligned)
        prepared.append((sample, aligned, rgb, roi_mask, plant_mask, maps))

    if progress:
        done_steps += 1
        pct = int(done_steps / total_steps * 100)
        progress(f"{pct}% Calculating wet/dry references and temperature limits")
    refs = {}
    temp_limits = {}
    for plant in sorted({s["plant"] for s in samples}):
        vals = []
        for sample, _aligned, _rgb, _roi, plant_mask, maps in prepared:
            if sample["plant"] == plant:
                vals.append(maps["Thermal_C"][plant_mask & np.isfinite(maps["Thermal_C"])])
        vals = np.concatenate([v for v in vals if v.size]) if vals else np.array([])
        refs[plant] = {
            "wet_ref_c": float(np.nanpercentile(vals, 5)) if vals.size else np.nan,
            "dry_ref_c": float(np.nanpercentile(vals, 95)) if vals.size else np.nan,
        }
        temp_limits[plant] = (
            float(np.nanpercentile(vals, 2)) if vals.size else np.nan,
            float(np.nanpercentile(vals, 98)) if vals.size else np.nan,
        )

    rows = []
    for idx, (sample, aligned, rgb, roi_mask, plant_mask, maps) in enumerate(prepared, start=1):
        done_steps += 1
        if progress:
            pct = int(done_steps / total_steps * 100)
            progress(f"{pct}% [{idx}/{len(prepared)}] Analyzing {sample['plant']} / {sample['group']} / S{sample['sample_number']}")
        ref = refs[sample["plant"]]
        wet, dry = ref["wet_ref_c"], ref["dry_ref_c"]
        cwsi = np.clip((maps["Thermal_C"] - wet) / (dry - wet), 0, 1) if np.isfinite(wet) and dry > wet else maps["Thermal_C"] * np.nan
        all_maps = dict(maps)
        all_maps["CWSI"] = cwsi
        regions = region_masks(plant_mask, sample.get("mode", "plant_area"), sample.get("grid_rows", 3), sample.get("grid_cols", 3))
        for region_id, region_mask in regions:
            for index_name, arr in all_maps.items():
                st = base.stats(arr, region_mask)
                rows.append(
                    {
                        "plant": sample["plant"],
                        "group": sample["group"],
                        "sample_number": sample["sample_number"],
                        "capture_id": sample["capture_id"],
                        "mode": sample.get("mode", "plant_area"),
                        "region_id": region_id,
                        "index": index_name,
                        "wet_ref_c": wet,
                        "dry_ref_c": dry,
                        **st,
                    }
                )
        if stepwise:
            save_stepwise(sample, rgb, roi_mask, plant_mask, plant_mask, all_maps, cwsi, temp_limits[sample["plant"]])

    CSV_DIR.mkdir(parents=True, exist_ok=True)
    region_df = pd.DataFrame(rows)
    region_df.to_csv(CSV_DIR / "region_level_results.csv", index=False, encoding="utf-8-sig")
    summary = (
        region_df.groupby(["plant", "group", "index"], as_index=False)
        .agg(samples=("sample_number", "nunique"), mean=("mean", "mean"), sd=("mean", "std"), median=("median", "median"), wet_ref_c=("wet_ref_c", "first"), dry_ref_c=("dry_ref_c", "first"))
    )
    summary.to_csv(CSV_DIR / "summary_results.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(CSV_DIR / "full_roi_analysis_results.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["ROI", "User-drawn ROI on full aligned RGB; no automatic margin crop."],
                ["Plant mask", "Plant mask is calculated on the full aligned image first, then intersected with user ROI."],
                ["Thermal conversion", "Celsius = raw thermal pixel / 100 - 273.15"],
                ["Band alignment", "All bands are aligned to Green. Lower-resolution Thermal is first resized to Green resolution with bilinear interpolation, then translation-aligned by FFT phase correlation."],
                ["CWSI", "Plant-level wet/dry reference: p5/p95 by plant name across saved samples."],
            ],
            columns=["item", "note"],
        ).to_excel(writer, sheet_name="README", index=False)
        region_df.to_excel(writer, sheet_name="region_level", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        pd.DataFrame([{**{"plant": k}, **v} for k, v in refs.items()]).to_excel(writer, sheet_name="wetdry_refs", index=False)
    plot_paths = []
    for idx in PLOT_INDICES:
        if progress:
            progress(f"90% Creating plot: {idx}")
        plot_paths.append(draw_barplot(summary, idx))
    make_plot_contact_sheet(plot_paths)
    if progress:
        progress(f"100% Done. Results saved to {APP_OUT}")
    out = APP_OUT
    APP_OUT, STEP_DIR, PLOT_DIR, CSV_DIR = old_dirs
    return out


class FullRoiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PlantSpec Quickviewer")
        self.root.geometry("1360x860")
        ensure_dirs()
        self.config = read_config()
        self.micasense_root = None
        self.captures = []
        self.last_result_folder = Path(self.config["last_result_folder"]) if self.config.get("last_result_folder") else None
        self.index = 0
        self.image = None
        self.rgb_image = None
        self.photo = None
        self.scale = 1
        self.offset_x = 0
        self.offset_y = 0
        self.rect = None
        self.poly = []
        self.finished_poly = None
        self.start = None
        self.samples = read_samples()
        self.selected_sample_index = None
        self.saving_sample = False
        self.mask_preview_live = False
        self._mask_preview_after = None
        self._build()
        self.apply_saved_settings()
        self.meta.insert(
            tk.END,
            "Quick start\n"
            "1. Click Open Dataset Folder or Select Subfolders.\n"
            "2. Preview Plant Mask and tune Mask scroll.\n"
            "3. Draw ROI, enter Plant/Group/Sample, then Save Sample.\n"
            "4. Repeat ROIs, then Run Analysis.\n"
            "5. Use Open Last Result Folder to find results_plot, results_csv, and stepwise outputs.",
        )

    def _build(self):
        top = ttk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)
        ttk.Button(top, text="Open Dataset Folder", command=self.open_micasense_folder).pack(side=tk.LEFT)
        ttk.Button(top, text="Select Subfolders", command=self.open_selected_subfolders).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(top, text="Prev", command=lambda: self.load_capture(self.index - 1)).pack(side=tk.LEFT, padx=(10, 4))
        ttk.Button(top, text="Next", command=lambda: self.load_capture(self.index + 1)).pack(side=tk.LEFT)
        self.combo = ttk.Combobox(top, state="readonly", width=54, values=[c["display"] for c in self.captures])
        self.combo.pack(side=tk.LEFT, padx=8)
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self.load_capture(self.combo.current()))
        self.save_button = ttk.Button(top, text="Save Sample", command=self.save_sample)
        self.save_button.pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Precompute Band Cache", command=self.precompute_band_cache).pack(side=tk.LEFT)
        self.run_button = ttk.Button(top, text="Run Analysis", command=self.run_analysis)
        self.run_button.pack(side=tk.LEFT)
        ttk.Button(top, text="Clear ROI", command=self.clear_roi).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Open Last Result Folder", command=self.open_last_result_folder).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top, text="Reset Project", command=self.reset_project).pack(side=tk.LEFT, padx=4)

        body = ttk.Frame(self.root)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.canvas = tk.Canvas(body, bg="#111", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-1>", self.on_click, add="+")

        side = ttk.Frame(body, width=360)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        side.pack_propagate(False)
        ttk.Label(
            side,
            text="v2: Mask method + Threshold + Analysis tab",
            foreground="#2d7d46",
        ).pack(anchor=tk.W, pady=(0, 8))
        self.draw_type = tk.StringVar(value="rect")
        self.mode = tk.StringVar(value="plant_area")
        self.plant = tk.StringVar()
        self.group = tk.StringVar()
        self.sample_number = tk.StringVar(value="1")
        self.grid_rows = tk.IntVar(value=3)
        self.grid_cols = tk.IntVar(value=3)
        self.mask_method = tk.StringVar(value="green_exg_auto")
        self.mask_threshold = tk.DoubleVar(value=0.45)
        self.total_samples_var = tk.StringVar()
        self.group_samples_var = tk.StringVar()
        self.stepwise = tk.BooleanVar(value=True)
        self.group.trace_add("write", lambda *_: self.update_next_sample_number())
        self._combo_field(side, "Draw", self.draw_type, ["rect", "polygon"])
        self._entry_field(side, "Plant name", self.plant)
        self._entry_field(side, "Group name", self.group)
        self._entry_field(side, "Sample no.", self.sample_number)
        self._combo_field(side, "Mode", self.mode, ["plant_area", "object", "grid"])
        self._combo_field(side, "Mask method", self.mask_method, ["green_exg_auto", "green_norm", "exg_norm", "ndvi_norm"])
        self._spin_field(side, "Threshold", self.mask_threshold, 0.0, 1.0, 0.05)
        self.mask_threshold.trace_add("write", lambda *_: self.schedule_live_mask_preview())
        self.mask_method.trace_add("write", lambda *_: self.schedule_live_mask_preview())
        self._scale_field(side, "Mask scroll", self.mask_threshold, 0.0, 1.0)
        self._spin_field(side, "Grid rows", self.grid_rows, 1, 20, 1)
        self._spin_field(side, "Grid cols", self.grid_cols, 1, 20, 1)
        ttk.Checkbutton(side, text="Save stepwise images", variable=self.stepwise).pack(anchor=tk.W, pady=6)
        mask_buttons = ttk.Frame(side)
        mask_buttons.pack(fill=tk.X, pady=(4, 6))
        ttk.Button(mask_buttons, text="Preview Plant Mask", command=self.preview_current_plant_mask).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(mask_buttons, text="Show RGB", command=self.show_current_rgb).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Button(side, text="Finish Polygon", command=self.finish_polygon).pack(fill=tk.X, pady=(6, 4))
        ttk.Label(side, textvariable=self.total_samples_var, foreground="#333").pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(side, textvariable=self.group_samples_var, foreground="#333").pack(anchor=tk.W)
        list_frame = ttk.Frame(side)
        list_frame.pack(fill=tk.X, pady=(4, 6))
        self.sample_list = tk.Listbox(list_frame, height=5)
        self.sample_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.sample_list.bind("<<ListboxSelect>>", self.on_sample_select)
        list_buttons = ttk.Frame(list_frame)
        list_buttons.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
        ttk.Button(list_buttons, text="Go", command=self.goto_selected_sample).pack(fill=tk.X)
        ttk.Button(list_buttons, text="Delete", command=self.delete_selected_sample).pack(fill=tk.X, pady=(4, 0))
        ttk.Button(list_buttons, text="Clear All", command=self.clear_all_samples).pack(fill=tk.X, pady=(4, 0))
        self.meta = tk.Text(side, height=6)
        self.meta.pack(fill=tk.X, pady=8)
        self.tabs = ttk.Notebook(side)
        self.tabs.pack(fill=tk.BOTH, expand=True)
        self.preview = tk.Text(self.tabs, height=16)
        self.analysis_frame = ttk.Frame(self.tabs)
        self.progress_value = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.analysis_frame, maximum=100, variable=self.progress_value)
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))
        self.analysis_log = tk.Text(self.analysis_frame, height=12)
        self.analysis_log.pack(fill=tk.BOTH, expand=True)
        self.plot_label = ttk.Label(self.analysis_frame)
        self.plot_label.pack(fill=tk.X, pady=(6, 0))
        self.plot_photo = None
        self.tabs.add(self.preview, text="Sample JSON")
        self.tabs.add(self.analysis_frame, text="Analysis")
        self.update_sample_panel()

    def _field(self, parent, label, widget):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        widget.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _entry_field(self, parent, label, variable):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _combo_field(self, parent, label, variable, values):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=variable, state="readonly", values=values).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _spin_field(self, parent, label, variable, from_, to, increment):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        ttk.Spinbox(row, from_=from_, to=to, increment=increment, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _scale_field(self, parent, label, variable, from_, to):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        ttk.Scale(row, from_=from_, to=to, variable=variable, orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def apply_saved_settings(self):
        if self.config.get("mask_method"):
            self.mask_method.set(self.config["mask_method"])
        if self.config.get("mode"):
            self.mode.set(self.config["mode"])
        if "mask_threshold" in self.config:
            try:
                self.mask_threshold.set(float(self.config["mask_threshold"]))
            except (TypeError, ValueError):
                pass

    def save_current_settings(self):
        self.config["mask_method"] = self.mask_method.get()
        self.config["mask_threshold"] = float(self.mask_threshold.get())
        self.config["mode"] = self.mode.get()
        if self.micasense_root:
            self.config["last_dataset_parent"] = str(self.micasense_root)
        if self.last_result_folder:
            self.config["last_result_folder"] = str(self.last_result_folder)
        write_config(self.config)

    def sample_display_id(self, sample):
        group = str(sample.get("group", "Group")).strip() or "Group"
        num = str(sample.get("sample_number", "?")).strip() or "?"
        return f"{group}S{num}"

    def next_group_sample_number(self, group):
        nums = []
        for sample in self.samples:
            if str(sample.get("group", "")).strip() == str(group).strip():
                try:
                    nums.append(int(sample.get("sample_number", 0)))
                except (TypeError, ValueError):
                    pass
        return str(max(nums, default=0) + 1)

    def update_next_sample_number(self):
        if not hasattr(self, "sample_number"):
            return
        group = self.group.get().strip()
        if group:
            self.sample_number.set(self.next_group_sample_number(group))

    def update_sample_panel(self):
        if not hasattr(self, "sample_list"):
            return
        self.total_samples_var.set(f"Total sample no.: {len(self.samples)}")
        group_counts = {}
        for sample in self.samples:
            group = str(sample.get("group", "")).strip() or "Group"
            group_counts[group] = group_counts.get(group, 0) + 1
        if group_counts:
            self.group_samples_var.set("Group sample no.: " + ", ".join(f"{k}={v}" for k, v in sorted(group_counts.items())))
        else:
            self.group_samples_var.set("Group sample no.: none")
        current_selection = self.sample_list.curselection()
        self.sample_list.delete(0, tk.END)
        for sample in self.samples:
            self.sample_list.insert(
                tk.END,
                f"{self.sample_display_id(sample)} | {sample.get('plant')} | {sample.get('source_crop')} {sample.get('source_group')} {sample.get('capture_id')}",
            )
        if self.selected_sample_index is not None and self.selected_sample_index < len(self.samples):
            self.sample_list.selection_set(self.selected_sample_index)

    def find_capture_index_for_sample(self, sample):
        for idx, cap in enumerate(self.captures):
            if (
                cap["source_crop"] == sample.get("source_crop")
                and cap["source_group"] == sample.get("source_group")
                and cap["capture_id"] == sample.get("capture_id")
            ):
                return idx
        return None

    def on_sample_select(self, _event=None):
        selection = self.sample_list.curselection()
        if not selection:
            return
        self.selected_sample_index = int(selection[0])
        self.redraw()

    def goto_selected_sample(self):
        selection = self.sample_list.curselection()
        if not selection:
            return
        self.selected_sample_index = int(selection[0])
        sample = self.samples[self.selected_sample_index]
        cap_idx = self.find_capture_index_for_sample(sample)
        if cap_idx is not None:
            self.load_capture(cap_idx)
            self.selected_sample_index = int(selection[0])
            self.sample_list.selection_set(self.selected_sample_index)
            self.redraw()

    def delete_selected_sample(self):
        selection = self.sample_list.curselection()
        if not selection:
            return
        idx = int(selection[0])
        sample = self.samples[idx]
        if not messagebox.askyesno("Delete sample", f"Delete {self.sample_display_id(sample)}?"):
            return
        del self.samples[idx]
        delete_sample_csv_rows(sample)
        self.selected_sample_index = None
        self.clear_roi(redraw=False)
        write_samples(self.samples)
        self.update_sample_panel()
        self.redraw()

    def clear_all_samples(self):
        if not self.samples:
            return
        if not messagebox.askyesno("Clear all samples", "Delete all saved samples?"):
            return
        self.samples = []
        self.selected_sample_index = None
        write_samples(self.samples)
        clear_sample_metric_csvs()
        self.clear_roi(redraw=False)
        self.update_sample_panel()
        self.redraw()

    def reset_project(self):
        if not messagebox.askyesno(
            "Reset project",
            "Delete saved ROIs and sample metric CSV files?\n\nBand/RGB caches will be kept so image loading remains fast.",
        ):
            return
        self.samples = []
        self.selected_sample_index = None
        write_samples(self.samples)
        clear_sample_metric_csvs()
        self.clear_roi(redraw=False)
        self.update_sample_panel()
        self.redraw()
        self.meta.delete("1.0", tk.END)
        self.meta.insert(tk.END, "Project reset. Band/RGB caches were kept.")

    def open_last_result_folder(self):
        if not self.last_result_folder or not Path(self.last_result_folder).exists():
            messagebox.showwarning("No result folder", "No completed result folder is available yet.")
            return
        try:
            os.startfile(str(self.last_result_folder))
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    def open_micasense_folder(self):
        folder = filedialog.askdirectory(
            title="Select dataset root folder",
            initialdir=self.config.get("last_dataset_parent") or str(WORKSPACE),
        )
        if not folder:
            return
        self.micasense_root = Path(folder)
        self.captures, skipped = dataset_report([self.micasense_root])
        self.load_capture_list()
        self.save_current_settings()
        messagebox.showinfo("Dataset report", format_dataset_report(self.captures, skipped))

    def load_capture_list(self):
        self.combo["values"] = [c["display"] for c in self.captures]
        self.index = 0
        if self.captures:
            self.load_capture(0)
        else:
            self.image = None
            self.rgb_image = None
            self.canvas.delete("all")
            self.meta.delete("1.0", tk.END)
            self.meta.insert(tk.END, "No captures found in selected folders.")

    def open_selected_subfolders(self):
        parent = filedialog.askdirectory(
            title="Select parent folder containing subfolders",
            initialdir=self.config.get("last_dataset_parent") or str(WORKSPACE),
        )
        if not parent:
            return
        parent = Path(parent)
        subfolders = [p for p in sorted(parent.iterdir()) if p.is_dir() and not p.name.startswith("_")]
        if not subfolders:
            messagebox.showwarning("No subfolders", "No selectable subfolders found.")
            return
        win = tk.Toplevel(self.root)
        win.title("Select subfolders to load")
        win.geometry("520x440")
        ttk.Label(win, text=f"Parent: {parent}").pack(anchor=tk.W, padx=10, pady=(10, 4))
        listbox = tk.Listbox(win, selectmode=tk.MULTIPLE, height=16)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        counts = []
        for folder in subfolders:
            count = len(discover_captures(folder))
            counts.append(count)
            listbox.insert(tk.END, f"{folder.name} ({count} captures)")
        for i, count in enumerate(counts):
            if count:
                listbox.selection_set(i)

        buttons = ttk.Frame(win)
        buttons.pack(fill=tk.X, padx=10, pady=10)

        def load_selected():
            selected = [subfolders[int(i)] for i in listbox.curselection()]
            if not selected:
                messagebox.showwarning("No selection", "Select at least one folder.")
                return
            self.micasense_root = parent
            self.captures, skipped = dataset_report(selected)
            self.load_capture_list()
            self.save_current_settings()
            win.destroy()
            messagebox.showinfo("Dataset report", format_dataset_report(self.captures, skipped))

        ttk.Button(buttons, text="Load Selected", command=load_selected).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=(0, 8))

    def load_capture(self, idx):
        if not self.captures:
            return
        self.index = idx % len(self.captures)
        cap = self.captures[self.index]
        self.combo.current(self.index)
        self.plant.set(cap["source_crop"])
        self.group.set(cap["source_group"])
        self.sample_number.set(self.next_group_sample_number(self.group.get()))
        self.rect = None
        self.poly = []
        self.finished_poly = None
        self.mask_preview_live = False
        path = make_full_rgb(cap)
        self.rgb_image = Image.open(path).convert("RGB")
        self.image = self.rgb_image.copy()
        self.meta.delete("1.0", tk.END)
        self.meta.insert(tk.END, f"{cap['display']}\n{path.name}\nSaved samples: {len(self.samples)}")
        self.redraw()

    def current_capture(self):
        if not self.captures:
            return None
        return self.captures[self.index]

    def mask_overlay_image(self, rgb, mask):
        src = np.asarray(rgb)
        arr = np.zeros_like(src)
        arr[mask] = src[mask]
        return Image.fromarray(arr, "RGB")

    def schedule_live_mask_preview(self):
        if not getattr(self, "mask_preview_live", False):
            return
        if self._mask_preview_after:
            self.root.after_cancel(self._mask_preview_after)
        self._mask_preview_after = self.root.after(180, self.preview_current_plant_mask)

    def preview_current_plant_mask(self):
        cap = self.current_capture()
        if not cap:
            return
        try:
            aligned = load_or_create_aligned_bands(cap)
            rgb = rgb_from_bands(aligned)
            full_area = np.ones_like(aligned["green"], dtype=bool)
            mask = plant_mask_roi(aligned, full_area, self.mask_method.get(), float(self.mask_threshold.get()))
            self.rgb_image = rgb
            self.image = self.mask_overlay_image(rgb, mask)
            self.mask_preview_live = True
            self.meta.delete("1.0", tk.END)
            self.meta.insert(
                tk.END,
                f"{cap['display']}\nPlant mask preview on black background\nmethod={self.mask_method.get()}\nthreshold={self.mask_threshold.get():.2f}\nmask fraction={mask.mean():.3f}",
            )
            self.redraw()
        except Exception as exc:
            messagebox.showerror("Mask preview failed", str(exc))

    def show_current_rgb(self):
        if self.rgb_image is not None:
            self.mask_preview_live = False
            self.image = self.rgb_image.copy()
            self.redraw()

    def norm_point(self, event):
        x = (event.x - self.offset_x) / (self.image.width * self.scale)
        y = (event.y - self.offset_y) / (self.image.height * self.scale)
        return [max(0, min(1, x)), max(0, min(1, y))]

    def canvas_point(self, p):
        return (self.offset_x + p[0] * self.image.width * self.scale, self.offset_y + p[1] * self.image.height * self.scale)

    def redraw(self):
        if not self.image:
            return
        self.canvas.delete("all")
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            self.root.after(100, self.redraw)
            return
        self.scale = min(cw / self.image.width, ch / self.image.height)
        w = max(1, int(self.image.width * self.scale))
        h = max(1, int(self.image.height * self.scale))
        self.offset_x, self.offset_y = (cw - w) / 2, (ch - h) / 2
        self.photo = ImageTk.PhotoImage(self.image.resize((w, h), Image.Resampling.LANCZOS))
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.photo)
        self.draw_saved_sample_rois()
        self.draw_shape(self.rect, "#ffd21f")
        self.draw_shape(self.finished_poly, "#41d17d")
        if self.poly:
            pts = []
            for p in self.poly:
                pts.extend(self.canvas_point(p))
            if len(pts) >= 4:
                self.canvas.create_line(*pts, fill="#41d17d", width=3)
        self.update_preview()

    def current_capture_key(self):
        if not self.captures:
            return None
        cap = self.captures[self.index]
        return (cap["source_crop"], cap["source_group"], cap["capture_id"])

    def sample_matches_current_capture(self, sample):
        key = self.current_capture_key()
        if not key:
            return False
        return (sample.get("source_crop"), sample.get("source_group"), sample.get("capture_id")) == key

    def draw_saved_sample_rois(self):
        colors = ["#ff4d4d", "#4d9fff", "#ffffff", "#ff8c1a", "#b366ff", "#00d5c8"]
        shown = 0
        for idx, sample in enumerate(self.samples):
            if not self.sample_matches_current_capture(sample):
                continue
            selected = idx == self.selected_sample_index
            color = "#00ffff" if selected else colors[shown % len(colors)]
            label = f"{self.sample_display_id(sample)} {sample.get('plant', '')}"
            self.draw_shape(sample.get("roi"), color, label=label, dash=None if selected else (6, 4), width=5 if selected else 3)
            shown += 1

    def draw_shape(self, shape, color, label=None, dash=None, width=3):
        if not shape:
            return
        if shape["type"] == "rect":
            x0, y0, x1, y1 = shape["coords"]
            p0 = self.canvas_point([x0, y0])
            p1 = self.canvas_point([x1, y1])
            self.canvas.create_rectangle(*p0, *p1, outline=color, width=width, dash=dash)
            if label:
                self.canvas.create_text(p0[0] + 5, p0[1] + 12, text=label, fill=color, anchor=tk.W)
        elif shape["type"] == "polygon":
            pts = []
            for p in shape["coords"]:
                pts.extend(self.canvas_point(p))
            if len(pts) >= 6:
                self.canvas.create_polygon(*pts, outline=color, fill="", width=width)
                if label:
                    p0 = self.canvas_point(shape["coords"][0])
                    self.canvas.create_text(p0[0] + 5, p0[1] + 12, text=label, fill=color, anchor=tk.W)

    def on_press(self, event):
        if self.draw_type.get() != "rect":
            return
        self.start = self.norm_point(event)
        self.rect = {"type": "rect", "coords": [self.start[0], self.start[1], self.start[0], self.start[1]]}
        self.redraw()

    def on_drag(self, event):
        if self.draw_type.get() != "rect" or not self.rect:
            return
        x, y = self.norm_point(event)
        self.rect["coords"][2:] = [x, y]
        self.redraw()

    def on_release(self, event):
        if self.draw_type.get() != "rect" or not self.rect:
            return
        x, y = self.norm_point(event)
        x0, y0 = self.start
        self.rect["coords"] = [min(x0, x), min(y0, y), max(x0, x), max(y0, y)]
        self.redraw()

    def on_click(self, event):
        if self.draw_type.get() != "polygon":
            return
        self.poly.append(self.norm_point(event))
        self.finished_poly = None
        self.redraw()

    def finish_polygon(self):
        if len(self.poly) >= 3:
            self.finished_poly = {"type": "polygon", "coords": self.poly[:]}
            self.poly = []
            self.redraw()

    def active_roi(self):
        return self.rect if self.draw_type.get() == "rect" else self.finished_poly

    def build_sample(self):
        cap = self.captures[self.index]
        roi = self.active_roi()
        if not roi:
            raise ValueError("ROI를 먼저 지정하세요.")
        return {
            "plant": self.plant.get().strip() or cap["source_crop"],
            "group": self.group.get().strip() or cap["source_group"],
            "sample_number": self.sample_number.get().strip() or str(len(self.samples) + 1),
            "capture_id": cap["capture_id"],
            "source_crop": cap["source_crop"],
            "source_group": cap["source_group"],
            "roi": roi,
            "mode": self.mode.get(),
            "grid_rows": int(self.grid_rows.get()),
            "grid_cols": int(self.grid_cols.get()),
            "mask_method": self.mask_method.get(),
            "mask_threshold": float(self.mask_threshold.get()),
            "mask_workflow": "full_image_mask_then_roi_intersection",
            "files": cap["files"],
        }

    def update_preview(self):
        self.preview.delete("1.0", tk.END)
        try:
            self.preview.insert(tk.END, json.dumps(self.build_sample(), ensure_ascii=False, indent=2))
        except Exception as exc:
            self.preview.insert(tk.END, str(exc))

    def save_sample(self):
        try:
            sample = self.build_sample()
        except ValueError as exc:
            messagebox.showwarning("Missing ROI", str(exc))
            return
        key = (sample["plant"], sample["group"], sample["sample_number"], sample["capture_id"])
        for i, old in enumerate(self.samples):
            if (old["plant"], old["group"], old["sample_number"], old["capture_id"]) == key:
                self.samples[i] = sample
                self.selected_sample_index = i
                break
        else:
            self.samples.append(sample)
            self.selected_sample_index = len(self.samples) - 1
        write_samples(self.samples)
        self.clear_roi(redraw=False)
        self.update_sample_panel()
        self.sample_number.set(self.next_group_sample_number(self.group.get()))
        self.redraw()
        self.meta.delete("1.0", tk.END)
        self.meta.insert(tk.END, f"Saved ROI only: {self.sample_display_id(sample)}\nRun Analysis to calculate metrics.\nSaved samples: {len(self.samples)}")

    def run_analysis(self):
        if self.saving_sample:
            messagebox.showinfo("Busy", "Wait until the current sample save finishes.")
            return
        if self.active_roi():
            messagebox.showwarning("Unsaved ROI", "Current ROI is not saved. Click Save Sample first, or Clear ROI.")
            return
        if not self.samples:
            messagebox.showwarning("No samples", "저장된 sample이 없습니다.")
            return
        if not messagebox.askyesno("Run analysis", sample_preflight_text(self.samples)):
            return
        self.tabs.select(self.analysis_frame)
        self.analysis_log.delete("1.0", tk.END)
        self.plot_label.configure(image="", text="")
        self.plot_photo = None
        self.progress_value.set(0)
        self.log_analysis(f"Starting plot/export from saved sample metrics for {len(self.samples)} samples")
        for sample in self.samples:
            self.log_analysis(
                f"- S{sample.get('sample_number')} {sample.get('plant')} / {sample.get('group')} / "
                f"{sample.get('source_crop')} {sample.get('source_group')} {sample.get('capture_id')}"
            )

        def worker():
            global PLOT_DIR, STEP_DIR
            old_dirs = (PLOT_DIR, STEP_DIR)
            try:
                out = APP_OUT / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
                PLOT_DIR = out / "results_plot"
                STEP_DIR = out / "stepwise"
                for path in (PLOT_DIR, STEP_DIR, out / "results_csv"):
                    path.mkdir(parents=True, exist_ok=True)
                self.root.after(0, lambda o=out: self.log_analysis(f"Result folder: {o}"))
                total = len(self.samples)
                for idx, sample in enumerate(self.samples, start=1):
                    pct = int((idx - 1) / max(total, 1) * 70)
                    display_id = self.sample_display_id(sample)
                    if sample_metrics_current(sample):
                        self.root.after(0, lambda p=pct, s=display_id: self.log_analysis(f"{p}% Skip cached metrics: {s}"))
                        continue
                    self.root.after(0, lambda p=pct, s=display_id: self.log_analysis(f"{p}% Analyze sample: {s}"))
                    rows, thermal_rows = compute_sample_rows(
                        sample,
                        stepwise=self.stepwise.get(),
                        progress=lambda msg: self.root.after(0, lambda m=msg: self.log_analysis(m)),
                    )
                    update_sample_csv(SAMPLE_REGION_CSV, rows, sample)
                    update_sample_csv(SAMPLE_THERMAL_CSV, thermal_rows, sample)
                self.root.after(0, lambda: self.log_analysis("75% Calculating wet/dry refs and pixelwise CWSI"))
                refs, temp_limits = wetdry_refs_from_samples(
                    self.samples,
                    progress=lambda msg: self.root.after(0, lambda m=msg: self.log_analysis(m)),
                )
                _region, summary = build_summary_from_incremental_csv(
                    out,
                    samples=self.samples,
                    refs=refs,
                    progress=lambda msg: self.root.after(0, lambda m=msg: self.log_analysis(m)),
                )
                if self.stepwise.get():
                    for sample in self.samples:
                        save_final_stepwise(
                            sample,
                            refs,
                            temp_limits,
                            progress=lambda msg: self.root.after(0, lambda m=msg: self.log_analysis(m)),
                        )
                self.root.after(0, lambda: self.log_analysis("90% Creating plots from summary CSV"))
                plot_paths = []
                total_plots = len(PLOT_INDICES)
                for plot_i, idx in enumerate(PLOT_INDICES, start=1):
                    pct = 90 + int(plot_i / max(total_plots, 1) * 7)
                    self.root.after(0, lambda p=pct, name=idx: self.log_analysis(f"{p}% Creating plot: {name}"))
                    t0 = time.perf_counter()
                    plot_paths.append(draw_barplot(summary, idx))
                    elapsed = time.perf_counter() - t0
                    self.root.after(0, lambda name=idx, sec=elapsed: self.log_analysis(f"Plot done: {name} ({sec:.1f}s)"))
                make_plot_contact_sheet(plot_paths)
                self.root.after(0, lambda: self.log_analysis("98% Copying manuscript figure files"))
                write_result_helpers(out, self.samples, refs)
                self.root.after(0, lambda: self.log_analysis("100% Export complete"))
                self.root.after(0, lambda: self.show_analysis_done(out))
            except Exception as exc:
                self.root.after(0, lambda: self.show_analysis_failed(exc))
            finally:
                PLOT_DIR, STEP_DIR = old_dirs
        threading.Thread(target=worker, daemon=True).start()
        self.log_analysis("Export is running in background")

    def precompute_band_cache(self):
        if not self.captures:
            messagebox.showwarning("No captures", "No captures loaded.")
            return
        self.tabs.select(self.analysis_frame)
        self.analysis_log.delete("1.0", tk.END)
        self.progress_value.set(0)
        self.log_analysis(f"Precomputing band cache for {len(self.captures)} captures")

        def worker():
            try:
                total = len(self.captures)
                for idx, cap in enumerate(self.captures, start=1):
                    pct = int(idx / max(total, 1) * 100)
                    self.root.after(
                        0,
                        lambda p=pct, c=cap: self.log_analysis(
                            f"{p}% Cache {c['source_crop']} / {c['source_group']} / {c['capture_id']}"
                        ),
                    )
                    load_or_create_aligned_bands(cap)
                    make_full_rgb(cap)
                self.root.after(0, lambda: self.log_analysis(f"100% Band cache ready: {CACHE_DIR}"))
                self.root.after(0, lambda: messagebox.showinfo("Done", f"Band cache ready:\n{CACHE_DIR}"))
            except Exception as exc:
                self.root.after(0, lambda: self.show_analysis_failed(exc))
        threading.Thread(target=worker, daemon=True).start()

    def log_analysis(self, msg):
        match = re.match(r"(\d+)%", str(msg))
        if match:
            self.progress_value.set(float(match.group(1)))
        self.analysis_log.insert(tk.END, str(msg) + "\n")
        self.analysis_log.see(tk.END)

    def show_analysis_done(self, out):
        self.last_result_folder = Path(out)
        self.save_current_settings()
        self.log_analysis(f"Analysis complete: {out}")
        summary_path = Path(out) / "results_csv" / "summary_results.csv"
        if summary_path.exists():
            try:
                df = pd.read_csv(summary_path)
                self.log_analysis("\nSummary preview:")
                self.log_analysis(df.head(30).to_string(index=False))
            except Exception as exc:
                self.log_analysis(f"Could not load summary preview: {exc}")
        plot_path = Path(out) / "results_plot" / "all_indices_barplots.png"
        if not plot_path.exists():
            plot_path = Path(out) / "results_plot" / "NDVI_barplot.png"
        if plot_path.exists():
            try:
                im = Image.open(plot_path).convert("RGB")
                im.thumbnail((330, 220))
                self.plot_photo = ImageTk.PhotoImage(im)
                self.plot_label.configure(image=self.plot_photo, text="")
                self.log_analysis(f"Plot preview loaded: {plot_path.name}")
            except Exception as exc:
                self.log_analysis(f"Could not load plot preview: {exc}")
        try:
            os.startfile(str(Path(out)))
            self.log_analysis(f"Opened result folder: {out}")
        except Exception as exc:
            self.log_analysis(f"Could not open result folder automatically: {exc}")
        messagebox.showinfo("Done", f"Analysis complete:\n{out}")

    def show_analysis_failed(self, exc):
        self.log_analysis(f"Analysis failed: {exc}")
        messagebox.showerror("Analysis failed", str(exc))

    def clear_roi(self, redraw=True):
        self.rect = None
        self.poly = []
        self.finished_poly = None
        if redraw:
            self.redraw()


def main():
    root = tk.Tk()
    app = FullRoiApp(root)
    root.bind("<Configure>", lambda _e: app.redraw())
    root.mainloop()


if __name__ == "__main__":
    main()

