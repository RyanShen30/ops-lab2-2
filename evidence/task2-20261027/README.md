# 任务 2 执行记录与证据

采集日期为 2026-10-27，时区 Asia/Shanghai（UTC+08:00）。实验在主机 `/home/lx/lab2` 仓库执行，执行身份为 Liuxiang400（系统账号 lx）。报告见 [`LAB2.md` 第 4 节](../../LAB2.md)，两次正式实验的原始数据见 [`runs/r1-pool4/`](../../runs/r1-pool4/meta.txt)、[`runs/r2-pool79/`](../../runs/r2-pool79/meta.txt)。

主机为 4 vCPU（`lscpu -e`：CPU 0/1 → CORE 0，CPU 2/3 → CORE 1），Ubuntu 24.04.5，内核 6.8.0-147-generic，Go 1.26.9，sysstat 12.6.1-2。enrolld 绑 CPU 2-3，loadgen、node_exporter、Prometheus 绑 CPU 0-1。`bin/` 由 `make build test` 生成，四个包测试通过。

## 工具下载

主机到 GitHub Release 的单连接带宽约 27 KB/s，`scripts/get-tools.sh` 直接下载过慢。改用固定大小的分块并行请求取得官方压缩包，放入 `tools/` 后运行 `scripts/get-tools.sh`；两个文件的固定 SHA-256 校验均通过，解压得到 Prometheus 3.13.4 与 node_exporter 1.12.1。

## 启动与抓取检查

三个进程在 tmux 会话 `lab2lx` 中启动，Prometheus 数据目录为 `/dev/shm/lab2-prom-lx`：

```bash
tmux new-session -d -s lab2lx -n enrolld -c /home/lx/lab2 'exec taskset -c 2-3 bin/enrolld > data/enrolld.log 2>&1'
tmux new-window -d -t lab2lx -n node -c /home/lx/lab2 'exec taskset -c 0-1 tools/node_exporter --web.listen-address=127.0.0.1:9100 > data/node_exporter.log 2>&1'
tmux new-window -d -t lab2lx -n prom -c /home/lx/lab2 'exec taskset -c 0-1 tools/prometheus --config.file=deploy/prometheus.yml --storage.tsdb.path=/dev/shm/lab2-prom-lx --web.listen-address=127.0.0.1:9090 > data/prometheus.log 2>&1'
```

R1 前两个抓取目标均为 up，见 [`targets-before.json`](targets-before.json)；enrolld `/config` 见 [`config.json`](config.json)：`work=200000`、`pool=4`、`db_ms=10`、`sync=each`、`GOMAXPROCS=2`。三个进程及其线程的亲和性见 [`services.json`](services.json)（enrolld `2,3`；node_exporter、Prometheus `0,1`）。启动日志见 [`enrolld-r1-startup.log`](enrolld-r1-startup.log)。

R2 前用 `-pool 79` 重启 enrolld（向 tmux 窗口发送 Ctrl-C，然后新建窗口），`/config` 中 `pool=79`、`GOMAXPROCS=2`、`pid=394257`，亲和性仍为 `2,3`，见 [`services-r2.json`](services-r2.json) 与 [`enrolld-r2-startup.log`](enrolld-r2-startup.log)。

## 预测

- 4.1：在 R1 之前写入并提交，提交 `97b527d`（R1 于 15:14:55 开始）。连接池上限 4 ÷ 0.0104843 = 381.5 请求/秒；CPU 上限 2 ÷ 0.000602963 = 3317.0 请求/秒；预测连接池先达到上限。
- 4.4：在 R2 之前写入并提交，提交 `18001b0`（R2 于 15:42:10 开始）。C = 2 ÷ 0.000533438 = 3749.2 请求/秒；P2 = ceil(2 × 3749.2 × 0.0104739) = 79；预测 CPU 先达到上限。

## R1：`-pool 4`

```bash
GEN_CPUS=0-1 scripts/run.sh r1-pool4 -url http://127.0.0.1:8080/api/courses/1 -rates 76,153,229,267,306,344,382,420,458
scripts/table.sh runs/r1-pool4 ok_rps error_rate p99_ms server_p99_ms server_mean_ms inflight_avg cpu_ms_per_req pool_in_use_avg pool_wait_p99_ms sched_wait_p99_ms svc_cpu_busy procs_running_avg
```

