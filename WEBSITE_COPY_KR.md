# PlantSpec Quickviewer

PlantSpec Quickviewer는 현장 다분광 이미지에서 식물 영역을 빠르게 확인하고, 사용자가 지정한 ROI를 기준으로 식생지수와 열화상 기반 지표를 계산하는 경량 분석 프로그램입니다. 전문 GIS 또는 원격탐사 소프트웨어에 익숙하지 않은 사용자도 실험 현장에서 control/test 샘플을 직접 지정하고, 바로 논문용 bar plot과 CSV 결과를 확인할 수 있도록 설계되었습니다.

## 간단 소개

작물 생육 실험에서는 이미지 촬영 후 데이터 정리, 식물 영역 분리, ROI 지정, 지표 계산, 그래프 생성까지 여러 단계를 반복해야 합니다. PlantSpec Quickviewer는 이 과정을 하나의 GUI 안에서 처리합니다.

사용자는 정합된 RGB 이미지를 보면서 분석할 영역을 직접 박스 또는 폴리곤으로 지정할 수 있고, 각 ROI에 작물명, 처리구 이름, 샘플 번호를 붙여 저장할 수 있습니다. 분석을 실행하면 ExG, NDVI, GNDVI, NDRE, SAVI, OSAVI, CWSI, 섭씨 온도 지표가 자동 계산되며, 그룹별 비교 plot과 raw CSV/XLSX 결과가 함께 저장됩니다.

## 주요 기능

- 다분광 이미지 폴더를 불러와 RGB preview 생성
- ExG 기반 plant mask 미리보기 및 threshold 조정
- 사용자가 직접 ROI를 지정하고 샘플명 저장
- control, test 등 자유로운 group 이름 지원
- ROI별 및 group별 식생지수 계산
- Thermal band를 Kelvin 및 Celsius로 변환
- Wet/dry reference 기반 CWSI 계산
- stepwise PNG 저장: RGB, plant mask, ROI, index map, CWSI, temperature map
- 논문용 matplotlib bar plot 자동 생성
- 결과 CSV, XLSX, plot을 시간별 run 폴더에 자동 저장
- Windows EXE 및 Python source package 제공

## 언제 사용하면 좋은가

PlantSpec Quickviewer는 다음 상황에 적합합니다.

- 비료, 바이오차, 관수, 스트레스 처리 등 처리구별 작물 반응을 빠르게 비교할 때
- 현장 실험 직후 이미지 품질과 처리구 차이를 즉시 확인하고 싶을 때
- 복잡한 원격탐사 소프트웨어 없이 ROI 기반 식생지수 분석을 하고 싶을 때
- 작물 개체 전체가 아닌 사용자가 지정한 plot 또는 구역만 분석하고 싶을 때
- 분석 결과를 바로 논문 figure, 보고서, 실험 노트에 활용하고 싶을 때
- 초보자도 다분광 이미지 분석을 반복 수행해야 할 때

정밀한 항공 정사영상 제작, 대면적 지리좌표 분석, 고급 radiometric calibration, 복잡한 머신러닝 분류를 대체하기 위한 프로그램은 아닙니다. 이 프로그램의 강점은 현장형 ROI 분석을 빠르고 단순하게 반복할 수 있다는 점입니다.

## 입력 데이터

권장 입력 구조는 capture 하나를 하나의 폴더로 저장하는 방식입니다.

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

MicaSense-style numbered format도 지원합니다.

```text
Cabbage/000/control/IMG_0003_1.tif  = Blue
Cabbage/000/control/IMG_0003_2.tif  = Green
Cabbage/000/control/IMG_0003_3.tif  = Red
Cabbage/000/control/IMG_0003_4.tif  = NIR
Cabbage/000/control/IMG_0003_5.tif  = Red edge
Cabbage/000/control/IMG_0003_7.tif  = Thermal
```

지원 파일 형식:

- TIFF: `.tif`, `.tiff`
- 일반 이미지: `.png`, `.jpg`, `.jpeg`, `.bmp`
- NumPy array: `.npy`, `.npz`

Thermal band는 원시 픽셀값을 `pixel / 100 - 273.15`로 변환하여 섭씨 온도로 계산합니다.

## 출력 결과

