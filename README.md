# PlantSpec Quickviewer

PlantSpec Quickviewer is a lightweight desktop tool for ROI-based multispectral plant image analysis. It helps field researchers inspect RGB previews, segment plant pixels, draw ROIs, calculate vegetation and thermal indices, and export publication-ready plots and CSV/XLSX result tables.

## Main Features

- Load multispectral image folders and generate RGB previews
- Preview ExG-based plant masks and adjust threshold values
- Draw ROI boxes or polygons directly on the image
- Assign custom plant names, group names, and sample numbers
- Compare treatment groups such as control vs test
- Calculate ExG, NDVI, GNDVI, NDRE, SAVI, OSAVI, CWSI, and Thermal_C
- Export matplotlib-based bar plots, CSV files, XLSX files, and stepwise PNGs
- Includes demo data for quick testing

## Quick Start

For Windows users, download the Windows ZIP from the GitHub Releases page, unzip it, and run:

```text
PlantSpecQuickviewer.exe
```

For source users:

```bash
python plantspec_quickviewer.py
```

Required Python packages:

```bash
pip install numpy pandas pillow openpyxl matplotlib
```

## Input Data Format

Recommended folder structure:

```text
YourDataset/
  Cabbage_control_IMG_0003/
    blue.tif
    green.tif
    red.tif
    nir.tif
    rededge.tif
    thermal.tif
  Cabbage_test_IMG_0005/
    blue.tif
    green.tif
    red.tif
    nir.tif
    rededge.tif
    thermal.tif
```

MicaSense-style numbered files are also supported:

```text
IMG_0003_1.tif = Blue
IMG_0003_2.tif = Green
IMG_0003_3.tif = Red
IMG_0003_4.tif = NIR
IMG_0003_5.tif = Red edge
IMG_0003_7.tif = Thermal
```

Supported file types include `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.npy`, and `.npz`.

## Output

Each analysis run is saved under:

```text
paper_figure_outputs/
  plantspec_quickviewer/
    runs/
      YYYYMMDD_HHMMSS/
        results_plot/
        results_csv/
        stepwise/
```

Main outputs:

- `results_plot/`: bar plots for each index and combined summary plots
- `results_csv/`: summary CSV, region-level CSV, XLSX workbook, column descriptions
- `stepwise/`: per-sample PNGs showing RGB, plant mask, ROI, index maps, CWSI, and temperature

## License

PlantSpec Quickviewer is released under the MIT License.

Copyright (c) 2026 MFM
