# 实验 2 记录：第 2 组

本文件中的数值均注明原始数据出处。任务 0 的命令输出和基线原始日志见下方证据链接；后续 HTTP 实验的数据保存于 `runs/<名字>/`，表格使用 `scripts/table.sh` 生成后粘贴，其他数值注明具体文件与阶段。

第 4.1、4.4、5.1、5.3 节的预测须在对应的测量之前写好，写好后不要修改。预测错误不扣分，与实测不一致之处在分析中讨论。

目前已完成任务 0、1、2，时区均为 Asia/Shanghai（UTC+08:00）。任务 0 于 **2026-10-26** 采集，主机命令、fsync 基准和资源工具原始输出见 [`evidence/task0-20261026/`](evidence/task0-20261026/README.md)。任务 1 于 **2026-10-27** 采集，HTTP 实验由 `scripts/run.sh` 生成的原始数据见 [`runs/t1-light/`](runs/t1-light/meta.txt)，启动、抓取状态与查询核验见 [`evidence/task1-20261027/`](evidence/task1-20261027/README.md)。任务 2 于 **2026-10-27** 在 `/home/lx/lab2` 以 Liuxiang400 身份执行，R1、R2、CPU 剖析与查询核验见 [`evidence/task2-20261027/`](evidence/task2-20261027/README.md)。任务 3～4 保留待填写。

## 1. 基本信息

| 项 | 内容 |
|---|---|
| 小组 | 第 2 组 |
| 仓库地址 | <https://github.com/RyanShen30/ops-lab2-2>；公开仓库，默认分支 `main` |
| 主机 | 华为云弹性云服务器 ECS，通用计算型 `x1.4u.8g`；控制台配置为 4 vCPU、8 GiB 内存；区域为华东-上海一，可用区 3。来宾系统检测为 OpenStack Nova / KVM |
| CPU | `General Purpose Processor`（Vendor ID：`GenuineIntel`）；4 vCPU；来宾暴露 1 socket、2 CORE、每 CORE 2 个线程。CPU 0/1 → CORE 0，CPU 2/3 → CORE 1 |
| 内存 | 控制台配置为 8 GiB；基线采集时 `free -m` 的 total 为 7556 MiB，available 为 6844 MiB，swap 为 0。实验计算采用来宾系统实测值 |
| 数据目录所在的盘 | 华为云 EVS 系统盘，通用型 SSD，40 GiB；仓库 `data/` 位于 `/dev/vda1`，文件系统 `ext4`，挂载于 `/`；整盘设备为 `vda`，数据目录位于块设备，非 tmpfs。`ROTA=1` 是虚拟设备上报值，磁盘类型按控制台信息记录 |
| 操作系统与内核 | `Ubuntu 24.04.5 LTS`；内核 `6.8.0-147-generic` |
| Go、Prometheus、node_exporter | `go version go1.26.9 linux/amd64`；Prometheus `3.13.4`；node_exporter `1.12.1`。`scripts/get-tools.sh` 已成功完成固定 SHA-256 校验并解压 |
| 分核 | enrolld 使用 CPU `2-3`；loadgen、Prometheus、node_exporter 使用 CPU `0-1`，任务 1 已按此执行。按来宾可见 CORE 分开服务与压测/监控；任务 0 的 fsync 基准按指导书直接执行，未对基准额外绑核 |

云厂商、实例规格、配置内存、区域及磁盘类型来源于用户提供的华为云控制台截图，补录日期为 2026-10-27，字段摘录见 [`cloud-specification.md`](evidence/task0-20261026/cloud-specification.md)。来宾系统环境与基线数值来源于 2026-10-26 采集的 [`host.txt`](evidence/task0-20261026/host.txt)。`make build test` 已通过，三个二进制生成成功，四个 Go 包测试全部通过，原始输出见 [`build-test.log`](evidence/task0-20261026/build-test.log)；下载与校验过程见 [`get-tools.log`](evidence/task0-20261026/get-tools.log)。sysstat `12.6.1-2`、procps `2:4.0.4-4ubuntu3.3` 已预装，本次无需安装软件包。

仓库协作状态来源：[`repository-access.json`](evidence/task0-20261026/repository-access.json)。`RyanShen30` 为管理员；`Liuxiang400`、`Shundi-Wu` 已有 push 权限。

关键命令实际输出节选（完整输出见 `host.txt`）：

