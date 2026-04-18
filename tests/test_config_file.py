"""Tests for config_file.py."""
from pathlib import Path

import pytest
import yaml

from backup_server.config_file import ConfigFile


def write_config(tmp_path: Path, data: dict) -> Path:
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(data), encoding="utf-8")
    return f


def minimal_data(tmp_path: Path) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    return {
        "dir_backup_local": "/backup/local",
        "dir_backup_remote": "user@host:/remote",
        "email_sender": "sender@example.com",
        "email_report": "report@example.com",
        "tasks": [{"name": "photos", "dir_source": str(src), "excludes": []}],
    }


def test_read_valid_config(tmp_path):
    data = minimal_data(tmp_path)
    config_file = write_config(tmp_path, data)
    result = ConfigFile(file_config=str(config_file)).read()
    assert result["dir_backup_local"] == "/backup/local"
    assert result["tasks"][0]["name"] == "photos"


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ConfigFile(file_config=str(tmp_path / "nonexistent.yml")).read()


def test_missing_required_top_level_key(tmp_path):
    data = minimal_data(tmp_path)
    del data["email_report"]
    config_file = write_config(tmp_path, data)
    with pytest.raises(KeyError, match="email_report"):
        ConfigFile(file_config=str(config_file)).read()


def test_missing_task_name(tmp_path):
    data = minimal_data(tmp_path)
    del data["tasks"][0]["name"]
    config_file = write_config(tmp_path, data)
    with pytest.raises(KeyError, match="name"):
        ConfigFile(file_config=str(config_file)).read()


def test_missing_task_dir_source(tmp_path):
    data = minimal_data(tmp_path)
    del data["tasks"][0]["dir_source"]
    config_file = write_config(tmp_path, data)
    with pytest.raises(KeyError, match="dir_source"):
        ConfigFile(file_config=str(config_file)).read()


def test_admin_email_defaults_to_empty_when_absent(tmp_path):
    data = minimal_data(tmp_path)
    config_file = write_config(tmp_path, data)
    result = ConfigFile(file_config=str(config_file)).read()
    assert result["email_admin"] == ""


def test_admin_email_cleared_when_same_as_report(tmp_path):
    data = minimal_data(tmp_path)
    data["email_admin"] = data["email_report"]
    config_file = write_config(tmp_path, data)
    result = ConfigFile(file_config=str(config_file)).read()
    assert result["email_admin"] == ""


def test_admin_email_preserved_when_different(tmp_path):
    data = minimal_data(tmp_path)
    data["email_admin"] = "admin@example.com"
    config_file = write_config(tmp_path, data)
    result = ConfigFile(file_config=str(config_file)).read()
    assert result["email_admin"] == "admin@example.com"
