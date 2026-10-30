#!/usr/bin/env bash
# 选做 O2：服务端在主机 A（本机），压测端在主机 B。scripts/run.sh 要求 loadgen 与 enrolld 在同一台主机，
# 所以这里在 B 上直接运行 loadgen，并在 A 上自行记录 sar、ss（指导书第 5 节 O2）。
#
# 用法（在 A 的仓库根目录，先 make build）：
#   B=wsd@<B 的内网地址> A_ADDR=<A 的内网地址>:18080 scripts/o2-run.sh <名字> <到达率，逗号分隔>
# 环境变量：KEY 登录 B 的私钥（默认 ~/.ssh/lab2_b_ed25519）、STEP 每阶段时长（默认 30s）、KB 响应大小（默认 256）。
#
# runs/<名字>/ 里有：
#   meta.txt                      两台主机、enrolld 的 /config、压测命令、仓库提交
#   steps.csv loadgen.log         B 上 loadgen 的结果（客户端）
#   a-sar-dev.log                 A 每秒的网卡收发（txkB/s 等）
#   a-sar-tcp.log                 A 每秒的 TCP 连接与重传（sar -n TCP,ETCP）
#   a-ss.log                      A 每 5 s 一次 ss -tin：一行汇总（连接数、Send-Q、rtt、cwnd、重传），外加前 10 条连接的原文
#   a-nstat-start.txt a-nstat-end.txt   A 的内核网络计数器（含 TcpRetransSegs）
#   a-mpstat.log a-pidstat.log    A 的各核 CPU 与 enrolld 进程 CPU
#   b-sar-dev.log b-mpstat.log    B 的网卡收发与各核 CPU
#   metrics-start.txt metrics-end.txt   enrolld 的 /metrics
set -euo pipefail

die() { echo "o2-run.sh：$*" >&2; exit 1; }
name=${1:-}
rates=${2:-}
[ -n "$name" ] && [ -n "$rates" ] || die "用法：B=… A_ADDR=… scripts/o2-run.sh <名字> <到达率>"
[[ $name =~ ^[A-Za-z0-9._-]+$ ]] || die "名字只能用字母、数字和 . _ -"
B=${B:?需要 B=用户@B 的内网地址}
A_ADDR=${A_ADDR:?需要 A_ADDR=A 的内网地址:端口}
KEY=${KEY:-$HOME/.ssh/lab2_b_ed25519}
STEP=${STEP:-30s}
KB=${KB:-256}
dir=runs/$name
data=data/$name
remote=lab2-o2/$name
[ -x bin/enrolld ] && [ -x bin/loadgen ] || die "先 make build"
[ ! -e "$dir" ] && [ ! -e "$data" ] || die "$dir 或 $data 已存在，换一个名字"
[ -f evidence/optional-20261030/o2-prediction.md ] || die "先写好 evidence/optional-20261030/o2-prediction.md"

ssh_b() { ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 "$B" "$@"; }
ssh_b "test ! -e $remote && mkdir -p $remote" || die "B 上的 ~/$remote 已存在或无法登录 B"
scp -q -i "$KEY" bin/loadgen "$B:$remote/loadgen"
mkdir -p "$dir" "$data"

export LC_ALL=C S_TIME_FORMAT=ISO
pids=()
cleanup() {
  kill "${pids[@]}" 2>/dev/null || true
  wait "${pids[@]}" 2>/dev/null || true
  ssh_b "pkill -u \$(id -u) -f '$remote/loadgen' || true" 2>/dev/null || true
}
trap cleanup EXIT

taskset -c 2-3 bin/enrolld -addr "$A_ADDR" -data "$data" >"$dir/a-enrolld.log" 2>&1 &
enrolld=$!
pids+=("$enrolld")
for i in $(seq 20); do
  ssh_b "curl -fsS -m 2 http://$A_ADDR/healthz" >/dev/null 2>&1 && break
  [ "$i" -lt 20 ] || die "B 连不上 http://$A_ADDR（安全组或防火墙？）"
  sleep 1
done