```text
$ lscpu -e
CPU NODE SOCKET CORE L1d:L1i:L2:L3 ONLINE
  0    0      0    0 0:0:0:0          yes
  1    0      0    0 0:0:0:0          yes
  2    0      0    1 1:1:1:0          yes
  3    0      0    1 1:1:1:0          yes

$ free -m
               total        used        free      shared  buff/cache   available
Mem:            7556         712        5137           2        1980        6844
Swap:              0           0           0

$ findmnt -T data
TARGET SOURCE    FSTYPE OPTIONS
/      /dev/vda1 ext4   rw,relatime

$ lsblk -o NAME,TYPE,SIZE,ROTA,FSTYPE,MOUNTPOINTS
NAME   TYPE SIZE ROTA FSTYPE MOUNTPOINTS
vda    disk  40G    1
└─vda1 part  40G    1 ext4   /
```

## 2. 任务 0：基线

在仓库根目录连续运行三次 `bin/enrolld -bench-fsync 2000`。程序在真实块设备上的 `data/` 中追加记录并调用 fsync；三次原始输出分别见 [`fsync-1.txt`](evidence/task0-20261026/fsync-1.txt)、[`fsync-2.txt`](evidence/task0-20261026/fsync-2.txt)、[`fsync-3.txt`](evidence/task0-20261026/fsync-3.txt)，执行时间与退出状态见 [`fsync-runs.json`](evidence/task0-20261026/fsync-runs.json)。

```text
第 1 次：
fsync 次数 2000，总耗时 2.49 s，数据目录 data
fsync 耗时（毫秒）：mean 1.238  p50 1.175  p90 1.394  p99 2.411  max 10.325
按平均值推算，一个写者串行 fsync 每秒最多约 808 次（= 1000 / 1.238）
第 2 次：
fsync 次数 2000，总耗时 2.49 s，数据目录 data
fsync 耗时（毫秒）：mean 1.240  p50 1.166  p90 1.434  p99 2.393  max 5.460
按平均值推算，一个写者串行 fsync 每秒最多约 806 次（= 1000 / 1.240）
第 3 次：
fsync 次数 2000，总耗时 2.46 s，数据目录 data
fsync 耗时（毫秒）：mean 1.227  p50 1.160  p90 1.414  p99 2.371  max 4.823
按平均值推算，一个写者串行 fsync 每秒最多约 815 次（= 1000 / 1.227）
```

三次各含 2000 次 fsync，按程序输出的三位小数 mean 等权平均：

```text
平均耗时 = (1.238 + 1.240 + 1.227) / 3 = 1.235 ms
串行 fsync 上限估计 = 1000 / 1.235 = 809.72 次/秒，约 810 次/秒
三次 mean 的最大差 = 1.240 - 1.227 = 0.013 ms
相对差异 = 0.013 / 1.235 × 100% ≈ 1.05%
```

三次平均值接近，p99 分别为 2.411、2.393、2.371 ms；单次最大耗时可到 10.325 ms。约 810 次/秒是该主机、文件系统与测量时段下，依据 fsync 平均耗时推算的单个写者串行上限；未计入应用其他开销，后续写路径仍须实测验证。计算使用输出中已舍入的 mean，来源见 [`summary.json`](evidence/task0-20261026/summary.json)。

资源观测：同时运行 `LC_ALL=C vmstat -w 1` 与 `LC_ALL=C iostat -dx 1 vda`，先观察 10.5 秒空载，再连续运行两次 `bin/enrolld -bench-fsync 5000`。单次约 6 秒，因此用两次覆盖超过 10 秒的写盘观测；两次输出保存在 `fsync-observe-1.txt`、`fsync-observe-2.txt`。原始日志分别为 [`vmstat.log`](evidence/task0-20261026/vmstat.log) 和 [`iostat.log`](evidence/task0-20261026/iostat.log)。

采样口径：排除两个工具开机以来的第一组统计；按采集时间只选完整落在单个空载或 fsync 区间内的 1 秒样本，排除跨阶段样本。两个工具各选取空载 **10 个**、fsync **11 个**样本。下表“典型值”取这些样本的算术平均并保留两位小数；`w_await`、`f_await` 是各秒读数的平均，包含无 I/O 时输出的 0，用于展示典型状态，未解释为所有 I/O 合并后的加权均值。vmstat 百分比原始读数已取整，均值相加可能有舍入误差。

阶段时间见 [`observation.json`](evidence/task0-20261026/observation.json)，原始行与采集时刻对应见 [`monitor-lines.jsonl`](evidence/task0-20261026/monitor-lines.jsonl)，选中样本及其原始日志行号见 [`vmstat-selected.csv`](evidence/task0-20261026/vmstat-selected.csv)、[`iostat-selected.csv`](evidence/task0-20261026/iostat-selected.csv)。表格由这些样本自动汇总，结果见 [`baseline-table.md`](evidence/task0-20261026/baseline-table.md) 和 [`summary.csv`](evidence/task0-20261026/summary.csv)。

