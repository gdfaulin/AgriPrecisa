"""
Builds dist/agriprecisa-<version>.zip ready for plugins.qgis.org.

Only the "agriprecisa" folder goes into the ZIP, without caches or hidden files.
Usage: python scripts/build_zip.py
"""
import configparser
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "agriprecisa")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}
SKIP_EXT = {".pyc", ".pyo"}

cp = configparser.ConfigParser()
cp.read(os.path.join(PLUGIN, "metadata.txt"), encoding="utf-8")
version = cp["general"]["version"]

os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
target = os.path.join(ROOT, "dist", f"agriprecisa-{version}.zip")
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
    for folder, dirs, files in os.walk(PLUGIN):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.startswith(".") or os.path.splitext(name)[1] in SKIP_EXT:
                continue
            path = os.path.join(folder, name)
            z.write(path, os.path.relpath(path, ROOT))
print("Created", target)
