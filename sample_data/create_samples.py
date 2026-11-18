"""Generate three tiny, synthetic training shapefiles around Lahore.

They are fabricated for demonstrating automation, NOT actual RUDA geodata.
Usage: python sample_data/create_samples.py
Requires: pip install pyshp pyproj
"""
from pathlib import Path
import shutil
import tempfile
import zipfile
import shapefile
from pyproj import CRS

ROOT = Path(__file__).resolve().parent
PRJ = CRS.from_epsg(4326).to_wkt(version='WKT1_ESRI')


def archive_shapefile(name, builder):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / name
        writer = shapefile.Writer(str(root))
        builder(writer)
        writer.close()
        root.with_suffix('.prj').write_text(PRJ, encoding='utf-8')
        root.with_suffix('.cpg').write_text('UTF-8', encoding='utf-8')
        zip_path = ROOT / (name + '.zip')
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                file = root.with_suffix(ext)
                z.write(file, arcname=file.name)
        print('Created:', zip_path.name)


def points(w):
    w.field('OBJECTID', 'N', size=8)
    w.field('x', 'F', size=18, decimal=7)
    w.field('y', 'F', size=18, decimal=7)
    w.field('zz', 'F', size=12, decimal=3)
    for i, (x, y, z) in enumerate([
        (74.303,31.515,212.45),(74.308,31.521,213.15),
        (74.313,31.518,212.98),(74.318,31.524,213.64),
        (74.323,31.520,214.12),(74.328,31.525,214.82),
        (74.333,31.519,214.53),(74.340,31.523,215.26),
    ], 1):
        w.point(x, y)
        w.record(i, x, y, z)


def lines(w):
    w.field('OBJECTID', 'N', size=8)
    w.field('name', 'C', size=60)
    w.field('dia_mm', 'N', size=8)
    w.field('type', 'C', size=30)
    paths = [
        ([(74.296,31.511),(74.308,31.516),(74.320,31.520)],'Demo Supply A',350,'Water'),
        ([(74.304,31.526),(74.317,31.524),(74.331,31.529)],'Demo Supply B',450,'Water'),
        ([(74.315,31.511),(74.326,31.517),(74.339,31.520)],'Demo Sewer C',600,'Sewer'),
    ]
    for idx,(coords,name,dia,kind) in enumerate(paths,1):
        w.line([coords]); w.record(idx,name,dia,kind)


def polygons(w):
    w.field('OBJECTID', 'N', size=8)
    w.field('mauza_name', 'C', size=50)
    w.field('tehsil', 'C', size=40)
    polygons_and_names = [
        ([(74.291,31.502),(74.291,31.519),(74.313,31.519),(74.313,31.502),(74.291,31.502)],'Demo Mauza A'),
        ([(74.313,31.502),(74.313,31.519),(74.336,31.519),(74.336,31.502),(74.313,31.502)],'Demo Mauza B'),
        ([(74.291,31.519),(74.291,31.537),(74.313,31.537),(74.313,31.519),(74.291,31.519)],'Demo Mauza C'),
        ([(74.313,31.519),(74.313,31.537),(74.336,31.537),(74.336,31.519),(74.313,31.519)],'Demo Mauza D'),
    ]
    for idx,(coords,name) in enumerate(polygons_and_names,1):
        # pyshp uses clockwise exterior rings for polygon shapefiles.
        w.poly([coords]); w.record(idx,name,'Lahore')


if __name__ == '__main__':
    archive_shapefile('01_Spot_Level_Points',points)
    archive_shapefile('02_Water_Lines',lines)
    archive_shapefile('03_Mauza_Polygons',polygons)