| 工具与列 | 空载 | 运行 `-bench-fsync` 时 | 该列的含义 |
|---|---|---|---|
| `vmstat -w 1`：r、b | r=0.00；b=0.20 | r=0.18；b=1.00 | r：可运行任务数；b：处于不可中断睡眠的阻塞任务数，常与 I/O 等待有关；此处为采样均值 |
| `vmstat -w 1`：us、sy、id、wa、st | us=0.30%；sy=0.10%；id=99.40%；wa=0.00%；st=0.00% | us=0.18%；sy=1.91%；id=74.64%；wa=23.27%；st=0.00% | 用户态 CPU、内核态 CPU、空闲、I/O 等待、被宿主机占用的 CPU 时间比例；均为全机口径 |
| `iostat -dx 1 vda`：w/s、wkB/s | w/s=4.50；wkB/s=122.00 | w/s=2355.73；wkB/s=12857.09 | 每秒块设备写请求数、每秒写入量（kB/s） |
| `iostat -dx 1 vda`：w_await、f/s、f_await | w_await=0.51；f/s=0.40；f_await=0.00 | w_await=0.41；f/s=1567.45；f_await=0.05 | 每次写 I/O 平均耗时（ms）、每秒 flush 次数、每次 flush 平均耗时（ms）；此表为每秒读数的算术平均 |
| `iostat -dx 1 vda`：aqu-sz、%util | aqu-sz=0.00；%util=0.07 | aqu-sz=1.04；%util=95.91 | 平均未完成 I/O 数、设备存在 I/O 的忙碌时间比例（%）；云盘的 %util 不能单独代表底层容量 |

运行 fsync 测试时，CPU 执行计算并不繁忙：全机 `us+sy` 约为 **2.09%**，`id` 为 **74.64%**；`wa` 为 **23.27%**，表示 I/O 等待时间，不能计作 CPU 正在执行计算。`st=0`，本次窗口内未观察到 CPU steal。

等待证据为：选中的 fsync 样本 `b` 均为 1，`wa` 从空载 0 上升到约 23.27%；设备平均未完成 I/O 数 `aqu-sz` 约 **1.04**，`%util` 约 **95.91%**，同时写入和 flush 频率明显增加。说明这个串行写者主要等待 I/O 完成。单个写 I/O 的 `w_await` 约 0.41 ms，flush 的 `f_await` 约 0.05 ms，口径按块设备 I/O 统计，不能直接当作一次应用 fsync 的全部耗时。

空载仍存在后台 I/O：`w/s` 均值 4.50、`b` 有一次取到 2；“空载”指未主动执行本实验负载。不能仅凭 `%util` 接近 100% 就断定云盘底层容量已经饱和，本任务结论限于当前单写者 fsync 的等待表现。

## 3. 任务 1：指标流水线

采集时间：**2026-10-27 11:12:55～11:14:25（UTC+08:00）**，三个阶段各 30 秒，到达过程为 Poisson。运行命令：

```bash
GEN_CPUS=0-1 scripts/run.sh t1-light -url http://127.0.0.1:8080/api/courses/1 -rates 0,50,100
```

enrolld 绑定 CPU `2-3`，loadgen、Prometheus、node_exporter 绑定 CPU `0-1`；服务启动日志显示 `GOMAXPROCS=2`。`/config` 确认为默认参数 `work=200000`、`pool=4`、`db_ms=10`、`sync=each`。Prometheus 每 1 秒抓取 enrolld、每 5 秒抓取 node_exporter，TSDB 目录为 `/dev/shm/lab2-prom`；三个服务均只监听 `127.0.0.1`。启动命令及原始证据见 [`任务 1 执行记录`](evidence/task1-20261027/README.md)，实验参数见 [`meta.txt`](runs/t1-light/meta.txt)。

两个抓取目标的状态：实验前后 `enrolld`、`node` 均为 **up**。API 原始响应见 [`targets-before.json`](evidence/task1-20261027/targets-before.json)、[`targets-after.json`](evidence/task1-20261027/targets-after.json)，两处 `"health"` 的值为：

```text
"health":"up"
"health":"up"
```

首次 `GET /api/courses/1` 正常返回课程 JSON（[`course-1.json`](evidence/task1-20261027/course-1.json)）。紧接着抓取的原始直方图中，`le="0.01"` 为 0，`le="0.02"` 为 1，`le="+Inf"` 与 `_count` 均为 1，`_sum` 为 `0.01062283` 秒，表示这一次成功请求耗时位于 10～20 ms。桶是累计计数，不能将各桶次数相加。完整输出见 [`histogram-before.txt`](evidence/task1-20261027/histogram-before.txt)。

本组编写的四条查询（与 `deploy/queries-red.txt` 一致）：

