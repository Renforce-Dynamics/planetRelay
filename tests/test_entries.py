from pathlib import Path
import socket

import pytest

from planetrelay.config import RelayConfigError, load_config
from planetrelay.runtime import main


ROOT = Path(__file__).resolve().parents[1]


def test_explicit_entry_and_required_argument_without_io(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('offline check opened a socket'))
    assert main(['--config', str(ROOT / 'configs/entry/entry_relay.yaml'), '--check']) == 0
    with pytest.raises(SystemExit) as error:
        main(['--check'])
    assert error.value.code == 2


def test_missing_entry_cannot_fall_back_to_package_or_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RelayConfigError):
        load_config('configs/entry/entry_relay.yaml')
    with pytest.raises(RelayConfigError, match='filesystem entry'):
        load_config('pkg://planetrelay/data/loopback.yaml')
    assert not list((ROOT / 'src').rglob('*.yaml'))
