"""Default output folder of the wizard (step 1)."""
import os

from agriprecisa.core.paths import default_output_folder, prepare_output_folder, PROJECT_SUBFOLDER


def test_last_folder_has_priority(tmp_path):
    last = tmp_path / "escolhida"
    last.mkdir()
    project = tmp_path / "projeto"
    project.mkdir()
    assert default_output_folder(str(last), str(project)) == (os.path.normpath(str(last)), "last")


def test_project_subfolder_when_no_previous_choice(tmp_path):
    folder, source = default_output_folder("", str(tmp_path))
    assert source == "project"
    assert folder == os.path.join(str(tmp_path), PROJECT_SUBFOLDER)
    assert not os.path.exists(folder)               # only created when the wizard runs


def test_deleted_last_folder_falls_back_to_project(tmp_path):
    folder, source = default_output_folder(str(tmp_path / "apagada"), str(tmp_path))
    assert source == "project"


def test_unsaved_project_and_no_history():
    assert default_output_folder("", "") == ("", "none")
    assert default_output_folder(None, None) == ("", "none")


def test_prepare_creates_missing_folder(tmp_path):
    target = tmp_path / "projeto" / PROJECT_SUBFOLDER
    assert prepare_output_folder(str(target))
    assert target.is_dir()
    assert prepare_output_folder(str(target))       # already existing is fine
    assert not prepare_output_folder("")


from agriprecisa.core.paths import (
    grid_file_name, result_file_name, format_size, sanitize_file_name, shapefile_field_names,
)


def test_grid_file_name_uses_boundary_layer_and_cell_size():
    assert grid_file_name("Talhão 1", 5) == "Talhão 1_Grade Padrão_5x5.shp"
    assert grid_file_name("Talhao1", 2.5) == "Talhao1_Grade Padrão_2,5x2,5.shp"
    assert grid_file_name("A/B:C", 10.0) == "A_B_C_Grade Padrão_10x10.shp"


def test_result_file_name():
    assert result_file_name("Talhao1", 10, "_20261103_1000") == "Talhao1_IDW_10x10_20261103_1000.shp"


def test_format_and_sanitize():
    assert format_size(5.0) == "5" and format_size(2.25) == "2,25"
    assert sanitize_file_name('  "x"  ') == "_x_"
    assert sanitize_file_name("...") == "talhao"


def test_shapefile_field_names_limit_and_duplicates():
    names = shapefile_field_names(["SHALLOW", "DEEP", "Potássio (mg/dm³)", "argila", "argila"],
                                  existing=["id", "left"])
    assert names == ["SHALLOW", "DEEP", "Potassio_m", "argila", "argila_2"]
    assert all(len(n) <= 10 for n in names)
    assert shapefile_field_names(["id"], existing=["id"]) == ["id_2"]
    long_dup = shapefile_field_names(["condutividade", "condutividade"])
    assert long_dup == ["condutivid", "condutiv_2"]
