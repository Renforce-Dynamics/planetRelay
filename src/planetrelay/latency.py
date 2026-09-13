"""Measure application-level UDP RTT through a PlanetRelay route."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import select
import socket
import struct
import time
from typing import Callable, Sequence


MAGIC = b"PLAT"
HEADER = struct.Struct("!4sIQ")


@dataclass(frozen=True, slots=True)
class LatencyResult:
    sent: int
    received: int
    lost: int
    invalid: int
    duplicates: int
    rtt_ms: tuple[float, ...]

    @property
    def loss_percent(self) -> float:
        return 100.0 * self.lost / self.sent if self.sent else 0.0

    def summary(self) -> dict[str, float | int]:
        values = sorted(self.rtt_ms)
        result: dict[str, float | int] = {
            "sent": self.sent,
            "received": self.received,
            "lost": self.lost,
            "loss_percent": self.loss_percent,
            "invalid": self.invalid,
            "duplicates": self.duplicates,
        }
        if values:
            result.update({
                "rtt_min_ms": values[0],
                "rtt_p50_ms": percentile(values, 50),
                "rtt_p95_ms": percentile(values, 95),
                "rtt_p99_ms": percentile(values, 99),
                "rtt_max_ms": values[-1],
                "rtt_mean_ms": sum(values) / len(values),
            })
        return result


def percentile(sorted_values: Sequence[float], percent: float) -> float:
    """Return a linearly interpolated percentile from sorted values."""
    if not sorted_values:
        raise ValueError("cannot calculate a percentile of an empty sequence")
    position = (len(sorted_values) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(
        sorted_values[lower] * (1.0 - fraction)
        + sorted_values[upper] * fraction
    )


def make_packet(sequence: int, sent_ns: int, packet_size: int) -> bytes:
    if packet_size < HEADER.size:
        raise ValueError(f"packet size must be at least {HEADER.size} bytes")
    return HEADER.pack(MAGIC, sequence, sent_ns) + bytes(packet_size - HEADER.size)


def measure(
    host: str,
    *,
    ingress_port: int = 50590,
    listen_host: str = "0.0.0.0",
    reply_port: int = 50591,
    count: int = 1000,
    interval_ms: float = 10.0,
    timeout_ms: float = 1000.0,
    packet_size: int = 108,
    clock_ns: Callable[[], int] = time.monotonic_ns,
) -> LatencyResult:
    if count <= 0:
        raise ValueError("count must be positive")
    if interval_ms <= 0 or timeout_ms <= 0:
        raise ValueError("interval and timeout must be positive")
    if not 1 <= ingress_port <= 65535 or not 1 <= reply_port <= 65535:
        raise ValueError("ports must be in [1, 65535]")

    destination = (socket.gethostbyname(host), ingress_port)
    interval_ns = round(interval_ms * 1_000_000)
    timeout_ns = round(timeout_ms * 1_000_000)
    pending: dict[int, int] = {}
    completed: set[int] = set()
    samples: list[float] = []
    invalid = 0
    duplicates = 0
    sent = 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_host, reply_port))
    sock.setblocking(False)
    try:
        next_send_ns = clock_ns()
        while sent < count or pending:
            now_ns = clock_ns()
            while sent < count and now_ns >= next_send_ns:
                packet = make_packet(sent, now_ns, packet_size)
                sock.sendto(packet, destination)
                pending[sent] = now_ns
                sent += 1
                next_send_ns += interval_ns
                now_ns = clock_ns()

            expired = [
                sequence for sequence, started_ns in pending.items()
                if now_ns - started_ns >= timeout_ns
            ]
            for sequence in expired:
                del pending[sequence]

            if sent >= count and not pending:
                break

            wake_ns = next_send_ns if sent < count else now_ns + timeout_ns
            if pending:
                wake_ns = min(
                    wake_ns,
                    min(started_ns + timeout_ns for started_ns in pending.values()),
                )
            wait_s = max(0.0, (wake_ns - clock_ns()) / 1_000_000_000)
            readable, _, _ = select.select((sock,), (), (), wait_s)
            if not readable:
                continue
            while True:
                try:
                    packet, _source = sock.recvfrom(65535)
                except BlockingIOError:
                    break
                received_ns = clock_ns()
                if len(packet) != packet_size:
                    invalid += 1
                    continue
                magic, sequence, embedded_sent_ns = HEADER.unpack_from(packet)
                started_ns = pending.get(sequence)
                if magic != MAGIC or started_ns is None or embedded_sent_ns != started_ns:
                    if sequence in completed:
                        duplicates += 1
                    else:
                        invalid += 1
                    continue
                del pending[sequence]
                completed.add(sequence)
                samples.append((received_ns - started_ns) / 1_000_000.0)
    finally:
        sock.close()

    received = len(samples)
    return LatencyResult(
        sent=sent,
        received=received,
        lost=sent - received,
        invalid=invalid,
        duplicates=duplicates,
        rtt_ms=tuple(samples),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="relay host name or IPv4 address")
    parser.add_argument("--ingress-port", type=int, default=50590)
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--reply-port", type=int, default=50591)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--interval-ms", type=float, default=10.0)
    parser.add_argument("--timeout-ms", type=float, default=1000.0)
    parser.add_argument("--packet-size", type=int, default=108)
    parser.add_argument("--json", action="store_true", help="print JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = measure(
            args.host,
            ingress_port=args.ingress_port,
            listen_host=args.listen_host,
            reply_port=args.reply_port,
            count=args.count,
            interval_ms=args.interval_ms,
            timeout_ms=args.timeout_ms,
            packet_size=args.packet_size,
        )
    except (OSError, ValueError) as error:
        _parser().error(str(error))
    summary = result.summary()
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            f"sent={result.sent} received={result.received} lost={result.lost} "
            f"loss={result.loss_percent:.2f}% invalid={result.invalid} "
            f"duplicates={result.duplicates}"
        )
        if result.rtt_ms:
            print(
                "rtt_ms "
                f"min={summary['rtt_min_ms']:.3f} "
                f"p50={summary['rtt_p50_ms']:.3f} "
                f"p95={summary['rtt_p95_ms']:.3f} "
                f"p99={summary['rtt_p99_ms']:.3f} "
                f"max={summary['rtt_max_ms']:.3f} "
                f"mean={summary['rtt_mean_ms']:.3f}"
            )
    return 0 if result.received else 1


if __name__ == "__main__":
    raise SystemExit(main())
