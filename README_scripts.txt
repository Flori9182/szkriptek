Használat

1) SNAP script
Fájl: run_snap_batch.py

Mit csinál:
- a D:\diplomamunka\lst_evek\2024\raw mappát bejárja
- minden kibontott Landsat scene *_MTL.txt fájlját megkeresi
- a D:\diplomamunka\graphok\lst_ndvi_ndbi.xml graph template-et scene-specifikusan átírja
- GeoTIFF-et készít ide:
  D:\diplomamunka\snap\2024
- fájlnév: YYYY_MM_DD.tif

Fontos:
- a graph logikája nem változik:
  Read -> Subset -> 3xBandMaths -> BandMerge -> Write
- a képletek a felhasználó által véglegesnek megadott változatok

Futtatás:
python run_snap_batch.py

2) QGIS/GDAL script
Fájl: run_qgis_batch.py

Mit csinál:
- beolvassa a SNAP kimeneti TIFF-eket innen:
  D:\diplomamunka\snap\2024
- EPSG:23700-ba vetíti és levágja a vegso_aoi.geojson alapján
- kivágott dátumos fájlokat ide menti:
  D:\diplomamunka\qgis\kivágatok\2024\<hónap>\
- hónaponként sávonként mediánt számol:
  NDVI / LST / NDBI
- havi mediánokat ide menti:
  D:\diplomamunka\eredmenyek\2024\<hónap>\
- a 3 havi mediánból nyári mediánt számol és ide menti:
  D:\diplomamunka\eredmenyek\2024\egesz\

Futtatás:
Olyan Python környezetből futtasd, ahol a GDAL és a numpy elérhető.
A legjobb: OSGeo4W Shell / QGIS Python környezet.

python run_qgis_batch.py

Megjegyzés:
- a SNAP output band-sorrendje:
  Band 1 = NDVI
  Band 2 = LST
  Band 3 = NDBI
- a QGIS/GDAL script erre épít.

3)
QGIS styles script

Mit csinál:
- a készített mediánkompozitokat látja el a QGIS-ben készült stílusokkal
- egyszerre megy végig az összes eredményen

FONTOS: a dátumokat átírni a szkriptekben, hogy a jó évre számoljanak, valamint az inputokat és outputokat, kivétel
  a style szkript-nél hiszen ez inkább ellenőrzésre volt való