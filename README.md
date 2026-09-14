# planetRelay

按配置转发 UDP 数据包，提供来源过滤、流量统计和往返延迟测量。

## 安装与启动

需要 Linux、Python 3.10+、`uv`。

```bash
git clone --recurse-submodules git@github.com:Renforce-Dynamics/planetRelay.git
cd planetRelay
./scripts/bootstrap.sh

./scripts/run.sh -- --config pkg://planetrelay/data/loopback.yaml
```

默认在本机转发 PLAT 探测包：`50590 → 50591`。
持续运行，Ctrl+C 退出；另开终端测量往返延迟：

```bash
.venv/bin/planetrelay-latency 127.0.0.1 --count 100 --interval-ms 10
```

## 配置路由

新建 `relay-site.yaml`，将地址改为实际收发端：

```yaml
extends: pkg://planetrelay/data/loopback.yaml
ingress:
  bind_host: 0.0.0.0
  allowed_source_hosts: [192.168.1.10]
target:
  host: 192.168.1.20
routes:
  probe:
    port: 50592
    target_port: 50593
```

```bash
./scripts/run.sh -- --config ./relay-site.yaml
```

示例继承了 PLAT 和 108 字节过滤条件；转发其他协议时一并调整 `magic`、
`packet_size`。`latest` 转发当前接收批次的最新有效包，`all` 转发所有有效包。
命令时效和丢包处理由接收应用负责。

## 文档与开发

- [路由配置和字段说明](docs/configuration.md)
- [Rally 现场网络示例](https://github.com/Renforce-Dynamics/planet-rally/blob/main/docs/guides/planetrelay-zh.md)

通过 [planetConfig](https://github.com/Renforce-Dynamics/planetConfig) 复用配置库，
不依赖 Cadence 或 SDK；任务地址与拓扑放在任务仓库。

开发：`./scripts/test.sh` 运行测试，`./scripts/build.sh` 构建安装包。

工具支持 `--venv /path/to/env`。由 **Renforce Dynamics** 开发维护，采用 [MIT License](LICENSE)。
