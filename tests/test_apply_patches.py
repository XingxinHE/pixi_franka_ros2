import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLY_PATCHES = PROJECT_ROOT / "scripts" / "apply_patches.sh"
CRISP_PATCH_ROOT = PROJECT_ROOT / "patches" / "crisp_controllers"
CRISP_SOURCE_ROOT = PROJECT_ROOT / "src" / "crisp_controllers"
NEW_FILES_MANIFEST = PROJECT_ROOT / "patches" / "new-files.manifest"

CRISP_PATCH_FILES = {
    "CMakeLists.txt",
    "include/crisp_controllers/cartesian_controller.hpp",
    "include/crisp_controllers/utils/target_command_watchdog.hpp",
    "include/crisp_controllers/utils/target_pose_validation.hpp",
    "src/cartesian_controller.cpp",
    "src/cartesian_controller.yaml",
    "tests/test_target_command_watchdog.cpp",
    "tests/test_target_pose_validation.cpp",
}
CRISP_NEW_FILES = {
    "include/crisp_controllers/utils/target_command_watchdog.hpp",
    "include/crisp_controllers/utils/target_pose_validation.hpp",
    "tests/test_target_command_watchdog.cpp",
    "tests/test_target_pose_validation.cpp",
}


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _run_applicator(workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(APPLY_PATCHES)],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )


def test_applies_existing_file_and_explicitly_manifested_new_file(tmp_path):
    _write(tmp_path / "patches" / "new-files.manifest", "demo/new.txt\n")
    _write(tmp_path / "patches" / "demo" / "existing.txt", "patched existing\n")
    _write(tmp_path / "patches" / "demo" / "new.txt", "manifested new\n")
    _write(tmp_path / "src" / "demo" / "existing.txt", "upstream existing\n")

    result = _run_applicator(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "src" / "demo" / "existing.txt").read_text() == (
        "patched existing\n"
    )
    assert (tmp_path / "src" / "demo" / "new.txt").read_text() == ("manifested new\n")
    assert "Files copied: 2; created: 1" in result.stdout


def test_rejects_unmanifested_new_file(tmp_path):
    _write(tmp_path / "patches" / "new-files.manifest", "")
    _write(tmp_path / "patches" / "demo" / "unexpected.txt", "must not copy\n")
    (tmp_path / "src" / "demo").mkdir(parents=True)

    result = _run_applicator(tmp_path)

    assert result.returncode != 0
    assert "Missing target file for unmanifested patch" in result.stdout
    assert not (tmp_path / "src" / "demo" / "unexpected.txt").exists()


def test_rejects_noncanonical_manifest_path(tmp_path):
    _write(tmp_path / "patches" / "new-files.manifest", "demo/../escape.txt\n")
    (tmp_path / "src").mkdir()

    result = _run_applicator(tmp_path)

    assert result.returncode != 0
    assert "Invalid new-file manifest path" in result.stdout
    assert not (tmp_path / "escape.txt").exists()


def test_rejects_symlink_target(tmp_path):
    _write(tmp_path / "patches" / "new-files.manifest", "")
    _write(tmp_path / "patches" / "demo" / "existing.txt", "must not copy\n")
    outside = tmp_path / "outside.txt"
    _write(outside, "outside\n")
    target = tmp_path / "src" / "demo" / "existing.txt"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)

    result = _run_applicator(tmp_path)

    assert result.returncode != 0
    assert "Patch target is not a regular file" in result.stdout
    assert outside.read_text() == "outside\n"


def test_rejects_symlinked_parent_for_manifested_new_file(tmp_path):
    _write(
        tmp_path / "patches" / "new-files.manifest",
        "demo/redirected/new.txt\n",
    )
    _write(
        tmp_path / "patches" / "demo" / "redirected" / "new.txt",
        "must not copy\n",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    target_parent = tmp_path / "src" / "demo" / "redirected"
    target_parent.parent.mkdir(parents=True)
    target_parent.symlink_to(outside, target_is_directory=True)

    result = _run_applicator(tmp_path)

    assert result.returncode != 0
    assert "Patch target parent may not be a symlink" in result.stdout
    assert not (outside / "new.txt").exists()


def test_preflights_all_targets_before_copying(tmp_path):
    _write(tmp_path / "patches" / "new-files.manifest", "")
    _write(tmp_path / "patches" / "demo" / "a_existing.txt", "patched\n")
    _write(tmp_path / "patches" / "demo" / "z_unexpected.txt", "must not copy\n")
    existing = tmp_path / "src" / "demo" / "a_existing.txt"
    _write(existing, "upstream\n")

    result = _run_applicator(tmp_path)

    assert result.returncode != 0
    assert "Missing target file for unmanifested patch" in result.stdout
    assert existing.read_text() == "upstream\n"
    assert not (tmp_path / "src" / "demo" / "z_unexpected.txt").exists()


def test_crisp_snapshot_set_and_new_file_manifest():
    patch_files = {
        str(path.relative_to(CRISP_PATCH_ROOT))
        for path in CRISP_PATCH_ROOT.rglob("*")
        if path.is_file()
    }
    assert patch_files == CRISP_PATCH_FILES

    manifested_new_files = {
        line.removeprefix("crisp_controllers/")
        for line in NEW_FILES_MANIFEST.read_text(encoding="utf-8").splitlines()
        if line
    }
    assert manifested_new_files == CRISP_NEW_FILES


def test_crisp_snapshot_matches_v230_worktree():
    if not (CRISP_SOURCE_ROOT / ".git").is_dir():
        pytest.skip("run the Jazzy clone task before checking patch snapshot parity")

    absent_upstream = set()
    for relative_path in sorted(CRISP_PATCH_FILES):
        assert (CRISP_PATCH_ROOT / relative_path).read_bytes() == (
            CRISP_SOURCE_ROOT / relative_path
        ).read_bytes()
        upstream_result = subprocess.run(
            [
                "git",
                "-C",
                str(CRISP_SOURCE_ROOT),
                "cat-file",
                "-e",
                f"HEAD:{relative_path}",
            ],
            capture_output=True,
            check=False,
        )
        if upstream_result.returncode != 0:
            absent_upstream.add(relative_path)

    assert absent_upstream == CRISP_NEW_FILES
