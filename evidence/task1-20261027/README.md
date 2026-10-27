# 任务 1 执行记录与证据

采集日期为 2026-10-27，时区 Asia/Shanghai（UTC+08:00）。全部实验在同一台主机的 `/home/sra/lab2` 仓库执行。报告见 [`LAB2.md` 第 3 节](../../LAB2.md)，正式实验原始数据见 [`runs/t1-light/`](../../runs/t1-light/meta.txt)。

## 启动与抓取检查

为使服务在终端断开后继续运行，实际执行以下命令，在 `lab2` tmux 会话中分别启动三个进程：

```bash
mkdir -p data evidence/task1-20261027
tmux new-session -d -s lab2 -n enrolld -c /home/sra/lab2 'exec taskset -c 2-3 bin/enrolld > data/enrolld.log 2>&1'
tmux new-window -d -t lab2 -n node_exporter -c /home/sra/lab2 'exec taskset -c 0-1 tools/node_exporter --web.listen-address=127.0.0.1:9100 > data/node_exporter.log 2>&1'
tmux new-window -d -t lab2 -n prometheus -c /home/sra/lab2 'exec taskset -c 0-1 tools/prometheus --config.file=deploy/prometheus.yml --storage.tsdb.path=/dev/shm/lab2-prom --web.listen-address=127.0.0.1:9090 > data/prometheus.log 2>&1'
```

启动日志：

```text
2026/10/27 11:12:28 enrolld 监听 127.0.0.1:8080；GOMAXPROCS=2；读：work=200000、pool=4、db-ms=10；写：sync=each，数据目录 data
```

用 Python 标准库 `urllib.request` 请求 `/config` 和 Prometheus `/api/v1/targets`，等待两个目标均为 `up`，于 11:12:34 保存 [`config.json`](config.json)、[`targets-before.json`](targets-before.json)。随后请求 `/api/courses/1` 和 `/metrics`，分别保存 [`course-1.json`](course-1.json)、[`metrics-before.txt`](metrics-before.txt)，提取直方图行至 [`histogram-before.txt`](histogram-before.txt)。启动日志副本见 [`enrolld-startup.log`](enrolld-startup.log)。

读取各进程及其所有线程的 CPU affinity，确认 enrolld 为 `2,3`，node_exporter、Prometheus 为 `0,1`，当时的 PID 和完整核对结果见 [`services.json`](services.json)。PID 是采集时的进程号，重启后会变化。Prometheus 沿用 [`deploy/prometheus.yml`](../../deploy/prometheus.yml)，enrolld 抓取间隔 1 秒、node 抓取间隔 5 秒。

## 正式实验与表格

补全 [`deploy/queries-red.txt`](../../deploy/queries-red.txt) 的四条查询后，实际执行：

```bash
set -o pipefail
GEN_CPUS=0-1 scripts/run.sh t1-light -url http://127.0.0.1:8080/api/courses/1 -rates 0,50,100 2>&1 | tee evidence/task1-20261027/run-console.log
scripts/table.sh runs/t1-light ok_rps mean_ms p99_ms server_rps server_mean_ms server_p99_ms cpu_ms_per_req db_query_mean_ms | tee evidence/task1-20261027/results-table.md
scripts/table.sh runs/t1-light sent ok error_rate slo_good server_rps server_error_rate server_p99_ms server_slo_good lag_p99_ms gen_cpu_pct | tee evidence/task1-20261027/checkpoint-table.md
curl -fsS 127.0.0.1:9090/api/v1/targets -o evidence/task1-20261027/targets-after.json
rg -o '"health":"[a-z]*"' evidence/task1-20261027/targets-after.json
```

实验于 11:12:55 开始，最后一个阶段于 11:14:25 结束，每阶段 30 秒。`run.sh` 成功退出，自动生成全部 11 个原始文件；未重新压测，也未修改 `runs/t1-light/` 中的文件。完整终端输出见 [`run-console.log`](run-console.log)，表格见 [`results-table.md`](results-table.md)、[`checkpoint-table.md`](checkpoint-table.md)。查询一次通过，无需 `requery.sh`。原始文件的 SHA-256 清单见 [`run-files.sha256`](run-files.sha256)，提交前通过 `sha256sum --check evidence/task1-20261027/run-files.sha256` 核验。

关键结果：第 2 / 3 阶段分别完成 1516 / 2935 个请求，总计 4451 个；全部成功且客户端延迟在 50 ms 内，`warn` 为空。100 请求/秒阶段的 `db_query_mean_ms=10.4843`、`cpu_ms_per_req=0.602963`；两个有负载阶段的 `server_error_rate=0`、`server_slo_good=1`。实验后两个目标仍为 `up`，API 原文见 [`targets-after.json`](targets-after.json)。

## 结果核验

Python 核验读取实际的 `steps.csv`、`red.csv`、`use.csv` 和指标快照，完成以下检查；结果见 [`validation.json`](validation.json)：

- 11 个正式原始文件均存在且非空，三张 CSV 的阶段一致，目标到达率依次为 0、50、100。
- 用 `steps.csv` 各阶段的结束时间及 25 秒窗口，向 Prometheus `/api/v1/query` 发起四条查询，共 12 次；每次都只返回一条序列，有负载阶段均为有限数值，并与 `red.csv` 保留六位有效数字后的值一致。展开后的查询、查询时刻及 API 原始响应保存在 [`query-checks.json`](query-checks.json)。
- 全部阶段的压测警告为空；有负载阶段的客户端成功数等于发送数，错误率为 0、50 ms SLI 为 1。
- 正式实验前后 `http_requests_total` 的成功请求计数从 1 增至 4452，增量 4451 与客户端总数一致；最初的 1 次为实验前的示例请求。
- 实验前后抓取目标均为 `up`。

空载阶段的请求数为 0，部分指标出现 `NaN` 或 `+Inf`，原样保留；未将这些值用于每请求开销估算。服务端 p99 根据直方图插值，客户端 p99 根据成功请求的实际延迟排序，测量口径及本次差异见报告第 3 节。

截至本次任务完成，三个服务继续在 `lab2` tmux 会话中运行，可用 `tmux attach -t lab2` 查看。已导出的原始文件在仓库磁盘中保存；Prometheus 的历史数据位于 `/dev/shm/lab2-prom`，如需重新查询历史阶段，应在重启主机之前导出。