```text
server_rps          sum(rate(http_requests_total{route="${route}"}[${window}]))
server_error_rate   (sum(rate(http_requests_total{route="${route}",code=~"5.."}[${window}])) or vector(0)) / sum(rate(http_requests_total{route="${route}"}[${window}]))
server_p99_ms       1000 * histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{route="${route}"}[${window}])))
server_slo_good     (sum(rate(http_request_duration_seconds_bucket{route="${route}",code="200",le="${slo}"}[${window}])) or vector(0)) / sum(rate(http_requests_total{route="${route}"}[${window}]))
```

四条查询均限定当前接口；错误率在没有 5xx 序列时用 `or vector(0)` 补零；p99 先按 `le` 合并各状态码的桶，再取分位数并转换为毫秒；SLI 的分子只计入成功且耗时不超过阈值的请求。本次 `${route}=/api/courses/{id}`、`${slo}=0.05`、`${window}=25s`。

`runs/t1-light` 的数据（`scripts/table.sh runs/t1-light ok_rps mean_ms p99_ms server_rps server_mean_ms server_p99_ms cpu_ms_per_req db_query_mean_ms`）：

| step | target_rps | ok_rps | mean_ms | p99_ms | server_rps | server_mean_ms | server_p99_ms | cpu_ms_per_req | db_query_mean_ms |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0.0 | - | - | 0 | NaN | NaN | +Inf | NaN |
| 2 | 50 | 50.5 | 11.58 | 12.57 | 51.2083 | 10.852 | 19.9 | 0.61067 | 10.4391 |
| 3 | 100 | 97.8 | 11.65 | 13.86 | 95.875 | 10.9344 | 19.9 | 0.602963 | 10.4843 |
| all | - | 74.2 | 11.62 | 12.86 | - | - | - | - | - |

表格由脚本直接生成，副本见 [`results-table.md`](evidence/task1-20261027/results-table.md)。原始数据见 [`steps.csv`](runs/t1-light/steps.csv)、[`red.csv`](runs/t1-light/red.csv)、[`use.csv`](runs/t1-light/use.csv)，完整实验终端输出见 [`run-console.log`](evidence/task1-20261027/run-console.log)。空载阶段没有请求，按请求数作分母的指标会产生 `NaN` 或 `+Inf`，不用于推算每请求开销。`all` 是两个有负载阶段的客户端合计，Prometheus 未对该行执行合并查询。

从 **100 请求/秒的第 3 阶段**读出：每次查询实际占用连接 **10.4843 ms**（`db_query_mean_ms`）；每个请求消耗的 CPU **0.602963 ms**（`cpu_ms_per_req`）。实际连接占用包含定时器唤醒和调度开销，因此略大于设置的 `db_ms=10`，后续预测应引用实测值。

检查点：两个有负载阶段的四条查询均得到有限数值，`server_error_rate=0`、`server_slo_good=1`。客户端共发送并成功完成 **4451** 个请求，HTTP 错误、超时、网络错误与丢弃均为 0，50 ms SLI 为 1；`warn` 为空，发送滞后 p99 为 1.05 / 1.06 ms，loadgen CPU 为 1% / 2%。实验前后服务端成功请求计数由 1 增至 4452，增量与客户端请求数相符。检查表见 [`checkpoint-table.md`](evidence/task1-20261027/checkpoint-table.md)；按各阶段结束时刻重新调用 Prometheus API，12 次查询均只返回一条序列，并与 `red.csv` 的六位有效数字一致，响应与核验结果分别见 [`query-checks.json`](evidence/task1-20261027/query-checks.json)、[`validation.json`](evidence/task1-20261027/validation.json)。

目标到达率是 Poisson 过程的参数，实际请求数会波动；客户端统计完整阶段，Prometheus 去掉每阶段开头 5 秒，因而两者的 RPS 略有不同。服务端 p99 的 19.9 ms 来自 10～20 ms 桶内的线性插值，精度受桶宽限制；它可以高于客户端按实际成功请求耗时排序得到的 p99（12.57 / 13.86 ms）。

## 4. 任务 2：读路径

### 4.1 预测（R1 之前写）

| 资源 | 容量 | 每个请求占用（数据来源） | 推算的上限（请求/秒） |
|---|---|---|---|
| 连接池 | `-pool 4`，即 4 个连接 | 10.4843 ms（任务 1 第 3 阶段、100 请求/秒的 `db_query_mean_ms`，见 `runs/t1-light/red.csv`） | 4 ÷ 0.0104843 = **381.5** |
| CPU | enrolld 的 2 个核（CPU 2-3，`GOMAXPROCS=2`） | 0.602963 ms（任务 1 第 3 阶段、100 请求/秒的 `cpu_ms_per_req`，见 `runs/t1-light/red.csv`） | 2 ÷ 0.000602963 = **3317.0** |

