from __future__ import annotations
import copy
import glob
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

YEAR = "2022"

RAW_ROOT = r"D:\diplomamunka\lst_evek\2022_kesz\raw"
GRAPH_TEMPLATE = r"D:\diplomamunka\graphok\lst_ndvi_ndbi.xml"
SNAP_OUT_DIR = r"D:\diplomamunka\snap\2022"

GPT_EXE_CANDIDATES = [
    r"C:\Program Files\esa-snap\bin\gpt.exe",
]

# A subsethez használt polygon (txt fájljából)
# balatonhoz.txt
BALATON_SUBSET_WKT = (
    "POLYGON ((17.762479782104492 47.23748779296875, "
    "18.335102081298828 47.23748779296875, "
    "18.335102081298828 46.75873565673828, "
    "17.762479782104492 46.75873565673828, "
    "17.762479782104492 47.23748779296875, "
    "17.762479782104492 47.23748779296875))"
)

SUBSET_SOURCE_BANDS = "sr_b4,sr_b5,sr_b6,st_b10,qa_pixel"

# végleges képletek
LST_EXPR = (
    "((qa_pixel & 2) == 0) && ((qa_pixel & 4) == 0) && "
    "((qa_pixel & 8) == 0) && ((qa_pixel & 16) == 0) && "
    "((qa_pixel & 32) == 0) ? (st_b10 - 273.15) : NaN"
)

NDVI_EXPR = (
    "(((qa_pixel & 2) == 0) && ((qa_pixel & 4) == 0) && "
    "((qa_pixel & 8) == 0) && ((qa_pixel & 16) == 0) && "
    '((qa_pixel & 32) == 0))?(  ((sr_b5 + sr_b4) == 0) ? NaN : '
    "max(-1.0, min(1.0,  (sr_b5 - sr_b4) / (sr_b5 + sr_b4)) )): NaN"
)

NDBI_EXPR = (
    "(((qa_pixel & 2) == 0) && ((qa_pixel & 4) == 0) && "
    "((qa_pixel & 8) == 0) && ((qa_pixel & 16) == 0) && "
    '((qa_pixel & 32) == 0))?(  ((sr_b6 + sr_b5) == 0) ? NaN : '
    "max(-1.0, min(1.0,  (sr_b6 - sr_b5) / (sr_b6 + sr_b5)) )): NaN"
)

# A script ide menti az átírt scene-specifikus XML-eket
GRAPH_RUN_DIRNAME = "_generated_graphs"


def find_gpt() -> str:
    for candidate in GPT_EXE_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "Nem találom a SNAP GPT-t. Állítsd be a GPT_EXE_CANDIDATES listát a script tetején."
    )


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def find_mtl_files(raw_root: str | Path) -> list[str]:
    pattern = os.path.join(str(raw_root), "**", "*_MTL.txt")
    return sorted(glob.glob(pattern, recursive=True))


def parse_scene_date(mtl_path: str | Path) -> tuple[str, str, str]:
    """
    Kinyeri a felvétel dátumát a Landsat MTL fájlnévből.
    Példa:
      LC08_L2SP_189027_20220706_20220722_02_T1_MTL.txt
    -> ('2022','07','06')
    """
    name = Path(mtl_path).name
    m = re.search(r"_(20\d{6})_", name)
    if not m:
        raise ValueError(f"Nem tudtam dátumot kinyerni ebből: {name}")
    datestr = m.group(1)
    return datestr[:4], datestr[4:6], datestr[6:8]


def patch_graph(template_xml: str, mtl_path: str, out_tif: str) -> ET.ElementTree:
    tree = ET.parse(template_xml)
    root = tree.getroot()

    def find_node(node_id: str) -> ET.Element:
        node = root.find(f"./node[@id='{node_id}']")
        if node is None:
            raise KeyError(f"Hiányzó node az XML-ben: {node_id}")
        return node

    # 1) Read/file
    read_node = find_node("Read")
    read_file_el = read_node.find("./parameters/file")
    if read_file_el is None:
        raise KeyError("A Read node-ban nincs <file> elem.")
    read_file_el.text = mtl_path

    # 2) Subset/sourceBands + geoRegion
    subset_node = find_node("Subset")
    source_bands_el = subset_node.find("./parameters/sourceBands")
    if source_bands_el is None:
        raise KeyError("A Subset node-ban nincs <sourceBands> elem.")
    source_bands_el.text = SUBSET_SOURCE_BANDS

    geo_region_el = subset_node.find("./parameters/geoRegion")
    if geo_region_el is None:
        raise KeyError("A Subset node-ban nincs <geoRegion> elem.")
    geo_region_el.text = BALATON_SUBSET_WKT

    # 3) BandMaths képletek
    def set_expression(node_id: str, expr: str):
        node = find_node(node_id)
        expr_el = node.find("./parameters/targetBands/targetBand/expression")
        if expr_el is None:
            raise KeyError(f"{node_id} node-ban nincs <expression> elem.")
        expr_el.text = expr

    set_expression("BandMaths", LST_EXPR)
    set_expression("BandMaths(2)", NDVI_EXPR)
    set_expression("BandMaths(3)", NDBI_EXPR)

    # 4) Write/file + formatName
    write_node = find_node("Write")
    write_file_el = write_node.find("./parameters/file")
    if write_file_el is None:
        raise KeyError("A Write node-ban nincs <file> elem.")
    write_file_el.text = out_tif

    format_el = write_node.find("./parameters/formatName")
    if format_el is None:
        raise KeyError("A Write node-ban nincs <formatName> elem.")
    format_el.text = "GeoTIFF"

    return tree


def run_gpt(gpt_exe: str, graph_xml_path: str) -> None:
    cmd = [gpt_exe, graph_xml_path]
    print("Futtatás:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"GPT hiba ennél a graphnál: {graph_xml_path}")

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def main() -> int:
    gpt = find_gpt()
    ensure_dir(SNAP_OUT_DIR)
    graph_run_dir = os.path.join(SNAP_OUT_DIR, GRAPH_RUN_DIRNAME)
    ensure_dir(graph_run_dir)

    mtl_files = find_mtl_files(RAW_ROOT)
    if not mtl_files:
        print(f"Nincs egyetlen *_MTL.txt fájl sem itt: {RAW_ROOT}")
        return 1

    print(f"{len(mtl_files)} db MTL fájl találva.")

    for mtl in mtl_files:
        y, m, d = parse_scene_date(mtl)
        out_name = f"{y}_{m}_{d}.tif"
        out_tif = os.path.join(SNAP_OUT_DIR, out_name)

        # Ha már létezik, kihagyjuk
        if os.path.exists(out_tif):
            print(f"Kihagyva (már létezik): {out_tif}")
            continue

        print(f"\nScene feldolgozás: {Path(mtl).name}")
        tree = patch_graph(GRAPH_TEMPLATE, mtl, out_tif)

        run_graph_path = os.path.join(graph_run_dir, f"{y}_{m}_{d}.xml")
        tree.write(run_graph_path, encoding="utf-8", xml_declaration=True)

        run_gpt(gpt, run_graph_path)

    print("\nKész.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
