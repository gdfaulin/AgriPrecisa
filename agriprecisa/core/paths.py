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
