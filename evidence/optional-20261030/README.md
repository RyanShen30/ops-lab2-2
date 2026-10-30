# 选做 O1、O2、O3 记录

2026-10-30 执行。O1、O3 在实验主机 `ecs-59c8`（下称 A）上执行，工作目录 `/home/wsd/projects/ops-lab2-2`，登录用户 `wsd`（GitHub：Shundi-Wu）。时间均为 Asia/Shanghai（UTC+08:00）。分核与任务 1～3 相同：enrolld 绑 CPU 2-3（`GOMAXPROCS=2`），loadgen、Prometheus、node_exporter 绑 CPU 0-1。

与任务 3 一样，本次使用独立端口：enrolld `127.0.0.1:18080`、Prometheus `127.0.0.1:19090`、node_exporter `127.0.0.1:19100`，没有停止或改动 lx 用户在 8080/9090/9100 上的服务，那套服务在本次实验期间处于空载。每次实验的 TSDB 在 `/dev/shm/lab2-prom-1001-<名字>`，数据目录在 `data/<名字>/`，都是全新的。

## 预测先于测量

- [o3-prediction.md](o3-prediction.md)：写于运行 o3-burn 之前，SHA-256 与修改时间记录在 `o3-burn-manifest.json`。
- [o1-prediction.md](o1-prediction.md)：写于运行 o1-gogc100、o1-gogc400 之前，SHA-256 与修改时间记录在 `o1-gogc*-manifest.json`。
- [o2-prediction.md](o2-prediction.md)：写于运行 o2-net 之前（文件修改时间早于 `runs/o2-net/meta.txt` 中的开始时刻），SHA-256 为 `82c7475463f9f6590f921235fac9f09984e375e93e926678b72077e9d2403cb5`。

三份预测在测量后都没有修改，偏差在 `LAB2.md` 第 7 节讨论。

## 复现

在仓库根目录（先 `make build`、`scripts/get-tools.sh`，确认 18080/19090/19100 空闲）：

```bash
python3 scripts/optional-run.py o3            # 约 15 分钟：200×3、420×4、200×7 个 60 s 阶段，另有 20/s 的写请求
python3 scripts/optional-run.py o1 --gogc 100 # 约 2 分钟：/api/report?mb=4，100 请求/秒 × 3 个 30 s 阶段
python3 scripts/optional-run.py o1 --gogc 400
python3 evidence/optional-20261030/summarize.py   # 重新生成 summary.txt 中的全部数值
```

O2 需要第二台主机 B（同一 VPC，A 能用密钥 SSH 登录 B），在 A 的仓库根目录：

```bash
B=wsd@<B 的内网地址> A_ADDR=<A 的内网地址>:18080 scripts/o2-run.sh o2-net 50,100,200,400,600,800,1000,1200,1600,2000,2500,3000
```

`scripts/o2-run.sh` 把 `bin/loadgen` 拷到 B 的 `~/lab2-o2/<名字>/`，在 A 上启动只监听内网地址的 enrolld 并记录 `sar`、`ss`、`nstat`、`mpstat`、`pidstat`，在 B 上记录 `sar -n DEV`、`mpstat` 并运行 loadgen，结束后把 B 的文件拷回 `runs/<名字>/`，再停止 enrolld。O2 的第一次尝试（21:24）因脚本错误没有发出任何请求：远端命令中 `cd … && … &` 让 `cd` 只在后台子 shell 中生效，`./loadgen` 找不到而退出（127）。当时只采集了约 20 s 的空载数据，已删除 A、B 两边的残留文件，修正为单独一行 `cd … || exit 1` 后重新运行，`runs/o2-net` 是第二次运行的结果。实验后两端的丢包计数另存于 `o2-a-drops-after.txt`、`o2-b-drops-after.txt`。

`scripts/optional-run.py` 调用课程原有的 `scripts/run.sh`，原始数据在 `runs/o3-burn/`、`runs/o1-gogc100/`、`runs/o1-gogc400/`。脚本拒绝覆盖已有的实验目录，只停止自己启动的进程。

第一次运行 O1 时，端口预检查因 O3 留下的 TIME_WAIT 连接报错，当时还没有创建任何目录，也没有开始测量；预检查改为与 Go、Prometheus 相同地设置 `SO_REUSEADDR` 后重新运行。`o1-gogc*-gc.csv` 第一次生成时，`cpu_ms_per_req` 一列因 PromQL 两侧标签不一致而为空；修正 [queries-gc.txt](queries-gc.txt)（分子加 `sum`）后，用保存在 `/dev/shm` 中的同一份 TSDB 重新执行 promsteps 生成，其余各列与第一次完全相同。

## 文件

| 文件 | 内容 |
|---|---|
| `*-manifest.json` | 提交号、命令、预测文件的 SHA-256 和修改时间，以及准备、开始、结束、清理时刻 |
| `*-config.json`、`*-enrolld.log` | enrolld 的 `/config` 与启动日志（`GOMAXPROCS`、`GOGC`） |
| `*-prometheus.yml` | 本次 Prometheus 的配置：由 `deploy/prometheus.yml` 换端口而来，`rule_files` 指向 `deploy/rules.yml` |
| `*-targets-before/after.json`、`*-rules-before/after.json` | 抓取目标与规则的状态（规则均为 `health: ok`） |
| `*-console.log` | `scripts/run.sh` 的完整终端输出 |
| `o3-burn-alerts.jsonl` | 每 5 s 一次的 `/api/v1/alerts` 原始响应，共 174 次 |
| `o3-burn-alerts-final.json` | 实验结束时的 `/api/v1/alerts` |
| `o3-burn-slo-range.json` | `ALERTS` 与四个窗口错误比例的 `query_range`（步长 5 s） |
| `o3-burn-dashboard-range.json` | 看板每条查询在实验期间的 `query_range`（步长 15 s） |
| `o3-burn-enroll-steps.csv`、`o3-burn-enroll-loadgen.log` | 后台 20/s 写请求的 loadgen 结果 |
| `o1-gogc*-gc.csv` | 按阶段查询 [queries-gc.txt](queries-gc.txt) 的结果 |
| `o2-a-drops-after.txt`、`o2-b-drops-after.txt` | O2 结束后 A、B 的网卡丢弃、softnet 丢弃、TCP 接收队列与乱序计数（开机以来累计；B 于 17:11 开机） |
| `summarize.py`、`summary.txt` | 从上述文件与 `runs/` 计算 `LAB2.md` 第 7 节引用的数值 |

