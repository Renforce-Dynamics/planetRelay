from pathlib import Path
import pytest
from planetrelay.config import RelayConfigError, load_config


def test_task_override_keeps_source_defaults(tmp_path):
    task = tmp_path / "relay.yaml"
    base = Path(__file__).resolve().parents[1] / "configs/entry/entry_relay.yaml"
    task.write_text(f"extends: {base}\nroutes:\n  probe:\n    target_port: 50601\n")
    cfg = load_config(task)
    assert cfg.routes[0].target_port == 50601
    assert cfg.routes[0].delivery == "all"
    assert cfg.routes[0].allowed_source_hosts == ("127.0.0.1",)


def test_duplicate_yaml_fields_are_rejected(tmp_path):
    task = tmp_path / "relay.yaml"
    task.write_text("version: 1\nversion: 2\n")
    with pytest.raises(RelayConfigError, match="duplicate"):
        load_config(task)
