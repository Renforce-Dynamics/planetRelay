"""Non-blocking UDP relay with latest-only and all-datagram delivery."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import math
import selectors
import socket
import time

from .config import RelayConfig, RelayConfigError, RouteConfig, load_config


@dataclass(slots=True)
class RelayStats:
    received: int = 0
    forwarded: int = 0
    coalesced: int = 0
    invalid: int = 0
    source_rejected: int = 0
    send_dropped: int = 0


class RelayRuntime:
    def __init__(self, config: RelayConfig) -> None:
        self.config = config
        self.selector = selectors.DefaultSelector()
        self.ingress: list[socket.socket] = []
        self.egress: dict[str, socket.socket] = {}
        self.stats: dict[str, RelayStats] = {
            route.name: RelayStats() for route in config.routes
        }

    def open(self) -> None:
        if self.ingress:
            return
        try:
            for route in self.config.routes:
                incoming = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                incoming.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_RCVBUF,
                    self.config.receive_buffer_bytes,
                )
                incoming.setblocking(False)
                incoming.bind((self.config.bind_host, route.port))
                outgoing = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                outgoing.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_SNDBUF,
                    self.config.send_buffer_bytes,
                )
                outgoing.setblocking(False)
                if route.outbound_bind_host:
                    outgoing.bind((route.outbound_bind_host, 0))
                outgoing.connect((route.target_host, route.target_port))
                self.ingress.append(incoming)
                self.egress[route.name] = outgoing
                self.selector.register(incoming, selectors.EVENT_READ, route)
        except Exception:
            self.close()
            raise

    def relay_ready(self, incoming: socket.socket, route: RouteConfig) -> None:
        latest: bytes | None = None
        while True:
            try:
                packet, source = incoming.recvfrom(65535)
            except BlockingIOError:
                break
            self.stats[route.name].received += 1
            if (
                route.allowed_source_hosts
                and source[0] not in route.allowed_source_hosts
            ):
                self.stats[route.name].source_rejected += 1
                continue
            if (
                not packet.startswith(route.magic)
                or len(packet) < route.min_packet_size
                or (
                    route.packet_size is not None
                    and len(packet) != route.packet_size
                )
            ):
                self.stats[route.name].invalid += 1
                continue
            if route.delivery == "all":
                self._send(route, packet)
                continue
            if latest is not None:
                self.stats[route.name].coalesced += 1
            latest = packet
        if latest is not None:
            self._send(route, latest)

    def _send(self, route: RouteConfig, packet: bytes) -> None:
        try:
            if self.egress[route.name].send(packet) == len(packet):
                self.stats[route.name].forwarded += 1
            else:
                self.stats[route.name].send_dropped += 1
        except OSError:
            self.stats[route.name].send_dropped += 1

    def run(self, duration_s: float = 0) -> int:
        self.open()
        print(
            f"[PlanetRelay] config={self.config.source_path} "
            f"bind={self.config.bind_host} target={self.config.target_host}"
        )
        next_report = time.monotonic() + self.config.report_interval_s
        deadline = time.monotonic() + duration_s if duration_s else math.inf
        try:
            while time.monotonic() < deadline:
                timeout = max(0.0, min(next_report, deadline) - time.monotonic())
                for key, _mask in self.selector.select(timeout):
                    self.relay_ready(key.fileobj, key.data)
                now = time.monotonic()
                if now >= next_report:
                    summary = " ".join(
                        f"{name}=rx:{s.received},tx:{s.forwarded},"
                        f"latest:{s.coalesced},invalid:{s.invalid},"
                        f"source_reject:{s.source_rejected},drop:{s.send_dropped}"
                        for name, s in self.stats.items()
                    )
                    print(f"[PlanetRelay] {summary}")
                    next_report = now + self.config.report_interval_s
        except KeyboardInterrupt:
            return 0
        finally:
            self.close()
        return 0

    def close(self) -> None:
        for incoming in self.ingress:
            try:
                self.selector.unregister(incoming)
            except Exception:
                pass
            incoming.close()
        for outgoing in self.egress.values():
            outgoing.close()
        self.ingress.clear()
        self.egress.clear()
        self.selector.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="pkg://planetrelay/data/loopback.yaml")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--duration-s", type=float, default=0)
    args = parser.parse_args(argv)
    if not math.isfinite(args.duration_s) or args.duration_s < 0:
        parser.error("duration must be finite and non-negative")
    try:
        config = load_config(args.config)
    except RelayConfigError as error:
        parser.error(str(error))
    if args.check:
        print(f"PlanetRelay configuration valid: {len(config.routes)} routes")
        return 0
    return RelayRuntime(config).run(args.duration_s)
