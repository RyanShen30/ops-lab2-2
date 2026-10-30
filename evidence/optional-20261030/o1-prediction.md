# O1 测前预测（运行 o1-gogc100、o1-gogc400 之前写好，之后不改）

写于 2026-10-30，运行之前。

## 实验安排

- `GET /api/report?mb=4`：每个请求分配 4 MiB 临时内存，并逐页写入。到达率 100 请求/秒，即每秒约分配 400 MiB。
- 两次实验仅 `GOGC` 不同（100、400），其余与任务 1～3 相同：enrolld 绑 CPU 2-3（`GOMAXPROCS=2`），loadgen、Prometheus、node_exporter 绑 CPU 0-1；端口 18080/19090/19100，不动 lx 的服务。
- 每次 `scripts/run.sh` 跑 3 个 30 s 阶段，都是 100 请求/秒。GC 增量取 `metrics-end.txt − metrics-start.txt`；每阶段的 GC 次数/秒、GC CPU、RSS 另用 [`queries-gc.txt`](queries-gc.txt) 按阶段查询。

## 预测

Go 的堆目标约为“上次 GC 后的存活堆 × (1 + GOGC/100)”，且不低于 4 MiB × GOGC/100。这里存活堆很小（在途请求约 0.1～1 个，每个 4 MiB），所以堆目标主要由下限决定：GOGC=100 约 4～8 MiB，GOGC=400 约 16～25 MiB。

1. **GC 次数**：GOGC=100 时大约每 1～2 个请求就触发一次 GC，约 **50～100 次/秒**；GOGC=400 时约每 4～5 个请求一次，约 **20～25 次/秒**，约为前者的 **1/4**。
2. **GC CPU**（`go_gc_cpu_seconds_total` 的增量）：存活堆小，每次标记的工作量很小，GC CPU 主要随次数增长；预计 GOGC=400 约为 GOGC=100 的 **1/3～1/4**。
3. **RSS**（`process_resident_memory_bytes`）：GOGC=100 约 **20～30 MiB**，GOGC=400 约 **40～60 MiB**，约 1.5～2.5 倍。
4. **p99**：100 请求/秒下 CPU 远未饱和，GC 与请求并发进行，停顿只有几十微秒，两者的 p99 都在几毫秒以内；GOGC=400 可能略低，但差距可能小于阶段间的噪声。
5. **取舍**：GOGC=400 用更多内存换取更少的 GC 次数和 GC CPU，与 L-06 第 12 页 JVM“堆越大，GC 越少，但单次回收的量越大”是同一种取舍。若内存受限（容器 limit），调大 GOGC 可能导致 OOM，此时应配合 `GOMEMLIMIT` 使用。