先达到上限的是：**连接池**。预计从多少请求/秒起，客户端 p99 超过 50 ms：**约 325 请求/秒（约 0.85 倍连接池上限）**，预期在第 0.9 档（344 请求/秒）首次超过 50 ms。理由：连接池上限约为 CPU 上限的 1/9，池内只有 4 个查询并行，排队等待随利用率上升很快；按“4 个并行服务、每次查询 10.4843 ms、泊松到达”的模型估算，利用率 0.85 时排队等待的 p99 约 35 ms，叠加任务 1 低负载时客户端 p99 约 13.9 ms，已接近 50 ms；利用率 0.9 时等待 p99 约 55 ms，必然超过。达到 381.5 请求/秒时 CPU 只需约 0.23 个核（381.5 × 0.602963 ms），远未饱和。

R1 的到达率（`scripts/rates.sh 382` 的输出，382 为 381.5 向上取整）：76,153,229,267,306,344,382,420,458

### 4.2 R1：`-pool 4`

`scripts/table.sh runs/r1-pool4 ok_rps error_rate p99_ms server_p99_ms server_mean_ms inflight_avg cpu_ms_per_req pool_in_use_avg pool_wait_p99_ms sched_wait_p99_ms svc_cpu_busy procs_running_avg`：

| step | target_rps | ok_rps | error_rate | p99_ms | server_p99_ms | server_mean_ms | inflight_avg | cpu_ms_per_req | pool_in_use_avg | pool_wait_p99_ms | sched_wait_p99_ms | svc_cpu_busy | procs_running_avg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 76 | 78.2 | 0.0000 | 12.68 | 19.9 | 10.913 | 0.64 | 0.595185 | 0.6 | 0.998385 | 0.477238 | 0.0245 | 1.8 |
| 2 | 153 | 151.7 | 0.0000 | 17.81 | 19.9299 | 11.1228 | 1.56 | 0.560588 | 1.48 | 7.3537 | 0.475798 | 0.0445 | 1.2 |
| 3 | 229 | 228.9 | 0.0000 | 22.09 | 31.8067 | 11.8161 | 2.2 | 0.547113 | 2.12 | 12.6696 | 0.47578 | 0.06125 | 2.6 |
| 4 | 267 | 272.0 | 0.0000 | 30.36 | 46.4885 | 13.4296 | 3.52 | 0.539737 | 2.76 | 19.599 | 0.474204 | 0.07425 | 1.6 |
| 5 | 306 | 309.5 | 0.0000 | 43.56 | 48.663 | 15.7854 | 4.88 | 0.532248 | 3.04 | 43.8011 | 0.474527 | 0.0765 | 1.2 |
| 6 | 344 | 340.7 | 0.0000 | 53.32 | 72.0578 | 19.7969 | 6.96 | 0.533438 | 3.52 | 48.6851 | 0.472476 | 0.08925 | 1.8 |
| 7 | 382 | 384.6 | 0.0000 | 557.23 | 902.645 | 248.324 | 96.4 | 0.517598 | 3.96 | 887.463 | 0.470076 | 0.09725 | 2 |
| 8 | 420 | 384.5 | 0.0779 | 1011.77 | 1980.68 | 995.354 | 412.64 | 0.506449 | 3.84 | 1892.84 | 0.470405 | 0.10325 | 1.2 |
| 9 | 458 | 381.3 | 0.1667 | 1012.14 | 1987.05 | 1002.36 | 458.84 | 0.510228 | 3.96 | 1946.44 | 0.472704 | 0.11625 | 2.4 |
| all | - | 281.3 | 0.0412 | 1011.24 | - | - | - | - | - | - | - | - | - |

最大吞吐量 **384.6** 请求/秒，出现在第 **7** 阶段（目标 382 请求/秒）；客户端 p99 首次超过 50 ms 是在第 **6** 阶段（**344** 请求/秒，p99=53.32 ms）。

第 7 阶段起 `pool_in_use_avg` 达到 3.96/4，`pool_wait_p99_ms` 从第 6 阶段的 48.69 ms 跳到 887.46 ms，客户端 mean 从 19.81 ms 升到 240.31 ms；第 8、9 阶段目标 420、458 请求/秒时，成功吞吐停在 384.5、381.3 请求/秒，客户端错误率 7.79%、16.67%，服务端 5xx 比例 8.30%、16.85%，即连接池饱和后多出的请求等连接超时并以 503 返回。实测吞吐平台 381～385 请求/秒与预测的 381.5 请求/秒相差不到 1%。

