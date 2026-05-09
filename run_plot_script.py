import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, linregress

# fájlok helye
fajlok = {
    2016: r"D:\diplomamunka\data_science\2016_pixels.csv",
    2017: r"D:\diplomamunka\data_science\2017_pixels.csv",
    2018: r"D:\diplomamunka\data_science\2018_pixels.csv",
    2019: r"D:\diplomamunka\data_science\2019_pixels.csv",
    2020: r"D:\diplomamunka\data_science\2020_pixels.csv",
    2021: r"D:\diplomamunka\data_science\2021_pixels.csv",
    2022: r"D:\diplomamunka\data_science\2022_pixels.csv",
    2023: r"D:\diplomamunka\data_science\2023_pixels.csv",
    2024: r"D:\diplomamunka\data_science\2024_pixels.csv",
    2025: r"D:\diplomamunka\data_science\2025_pixels.csv"
}

# mentési mappa
kimeneti_mappa = r"D:\diplomamunka\subplot"
if not os.path.exists(kimeneti_mappa):
    os.makedirs(kimeneti_mappa)

# ide gyűjtjük az összesített eredményeket
eredmenyek = []

# 25%-os mintavétel
mintaarany = 0.25

for ev, fajl in fajlok.items():
    print(f"Feldolgozás: {ev}")

    if not os.path.exists(fajl):
        print(f"Nem található: {fajl}")
        continue

    # fájl beolvasása
    # ha normál csv, ez jó lesz
    adat = pd.read_csv(fajl, sep=",", quotechar='"')

    # ha valamiért minden egy oszlopba ment volna be
    if len(adat.columns) == 1:
        adat = pd.read_csv(fajl, sep=";", quotechar='"')

    # oszlopnevek tisztítása
    adat.columns = [c.strip().replace('"', "") for c in adat.columns]

    # csak a szükséges oszlopok
    szukseges = ["lst", "ndvi", "ndbi"]
    for oszlop in szukseges:
        if oszlop not in adat.columns:
            print(f"Hiányzó oszlop ({oszlop}) ebben a fájlban: {ev}")
            continue

    adat = adat[szukseges].copy()

    # numerikussá alakítás
    for oszlop in szukseges:
        adat[oszlop] = pd.to_numeric(adat[oszlop], errors="coerce")

    adat = adat.dropna()

    if len(adat) == 0:
        print(f"Nincs használható adat: {ev}")
        continue

    # 25%-os minta
    minta = adat.sample(frac=mintaarany, random_state=42)

    # NDVI vs LST

    x1 = minta["ndvi"]
    y1 = minta["lst"]

    r1, p1 = pearsonr(x1, y1)
    regresszio1 = linregress(x1, y1)
    r2_1 = r1 ** 2

    x_vonal1 = np.linspace(x1.min(), x1.max(), 100)
    y_vonal1 = regresszio1.slope * x_vonal1 + regresszio1.intercept

    plt.figure(figsize=(8, 6))
    plt.scatter(x1, y1, s=8, alpha=0.25, color="forestgreen")
    plt.plot(x_vonal1, y_vonal1, linestyle="--",
             linewidth=2, color="darkgreen")

    plt.xlabel("NDVI")
    plt.ylabel("LST (°C)")
    plt.title(f"{ev} - NDVI és LST kapcsolata")
    plt.grid(True, alpha=0.3)

    szoveg1 = f"r = {r1:.3f}\nR² = {r2_1:.3f}\np = "
    if p1 < 0.001:
        szoveg1 += "< 0,001"
    else:
        szoveg1 += str(round(p1, 3)).replace(".", ",")

    plt.text(
        0.05, 0.95, szoveg1,
        transform=plt.gca().transAxes,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.8, edgecolor="gray")
    )

    plt.tight_layout()
    plt.savefig(os.path.join(kimeneti_mappa, f"{ev}_ndvi_lst.png"), dpi=300)
    plt.close()

    # NDBI vs LST

    x2 = minta["ndbi"]
    y2 = minta["lst"]

    r2corr, p2 = pearsonr(x2, y2)
    regresszio2 = linregress(x2, y2)
    r2_2 = r2corr ** 2

    x_vonal2 = np.linspace(x2.min(), x2.max(), 100)
    y_vonal2 = regresszio2.slope * x_vonal2 + regresszio2.intercept

    plt.figure(figsize=(8, 6))
    plt.scatter(x2, y2, s=8, alpha=0.25, color="mediumpurple")
    plt.plot(x_vonal2, y_vonal2, linestyle="--", linewidth=2, color="indigo")

    plt.xlabel("NDBI")
    plt.ylabel("LST (°C)")
    plt.title(f"{ev} - NDBI és LST kapcsolata")
    plt.grid(True, alpha=0.3)

    szoveg2 = f"r = {r2corr:.3f}\nR² = {r2_2:.3f}\np = "
    if p2 < 0.001:
        szoveg2 += "< 0,001"
    else:
        szoveg2 += str(round(p2, 3)).replace(".", ",")

    plt.text(
        0.05, 0.95, szoveg2,
        transform=plt.gca().transAxes,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.8, edgecolor="gray")
    )

    plt.tight_layout()
    plt.savefig(os.path.join(kimeneti_mappa, f"{ev}_ndbi_lst.png"), dpi=300)
    plt.close()

    # eredmények táblázatba

    eredmenyek.append({
        "year": ev,
        "kapcsolat": "NDVI-LST",
        "r": r1,
        "R2": r2_1,
        "p": p1,
        "minta_db": len(minta)
    })

    eredmenyek.append({
        "year": ev,
        "kapcsolat": "NDBI-LST",
        "r": r2corr,
        "R2": r2_2,
        "p": p2,
        "minta_db": len(minta)
    })

# összesítő csv mentése
eredmeny_df = pd.DataFrame(eredmenyek)
eredmeny_df.to_csv(os.path.join(
    kimeneti_mappa, "korrelacios_eredmenyek.csv"), index=False, encoding="utf-8-sig")

print("Kész.")