{
  echo "名字: $name"
  echo "开始: $(date -Iseconds)（A）；$(ssh_b 'date -Iseconds')（B）"
  echo "A: $(hostname)，$(uname -srm)，$(nproc) 个逻辑核，网卡 eth0 驱动 $(basename "$(readlink /sys/class/net/eth0/device/driver)")"
  echo "B: $(ssh_b 'echo $(hostname)，$(uname -srm)，$(nproc) 个逻辑核，网卡 eth0 驱动 $(basename $(readlink /sys/class/net/eth0/device/driver))')"
  echo "enrolld（A）: pid $enrolld，绑定的核 $(taskset -pc "$enrolld" | sed 's/.*: *//')，监听 A 的内网地址"
  echo "loadgen（B）: 不绑核，GOMAXPROCS 取 B 的全部核"
  echo "仓库提交: $(git rev-parse --short HEAD)，未提交的改动 $(git status --porcelain | wc -l) 处"
  echo "压测命令（B）: loadgen -url http://<A>/api/export?kb=$KB -rates $rates -step $STEP"
  echo "enrolld /config:"
  curl -fsS -m 5 "http://$A_ADDR/config"
} >"$dir/meta.txt"
curl -fsS -m 5 "http://$A_ADDR/metrics" >"$dir/metrics-start.txt"
nstat -asz >"$dir/a-nstat-start.txt"

sar -n DEV 1 >"$dir/a-sar-dev.log" 2>&1 & pids+=($!)
sar -n TCP,ETCP 1 >"$dir/a-sar-tcp.log" 2>&1 & pids+=($!)
mpstat -P ALL 1 >"$dir/a-mpstat.log" 2>&1 & pids+=($!)
pidstat -h -u -p "$enrolld" 1 >"$dir/a-pidstat.log" 2>&1 & pids+=($!)
port=${A_ADDR##*:}
(
  while true; do
    out=$(ss -tin state established "( sport = :$port )")
    awk -v t="$(date -Iseconds)" '
      /^[0-9]/ { n++; sendq += $2 }
      /rtt:/ {
        if (match($0, /rtt:[0-9.]+/)) { r = substr($0, RSTART + 4, RLENGTH - 4) + 0; rtt += r; if (r > rmax) rmax = r }
        if (match($0, /cwnd:[0-9]+/)) cwnd += substr($0, RSTART + 5, RLENGTH - 5)
        if (match($0, /retrans:[0-9]+\/[0-9]+/)) { split(substr($0, RSTART + 8, RLENGTH - 8), a, "/"); retr += a[2] }
      }
      END { printf "== %s 连接 %d，Send-Q 合计 %d B，rtt 平均 %.3f ms，最大 %.3f ms，cwnd 平均 %.1f，存活连接累计重传 %d\n",
                   t, n, sendq, n ? rtt / n : 0, rmax, n ? cwnd / n : 0, retr }' <<<"$out"
    head -n 21 <<<"$out"
    sleep 5
  done
) >"$dir/a-ss.log" 2>&1 & pids+=($!)

echo "== B 上运行 loadgen：$rates（每阶段 $STEP）"
status=0
ssh_b "cd $remote || exit 1
  export LC_ALL=C S_TIME_FORMAT=ISO
  sar -n DEV 1 >b-sar-dev.log 2>&1 & s1=\$!
  mpstat -P ALL 1 >b-mpstat.log 2>&1 & s2=\$!
  ./loadgen -url 'http://$A_ADDR/api/export?kb=$KB' -rates '$rates' -step '$STEP' -out steps.csv >loadgen.log 2>&1; st=\$?
  sleep 1; kill \$s1 \$s2; wait 2>/dev/null; exit \$st" || status=$?
sleep 1
for f in steps.csv loadgen.log b-sar-dev.log b-mpstat.log; do
  scp -q -i "$KEY" "$B:$remote/$f" "$dir/${f}" || echo "警告：取不回 B 上的 $f" >&2
done
curl -fsS -m 5 "http://$A_ADDR/metrics" >"$dir/metrics-end.txt" || echo "警告：结束时取不到 /metrics" >&2
nstat -asz >"$dir/a-nstat-end.txt"
cleanup
trap - EXIT
echo "结束: $(date -Iseconds)" >>"$dir/meta.txt"
[ "$status" -eq 0 ] || die "loadgen 退出码 $status，见 $dir/loadgen.log"
cat "$dir/loadgen.log" | tail -n 20
echo "完成：$dir"
