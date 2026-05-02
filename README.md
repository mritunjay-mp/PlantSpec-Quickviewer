# PlantSpec Quickviewer

PlantSpec Quickviewer is a lightweight desktop tool for quick ROI-based multispectral plant image analysis. It helps users inspect aligned RGB previews, define plant regions manually, calculate vegetation and thermal indices, and export publication-ready plots and CSV/XLSX results without using complex remote sensing software.

You can visit our company's website for more contact such as bug or suggestion.
https://sites.google.com/view/mfminc/home

## Overview

Plant growth experiments often require repeated steps: organizing multispectral bands, checking plant segmentation, defining regions of interest, calculating indices, and creating figures for reports or manuscripts. PlantSpec Quickviewer combines these steps into one simple GUI.

Users can view an RGB image, preview the plant mask, adjust the threshold, draw ROI boxes or polygons, assign plant names, group names, and sample numbers, and then run the full analysis. The software calculates ExG, NDVI, GNDVI, NDRE, SAVI, OSAVI, CWSI, and temperature in Celsius, then saves group comparison plots and raw data tables.

## Key Features

- Load multispectral image folders and generate RGB previews
- Preview ExG-based plant masks and adjust segmentation threshold
- Draw ROI boxes or polygons directly on the image
- Assign custom plant names, group names, and sample numbers
- Compare treatment groups such as control vs test
- Calculate ROI-level and group-level vegetation indices
- Convert thermal raw pixels to Kelvin and Celsius
- Calculate CWSI using wet/dry reference scaling
- Save stepwise PNGs showing RGB, plant mask, ROI, index maps, CWSI, and temperature maps
- Generate matplotlib-based publication-style bar plots
- Export CSV and XLSX result tables
- Available as a Windows executable and Python source package

## When To Use It

PlantSpec Quickviewer is useful when you need to:

- Compare crop responses between fertilizer, biochar, irrigation, stress, or treatment groups
- Check experimental image results immediately after or during field experiments
- Perform ROI-based vegetation index analysis without GIS or remote sensing software
- Analyze only user-selected plots, beds, or plant regions
- Produce quick figures and data tables for manuscripts, reports, and lab notes
- Provide a beginner-friendly multispectral analysis workflow to non-programmers

It is not intended to replace high-end orthomosaic generation, large-scale geospatial analysis, advanced radiometric calibration workflows, or machine learning classification pipelines. Its main value is fast, field-friendly ROI analysis.

## Input Data

The recommended input structure is one capture per folder.

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

MicaSense-style numbered files are also supported.

```text
Cabbage/000/control/IMG_0003_1.tif  = Blue
Cabbage/000/control/IMG_0003_2.tif  = Green
Cabbage/000/control/IMG_0003_3.tif  = Red
Cabbage/000/control/IMG_0003_4.tif  = NIR
Cabbage/000/control/IMG_0003_5.tif  = Red edge
Cabbage/000/control/IMG_0003_7.tif  = Thermal
```

Supported file types:

- TIFF: `.tif`, `.tiff`
- Common image files: `.png`, `.jpg`, `.jpeg`, `.bmp`
- NumPy arrays: `.npy`, `.npz`

Thermal images are converted to Celsius using:

```text
Celsius = raw_pixel_value / 100 - 273.15
```

## Output Files

Each run is saved in a timestamped folder.

```text
paper_figure_outputs/
  plantspec_quickviewer/
    runs/
      YYYYMMDD_HHMMSS/
        results_plot/
        results_csv/
        stepwise/
```

`results_plot/` contains publication-style PNG plots.

```text
all_indices_barplots.png
ExG_barplot.png
NDVI_barplot.png
GNDVI_barplot.png
NDRE_barplot.png
SAVI_barplot.png
OSAVI_barplot.png
CWSI_barplot.png
Thermal_C_barplot.png
```

`results_csv/` contains summary and raw result tables.

```text
summary_results.csv
region_level_results.csv
full_roi_analysis_results.xlsx
columns_description.csv
README_results.txt
```

`stepwise/` contains one PNG per saved sample, showing the analysis workflow: RGB, plant mask, ROI, vegetation index maps, CWSI, and temperature.

## Basic Workflow

1. Run `PlantSpecQuickviewer.exe`.
2. Click `Open Dataset Folder`.
3. Select your multispectral image dataset.
4. Click `Preview Plant Mask`.
5. Adjust the threshold until the plant area is properly segmented.
6. Draw an ROI on the RGB image.
7. Enter Plant name, Group name, and Sample no.
8. Click `Save Sample`.
9. Repeat for all treatment groups and samples.
10. Click `Run Analysis`.
11. Review the exported plots and result tables in the automatically opened result folder.

## Calculated Indices

PlantSpec Quickviewer calculates:

- ExG: RGB-based green plant enhancement index
- NDVI: NIR/Red vegetation vigor index
- GNDVI: NIR/Green chlorophyll and growth response index
- NDRE: NIR/Red edge index related to chlorophyll and stress
- SAVI: soil-adjusted vegetation index
- OSAVI: optimized soil-adjusted vegetation index
- Thermal_C: canopy or plant-region temperature in Celsius
- CWSI: crop water stress index; higher values generally indicate greater water stress

All index statistics are calculated from plant-mask pixels within each user-defined ROI. In other words, the analysis uses segmented plant pixels inside the ROI, not every pixel in the ROI.

## Demo Data

The package includes a small `demo_data/` folder. New users can load this folder to test the full workflow without preparing their own dataset.

The demo contains one Cabbage control capture and one Cabbage test capture. Select `demo_data/` with `Open Dataset Folder` to try the software immediately.

## Downloads

Windows users can download `PlantSpec_Quickviewer_Windows.zip`, unzip it, and run `PlantSpecQuickviewer.exe`.

Developer and non-Windows packages are also available.

```text
PlantSpec_Quickviewer_Windows.zip
PlantSpec_Quickviewer_Source.zip
PlantSpec_Quickviewer_macOS.zip
PlantSpec_Quickviewer_Linux_x64.zip
PlantSpec_Quickviewer_RPi_Jetson_ARM64.zip
```

## License

PlantSpec Quickviewer is distributed under the MIT License. Users may use, modify, and redistribute the software. When redistributing the program, include `LICENSE.txt` and `THIRD_PARTY_NOTICES.txt`.

## Short Summary

PlantSpec Quickviewer is a beginner-friendly multispectral image analysis tool that lets field researchers draw ROIs, segment plant pixels, calculate vegetation and thermal indices, and export publication-ready plots and result tables in a lightweight workflow.
