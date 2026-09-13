import socket

import pytest

from planetrelay.config import RelayConfigError, load_config
from planetrelay.runtime import RelayRuntime



def _free_udp_port():
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind(("127.0.0.1", 0))
  port = sock.getsockname()[1]
  sock.close()
  return port


def test_relay_rejects_duplicate_ingress_ports(tmp_path):
  path = tmp_path / "relay.yaml"
  path.write_text(
    "version: 1\ningress: {bind_host: 127.0.0.1}\ntarget: {host: 127.0.0.1}\n"
    "routes:\n  a: {port: 50550, magic: PLNU, packet_size: 108}\n"
    "  b: {port: 50550, magic: PLNJ, packet_size: 72}\n",
    encoding="utf-8",
  )
  with pytest.raises(RelayConfigError, match="ports must be unique"):
    load_config(path)


def test_relay_forwards_only_latest_valid_datagram(tmp_path):
  ingress_port = _free_udp_port()
  target_port = _free_udp_port()
  path = tmp_path / "relay.yaml"
  path.write_text(
    f"version: 1\ningress: {{bind_host: 127.0.0.1}}\n"
    f"target: {{host: 127.0.0.1}}\nroutes:\n"
    f"  test: {{port: {ingress_port}, target_port: {target_port}, magic: TEST, packet_size: 8}}\n",
    encoding="utf-8",
  )
  receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  receiver.bind(("127.0.0.1", target_port))
  receiver.settimeout(1.0)
  sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  runtime = RelayRuntime(load_config(path))
  runtime.open()
  try:
    sender.sendto(b"BAD!0000", ("127.0.0.1", ingress_port))
    sender.sendto(b"TEST0001", ("127.0.0.1", ingress_port))
    sender.sendto(b"TEST0002", ("127.0.0.1", ingress_port))
    events = runtime.selector.select(1.0)
    assert events
    key, _ = events[0]
    runtime.relay_ready(key.fileobj, key.data)
    assert receiver.recv(64) == b"TEST0002"
    stats = runtime.stats["test"]
    assert (stats.received, stats.forwarded, stats.coalesced, stats.invalid) == (3, 1, 1, 1)
  finally:
    runtime.close()
    sender.close()
    receiver.close()


def test_relay_forwards_all_variable_length_record_chunks(tmp_path):
  ingress_port = _free_udp_port()
  target_port = _free_udp_port()
  path = tmp_path / "relay.yaml"
  path.write_text(
    f"version: 1\ningress: {{bind_host: 127.0.0.1}}\n"
    f"target: {{host: 127.0.0.1}}\nroutes:\n"
    f"  record: {{port: {ingress_port}, target_port: {target_port}, "
    f"magic: A3DB, min_packet_size: 8, delivery: all}}\n",
    encoding="utf-8",
  )
  receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  receiver.bind(("127.0.0.1", target_port))
  receiver.settimeout(1.0)
  sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  runtime = RelayRuntime(load_config(path))
  runtime.open()
  chunks = (b"A3DB0001", b"A3DB0002-variable")
  try:
    for chunk in chunks:
      sender.sendto(chunk, ("127.0.0.1", ingress_port))
    events = runtime.selector.select(1.0)
    assert events
    key, _ = events[0]
    runtime.relay_ready(key.fileobj, key.data)
    assert tuple(receiver.recv(64) for _ in chunks) == chunks
    stats = runtime.stats["record"]
    assert (stats.received, stats.forwarded, stats.coalesced) == (2, 2, 0)
  finally:
    runtime.close()
    sender.close()
    receiver.close()


