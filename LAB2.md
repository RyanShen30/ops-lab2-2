# 实验 2 记录：第 2 组

本文件中的数值均注明原始数据出处。任务 0 的命令输出和基线原始日志见下方证据链接；后续 HTTP 实验的数据保存于 `runs/<名字>/`，表格使用 `scripts/table.sh` 生成后粘贴，其他数值注明具体文件与阶段。

第 4.1、4.4、5.1、5.3 节的预测须在对应的测量之前写好，写好后不要修改。预测错误不扣分，与实测不一致之处在分析中讨论。

本次更新完成任务 0 的环境与基线记录，采集日期为 **2026-10-26（Asia/Shanghai，UTC+08:00）**。任务 0 的主机命令、fsync 基准和资源工具原始输出保存在 [`evidence/task0-20261026/`](evidence/task0-20261026/README.md)，各数值的来源如下；后续 HTTP 实验按指导书使用 `scripts/run.sh` 生成 `runs/` 数据。任务 1～4 的实验与预测保留待填写。

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
| 分核 | 后续 enrolld 使用 CPU `2-3`；loadgen、Prometheus、node_exporter 使用 CPU `0-1`。按来宾可见 CORE 分开服务与压测/监控；本任务 fsync 基准按指导书直接执行，未对基准额外绑核 |

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

两个抓取目标的状态（`curl -s 127.0.0.1:9090/api/v1/targets` 中两处 `"health"` 的值）：<填写>

本组编写的四条查询（与 `deploy/queries-red.txt` 一致）：

```text
server_rps          <填写>
server_error_rate   <填写>
server_p99_ms       <填写>
server_slo_good     <填写>
```

`runs/t1-light` 的数据（`scripts/table.sh runs/t1-light ok_rps mean_ms p99_ms server_rps server_mean_ms server_p99_ms cpu_ms_per_req db_query_mean_ms`）：

<粘贴表格>

从这次实验读出：每次查询实际占用连接 <填写> ms（`db_query_mean_ms`）；每个请求消耗的 CPU <填写> ms（`cpu_ms_per_req`，取 100 请求/秒的阶段）。

## 4. 任务 2：读路径

### 4.1 预测（R1 之前写）

| 资源 | 容量 | 每个请求占用（数据来源） | 推算的上限（请求/秒） |
|---|---|---|---|
| 连接池 | <`-pool`> 个连接 | <填写> ms | <填写> |
| CPU | enrolld 的 <填写> 个核 | <填写> ms | <填写> |

先达到上限的是：<填写>。预计从多少请求/秒起，客户端 p99 超过 50 ms：<填写>，理由：<填写>

R1 的到达率（`scripts/rates.sh <较小的上限>` 的输出）：<填写>

### 4.2 R1：`-pool 4`

`scripts/table.sh runs/r1-<…> ok_rps error_rate p99_ms server_p99_ms server_mean_ms inflight_avg cpu_ms_per_req pool_in_use_avg pool_wait_p99_ms sched_wait_p99_ms svc_cpu_busy procs_running_avg`：

<粘贴表格>

最大吞吐量 <填写> 请求/秒，出现在第 <填写> 阶段；客户端 p99 首次超过 50 ms 是在第 <填写> 阶段（<填写> 请求/秒）。

### 4.3 CPU 消耗在何处

在约 0.8 倍上限的负载下采集 20 秒 CPU 剖析，`go tool pprof -top` 的前 10 行（同时保存在 `runs/<填写>/pprof-top.txt`）：

```text
<粘贴>
```

`main.spin` 占 <填写>%；按本次的吞吐量和 enrolld 消耗的 CPU 计算，每个请求 <填写> ms，其中 spin 约 <填写> ms，其余 <填写> ms 消耗在：<填写>

### 4.4 R2：调大连接池（预测在 R2 之前写）

| 项 | 值与算法 |
|---|---|
| 每个请求占用的 CPU（取 R1 哪一阶段的 `cpu_ms_per_req`，选取理由） | <填写> |
| 推算的 CPU 上限 C | <填写> |
| R2 的池大小 P2 = ceil(2 × C × 每次查询的秒数) | <填写> |
| R2 的到达率（`scripts/rates.sh C 0.3 0.6 0.8 0.9 1.0 1.1 1.25 1.5`） | <填写> |
| 预测：R2 中先达到上限的是 | <填写> |

`scripts/table.sh runs/r2-<…> ok_rps error_rate p99_ms server_p99_ms inflight_avg cpu_cores cpu_ms_per_req cpu_wait_threads sched_wait_p99_ms pool_in_use_avg svc_cpu_busy procs_running_avg cpu_psi_some`：

<粘贴表格>

最大吞吐量 <填写> 请求/秒；与预测的 C 相差：<填写>

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
| RyanShen30 | 任务 0：环境核验、构建测试与工具下载、fsync 基线、资源观测、报告及原始证据整理 |
| Liuxiang400 | 后续任务分工待确认 |
| Shundi-Wu | 后续任务分工待确认 |
| ashkirakira | 后续任务分工待确认 |
