# planetRelay: configuration and dependencies

## Routes and defaults

The packaged default is `pkg://planetrelay/data/loopback.yaml`. The profile is a localhost PLAT probe route: ingress 50590, destination 50591, exact size 108, delivery `all`.

`routes` is a mapping keyed by route name. Inherited route fields can be overridden individually. `allowed_source_hosts` is a list and replaces its inherited value. A task owns actual hosts, interface bindings and protocol-specific routes.

```yaml
extends: pkg://planetrelay/data/loopback.yaml
routes:
  probe:
    port: 50592
    target_port: 50593
runtime:
  report_interval_s: 2.0
```

Run `planetrelay --config FILE --check` to validate without opening sockets. Use `--duration-s 2` for a bounded run. `latest` coalesces valid queued packets; `all` forwards each packet. Use `all` for fragmented recording traffic. Forwarded packet bytes are unchanged.

## Source installation

Bootstrap installs only `planet-config` from the pinned `external/planetConfig` and the local relay package. Runtime dependencies remain task independent. Rally site routes live in the task repository, including `configs/a3/sites/ad201/relay.yaml`.

## Layering rules

All service configuration entry points use `planet-config`; each service validates its own schema after composition.

1. Apply `extends` entries in their listed order.
2. Apply `compose` layers in the fixed order `robot`, `backend`, `task`, `site`, `experiment`.
3. Merge the current file.
4. Apply explicit entry-point overrides, where supported.

Mappings merge recursively; lists and scalars replace. Missing parents, duplicate YAML keys and inheritance cycles fail. A service may reject fields that are valid for a different service. `compose` keys are loader directives, not fields added to the resulting service configuration.

Relative inheritance paths resolve beside the YAML declaring them. `pkg://package/path` resolves installed package resources. Resource fields accessed through `ResolvedConfig.path()` resolve relative to their declaration; output directories and Linux device/abstract-socket endpoints follow the consuming service's rules below. The generic loader does not rewrite every string into a filesystem path.

Source ownership, Python dependencies and YAML inheritance are separate: Git submodules select code revisions; package metadata selects compatible installed distributions; `extends` selects configuration values. Changing a Git submodule does not select a task profile automatically.

See the [shared loader reference](https://github.com/Renforce-Dynamics/planetConfig/blob/main/docs/configuration.md).