CPU 在所有阶段都远未饱和：第 7 阶段 `svc_cpu_busy` 仅 0.097，`sched_wait_p99_ms` 稳定在 0.47～0.48 ms，`procs_running_avg` 在 1.2～2.6 之间波动，没有随负载持续上升。

### 4.3 CPU 消耗在何处

在约 0.8 倍上限的负载下采集 20 秒 CPU 剖析，`go tool pprof -top` 的前 10 行（同时保存在 `runs/r1-pool4/pprof-top.txt`）：

```text
      flat  flat%   sum%        cum   cum%
     2.41s 82.82% 82.82%      2.41s 82.82%  main.spin (inline)
     0.14s  4.81% 87.63%      0.14s  4.81%  internal/runtime/syscall/linux.Syscall6
     0.07s  2.41% 90.03%      0.07s  2.41%  runtime.futex
     0.03s  1.03% 91.07%      0.03s  1.03%  runtime.usleep
     0.02s  0.69% 91.75%      0.02s  0.69%  internal/runtime/atomic.(*Uint32).CompareAndSwap (inline)
     0.02s  0.69% 92.44%      0.02s  0.69%  runtime.memclrNoHeapPointers
     0.02s  0.69% 93.13%      0.02s  0.69%  runtime.nextFreeFast (inline)
     0.01s  0.34% 93.47%      2.45s 84.19%  main.(*server).handleCourse
     0.01s  0.34% 93.81%      0.09s  3.09%  net/http.(*conn).readRequest
     0.01s  0.34% 94.16%      0.02s  0.69%  runtime.newobject
```

`main.spin` 占 **82.82%**；按本次的吞吐量和 enrolld 消耗的 CPU 计算，每个请求 **0.532 ms**（R1 第 5 阶段、306 请求/秒的 `cpu_ms_per_req=0.532248`），其中 spin 约 **0.441 ms**，其余约 **0.091 ms** 消耗在 HTTP 请求解析与响应写出、读写 socket 的系统调用，以及 Go 运行时的调度、内存分配与 GC 上。剖析窗口共 20 秒、采样 2.91 s，相当于 0.146 个核，与同一到达率下 R1 第 5 阶段的进程 CPU 0.166 个核（`cpu_cores`）同一量级。

### 4.4 R2：调大连接池（预测在 R2 之前写）

| 项 | 值与算法 |
|---|---|
| 每个请求占用的 CPU（取 R1 哪一阶段的 `cpu_ms_per_req`，选取理由） | 0.533438 ms（R1 第 6 阶段、344 请求/秒）。这是尚未达到连接池上限的最高阶段：第 7 阶段池占用已到 3.96/4、排队时间飙升，不适合代表饱和前的每请求开销；第 6 阶段池平均占用 3.52/4、无错误，且负载最高 |
| 推算的 CPU 上限 C | 2 ÷ 0.000533438 = **3749.2** 请求/秒 |
| R2 的池大小 P2 = ceil(2 × C × 每次查询的秒数) | ceil(2 × 3749.2 × 0.0104739) = ceil(78.53) = **79** |
| R2 的到达率（`scripts/rates.sh 3749 0.3 0.6 0.8 0.9 1.0 1.1 1.25 1.5`） | 1125,2249,2999,3374,3749,4124,4686,5624 |
| 预测：R2 中先达到上限的是 | **CPU**。79 个连接按每次查询 10.4739 ms 计算可支撑约 7543 请求/秒，约为 C 的 2.0 倍；预计吞吐在 C≈3749 请求/秒附近达到平台，随后 `svc_cpu_busy` 接近 1、`sched_wait_p99_ms` 明显上升 |

`scripts/table.sh runs/r2-pool79 ok_rps error_rate p99_ms server_p99_ms inflight_avg cpu_cores cpu_ms_per_req cpu_wait_threads sched_wait_p99_ms pool_in_use_avg svc_cpu_busy procs_running_avg cpu_psi_some`：

