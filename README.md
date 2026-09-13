# PlanetRelay

通用 UDP 转发服务：根据 route 配置过滤来源、校验 magic 与包长，按 `latest` 或 `all` 策略原样转发，并提供计数与 RTT 测量。只依赖轻量配置包 `cadence-config`；安装时不包含 planner、手柄、录制或机器人执行器。

```bash
./scripts/setup.sh --wheelhouse /path/to/wheels
./scripts/doctor.sh
./scripts/run.sh -- --duration-s 2
./scripts/test.sh
./scripts/build.sh
```

默认配置为本机 PLAT 回环探测。命令也可以直接使用：

```bash
planetrelay --check
planetrelay --config /path/to/task/relay.yaml
planetrelay-latency 127.0.0.1 --count 100 --interval-ms 10
```

配置支持 `extends`、严格字段检查及 `pkg://` 资源引用。场地地址和业务协议的 route 由任务仓库维护；rally 的 HDU/MDU 拓扑与路由见 `planet-rally/configs/a3/sites/ad201/relay.yaml`。

`latest` 在当前接收队列中合并有效包；`all` 逐包转发，适合分片的录制数据。UDP 不提供可靠送达或重传，转发失败会计数。服务不解析业务 payload，不改写序号、CRC 或 TTL；过期命令的最终拒绝由消费端负责。
