"""Strict configuration for the deployment UDP relay."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cadence_config import ConfigError, load_config as load_layers


class RelayConfigError(ValueError):
    pass


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RelayConfigError(f"{path} must be a mapping")
    return value


def _only_keys(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise RelayConfigError(
            f"{path} contains unknown keys: {', '.join(sorted(map(str, unknown)))}"
        )


@dataclass(frozen=True, slots=True)
class RouteConfig:
    name: str
    port: int
    target_port: int
    target_host: str
    outbound_bind_host: str | None
    allowed_source_hosts: tuple[str, ...]
    magic: bytes
    packet_size: int | None
    min_packet_size: int
    delivery: str

    def __post_init__(self) -> None:
        if not self.name:
            raise RelayConfigError("route name cannot be empty")
        if not 1 <= self.port <= 65535 or not 1 <= self.target_port <= 65535:
            raise RelayConfigError(f"route {self.name} ports must be in [1, 65535]")
        if not self.target_host:
            raise RelayConfigError(f"route {self.name} target_host cannot be empty")
        if len(self.magic) != 4:
            raise RelayConfigError(f"route {self.name} magic must be exactly 4 bytes")
        if self.packet_size is not None and self.packet_size < len(self.magic):
            raise RelayConfigError(f"route {self.name} packet_size is too small")
        if self.min_packet_size < len(self.magic):
            raise RelayConfigError(f"route {self.name} min_packet_size is too small")
        if (
            self.packet_size is not None
            and self.packet_size < self.min_packet_size
        ):
            raise RelayConfigError(
                f"route {self.name} packet_size cannot be smaller than min_packet_size"
            )
        if self.delivery not in {"latest", "all"}:
            raise RelayConfigError(
                f"route {self.name} delivery must be latest or all"
            )


@dataclass(frozen=True, slots=True)
class RelayConfig:
    version: int
    bind_host: str
    allowed_source_hosts: tuple[str, ...]
    target_host: str
    receive_buffer_bytes: int
    send_buffer_bytes: int
    report_interval_s: float
    routes: tuple[RouteConfig, ...]
    source_path: Path

    def __post_init__(self) -> None:
        if self.version != 1:
            raise RelayConfigError(f"unsupported relay config version {self.version}")
        if not self.bind_host or not self.target_host:
            raise RelayConfigError("ingress.bind_host and target.host cannot be empty")
        if self.receive_buffer_bytes <= 0 or self.send_buffer_bytes <= 0:
            raise RelayConfigError("socket buffer sizes must be positive")
        if self.report_interval_s <= 0:
            raise RelayConfigError("runtime.report_interval_s must be positive")
        if not self.routes:
            raise RelayConfigError("routes must not be empty")
        ports = [route.port for route in self.routes]
        if len(ports) != len(set(ports)):
            raise RelayConfigError("route ingress ports must be unique")


def load_config(path: str | Path) -> RelayConfig:
    try:
        resolved = load_layers(path)
    except (ConfigError, OSError) as error:
        raise RelayConfigError(str(error)) from error
    source_path = resolved.source
    root = _mapping(resolved.data, "config")
    _only_keys(root, {"version", "ingress", "target", "routes", "runtime"}, "config")
    ingress = _mapping(root.get("ingress", {}), "ingress")
    target = _mapping(root.get("target", {}), "target")
    runtime = _mapping(root.get("runtime", {}), "runtime")
    routes = _mapping(root.get("routes", {}), "routes")
    _only_keys(ingress, {"bind_host", "allowed_source_hosts"}, "ingress")
    _only_keys(target, {"host"}, "target")
    _only_keys(runtime, {"receive_buffer_bytes", "send_buffer_bytes", "report_interval_s"}, "runtime")
    try:
        default_target_host = str(target["host"])
    except KeyError as error:
        raise RelayConfigError("target.host is required") from error
    default_allowed_sources = ingress.get("allowed_source_hosts", ())
    if isinstance(default_allowed_sources, (str, bytes)) or not isinstance(
        default_allowed_sources, Sequence
    ):
        raise RelayConfigError("ingress.allowed_source_hosts must be a sequence")
    parsed_routes = []
    for name, value in routes.items():
        route = _mapping(value, f"routes.{name}")
        _only_keys(
            route,
            {
                "port", "target_port", "target_host", "allowed_source_hosts",
                "outbound_bind_host", "magic", "packet_size",
                "min_packet_size", "delivery",
            },
            f"routes.{name}",
        )
        try:
            port = int(route["port"])
            allowed_sources = route.get(
                "allowed_source_hosts", default_allowed_sources
            )
            if isinstance(allowed_sources, (str, bytes)) or not isinstance(
                allowed_sources, Sequence
            ):
                raise RelayConfigError(
                    f"routes.{name}.allowed_source_hosts must be a sequence"
                )
            exact_size = route.get("packet_size")
            outbound = route.get("outbound_bind_host")
            parsed_routes.append(RouteConfig(
                name=str(name), port=port,
                target_port=int(route.get("target_port", port)),
                target_host=str(route.get("target_host", default_target_host)),
                outbound_bind_host=(
                    None if outbound in (None, "") else str(outbound)
                ),
                allowed_source_hosts=tuple(str(host) for host in allowed_sources),
                magic=str(route["magic"]).encode("ascii"),
                packet_size=None if exact_size is None else int(exact_size),
                min_packet_size=int(route.get("min_packet_size", 4)),
                delivery=str(route.get("delivery", "latest")),
            ))
        except (KeyError, UnicodeEncodeError, ValueError, TypeError) as error:
            raise RelayConfigError(f"invalid route {name}: {error}") from error
    try:
        return RelayConfig(
            version=int(root.get("version", 1)),
            bind_host=str(ingress.get("bind_host", "0.0.0.0")),
            allowed_source_hosts=tuple(
                str(host) for host in default_allowed_sources
            ),
            target_host=default_target_host,
            receive_buffer_bytes=int(runtime.get("receive_buffer_bytes", 262144)),
            send_buffer_bytes=int(runtime.get("send_buffer_bytes", 262144)),
            report_interval_s=float(runtime.get("report_interval_s", 1.0)),
            routes=tuple(parsed_routes), source_path=source_path,
        )
    except (KeyError, ValueError, TypeError) as error:
        raise RelayConfigError(f"invalid relay config value: {error}") from error