| step | target_rps | ok_rps | error_rate | p99_ms | server_p99_ms | inflight_avg | cpu_cores | cpu_ms_per_req | cpu_wait_threads | sched_wait_p99_ms | pool_in_use_avg | svc_cpu_busy | procs_running_avg | cpu_psi_some |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1125 | 1133.7 | 0.0000 | 12.57 | 19.9 | 11.88 | 0.533131 | 0.468687 | 0.183511 | 0.48795 | 11.68 | 0.2615 | 1.8 | 0.0855305 |
| 2 | 2249 | 2244.6 | 0.0000 | 13.12 | 19.9006 | 23.92 | 0.985429 | 0.438635 | 0.287623 | 0.871893 | 23.36 | 0.489 | 2 | 0.129241 |
| 3 | 2999 | 2990.4 | 0.0000 | 13.49 | 19.9 | 30.12 | 1.27726 | 0.427718 | 0.276567 | 1.47254 | 29.6 | 0.63225 | 4.6 | 0.128191 |
| 4 | 3374 | 3367.4 | 0.0000 | 14.04 | 19.9 | 35.04 | 1.42381 | 0.422506 | 0.221169 | 1.85994 | 34.48 | 0.7035 | 3 | 0.106111 |
| 5 | 3749 | 3751.4 | 0.0000 | 14.86 | 19.9 | 38.36 | 1.57274 | 0.419236 | 0.13676 | 3.02574 | 37.6 | 0.782 | 3.8 | 0.0683133 |
| 6 | 4124 | 4142.3 | 0.0000 | 16.54 | 19.9 | 42.6 | 1.73466 | 0.418275 | 0.0733433 | 4.48178 | 41.72 | 0.86375 | 4.2 | 0.0422541 |
| 7 | 4686 | 4698.7 | 0.0000 | 31.65 | 19.9069 | 50.24 | 1.93354 | 0.412024 | 0.0427166 | 17.8061 | 49.24 | 0.965 | 5 | 0.0295159 |
| 8 | 5624 | 817.4 | 0.8545 | 1999.58 | 1970.69 | 2821.8 | 2.01518 | 0.428402 | 0.0142152 | 1000 | 69.8 | 0.99925 | 3.4 | 0.0257958 |
| all | - | 2893.2 | 0.1718 | 1760.45 | - | - | - | - | - | - | - | - | - | - |

最大吞吐量 **4698.7** 请求/秒（第 7 阶段，目标 4686）；与预测的 C 相差：**实测比预测 3749.2 高 25.3%**。第 7 阶段 `svc_cpu_busy=0.965`，用该阶段的 `cpu_ms_per_req=0.412024` 反推，饱和时的 CPU 上限约为 2 ÷ 0.000412 = **4854** 请求/秒。差异的原因是每请求 CPU 随负载下降：R1 第 6 阶段为 0.533 ms，R2 第 7 阶段为 0.412 ms（-22.7%），故用中低负载的每请求 CPU 推算上限偏保守。

R2 中先达到上限的是 **CPU**，连接池没有先到：第 7 阶段 CPU 已 96.5%，池占用 49.24/79；第 8 阶段 CPU 99.9%，池占用 69.8/79。CPU 饱和的迹象首先出现在 Go 运行时层：`sched_wait_p99_ms` 从第 1 阶段的 0.49 ms 升到第 7 阶段的 17.81 ms、第 8 阶段的 1000 ms，而内核层 `cpu_wait_threads` 始终只有 0.014～0.29。第 8 阶段目标 5624 请求/秒已超过实测上限：服务端仍处理约 4704 请求/秒（`server_rps=4703.96`），`svc_cpu_busy=0.999`，但客户端 85.45% 失败（13975 个 5xx、130086 个超时），`warn` 同时记录了“发送滞后 p99 = 40.3 ms”，该阶段的客户端延迟不代表服务能力，饱和结论以 CPU 指标和第 7 阶段的吞吐为准。该阶段同时出现连接池等连接 p99 1957.93 ms、`db_query_mean_ms` 升到 39.28 ms：CPU 饥饿拖长了每次查询占用连接的时间，池才被动变成第二个瓶颈。

## 5. 任务 3：写路径

### 5.1 预测：`-sync each`（W1 之前写）

| 项 | 值与算法 |
|---|---|
| fsync 平均耗时（任务 0） | <填写> ms |
| 推算的最大 TPS | <填写> |
| 达到上限时 enrolld 大约使用几个核（写路径没有 spin，按 4.3 节拆分出的“spin 以外的开销”估计每个写请求的 CPU） | <填写> |
| W1 的到达率（`scripts/rates.sh <最大 TPS> 0.2 0.4 0.6 0.8 0.9 1.0 1.1 1.2`） | <填写> |

### 5.2 W1：`-sync each`

`scripts/table.sh runs/w1-<…> ok_rps error_rate p99_ms server_p99_ms cpu_cores fsync_per_s fsync_mean_ms batch_mean svc_cpu_busy cpu_iowait disk_w_per_s disk_w_await_ms disk_f_per_s disk_f_await_ms disk_aqu_sz disk_util`：

<粘贴表格>

### 5.3 预测：`-sync group`（W2 之前写）

在 W1 达到上限时的到达率下，改为组提交后：吞吐量 <填写>；平均每次 fsync 处理 <填写> 条记录；客户端 p99 约 <填写>。理由：<填写>

W2 的到达率：<填写>