9 个阶段各 30 秒，15:14:55 开始。表格见 [`r1-table.md`](r1-table.md)，完整终端输出见 [`run-console-r1.log`](run-console-r1.log)。最大吞吐 384.6 请求/秒（第 7 阶段）；客户端 p99 首次超过 50 ms 在第 6 阶段（344 请求/秒，53.32 ms）。第 7 阶段池占用 3.96/4、等待 p99 887.46 ms；第 8、9 阶段目标 420、458 请求/秒时吞吐停在 384.5、381.3，客户端错误率 7.79%、16.67%。所有阶段的 `warn` 为空，无超时、无 dropped。

服务端计数：`runs/r1-pool4/metrics-end.txt` 中 `http_requests_total{route="/api/courses/{id}",code="200"} = 75944`、`code="503" = 3262`，与 `steps.csv` 的 ok=75944、http_err=3262 完全一致。

## CPU 剖析

在 0.8 倍上限（306 请求/秒）下采集 20 秒：

```bash
GEN_CPUS=0-1 taskset -c 0-1 bin/loadgen -url http://127.0.0.1:8080/api/courses/1 \
  -rates "$(scripts/rates.sh 382 0.8)" -step 40s >/dev/null 2>&1 &
LG=$!
sleep 10
go tool pprof -top -nodecount=15 'http://127.0.0.1:8080/debug/pprof/profile?seconds=20' | tee runs/r1-pool4/pprof-top.txt
wait "$LG"
```

20 秒内采样 2.91 s，`main.spin` 占 82.82%，其余为系统调用、Go 运行时与 HTTP 处理。完整输出见 [`runs/r1-pool4/pprof-top.txt`](../../runs/r1-pool4/pprof-top.txt)。

## R2：`-pool 79`

```bash
GEN_CPUS=0-1 scripts/run.sh r2-pool79 -url http://127.0.0.1:8080/api/courses/1 -rates 1125,2249,2999,3374,3749,4124,4686,5624
scripts/table.sh runs/r2-pool79 ok_rps error_rate p99_ms server_p99_ms inflight_avg cpu_cores cpu_ms_per_req cpu_wait_threads sched_wait_p99_ms pool_in_use_avg svc_cpu_busy procs_running_avg cpu_psi_some
```

8 个阶段各 30 秒，15:42:10 开始。表格见 [`r2-table.md`](r2-table.md)，完整终端输出见 [`run-console-r2.log`](run-console-r2.log)。第 7 阶段（目标 4686）吞吐 4698.7 请求/秒、`svc_cpu_busy=0.965`、无错误；第 8 阶段（目标 5624）`svc_cpu_busy=0.999`、`sched_wait_p99_ms=1000`，客户端错误率 85.45%（13975 个 5xx、130086 个超时），成功吞吐降到 817.4。第 8 阶段的 `warn` 记录“发送滞后 p99 = 40.3 ms”，其客户端延迟不可信，CPU 饱和由资源层指标确认。

服务端计数：`metrics-end.txt` 中 code=200 为 730960、499 为 55873、503 为 30105，合计 816938；客户端发送 838440，少 21502，是阶段结束时仍在服务端排队的请求（客户端 2 s 超时后放弃，服务端仍继续处理）。客户端 ok=694379 小于服务端 200=730960，因为部分响应在客户端超时后才完成，被客户端记为超时。这是客户端与服务端延迟口径差异的直接体现。

## 核验

- 实验前后两个抓取目标均为 up，见 [`targets-before.json`](targets-before.json)、[`targets-after.json`](targets-after.json)。
- R1 的服务端 200/503 计数与客户端 ok/http_err 完全一致；R2 的差异及原因如上。
- `runs/r1-pool4/`、`runs/r2-pool79/` 的文件在提交前用 `sha256sum -c` 校验，清单见 [`r1-files.sha256`](r1-files.sha256)、[`r2-files.sha256`](r2-files.sha256)。
- 报告中引用的数值均取自上述表格、CSV 或 metrics 快照，未修改 `runs/` 中的任何文件。

## 文件

| 文件 | 内容 |
|---|---|
| `config.json`、`services.json`、`services-r2.json` | R1/R2 的 enrolld 参数与三个进程的绑核 |
| `targets-before.json`、`targets-after.json` | 实验前后 Prometheus 抓取目标状态 |
| `enrolld-r1-startup.log`、`enrolld-r2-startup.log`、`prometheus.log`、`node_exporter.log` | 进程启动与运行日志 |
| `r1-table.md`、`r2-table.md` | `scripts/table.sh` 生成的报告表格 |
| `run-console-r1.log`、`run-console-r2.log` | 两次实验的完整终端输出 |
| `r1-files.sha256`、`r2-files.sha256` | `runs/` 原始文件的 SHA-256 清单 |
| `../../runs/r1-pool4/`、`../../runs/r2-pool79/` | `scripts/run.sh` 生成的原始数据 |
