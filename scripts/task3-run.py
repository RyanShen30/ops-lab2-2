#!/usr/bin/env python3
"""Run one Task 3 experiment in isolated ports/directories on the lab host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from datetime import datetime
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("each", "group", "interval"))
parser.add_argument("base", type=float, help="predicted W1 TPS, or observed W1 ceiling for W2/W3")
parser.add_argument("--evidence", default="evidence/task3-20261027")
parser.add_argument("--suffix", default="", help="use a new name for a repeat; never overwrite runs")
args = parser.parse_args()
if args.base <= 0:
    parser.error("base must be positive")
mode = args.mode
name = {"each": "w1-each", "group": "w2-group", "interval": "w3-interval"}[mode] + args.suffix
factors = {"each": [0.2, 0.4, 0.6, 0.8, 0.9, 1, 1.1, 1.2],
           "group": [0.4, 0.8, 1, 1.5, 2, 3, 4], "interval": [0.4, 1.5, 4]}[mode]
evidence = ROOT / args.evidence
prediction = evidence / ("prediction-w1.md" if mode == "each" else "prediction-w2.md")
if not prediction.is_file():
    parser.error(f"write {prediction} before measuring")
run = ROOT / "runs" / name
data = ROOT / "data" / ("task3-" + name)
tsdb = Path("/dev/shm") / (f"lab2-prom-{os.getuid()}-{name}")
if any(p.exists() for p in (run, data, tsdb)):
    parser.error("run/data/TSDB already exists; choose a new --suffix")
for port in (18080, 19090, 19100):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
for tool in ("bin/enrolld", "bin/loadgen", "bin/promsteps", "tools/prometheus", "tools/node_exporter"):
    if not os.access(tool, os.X_OK):
        parser.error(f"missing executable {tool}; run make build test and scripts/get-tools.sh")
data.mkdir(parents=True)
if subprocess.check_output(["findmnt", "-no", "FSTYPE", "-T", str(data)], text=True).strip() == "tmpfs":
    parser.error("data must reside on a real block device")
evidence.mkdir(parents=True, exist_ok=True)
rates = subprocess.check_output(["scripts/rates.sh", str(args.base), *map(str, factors)], text=True).strip()
config = evidence / "prometheus.yml"
config.write_text((ROOT / "deploy/prometheus.yml").read_text().replace("127.0.0.1:8080", "127.0.0.1:18080").replace("127.0.0.1:9100", "127.0.0.1:19100"))
commands = [
    ["taskset", "-c", "0-1", "tools/node_exporter", "--web.listen-address=127.0.0.1:19100"],
    ["taskset", "-c", "0-1", "tools/prometheus", f"--config.file={config.relative_to(ROOT)}", f"--storage.tsdb.path={tsdb}", "--web.listen-address=127.0.0.1:19090"],
    ["taskset", "-c", "2-3", "bin/enrolld", "-addr", "127.0.0.1:18080", "-sync", mode, "-data", str(data.relative_to(ROOT))],
]
load = ["scripts/run.sh", name, "-url", "http://127.0.0.1:18080/api/enroll", "-body", '{"student":"s{{seq}}","course":"c1"}', "-rates", rates]
environment = dict(os.environ, GEN_CPUS="0-1", SVC="http://127.0.0.1:18080", PROM="http://127.0.0.1:19090", SLO="0.02", DATA=str(data.relative_to(ROOT)))
manifest = {"prepared_at": datetime.now().astimezone().isoformat(), "mode": mode, "base": args.base,
            "rates": rates, "commands": commands, "load_command": load,
            "prediction": str(prediction.relative_to(ROOT)), "prediction_sha256": hashlib.sha256(prediction.read_bytes()).hexdigest(),
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}
(evidence / f"{name}-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
processes = []
logs = []


def get(url):
    with urlopen(url, timeout=5) as response:
        return response.read()


def interrupted(signum, frame):
    raise KeyboardInterrupt(f"signal {signum}")


signal.signal(signal.SIGTERM, interrupted)
try:
    for label, command in zip(("node", "prometheus", "enrolld"), commands):
        log = open(evidence / f"{name}-{label}.log", "w")
        logs.append(log)
        processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
    deadline = time.monotonic() + 45
    while True:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("service exited; inspect startup logs")
        try:
            targets = get("http://127.0.0.1:19090/api/v1/targets")
            active = json.loads(targets)["data"]["activeTargets"]
            if len(active) == 2 and all(t["health"] == "up" for t in active):
                break
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("scrape targets did not become healthy")
        time.sleep(1)
    time.sleep(10)
    (evidence / f"{name}-targets-before.json").write_bytes(get("http://127.0.0.1:19090/api/v1/targets"))
    (evidence / f"{name}-config.json").write_bytes(get("http://127.0.0.1:18080/config"))
    manifest["measurement_started_at"] = datetime.now().astimezone().isoformat()
    with open(evidence / f"{name}-console.log", "w") as output:
        experiment = subprocess.Popen(load, env=environment, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(experiment)
        if experiment.wait() != 0:
            raise RuntimeError("run.sh failed; inspect console log")
    (evidence / f"{name}-targets-after.json").write_bytes(get("http://127.0.0.1:19090/api/v1/targets"))
    for csv in ("steps.csv", "red.csv", "use.csv"):
        if not (run / csv).is_file() or (run / csv).stat().st_size == 0:
            raise RuntimeError(f"missing {csv}; keep evidence and requery before stopping Prometheus")
    manifest["measurement_finished_at"] = datetime.now().astimezone().isoformat()
finally:
    # Only terminate processes created by this invocation, never a teammate's service.
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
    (evidence / f"{name}-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(f"Completed {name}: {rates}", flush=True)
