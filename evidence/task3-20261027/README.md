# 任务 3：写路径实验记录

实验在任务 0～2 使用的 `devops-server` 上执行，工作目录为 `/home/gyz/ops-lab2-2-task3`，登录用户为 `gyz`。基础提交为 `76a2e2ab9861fbfc2635d79d257f86a2f2cac169`。用户确认当前没有其他人在压测后开始本次实验。时间均为 Asia/Shanghai（UTC+08:00）。

## 环境和复现

本次使用独立的 enrolld（`127.0.0.1:18080`）、Prometheus（`127.0.0.1:19090`）和 node_exporter（`127.0.0.1:19100`），未停止或更改 lx 用户的服务。旧服务及其监控仍有少量后台开销，块设备指标也是全盘口径。各次实验使用同样的分核、端口和监控配置：enrolld 绑定 CPU `2-3`，其余绑定 CPU `0-1`。Prometheus 的 TSDB 放在 `/dev/shm/lab2-prom-1003-<实验名>`，不与被测云盘竞争写入。

`scripts/task3-run.py` 调用课程原有的 `scripts/run.sh`，使用 Poisson 到达、默认随机种子 1、每阶段 30 秒、请求超时 2 秒和 SLO 20 ms。每次启动使用全新的 `data/task3-<实验名>/`，因此没有上次日志的残留。写入仍位于 `/dev/vda1` 的 ext4 文件系统；这是任务 0 相同的块设备。源程序及两份查询文件保持原样，三种模式仅通过 `-sync` 切换。

独立目录的构建和测试输出转录见 [build-test.txt](build-test.txt)，工具版本与课程脚本的 SHA-256 校验通过记录见 [get-tools.log](get-tools.log)。[host-before.txt](host-before.txt) 保存运行前的系统、分核、内存、磁盘和进程信息；[prometheus.yml](prometheus.yml) 是本次监控配置。

运行脚本先检查预测文件、端口、目录和工具，等待两个抓取目标均为 up，再预热 10 秒。实验结束后导出 CSV、记录目标状态，终止自己启动的进程。原始数据、TSDB 和应用日志保留在实验主机，TSDB 位于内存文件系统，主机重启会丢失。

在实验主机仓库根目录复现同一条件（先确认没有其他压测）：

```bash
python3 scripts/task3-run.py each 810 --suffix=-check
# 先检查 W1，再确认或重新写好组提交预测，才运行下面两条。
python3 scripts/task3-run.py group 810 --suffix=-check
python3 scripts/task3-run.py interval 810 --suffix=-check
```

首次正式运行未使用 `--suffix`；复测需选择尚未使用的后缀。若主机、基线或到达率发生变化，应另外保存测前预测并通过 `--evidence` 指定新证据目录。脚本拒绝覆盖已有实验、数据目录和 TSDB，也不会删除其他人的文件。W2 第一次启动前的端口预检查曾遇到上一轮连接的 TIME_WAIT，修正为使用 `SO_REUSEADDR` 后启动；当时尚未开始 W2 测量，源服务与压测参数没有变化。

## 预测和原始证据

- [prediction-w1.md](prediction-w1.md)：W1 测量前保存的第 5.1 节预测。
- [prediction-w2.md](prediction-w2.md)：W1 测量完成、W2 开始前保存的第 5.3 节预测。
- `w*-manifest.json`：源提交、命令、到达率、预测文件 SHA-256，以及准备、开始、结束和清理时间。
- `w*-config.json`、`w*-enrolld.log`：每次启动的参数与 GOMAXPROCS。
- `w*-targets-before.json`、`w*-targets-after.json`：实验前后的抓取目标和健康状态。
- `w*-console.log`：课程脚本完整终端输出；`w*-node.log`、`w*-prometheus.log` 为监控启动与退出记录。
- [runs/w1-each](../../runs/w1-each/meta.txt)、[runs/w2-group](../../runs/w2-group/meta.txt)、[runs/w3-interval](../../runs/w3-interval/meta.txt)：客户端、服务端、资源层 CSV、原始 metrics 和每秒系统日志。

报告表格由 `scripts/table.sh` 生成，保存为 `w1-table.md`、`w2-table.md`、`w3-table.md`，并原样粘贴到 `LAB2.md` 第 5 节。预测不会按实测结果回改，偏差在各结果表后讨论。写路径没有读请求，连接池相关指标可能为 NaN；这些字段不用于写路径结论。

三次实验共 18 个阶段，构建测试及数据核验均已通过。[validation.json](validation.json) 记录阶段数、指标完整性、客户端计数守恒、压测警告、监控健康、实验配置、预测时间与校验值、表格一致性及此前任务保持原样的检查结果。在仓库根目录运行 `python3 evidence/task3-20261027/validate.py` 可复核（会更新核验时间）；`sha256sum -c evidence/task3-20261027/files.sha256` 用于检查交付时的文件内容，重新生成文件后需相应更新清单。[services-after.txt](services-after.txt) 确认本次服务已退出，原 lx 用户的三个服务 PID 保持运行。

## 测量口径

客户端 CSV 统计整个 30 秒阶段，Prometheus 的查询窗口去掉每阶段开头 5 秒。`cpu_cores` 是 enrolld 进程的 CPU 核数，`svc_cpu_busy` 是 CPU 2～3 的忙碌比例，`cpu_iowait` 是全机平均等待比例。比例列均为 0～1，不能当成百分数直接引用。

应用 fsync 耗时、块设备每次写入耗时和每次 flush 耗时的统计对象不同。一笔 fsync 可能产生多次设备 I/O，不能直接将三列相等比较。客户端 p99 使用成功请求的实测延迟；服务端 p99 由直方图桶插值得到，且窗口不同。过载时要结合错误率、发送滞后和服务端完成速率解释，不能只看成功请求延迟。

`each` 与 `group` 都在 fsync 成功之后响应。`interval` 写入页缓存即响应，后台每秒尝试 fsync；本次没有模拟掉电。正常周期下可能丢失最近约一秒已确认记录，调度或磁盘阻塞时暴露窗口还可能更长，不能将一秒视为严格保证。
