from qgis.PyQt.QtGui import QImage, QColor, QPainter
from qgis.PyQt.QtCore import QSize
from qgis.core import QgsApplication, QgsRasterLayer, QgsMapSettings, QgsMapRendererParallelJob, QgsRectangle
import os
from pathlib import Path

RESULT_ROOT = r"D:\diplomamunka\eredmenyek"
FINAL_MAP_ROOT = r"D:\diplomamunka\eredmenyek\vegso_terkepek"
STYLE_QML = {
    "LST":  r"D:\diplomamunka\qgis\symbology\LST.qml",
    "NDVI": r"D:\diplomamunka\qgis\symbology\NDVI.qml",
    "NDBI": r"D:\diplomamunka\qgis\symbology\NDBI.qml",
}
EXPORT_WIDTH = 2600
EXPORT_HEIGHT = 1800
BACKGROUND_WHITE = True
EXTENT_PADDING_RATIO = 0.02
QGIS_PREFIX_CANDIDATES = [
    os.environ.get("QGIS_PREFIX_PATH", ""),
    r"C:\Program Files\QGIS 3.34.14",
    r"C:\Program Files\QGIS 3.34.0",
    r"C:\Program Files\QGIS 3.34.1",
]


def ensure_qgis_prefix():
    for c in QGIS_PREFIX_CANDIDATES:
        if c and os.path.isdir(c):
            return c
    return None


QGIS_PREFIX = ensure_qgis_prefix()
if QGIS_PREFIX:
    os.environ.setdefault("QGIS_PREFIX_PATH", QGIS_PREFIX)


def detect_index_type(filename: str):
    upper = filename.upper()
    if "LST" in upper:
        return "LST"
    if "NDVI" in upper:
        return "NDVI"
    if "NDBI" in upper:
        return "NDBI"
    return None


qgs = QgsApplication([], False)
if QGIS_PREFIX:
    QgsApplication.setPrefixPath(QGIS_PREFIX, True)
qgs.initQgis()


def padded_extent(ext: QgsRectangle, ratio: float = 0.02) -> QgsRectangle:
    xpad = ext.width() * ratio
    ypad = ext.height() * ratio
    return QgsRectangle(ext.xMinimum() - xpad, ext.yMinimum() - ypad, ext.xMaximum() + xpad, ext.yMaximum() + ypad)


def render_layer_to_png(raster_path: str, qml_path: str, out_png: str):
    layer = QgsRasterLayer(raster_path, Path(raster_path).stem)
    if not layer.isValid():
        raise RuntimeError(f"Érvénytelen raszter: {raster_path}")
    if not os.path.exists(qml_path):
        raise FileNotFoundError(f"Nincs meg a QML stílus: {qml_path}")

    msg, ok = layer.loadNamedStyle(qml_path)
    if not ok:
        raise RuntimeError(
            f"Nem sikerült betölteni a stílust: {qml_path}\n{msg}")
    layer.triggerRepaint()

    settings = QgsMapSettings()
    settings.setLayers([layer])
    settings.setDestinationCrs(layer.crs())
    settings.setExtent(padded_extent(layer.extent(), EXTENT_PADDING_RATIO))
    settings.setOutputSize(QSize(EXPORT_WIDTH, EXPORT_HEIGHT))
    settings.setOutputDpi(300)

    image = QImage(EXPORT_WIDTH, EXPORT_HEIGHT, QImage.Format_ARGB32)
    image.fill(QColor(255, 255, 255, 255)
               if BACKGROUND_WHITE else QColor(255, 255, 255, 0))

    painter = QPainter(image)
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    painter.drawImage(0, 0, job.renderedImage())
    painter.end()

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    if not image.save(out_png, "PNG"):
        raise RuntimeError(f"Nem sikerült menteni: {out_png}")


def main():
    result_root = os.path.normpath(RESULT_ROOT)
    final_root = os.path.normpath(FINAL_MAP_ROOT)
    if not os.path.isdir(result_root):
        raise SystemExit(f"Nincs ilyen eredmény mappa: {result_root}")

    processed = 0
    skipped = 0
    for root, dirs, files in os.walk(result_root):
        dirs[:] = [d for d in dirs if os.path.normpath(
            os.path.join(root, d)) != final_root]
        for fn in files:
            if not fn.lower().endswith((".tif", ".tiff")):
                continue
            src = os.path.join(root, fn)
            if os.path.commonpath([os.path.normpath(src), final_root]) == final_root:
                continue
            idx = detect_index_type(fn)
            if idx is None:
                print(
                    f"[SKIP] Nem derül ki az index típusa a fájlnévből: {src}")
                skipped += 1
                continue
            qml = STYLE_QML.get(idx)
            rel_dir = os.path.relpath(root, result_root)
            out_png = os.path.join(final_root, rel_dir, Path(fn).stem + ".png")
            print(f"[OK] {idx}: {src} -> {out_png}")
            render_layer_to_png(src, qml, out_png)
            processed += 1
    print(f"\nKész. Feldolgozott: {processed}, kihagyott: {skipped}")


if __name__ == "__main__":
    try:
        main()
    finally:
        qgs.exitQgis()