분석 결과는 실행 시간별 폴더에 자동 저장됩니다.

```text
paper_figure_outputs/
  plantspec_quickviewer/
    runs/
      YYYYMMDD_HHMMSS/
        results_plot/
        results_csv/
        stepwise/
```

`results_plot/`에는 논문용 bar plot PNG가 저장됩니다.

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

`results_csv/`에는 통계와 원자료가 저장됩니다.

```text
summary_results.csv
region_level_results.csv
full_roi_analysis_results.xlsx
columns_description.csv
README_results.txt
```

`stepwise/`에는 샘플별 진행 확인용 PNG가 저장됩니다. 각 이미지에는 RGB, plant mask, ROI, 식생지수 map, CWSI, Thermal_C map이 포함됩니다.

## 기본 사용법

1. `PlantSpecQuickviewer.exe`를 실행합니다.
2. `Open Dataset Folder`를 눌러 이미지 데이터 폴더를 선택합니다.
3. `Preview Plant Mask`를 눌러 식물 영역 분리가 적절한지 확인합니다.
4. threshold를 조정하면서 plant mask가 식물 부분을 잘 잡는지 확인합니다.
5. RGB 화면 위에서 ROI를 그립니다.
6. Plant name, Group name, Sample no.를 입력합니다.
7. `Save Sample`을 눌러 샘플을 저장합니다.
8. control/test 등 필요한 샘플을 모두 저장합니다.
9. `Run Analysis`를 눌러 분석을 실행합니다.
10. 완료되면 결과 폴더가 자동으로 열립니다.

## 분석 지표

PlantSpec Quickviewer는 다음 지표를 계산합니다.

- ExG: RGB 기반 녹색 식물 영역 강조 지표
- NDVI: NIR과 Red 기반 식생 활력 지표
- GNDVI: NIR과 Green 기반 엽록소 및 생육 반응 지표
- NDRE: NIR과 Red edge 기반 엽록소/스트레스 관련 지표
- SAVI: 토양 배경 영향을 줄인 식생지수
- OSAVI: 토양 보정 식생지수
- Thermal_C: thermal band 기반 섭씨 온도
- CWSI: crop water stress index, 값이 높을수록 상대적으로 수분 스트레스가 큰 상태로 해석

각 지표는 ROI 내부의 plant mask 영역을 기준으로 계산됩니다. 즉, ROI 안의 전체 픽셀이 아니라 식물로 분리된 픽셀만 통계에 사용됩니다.

## 데모 데이터

배포 폴더에는 `demo_data/`가 포함되어 있습니다. 처음 사용하는 사용자는 별도의 데이터를 준비하지 않아도 데모 데이터를 불러와 전체 workflow를 테스트할 수 있습니다.

데모 데이터에는 Cabbage control capture와 Cabbage test capture가 포함되어 있으며, `Open Dataset Folder`에서 `demo_data` 폴더를 선택하면 바로 사용할 수 있습니다.

## 배포 파일

Windows 사용자는 `PlantSpec_Quickviewer_Windows.zip`을 내려받아 압축을 푼 뒤 `PlantSpecQuickviewer.exe`를 실행하면 됩니다.

개발자 또는 macOS/Linux 사용자는 source package를 사용할 수 있습니다.

```text
PlantSpec_Quickviewer_Windows.zip
PlantSpec_Quickviewer_Source.zip
PlantSpec_Quickviewer_macOS.zip
PlantSpec_Quickviewer_Linux_x64.zip
PlantSpec_Quickviewer_RPi_Jetson_ARM64.zip
```

## 라이선스

PlantSpec Quickviewer는 MIT License로 배포됩니다. 자유롭게 사용, 수정, 재배포할 수 있으며, 배포 시 `LICENSE.txt`와 `THIRD_PARTY_NOTICES.txt`를 함께 포함하는 것을 권장합니다.

## 한 줄 요약

PlantSpec Quickviewer는 현장 실험자가 다분광 이미지에서 직접 ROI를 지정하고, 식물 영역 기반 식생지수와 열화상 지표를 빠르게 계산해 논문용 plot과 CSV 결과를 얻을 수 있게 해주는 초보자 친화형 다분광 이미지 분석 도구입니다.
