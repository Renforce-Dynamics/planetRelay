# planetRelay

**Configurable UDP routing and latency measurement.**

planetRelay forwards UDP datagrams according to explicit routes. It supports source filtering, magic and length checks, queue delivery policies, counters and round-trip latency probes.

Routes retain the original datagram bytes. Task repositories own addresses, protocol choices and network topology.

## Quick start

Requires Linux, Python 3.10+ and `uv`.

```bash
git clone --recurse-submodules git@github.com:Renforce-Dynamics/planetRelay.git
cd planetRelay
./scripts/bootstrap.sh
./scripts/doctor.sh
./scripts/run.sh -- --duration-s 2
./scripts/test.sh
```

## Dependencies and configuration

The `external/cadence` submodule supplies only `cadence-config`; no planner, joystick, recording or execution service is installed.

The built-in `pkg://planetrelay/data/loopback.yaml` profile routes local PLAT probes from port 50590 to 50591. Override individual route fields in an overlay:

```yaml
extends: pkg://planetrelay/data/loopback.yaml
routes:
  probe:
    port: 50592
    target_port: 50593
```

```bash
.venv/bin/planetrelay --config /path/to/relay.yaml --check
.venv/bin/planetrelay --config /path/to/relay.yaml
.venv/bin/planetrelay-latency 127.0.0.1 --count 100 --interval-ms 10
```

`latest` keeps the newest valid datagram in the current receive batch; `all` forwards every valid datagram and is suitable for fragmented recordings. UDP delivery and retransmission are outside the relay contract. Consumers enforce command expiry.

See [configuration](docs/configuration.md) and the [rally network guide](https://github.com/Renforce-Dynamics/planet-rally/blob/main/docs/guides/planetrelay-zh.md).

## Development

```bash
./scripts/submodules.sh init    # initialize or restore pinned dependencies
./scripts/submodules.sh check
./scripts/test.sh
./scripts/build.sh
```

Submodules pin source commits; Python requirements describe package compatibility. Bootstrap installs only the explicit packages in `source-workspace.json`. `scripts/setup.sh --wheelhouse /path/to/wheels` is available for package-based installation. Upgrade dependencies by committing reviewed submodule revisions with the parent repository.

## Authorship and license

Developed and maintained by [Renforce Dynamics](https://github.com/Renforce-Dynamics). See [AUTHORS.md](AUTHORS.md). Project code is available under the [MIT License](LICENSE).