### 5.4 W2：`-sync group`

（列与 5.2 相同）

<粘贴表格>

### 5.5 W3：`-sync interval`

（列与 5.2 相同）

<粘贴表格>

## 6. 分析问题

每题先列出所用数据（引用上面的表或 `runs/` 中的文件），再写结论，并说明结论的成立条件。每题 300～600 字。

**问题 1：上限由什么决定。** 按 L-07 第 25 页资源账的格式，为 enrolld 的读路径编制一份资源账：资源、每个请求占用（实测）、容量、推算的上限、实测的最大吞吐量、饱和观测项。预测与实测相差多少，差异来自何处？`cpu_ms_per_req` 随负载如何变化，原因是什么？这对“在低负载下测量每请求开销，再推算上限”的做法意味着什么？`db_query_mean_ms` 为什么大于 `-db-ms`？以“p99 ≤ 50 ms”为目标，R1 能承受的最大阶段相当于上限的多少比例？与 L-07 第 6 页“容量 = 上限 × 0.7”比较，为什么尚未达到上限延迟就已上升？R2 调大连接池后，瓶颈转移到了哪个资源？

<填写>

**问题 2：利用率不等于饱和。** R1 达到上限时，enrolld 所在核的 CPU 利用率是多少？哪个数值最先表明资源已经饱和？R2 中 CPU 利用率接近 100% 时，内核层的 `procs_running_avg`、`cpu_psi_some`、`cpu_wait_threads` 和 Go 运行时层的 `sched_wait_p99_ms` 分别如何变化？为什么内核层几乎观察不到排队，排队发生在哪里？这与 L-06 第 16、17 页 Tomcat 的线程池有何相同之处？最后用 Little's Law 核对：从 R1 选取三个阶段，用 `server_rps × server_mean_ms` 计算在途请求数，并与 `inflight_avg` 比较；W 为什么必须用平均值而不能用 p99？哪个阶段不一致，原因是什么？

<填写>

**问题 3：持久性以延迟为代价。** W1 实测的最大 TPS 与 1000 ÷ fsync 平均耗时相比如何？W1 达到上限时 CPU、内存、磁盘的指标各是多少，哪几列表明磁盘饱和？应用测得的 `fsync_mean_ms` 与 `disk_w_await_ms`、`disk_f_await_ms` 为什么不同？一次 fsync 大约对应几次写和几次 flush？W1 与 W2 在 `disk_util` 相近时吞吐量相差多少，`%util` 接近 100% 能否说明磁盘已经饱和？组提交的 `batch_mean` 如何随负载变化，低负载时是否有收益，本组的预测是否正确？W3 快了多少，代价是什么？选课记录应采用哪一种方式，在什么条件下 interval 可以接受？

<填写>

**问题 4：延迟数值的测量位置与方法。** 同一阶段中，客户端与服务端的平均值、p99 各相差多少？列出只计入客户端的时间组成。找出一个服务端 p99 大于客户端 p99 的阶段，并解释原因（L-08 第 10 页）。比较服务端的 `server_slo_good` 与客户端的 `slo_good`；若存在过载阶段，二者为何相差很大？SLI 应在何处测量（L-08 第 19 页）？用 R1 的 `steps.csv`，将各阶段的 p99 求平均，与 `all` 行的 p99 比较，说明百分位数为什么不能平均，以及正确的合并方法。最后计算错误预算：SLO 为“30 天内 99% 的读请求在 50 ms 内成功返回”，若 R1 中第一个不达标阶段的负载持续下去，燃烧率是多少，30 天的预算多久耗尽（L-08 第 21 页）？

<填写>

## 7. 选做记录

| 选做 | 完成情况与证据 |
|---|---|
| O1 内存与 GC | <未做 / 预测、`runs/` 目录、结论> |
| O2 网络 | <未做 / 两台主机的规格与拓扑、`runs/` 或日志、结论> |
| O3 告警与看板 | <未做 / 规则文件、触发记录、看板说明> |
| O4 迁移到小组项目 | <未做 / 仓库链接、测了哪个资源、结论> |

## 8. 成员分工

每位成员一行，只填写 GitHub 用户名，无需填写姓名；行数应与小组人数一致。

| GitHub 用户名 | 负责的部分 |
|---|---|
| RyanShen30 | 任务 0：环境核验、构建测试与工具下载、fsync 基线、资源观测；任务 1：监控启动与绑核、四条 PromQL、轻载实验、报告及原始证据整理 |
| Liuxiang400 | 任务 2：读路径预测、R1/R2 压测、CPU 剖析、报告及原始证据整理 |
| Shundi-Wu | 后续任务分工待确认 |
| ashkirakira | 后续任务分工待确认 |
