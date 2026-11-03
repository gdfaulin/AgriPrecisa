# -*- coding: utf-8 -*-
"""
AgriPrecisa: choice of the default output folder (no QGIS imports, unit-tested).
"""

import os

PROJECT_SUBFOLDER = "AgriPrecisa"


def default_output_folder(last_folder, project_home):
    """
    Default output folder of the wizard and where it came from:

    1. ``last_folder``: the folder chosen in the previous run, if it still exists;
    2. ``<project folder>/AgriPrecisa``: when the QGIS project has been saved
       (created on demand when the wizard runs);
    3. ``""``: project not saved and no previous folder; the user must choose one.

    Returns (folder, source) with source in {"last", "project", "none"}.
    """
    if last_folder and os.path.isdir(last_folder):
        return os.path.normpath(last_folder), "last"
    if project_home and os.path.isdir(project_home):
        return os.path.normpath(os.path.join(project_home, PROJECT_SUBFOLDER)), "project"
    return "", "none"


def prepare_output_folder(folder):
    """
    Make sure ``folder`` exists and is writable, creating it (and missing parents) when
    needed. Returns True on success.
    """
    if not folder:
        return False
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return False
    return os.path.isdir(folder) and os.access(folder, os.W_OK)


# ---------------------------------------------------------------------------
# File and field names (Shapefile)
# ---------------------------------------------------------------------------
GRID_SUFFIX = "Grade Padrão"
SHP_FIELD_MAX = 10
_INVALID = '<>:"/\\|?*'


def sanitize_file_name(name):
    """Keep the layer name as typed, removing only characters not allowed in file names."""
    clean = "".join("_" if (c in _INVALID or ord(c) < 32) else c for c in str(name)).strip(" .")
    return clean or "talhao"


def format_size(value):
    """5 -> '5', 2.5 -> '2,5' (no trailing zeros)."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def grid_file_name(boundary_name, cell):
    """'<boundary layer>_Grade Padrão_<cell>x<cell>.shp'."""
    size = format_size(cell)
    return f"{sanitize_file_name(boundary_name)}_{GRID_SUFFIX}_{size}x{size}.shp"


def result_file_name(boundary_name, cell, stamp=""):
    """'<boundary layer>_IDW_<cell>x<cell><stamp>.shp' (grid with the interpolated means)."""
    size = format_size(cell)
    return f"{sanitize_file_name(boundary_name)}_IDW_{size}x{size}{stamp}.shp"


def shapefile_field_names(attributes, existing=()):
    """
    Column names for the interpolated means: the attribute name itself, ASCII, at most
    10 characters (Shapefile limit). Names repeated (or already used by ``existing`` fields)
    get _2, _3... keeping the 10-character limit.
    """
    import re
    import unicodedata
    used = {e.lower() for e in existing}
    out = []
    for name in attributes:
        base = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
        base = re.sub(r"[^0-9A-Za-z_]+", "_", base).strip("_") or "campo"
        base = base[:SHP_FIELD_MAX]
        cand, k = base, 2
        while cand.lower() in used:
            suffix = f"_{k}"
            cand = base[:SHP_FIELD_MAX - len(suffix)] + suffix
            k += 1
        used.add(cand.lower())
        out.append(cand)
    return out
