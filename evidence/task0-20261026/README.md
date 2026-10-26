# 任务 0 原始证据

采集日期：2026-10-26（Asia/Shanghai）。对应小组仓库 RyanShen30/ops-lab2-2；报告见仓库根目录 LAB2.md 第 1、2 节。

本目录保存任务 0 的实际命令输出。原始日志保持采集内容；*-selected.csv、summary.* 和 baseline-table.md 是从原始输出生成的派生文件。后续 HTTP 压测使用指导书的 scripts/run.sh 和 runs/，不将任务 0 的 fsync 工具观测伪装为 HTTP run。

## 命令与文件

| 命令/内容 | 文件 |
|---|---|
| make build test | build-test.log |
| scripts/get-tools.sh；脚本固定 SHA-256 校验成功后才解压 | get-tools.log |
| lscpu、lscpu -e、free -m、uname -r、OS、挂载、磁盘、工具版本、DMI、id | host.txt |
| 用户提供的华为云控制台截图中的实例规格与系统盘信息，2026-10-27 补录 | cloud-specification.md |
| 连续三次 bin/enrolld -bench-fsync 2000 | fsync-1.txt、fsync-2.txt、fsync-3.txt |
| 三次执行的时间与退出状态 | fsync-runs.json |
| LC_ALL=C vmstat -w 1 | vmstat.log |
| LC_ALL=C iostat -dx 1 vda | iostat.log |
| 空载后连续两次 bin/enrolld -bench-fsync 5000 | fsync-observe-1.txt、fsync-observe-2.txt |
| 观测区间与命令 | observation.json |
| 原始输出行及相对采集秒数 | monitor-lines.jsonl |
| 选中的每秒样本、原始文件行号和区间 | vmstat-selected.csv、iostat-selected.csv |
| 各列均值/最小值/最大值、fsync 容量计算 | summary.json、summary.csv |
| 自动生成的报告基线表 | baseline-table.md |
| 仓库公开性及协作者权限的只读快照 | repository-access.json |

## 观测与汇总方法

1. vmstat 和 iostat 同时启动；先保持约 10.5 秒无主动实验负载。
2. 连续两次运行 5000 次 fsync，单次约 6 秒，覆盖至少 10 秒的写盘观测。
3. 两个工具的第一条数值记录为开机以来的平均值，排除。后续记录的区间为前一条数值记录采集时刻至本条时刻。
4. 仅保留整个采样区间都位于 observation.json 中同一个空载或 fsync 段内的记录，跨阶段记录排除。工具重复打印的表头不算数值记录。
5. 每个工具选中空载 10 个、fsync 11 个每秒样本。各列的算术平均用于报告典型值；完整范围见 summary.json。await 列不是按 I/O 次数加权的全程平均。
6. 三次基准各 2000 次，使用打印的 mean 等权平均得到 1.235 ms；1000/1.235=809.7166 次/秒，作为串行 fsync 的估计上限。打印值精度为 0.001 ms。

2026-10-27 根据用户提供的华为云控制台截图补录：华为云 ECS，通用计算型 `x1.4u.8g`，4 vCPU、8 GiB，华东-上海一、可用区 3；系统盘为通用型 SSD，40 GiB。字段摘录见 [cloud-specification.md](cloud-specification.md)。来宾系统检测到 OpenStack Nova/KVM；`free -m` 实测 total 7556 MiB 与控制台配置 8 GiB 分别记录，基线原始输出保持采集时的内容。
