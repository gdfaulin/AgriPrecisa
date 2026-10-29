"""Packaging rules of plugins.qgis.org and regression tests for fixed bugs."""
import configparser
import os
import re

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agriprecisa")
REQUIRED = ["name", "qgisMinimumVersion", "description", "about", "version", "author",
            "email", "repository"]


def read_metadata():
    cp = configparser.ConfigParser()
    cp.read(os.path.join(PLUGIN, "metadata.txt"), encoding="utf-8")
    return cp["general"]


def test_required_metadata_fields():
    md = read_metadata()
    for field in REQUIRED:
        assert md.get(field, "").strip(), f"metadata.txt: missing '{field}'"
    assert re.fullmatch(r"\d+\.\d+\.\d+", md["version"])
    assert "plugin" not in md["name"].lower()


def test_mandatory_files_and_folder_name():
    for name in ("metadata.txt", "__init__.py", "LICENSE", "icon.png"):
        assert os.path.isfile(os.path.join(PLUGIN, name)), name
    assert re.fullmatch(r"[A-Za-z_-][A-Za-z0-9_-]*", os.path.basename(PLUGIN))


def test_icons_referenced_exist():
    md = read_metadata()
    assert os.path.isfile(os.path.join(PLUGIN, md["icon"]))
    for icon in ("idw.png", "help.png"):
        assert os.path.isfile(os.path.join(PLUGIN, "icons", icon))


def _sources():
    for folder, _, files in os.walk(PLUGIN):
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(folder, name)
                yield path, open(path, encoding="utf-8").read()


def test_regression_no_qwizard_dialogcode():
    # Bug fixed in v0.1: QWizard.DialogCode does not exist; the correct enum is QDialog.DialogCode.
    for path, text in _sources():
        assert "QWizard.DialogCode" not in text, path


def test_regression_no_module_level_main_call():
    # The original script ended with a bare "main()" call, which would run the wizard
    # as soon as QGIS imported the plugin.
    for path, text in _sources():
        assert not re.search(r"^main\(\)\s*$", text, re.M), path
