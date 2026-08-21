#!/usr/bin/env python3
"""Run PlantSpec Quickviewer analysis on bundled demo_data without the GUI."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Headless environments may not ship Tk; the analysis path does not need it.
if "tkinter" not in sys.modules:
    tk = types.ModuleType("tkinter")
    ttk = types.ModuleType("tkinter.ttk")
    filedialog = types.ModuleType("tkinter.filedialog")
    messagebox = types.ModuleType("tkinter.messagebox")

    class _Tk:
        def __init__(self, *args, **kwargs):
            pass

        def title(self, *args, **kwargs):
            pass

        def geometry(self, *args, **kwargs):
            pass

        def mainloop(self, *args, **kwargs):
            pass

    tk.Tk = _Tk
    tk.END = "end"
    tk.BOTH = "both"
    tk.X = "x"
    tk.Y = "y"
    tk.LEFT = "left"
    tk.RIGHT = "right"
    tk.TOP = "top"
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = ttk
    sys.modules["tkinter.filedialog"] = filedialog
    sys.modules["tkinter.messagebox"] = messagebox

import plantspec_quickviewer as pq  # noqa: E402


def build_demo_samples(demo_dir: Path) -> list[dict]:
    captures = pq.discover_captures(demo_dir)
    if not captures:
        raise SystemExit(f"No valid captures found under {demo_dir}")

    samples = []
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


def main() -> None:
    demo_dir = ROOT / "demo_data"
    if not demo_dir.exists():
        raise SystemExit(f"Demo folder not found: {demo_dir}")

    samples = build_demo_samples(demo_dir)
    pq.ensure_dirs()
    pq.write_samples(samples)

    print(f"Prepared {len(samples)} demo sample(s):")
    for sample in samples:
        print(
            f"  - {sample['plant']} / {sample['group']} / "
            f"S{sample['sample_number']} / {sample['capture_id']}"
        )

    def progress(msg: str) -> None:
        print(msg)

    out = pq.analyze_samples(samples, stepwise=True, progress=progress)
    summary_path = out / "results_csv" / "summary_results.csv"
    manifest = {
        "demo_dir": str(demo_dir),
        "samples": len(samples),
        "result_dir": str(out),
        "summary_csv": str(summary_path),
        "plots_dir": str(out / "results_plot"),
        "stepwise_dir": str(out / "stepwise"),
    }
    manifest_path = out / "demo_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nAnalysis complete.\nResults: {out}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