## 在 Prometheus 界面中打开看板

先按指导书建立 SSH 隧道（`ssh -L 9090:127.0.0.1:9090 <用户>@<主机>`），并用 `deploy/prometheus.yml` 启动 Prometheus 与 enrolld。下面的链接在一个页面中打开看板的 19 条查询，顺序与 `LAB2.md` 第 7 节的“三行九格”表一致（业务 3 条、服务 7 条、资源 9 条），时间范围为最近 15 分钟：

[打开看板](http://127.0.0.1:9090/query?g0.expr=sum%28increase%28enroll_commits_total%7Bjob%3D%22enrolld%22%7D%5B10m%5D%29%29&g0.tab=graph&g0.range_input=15m&g1.expr=sum%28rate%28http_requests_total%7Bjob%3D%22enrolld%22%2Croute%3D%22%2Fapi%2Fenroll%22%2Ccode%3D~%222..%22%7D%5B1m%5D%29%29+%2F+sum%28rate%28http_requests_total%7Bjob%3D%22enrolld%22%2Croute%3D%22%2Fapi%2Fenroll%22%7D%5B1m%5D%29%29&g1.tab=graph&g1.range_input=15m&g2.expr=node_netstat_Tcp_CurrEstab%7Bjob%3D%22node%22%7D&g2.tab=graph&g2.range_input=15m&g3.expr=sum+by+%28route%29+%28rate%28http_requests_total%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29&g3.tab=graph&g3.range_input=15m&g4.expr=%28sum+by+%28route%29+%28rate%28http_requests_total%7Bjob%3D%22enrolld%22%2Ccode%3D~%225..%22%7D%5B1m%5D%29%29+or+0+%2A+sum+by+%28route%29+%28rate%28http_requests_total%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29%29+%2F+sum+by+%28route%29+%28rate%28http_requests_total%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29&g4.tab=graph&g4.range_input=15m&g5.expr=histogram_quantile%280.5%2C+sum+by+%28route%2C+le%29+%28rate%28http_request_duration_seconds_bucket%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29%29&g5.tab=graph&g5.range_input=15m&g6.expr=histogram_quantile%280.99%2C+sum+by+%28route%2C+le%29+%28rate%28http_request_duration_seconds_bucket%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29%29&g6.tab=graph&g6.range_input=15m&g7.expr=sum+by+%28route%29+%28http_inflight_requests%7Bjob%3D%22enrolld%22%7D%29&g7.tab=graph&g7.range_input=15m&g8.expr=db_pool_in_use%7Bjob%3D%22enrolld%22%7D+%2F+db_pool_size%7Bjob%3D%22enrolld%22%7D&g8.tab=graph&g8.range_input=15m&g9.expr=histogram_quantile%280.99%2C+sum+by+%28le%29+%28rate%28db_pool_wait_seconds_bucket%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29%29&g9.tab=graph&g9.range_input=15m&g10.expr=sum%28rate%28node_cpu_seconds_total%7Bjob%3D%22node%22%2Cmode%21~%22idle%7Ciowait%22%2Ccpu%3D~%222%7C3%22%7D%5B1m%5D%29%29+%2F+count%28node_cpu_seconds_total%7Bjob%3D%22node%22%2Cmode%3D%22idle%22%2Ccpu%3D~%222%7C3%22%7D%29&g10.tab=graph&g10.range_input=15m&g11.expr=rate%28process_cpu_wait_seconds_total%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29&g11.tab=graph&g11.range_input=15m&g12.expr=process_resident_memory_bytes%7Bjob%3D%22enrolld%22%7D&g12.tab=graph&g12.range_input=15m&g13.expr=node_memory_MemAvailable_bytes%7Bjob%3D%22node%22%7D&g13.tab=graph&g13.range_input=15m&g14.expr=rate%28node_disk_io_time_seconds_total%7Bjob%3D%22node%22%2Cdevice%3D%22vda%22%7D%5B1m%5D%29&g14.tab=graph&g14.range_input=15m&g15.expr=rate%28node_disk_io_time_weighted_seconds_total%7Bjob%3D%22node%22%2Cdevice%3D%22vda%22%7D%5B1m%5D%29&g15.tab=graph&g15.range_input=15m&g16.expr=histogram_quantile%280.99%2C+rate%28enroll_fsync_duration_seconds_bucket%7Bjob%3D%22enrolld%22%7D%5B1m%5D%29%29&g16.tab=graph&g16.range_input=15m&g17.expr=rate%28node_network_receive_bytes_total%7Bjob%3D%22node%22%2Cdevice%3D%22lo%22%7D%5B1m%5D%29+%2B+rate%28node_network_transmit_bytes_total%7Bjob%3D%22node%22%2Cdevice%3D%22lo%22%7D%5B1m%5D%29&g17.tab=graph&g17.range_input=15m&g18.expr=rate%28node_netstat_Tcp_RetransSegs%7Bjob%3D%22node%22%7D%5B1m%5D%29&g18.tab=graph&g18.range_input=15m)
