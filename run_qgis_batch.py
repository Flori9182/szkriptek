from __future__ import annotations
import math
import os
import re
from pathlib import Path
from typing import Iterable

import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()

YEAR = "2022"

SNAP_IN_DIR = r"D:\diplomamunka\snap\2022"
AOI_PATH = r"D:\diplomamunka\qgis\aoi_eloallitas\vegso_aoi.geojson"

CLIP_ROOT = r"D:\diplomamunka\qgis\kivágatok\2022"
RESULTS_ROOT = r"D:\diplomamunka\eredmenyek\2022"

TARGET_EPSG = 23700
TARGET_RES = 30.0
DST_NODATA = -9999.0

MONTH_NAME = {
    "06": "június",
    "07": "július",
    "08": "augusztus",
}

BAND_LABELS = {
    1: "NDVI",
    2: "LST",
    3: "NDBI",
}


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def parse_date_from_filename(path: str | Path) -> tuple[str, str, str]:
    name = Path(path).stem
    m = re.search(r"(20\d{2})_(\d{2})_(\d{2})", name)
    if not m:
        raise ValueError(f"Nem tudtam dátumot olvasni a fájlnévből: {name}")
    return m.group(1), m.group(2), m.group(3)


def get_reprojected_aoi_extent(aoi_path: str, target_epsg: int) -> tuple[float, float, float, float]:
    ds = ogr.Open(aoi_path)
    if ds is None:
        raise RuntimeError(f"Nem sikerült megnyitni az AOI-t: {aoi_path}")

    layer = ds.GetLayer(0)
    src_srs = layer.GetSpatialRef()
    if src_srs is None:
        raise RuntimeError("Az AOI réteghez nem tartozik CRS.")

    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(target_epsg)

    transform = osr.CoordinateTransformation(src_srs, dst_srs)

    minx, maxx, miny, maxy = None, None, None, None

    for feat in layer:
        geom = feat.GetGeometryRef()
        geom = geom.Clone()
        geom.Transform(transform)
        env = geom.GetEnvelope()  # (minx, maxx, miny, maxy)

        if minx is None:
            minx, maxx, miny, maxy = env[0], env[1], env[2], env[3]
        else:
            minx = min(minx, env[0])
            maxx = max(maxx, env[1])
            miny = min(miny, env[2])
            maxy = max(maxy, env[3])

    if minx is None:
        raise RuntimeError("Az AOI réteg üres.")

    return minx, miny, maxx, maxy


