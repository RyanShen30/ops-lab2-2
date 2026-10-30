#!/usr/bin/env python3
"""Run optional experiment O1 or O3 on isolated ports/directories, leaving teammates' services running."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SVC, PROM, NODE = "127.0.0.1:18080", "127.0.0.1:19090", "127.0.0.1:19100"
READ_URL = f"http://{SVC}/api/courses/1"
ENROLL_BODY = '{"student":"s{{seq}}","course":"c1"}'

# O3 看板：三行九格（业务 / 服务 RED / 资源 USE），每格一到三条查询
DASHBOARD = [
    ("业务", "开放后 10 分钟完成的选课数", 'sum(increase(enroll_commits_total{job="enrolld"}[10m]))'),
    ("业务", "提交成功率", 'sum(rate(http_requests_total{job="enrolld",route="/api/enroll",code=~"2.."}[1m])) / sum(rate(http_requests_total{job="enrolld",route="/api/enroll"}[1m]))'),
    ("业务", "在线连接数（近似在线人数）", 'node_netstat_Tcp_CurrEstab{job="node"}'),
    ("服务", "按接口 QPS", 'sum by (route) (rate(http_requests_total{job="enrolld"}[1m]))'),
    ("服务", "按接口 5xx 比例", '(sum by (route) (rate(http_requests_total{job="enrolld",code=~"5.."}[1m])) or 0 * sum by (route) (rate(http_requests_total{job="enrolld"}[1m]))) / sum by (route) (rate(http_requests_total{job="enrolld"}[1m]))'),
    ("服务", "按接口 p50（秒）", 'histogram_quantile(0.5, sum by (route, le) (rate(http_request_duration_seconds_bucket{job="enrolld"}[1m])))'),
    ("服务", "按接口 p99（秒）", 'histogram_quantile(0.99, sum by (route, le) (rate(http_request_duration_seconds_bucket{job="enrolld"}[1m])))'),
    ("服务", "队列：在途请求", 'sum by (route) (http_inflight_requests{job="enrolld"})'),
    ("服务", "队列：连接池占用比例", 'db_pool_in_use{job="enrolld"} / db_pool_size{job="enrolld"}'),
    ("服务", "队列：等连接 p99（秒）", 'histogram_quantile(0.99, sum by (le) (rate(db_pool_wait_seconds_bucket{job="enrolld"}[1m])))'),
    ("资源", "CPU：enrolld 所在核忙碌比例", 'sum(rate(node_cpu_seconds_total{job="node",mode!~"idle|iowait",cpu=~"2|3"}[1m])) / count(node_cpu_seconds_total{job="node",mode="idle",cpu=~"2|3"})'),
    ("资源", "CPU：等核线程数", 'rate(process_cpu_wait_seconds_total{job="enrolld"}[1m])'),
    ("资源", "内存：enrolld RSS（字节）", 'process_resident_memory_bytes{job="enrolld"}'),
    ("资源", "内存：可用（字节）", 'node_memory_MemAvailable_bytes{job="node"}'),
    ("资源", "磁盘：vda 忙碌比例", 'rate(node_disk_io_time_seconds_total{job="node",device="vda"}[1m])'),
    ("资源", "磁盘：vda 平均队列", 'rate(node_disk_io_time_weighted_seconds_total{job="node",device="vda"}[1m])'),
    ("资源", "磁盘：fsync p99（秒）", 'histogram_quantile(0.99, rate(enroll_fsync_duration_seconds_bucket{job="enrolld"}[1m]))'),
    ("资源", "网络：回环收发（字节/秒）", 'rate(node_network_receive_bytes_total{job="node",device="lo"}[1m]) + rate(node_network_transmit_bytes_total{job="node",device="lo"}[1m])'),
    ("资源", "网络：TCP 重传（段/秒）", 'rate(node_netstat_Tcp_RetransSegs{job="node"}[1m])'),
]
SLO_SERIES = ['ALERTS{alertname=~"EnrolldRead.*"}'] + [
    f"enrolld:read_slo_error_ratio:rate{w}" for w in ("5m", "30m", "1h", "6h")]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("experiment", choices=("o1", "o3"))
parser.add_argument("--gogc", type=int, help="O1：enrolld 的 GOGC")
parser.add_argument("--evidence", default="evidence/optional-20261030")
args = parser.parse_args()
if args.experiment == "o1" and not args.gogc:
    parser.error("O1 需要 --gogc")
name = f"o1-gogc{args.gogc}" if args.experiment == "o1" else "o3-burn"
evidence = ROOT / args.evidence
prediction = evidence / f"{args.experiment}-prediction.md"
if not prediction.is_file():
    parser.error(f"先写好 {prediction} 再测量")
run = ROOT / "runs" / name
data = ROOT / "data" / name
tsdb = Path("/dev/shm") / f"lab2-prom-{os.getuid()}-{name}"
if any(p.exists() for p in (run, data, tsdb)):
    parser.error("runs/、data/ 或 TSDB 目录已存在，不覆盖")
for hostport in (SVC, PROM, NODE):
    with socket.socket() as sock:
        # 和 Go、Prometheus 一样允许重用 TIME_WAIT 的端口；真有进程在监听时仍会报错
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", int(hostport.split(":")[1])))
for tool in ("bin/enrolld", "bin/loadgen", "bin/promsteps", "tools/prometheus", "tools/node_exporter"):
    if not os.access(tool, os.X_OK):
        parser.error(f"缺少 {tool}：先 make build、scripts/get-tools.sh")
data.mkdir(parents=True)

config = evidence / f"{name}-prometheus.yml"
config.write_text((ROOT / "deploy/prometheus.yml").read_text()
                  .replace("127.0.0.1:8080", SVC).replace("127.0.0.1:9100", NODE)
                  .replace("  - rules.yml", "  - ../../deploy/rules.yml"))
enrolld = ["taskset", "-c", "2-3", "bin/enrolld", "-addr", SVC, "-data", str(data.relative_to(ROOT))]
env_enrolld = dict(os.environ)
if args.experiment == "o3":
    enrolld += ["-sync", "group"]
    load = ["scripts/run.sh", name, "-url", READ_URL, "-step", "60s",
            "-rates", ",".join(["200"] * 3 + ["420"] * 4 + ["200"] * 7)]
    slo = "0.05"
else:
    env_enrolld["GOGC"] = str(args.gogc)
    load = ["scripts/run.sh", name, "-url", f"http://{SVC}/api/report?mb=4", "-rates", "100,100,100"]
    slo = "0.05"
commands = [
    ("node", ["taskset", "-c", "0-1", "tools/node_exporter", f"--web.listen-address={NODE}"], None),
    ("prometheus", ["taskset", "-c", "0-1", "tools/prometheus", f"--config.file={config.relative_to(ROOT)}",
                    f"--storage.tsdb.path={tsdb}", f"--web.listen-address={PROM}"], None),
    ("enrolld", enrolld, env_enrolld),
]
env_load = dict(os.environ, GEN_CPUS="0-1", SVC=f"http://{SVC}", PROM=f"http://{PROM}", SLO=slo,
                DATA=str(data.relative_to(ROOT)))
manifest = {"name": name, "prepared_at": datetime.now().astimezone().isoformat(),
            "commands": [c for _, c, _ in commands], "gogc": args.gogc, "load_command": load,
            "prediction": str(prediction.relative_to(ROOT)),
            "prediction_sha256": hashlib.sha256(prediction.read_bytes()).hexdigest(),
            "prediction_mtime": datetime.fromtimestamp(prediction.stat().st_mtime).astimezone().isoformat(),
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}


def get(path, **params):
    url = f"http://{path}" + (("?" + urlencode(params)) if params else "")
    with urlopen(url, timeout=10) as response:
        return response.read()


def save_manifest():
    (evidence / f"{name}-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def interrupted(signum, frame):
    raise KeyboardInterrupt(f"signal {signum}")


signal.signal(signal.SIGTERM, interrupted)
save_manifest()
processes, logs = [], []
stop_polling = threading.Event()


def poll_alerts():
    with open(evidence / f"{name}-alerts.jsonl", "w") as out:
        while not stop_polling.is_set():
            try:
                body = json.loads(get(f"{PROM}/api/v1/alerts"))
                out.write(json.dumps({"t": datetime.now().astimezone().isoformat(), "alerts": body["data"]["alerts"]},
                                     ensure_ascii=False) + "\n")
                out.flush()
            except (OSError, ValueError) as err:
                out.write(json.dumps({"t": datetime.now().astimezone().isoformat(), "error": str(err)}) + "\n")
            stop_polling.wait(5)


try:
    for label, command, env in commands:
        log = open(evidence / f"{name}-{label}.log", "w")
        logs.append(log)
        processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True))
    deadline = time.monotonic() + 45
    while True:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("有服务退出了，见启动日志")
        try:
            active = json.loads(get(f"{PROM}/api/v1/targets"))["data"]["activeTargets"]
            if len(active) == 2 and all(t["health"] == "up" for t in active):
                break
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("抓取目标没有全部 up")
        time.sleep(1)
    time.sleep(10)
    (evidence / f"{name}-targets-before.json").write_bytes(get(f"{PROM}/api/v1/targets"))
    (evidence / f"{name}-config.json").write_bytes(get(f"{SVC}/config"))
    (evidence / f"{name}-rules-before.json").write_bytes(get(f"{PROM}/api/v1/rules"))
    poller = None
    if args.experiment == "o3":
        poller = threading.Thread(target=poll_alerts, daemon=True)
        poller.start()
        enroll_log = open(evidence / f"{name}-enroll-loadgen.log", "w")
        logs.append(enroll_log)
        processes.append(subprocess.Popen(
            ["taskset", "-c", "0-1", "bin/loadgen", "-url", f"http://{SVC}/api/enroll", "-body", ENROLL_BODY,
             "-rates", "20", "-step", "870s", "-slo", "20ms", "-out", str(evidence / f"{name}-enroll-steps.csv")],
            stdout=enroll_log, stderr=subprocess.STDOUT, start_new_session=True))
    start = time.time()
    manifest["measurement_started_at"] = datetime.now().astimezone().isoformat()
    save_manifest()
    with open(evidence / f"{name}-console.log", "w") as output:
        experiment = subprocess.Popen(load, env=env_load, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(experiment)
        if experiment.wait() != 0:
            raise RuntimeError("run.sh 失败，见 console.log")
    manifest["measurement_finished_at"] = datetime.now().astimezone().isoformat()
    for csv in ("steps.csv", "red.csv", "use.csv"):
        if not (run / csv).is_file() or (run / csv).stat().st_size == 0:
            raise RuntimeError(f"缺少 {csv}")
    if args.experiment == "o3":
        processes[-2].wait(timeout=120)  # 后台的写请求 loadgen
        end = time.time()
        stop_polling.set()
        poller.join()
        (evidence / f"{name}-alerts-final.json").write_bytes(get(f"{PROM}/api/v1/alerts"))
        (evidence / f"{name}-rules-after.json").write_bytes(get(f"{PROM}/api/v1/rules"))
        ranges = {}
        for expr in SLO_SERIES:
            ranges[expr] = json.loads(get(f"{PROM}/api/v1/query_range", query=expr, start=start - 60, end=end, step=5))
        (evidence / f"{name}-slo-range.json").write_text(json.dumps(ranges, ensure_ascii=False, indent=1) + "\n")
        panels = []
        for row, title, expr in DASHBOARD:
            resp = json.loads(get(f"{PROM}/api/v1/query_range", query=expr, start=start, end=end, step=15))
            panels.append({"row": row, "title": title, "expr": expr, "response": resp})
        (evidence / f"{name}-dashboard-range.json").write_text(json.dumps(panels, ensure_ascii=False, indent=1) + "\n")
    else:
        with open(evidence / f"{name}-gc.csv", "w") as out:
            subprocess.run(["bin/promsteps", "-steps", str(run / "steps.csv"), "-prom", f"http://{PROM}",
                            "-var", "route=/api/report", "-queries", str(evidence / "queries-gc.txt")],
                           stdout=out, check=True)
    (evidence / f"{name}-targets-after.json").write_bytes(get(f"{PROM}/api/v1/targets"))
finally:
    stop_polling.set()
    # 只停本次启动的进程，不碰其他成员的服务
    for process in reversed(processes):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    for log in logs:
        log.close()
    manifest["cleanup_at"] = datetime.now().astimezone().isoformat()
    save_manifest()
print(f"完成 {name}", flush=True)
