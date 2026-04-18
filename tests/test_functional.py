# tests/test_functional.py
import pytest
from pathlib import Path
from backup_server.backup_task import BackupTask

@pytest.mark.functional
def test_backup_creates_files_in_destination(tmp_path):
    # Arrange — real source files
    src = tmp_path / "source"
    src.mkdir()
    (src / "document.txt").write_text("important data")
    (src / "photo.jpg").write_bytes(b"\xff\xd8\xff")  # dummy bytes

    dst = tmp_path / "destination"
    dst.mkdir()

    # Point work_dir at the real scripts in your project root
    project_root = Path(__file__).parent.parent

    # Act — no fake runner, uses real subprocess.run
    task = BackupTask(
        task={"name": "test-task", "dir_source": str(src), "excludes": []},
        dir_local=str(dst),
        dir_remote="user@host:/remote",  # sync step will fail, that's ok
        work_dir=project_root,
    )
    status = task.start()

    # Assert — files should have been backed up
    assert status["steps"][0]["step"] == "backup"
    assert status["steps"][0]["success"] is True
    # Check the actual files landed somewhere under dst
    backed_up = list(dst.rglob("document.txt"))
    assert len(backed_up) == 1