def align_bounds(bounds: tuple[float, float, float, float], res: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    minx = math.floor(minx / res) * res
    miny = math.floor(miny / res) * res
    maxx = math.ceil(maxx / res) * res
    maxy = math.ceil(maxy / res) * res
    return minx, miny, maxx, maxy


def clip_and_reproject(in_tif: str, out_tif: str, aoi_path: str, bounds_23700: tuple[float, float, float, float]) -> None:
    ensure_dir(Path(out_tif).parent)

    warp_opts = gdal.WarpOptions(
        dstSRS=f"EPSG:{TARGET_EPSG}",
        outputBounds=bounds_23700,
        xRes=TARGET_RES,
        yRes=TARGET_RES,
        targetAlignedPixels=True,
        cutlineDSName=aoi_path,
        cropToCutline=True,
        dstNodata=DST_NODATA,
        multithread=True,
        resampleAlg="near",
        format="GTiff",
        outputType=gdal.GDT_Float32,
    )

    out_ds = gdal.Warp(out_tif, in_tif, options=warp_opts)
    if out_ds is None:
        raise RuntimeError(f"Nem sikerült a kivágás/reprojektálás: {in_tif}")
    out_ds = None


def list_snap_tifs(snap_in_dir: str) -> list[str]:
    return sorted(str(p) for p in Path(snap_in_dir).glob("*.tif"))


def read_band_as_nan(path: str, band_idx: int) -> tuple[np.ndarray, tuple, str]:
    ds = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Nem sikerült megnyitni: {path}")

    band = ds.GetRasterBand(band_idx)
    arr = band.ReadAsArray().astype(np.float32)

    nodata = band.GetNoDataValue()
    if nodata is not None:
        arr[arr == nodata] = np.nan

    arr[~np.isfinite(arr)] = np.nan

    gt = ds.GetGeoTransform()
    proj = ds.GetProjection()
    xsize = ds.RasterXSize
    ysize = ds.RasterYSize
    ds = None
    return arr, (gt, xsize, ysize), proj


def write_single_band(out_tif: str, array: np.ndarray, ref_meta: tuple, ref_proj: str, nodata: float = DST_NODATA) -> None:
    ensure_dir(Path(out_tif).parent)

    gt, xsize, ysize = ref_meta
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(out_tif, xsize, ysize, 1,
                       gdal.GDT_Float32, options=["COMPRESS=LZW"])
    ds.SetGeoTransform(gt)
    ds.SetProjection(ref_proj)

    out = np.where(np.isfinite(array), array, nodata).astype(np.float32)

    band = ds.GetRasterBand(1)
    band.WriteArray(out)
    band.SetNoDataValue(nodata)
    band.FlushCache()
    ds = None


def median_stack(arrays: list[np.ndarray]) -> np.ndarray:
    stack = np.stack(arrays, axis=0)
    with np.errstate(all="ignore"):
        med = np.nanmedian(stack, axis=0)
    return med.astype(np.float32)


def month_folder_name(mm: str) -> str:
    if mm not in MONTH_NAME:
        raise KeyError(f"Nem támogatott hónap: {mm}")
    return MONTH_NAME[mm]


def group_by_month(paths: Iterable[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {"06": [], "07": [], "08": []}
    for p in paths:
        _, mm, _ = parse_date_from_filename(p)
        if mm in grouped:
            grouped[mm].append(p)
    return grouped


def build_monthly_medians(clipped_month_files: list[str], year: str, month: str) -> dict[int, str]:
    out_files: dict[int, str] = {}
    month_name_hu = month_folder_name(month)
    month_out_dir = os.path.join(RESULTS_ROOT, year, month_name_hu)
    ensure_dir(month_out_dir)

    if not clipped_month_files:
        return out_files

    for band_idx, label in BAND_LABELS.items():
        arrays = []
        ref_meta = None
        ref_proj = None

        for fp in clipped_month_files:
            arr, meta, proj = read_band_as_nan(fp, band_idx)
            arrays.append(arr)
            if ref_meta is None:
                ref_meta = meta
                ref_proj = proj

        med = median_stack(arrays)
        out_path = os.path.join(
            month_out_dir, f"{label}_{year}_{month}_median.tif")
        write_single_band(out_path, med, ref_meta, ref_proj)
        out_files[band_idx] = out_path

    return out_files


def build_summer_medians(monthly_outputs: dict[str, dict[int, str]], year: str) -> dict[int, str]:
    summer_out_dir = os.path.join(RESULTS_ROOT, year, "egesz")
    ensure_dir(summer_out_dir)
    out_files: dict[int, str] = {}

    for band_idx, label in BAND_LABELS.items():
        inputs = []
        for month in ("06", "07", "08"):
            if month in monthly_outputs and band_idx in monthly_outputs[month]:
                inputs.append(monthly_outputs[month][band_idx])

        if not inputs:
            continue

        arrays = []
        ref_meta = None
        ref_proj = None
        for fp in inputs:
            # monthly outputs már single-band raszterek
            arr, meta, proj = read_band_as_nan(fp, 1)
            arrays.append(arr)
            if ref_meta is None:
                ref_meta = meta
                ref_proj = proj

        med = median_stack(arrays)
        out_path = os.path.join(
            summer_out_dir, f"{label}_{year}_JJA_median.tif")
        write_single_band(out_path, med, ref_meta, ref_proj)
        out_files[band_idx] = out_path

    return out_files


def main() -> int:
    ensure_dir(CLIP_ROOT)
    ensure_dir(RESULTS_ROOT)

    input_tifs = list_snap_tifs(SNAP_IN_DIR)
    if not input_tifs:
        print(f"Nincs TIFF a SNAP bemeneti mappában: {SNAP_IN_DIR}")
        return 1

    bounds = get_reprojected_aoi_extent(AOI_PATH, TARGET_EPSG)
    bounds = align_bounds(bounds, TARGET_RES)

    print("AOI extent (EPSG:23700, illesztve):", bounds)

    # 1) Dátumos fájlok kivágása hónapok szerint
    clipped_paths = []
    for in_tif in input_tifs:
        yy, mm, dd = parse_date_from_filename(in_tif)
        month_name_hu = month_folder_name(mm)
        out_dir = os.path.join(CLIP_ROOT, yy, month_name_hu)
        ensure_dir(out_dir)

        out_tif = os.path.join(out_dir, f"{yy}_{mm}_{dd}_clip.tif")
        if not os.path.exists(out_tif):
            print("Kivágás:", Path(in_tif).name, "->", out_tif)
            clip_and_reproject(in_tif, out_tif, AOI_PATH, bounds)
        else:
            print("Kihagyva (már létezik):", out_tif)

        clipped_paths.append(out_tif)

    # 2) Havi mediánok
    grouped = group_by_month(clipped_paths)
    monthly_outputs: dict[str, dict[int, str]] = {}

    for month in ("06", "07", "08"):
        files = grouped.get(month, [])
        if not files:
            print(f"Nincs kivágott fájl ehhez a hónaphoz: {month}")
            continue
        print(f"Havi medián készítése: {month} ({len(files)} fájl)")
        monthly_outputs[month] = build_monthly_medians(files, YEAR, month)

    # 3) Nyári mediánok
    if monthly_outputs:
        print("Nyári (JJA) mediánok készítése...")
        build_summer_medians(monthly_outputs, YEAR)

    print("Kész.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
