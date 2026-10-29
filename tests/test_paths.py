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
