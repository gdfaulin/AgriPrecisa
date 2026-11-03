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


def test_cv_table_decimals_show_three_significant_digits():
    # Regression: RMSE values like 0.039 and 0.045 were shown as 0,04 / 0,05 and the
    # table could not be compared. cv_dialog needs QGIS, so the helper is checked by source.
    import ast
    src = open(os.path.join(PLUGIN, "gui", "cv_dialog.py"), encoding="utf-8").read()
    fn = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "significant_decimals"][0]
    import math
    import numpy as np
    ns = {"math": math}
    exec(compile(ast.Module([fn], []), "cv", "exec"), ns)
    f = ns["significant_decimals"]
    assert f(np.array([0.0391, 0.045])) == 4
    assert f(np.array([12.3, 40.1])) == 2
    assert f(np.array([float("nan")])) == 2


def test_help_reviewed_for_this_version():
    # Rule: every new version must review the Help texts (wizard pages, "Saiba mais" and the
    # Processing help) and then set i18n.HELP_REVIEWED_VERSION to the new version.
    from agriprecisa import i18n
    version = read_metadata()["version"]
    assert i18n.HELP_REVIEWED_VERSION == version, (
        f"Help texts not reviewed for version {version}: review help_page*, *_more and "
        f"alg_help in i18n.py and set HELP_REVIEWED_VERSION = '{version}'")


def test_help_texts_use_only_known_html_tags():
    # Regression: "<contorno>_Grade Padrão_<célula>x<célula>.shp" in the Processing help was
    # read as HTML and shown as "_Grade Padrão_ x .shp".
    from agriprecisa import i18n
    allowed = {"b", "i", "br", "ul", "li", "sub", "sup", "a"}
    for key, entry in i18n.STRINGS.items():
        for lang, text in entry.items():
            for tag in re.findall(r"</?([A-Za-z][^\s>/]*)", text):
                assert tag.lower() in allowed, f"{key} [{lang}]: unexpected tag <{tag}>"
