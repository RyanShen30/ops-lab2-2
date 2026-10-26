| 工具与列 | 空载 | 运行 `-bench-fsync` 时 | 该列的含义 |
|---|---|---|---|
| `vmstat -w 1`：r、b | r=0.00；b=0.20 | r=0.18；b=1.00 | r：可运行任务数；b：处于不可中断睡眠的阻塞任务数，常与 I/O 等待有关；此处为采样均值 |
| `vmstat -w 1`：us、sy、id、wa、st | us=0.30%；sy=0.10%；id=99.40%；wa=0.00%；st=0.00% | us=0.18%；sy=1.91%；id=74.64%；wa=23.27%；st=0.00% | 用户态 CPU、内核态 CPU、空闲、I/O 等待、被宿主机占用的 CPU 时间比例；均为全机口径 |
| `iostat -dx 1 vda`：w/s、wkB/s | w/s=4.50；wkB/s=122.00 | w/s=2355.73；wkB/s=12857.09 | 每秒块设备写请求数、每秒写入量（kB/s） |
| `iostat -dx 1 vda`：w_await、f/s、f_await | w_await=0.51；f/s=0.40；f_await=0.00 | w_await=0.41；f/s=1567.45；f_await=0.05 | 每次写 I/O 平均耗时（ms）、每秒 flush 次数、每次 flush 平均耗时（ms）；此表为每秒读数的算术平均 |
| `iostat -dx 1 vda`：aqu-sz、%util | aqu-sz=0.00；%util=0.07 | aqu-sz=1.04；%util=95.91 | 平均未完成 I/O 数、设备存在 I/O 的忙碌时间比例（%）；云盘的 %util 不能单独代表底层容量 |
