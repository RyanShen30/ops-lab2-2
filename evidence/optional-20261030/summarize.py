#!/usr/bin/env python3
"""Summarize optional experiments O1/O3 from runs/ and this evidence directory (read-only)."""
import csv
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = Path(__file__).resolve().parent
RUNS = ROOT / "runs"


def steps(run):
    with open(RUNS / run / "steps.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scalar(path, metric):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(metric + " "):
            return float(line.split()[1])
    return float("nan")


def ts(s):
    return datetime.fromisoformat(s).timestamp()


def o3():
    if not (EV / "o3-burn-alerts.jsonl").is_file():
        return
    print("== O3：燃烧率告警")
    st = [r for r in steps("o3-burn") if r["step"] != "all"]
    for r in st:
        print(f"  阶段 {r['step']:>2} 目标 {r['target_rps']:>3}：ok_rps {r['ok_rps']}，error_rate {r['error_rate']}，"
              f"p99 {r['p99_ms']} ms，slo_good {r['slo_good']}")
    t0 = float(st[0]["start_unix"])
    ov_start, ov_end = float(st[3]["start_unix"]), float(st[6]["end_unix"])
    print(f"  过载区间：开始后 {ov_start - t0:.0f}～{ov_end - t0:.0f} s")
    seen = {}
    polls = [json.loads(l) for l in (EV / "o3-burn-alerts.jsonl").read_text().splitlines() if l.strip()]
    for p in polls:
        t = ts(p["t"])
        names = set()
        for a in p.get("alerts", []):
            n = a["labels"]["alertname"]
            names.add(n)
            d = seen.setdefault(n, {})
            d.setdefault(a["state"], t)
            d["activeAt"] = a.get("activeAt")
            d["last"] = t
        for n, d in seen.items():
            if n not in names and "last" in d and "gone" not in d and t > d["last"]:
                d["gone"] = t
    for n, d in seen.items():
        msg = [f"  {n}："]
        if "pending" in d:
            msg.append(f"pending 首次见于过载开始后 {d['pending'] - ov_start:+.0f} s")
        if "firing" in d:
            msg.append(f"firing 首次见于过载开始后 {d['firing'] - ov_start:+.0f} s")
        if d.get("activeAt"):
            msg.append(f"activeAt {d['activeAt']}（过载开始后 {ts(d['activeAt'].replace('Z', '+00:00')) - ov_start:+.1f} s）")
        msg.append(f"消失于过载结束后 {d['gone'] - ov_end:+.0f} s" if "gone" in d else "观测结束时仍在")
        print("，".join(msg))
    print(f"  共抓取 /api/v1/alerts {len(polls)} 次，出错 {sum('error' in p for p in polls)} 次")
    rng = json.loads((EV / "o3-burn-slo-range.json").read_text())
    for expr, resp in rng.items():
        if not expr.startswith("enrolld:"):
            continue
        vals = [(float(t), float(v)) for res in resp["data"]["result"] for t, v in res["values"]]
        if not vals:
            continue
        mx = max(vals, key=lambda x: x[1])
        before = [v for t, v in vals if t < ov_start]
        end = vals[-1]
        print(f"  {expr}：过载前最大 {max(before) if before else float('nan'):.4f}，峰值 {mx[1]:.4f}"
              f"（过载开始后 {mx[0] - ov_start:+.0f} s），观测结束 {end[1]:.4f}")
    print("  看板（正常＝第 2 阶段末、过载＝第 6 阶段末、恢复＝第 13 阶段末的最近样本）：")
    marks = {"正常": float(st[1]["end_unix"]), "过载": float(st[5]["end_unix"]), "恢复": float(st[12]["end_unix"])}
    for panel in json.loads((EV / "o3-burn-dashboard-range.json").read_text()):
        res = panel["response"]["data"]["result"]
        parts = []
        for series in res:
            label = series["metric"].get("route") or series["metric"].get("__name__", "")
            vals = [(float(t), v) for t, v in series["values"]]
            got = []
            for k, m in marks.items():
                t, v = min(vals, key=lambda x: abs(x[0] - m))
                got.append(f"{k} {float(v):.4g}" if abs(t - m) <= 20 else f"{k} -")
            parts.append(f"[{label}] " + "，".join(got))
        print(f"    {panel['row']}｜{panel['title']}：" + ("；".join(parts) if parts else "无数据"))


def o1():
    runs = [r for r in ("o1-gogc100", "o1-gogc400") if (RUNS / r / "steps.csv").is_file()]
    if not runs:
        return
    print("\n== O1：GOGC")
    for run in runs:
        s, e = RUNS / run / "metrics-start.txt", RUNS / run / "metrics-end.txt"
        d = {m: scalar(e, m) - scalar(s, m)
             for m in ("go_gc_cycles_total", "go_gc_cpu_seconds_total", "process_cpu_seconds_total")}
        st = steps(run)
        ok = sum(int(r["ok"]) for r in st if r["step"] != "all")
        rss = []
        usr, sys_, flt = [], [], []
        for line in (RUNS / run / "pidstat.log").read_text().splitlines():
            f = line.split()
            if len(f) >= 17 and f[-1] == "enrolld" and re.fullmatch(r"\d+", f[12]):
                rss.append(int(f[12]) / 1024)
                if float(f[7]) > 0:  # 有负载的秒
                    usr.append(float(f[3]))
                    sys_.append(float(f[4]))
                    flt.append(float(f[9]))
        allr = next(r for r in st if r["step"] == "all")
        print(f"  {run}：GC {d['go_gc_cycles_total']:.0f} 次，GC CPU {d['go_gc_cpu_seconds_total']:.3f} s，"
              f"进程 CPU {d['process_cpu_seconds_total']:.3f} s（GC 占 {d['go_gc_cpu_seconds_total'] / d['process_cpu_seconds_total'] * 100:.1f}%），"
              f"成功请求 {ok}，每请求 GC {d['go_gc_cycles_total'] / ok:.3f} 次；"
              f"RSS 结束 {scalar(e, 'process_resident_memory_bytes') / 1048576:.1f} MiB，pidstat 最大 {max(rss):.1f} MiB；"
              f"客户端 all：mean {allr['mean_ms']} ms，p99 {allr['p99_ms']} ms")
        print(f"    pidstat 有负载的 {len(usr)} 秒平均：%usr {sum(usr) / len(usr):.2f}，%system {sum(sys_) / len(sys_):.2f}，"
              f"minflt/s {sum(flt) / len(flt):.0f}（每请求约 {sum(flt) / len(flt) / 100:.0f} 次缺页）")
        for r in st:
            if r["step"] != "all":
                print(f"    阶段 {r['step']}：ok_rps {r['ok_rps']}，mean {r['mean_ms']}，p99 {r['p99_ms']}，max {r['max_ms']} ms")
        gc = EV / f"{run}-gc.csv"
        if gc.is_file():
            print("    " + gc.read_text().strip().replace("\n", "\n    "))


def sar_rows(path, date):
    """Yield (epoch, fields) for timestamped data lines of a sysstat log (S_TIME_FORMAT=ISO, LC_ALL=C)."""
    for line in path.read_text().splitlines():
        f = line.split()
        if len(f) > 2 and re.fullmatch(r"\d\d:\d\d:\d\d", f[0]):
            yield datetime.fromisoformat(f"{date}T{f[0]}+08:00").timestamp(), f


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def o2():
    run = RUNS / "o2-net"
    if not (run / "steps.csv").is_file():
        return
    print("\n== O2：网络（A 服务端，B 压测端）")
    date = re.search(r"\d{4}-\d\d-\d\d", (run / "meta.txt").read_text())[0]
    dev = {"a": list(sar_rows(run / "a-sar-dev.log", date)), "b": list(sar_rows(run / "b-sar-dev.log", date))}
    mp = {"a": list(sar_rows(run / "a-mpstat.log", date)), "b": list(sar_rows(run / "b-mpstat.log", date))}
    tcp, oseg, kind = [], [], None
    for t, f in sar_rows(run / "a-sar-tcp.log", date):
        if "active/s" in f or "atmptf/s" in f:
            kind = "tcp" if "active/s" in f else "etcp"
        elif kind == "etcp":
            tcp.append((t, float(f[3])))  # retrans/s
        elif kind == "tcp":
            oseg.append((t, float(f[4])))  # oseg/s
    ss = []
    for line in (run / "a-ss.log").read_text().splitlines():
        m = re.match(r"== (\S+) 连接 (\d+)，Send-Q 合计 (\d+) B，rtt 平均 ([\d.]+) ms，最大 ([\d.]+) ms", line)
        if m:
            ss.append((datetime.fromisoformat(m[1]).timestamp(), int(m[2]), int(m[3]), float(m[4]), float(m[5])))
    print("  阶段 目标 ok_rps err p50 p99（ms） lag_p99 | A eth0 tx（kB/s，Gbit/s，每请求 kB） | B eth0 rx（kB/s） | "
          "A CPU2-3 忙 / A 全机 %soft | B 全机忙 | A retrans/s | ss 连接、rtt 平均（ms）")
    for r in steps("o2-net"):
        if r["step"] == "all":
            continue
        lo, hi = float(r["start_unix"]) + 5, float(r["end_unix"])
        inwin = lambda t: lo <= t <= hi
        tx = [float(f[5]) for t, f in dev["a"] if inwin(t) and f[1] == "eth0"]
        rx = [float(f[4]) for t, f in dev["b"] if inwin(t) and f[1] == "eth0"]
        a23 = [100 - float(f[-1]) - float(f[5]) for t, f in mp["a"] if inwin(t) and f[1] in ("2", "3")]
        asoft = [float(f[7]) for t, f in mp["a"] if inwin(t) and f[1] == "all"]
        ball = [100 - float(f[-1]) - float(f[5]) for t, f in mp["b"] if inwin(t) and f[1] == "all"]
        re_ = [v for t, v in tcp if inwin(t)]
        os_ = [v for t, v in oseg if inwin(t)]
        s = [x for x in ss if inwin(x[0])]
        txm = mean(tx)
        ok = float(r["ok_rps"])
        print(f"  {r['step']:>2} {r['target_rps']:>5} {r['ok_rps']:>7} {float(r['error_rate']):.4f} {r['p50_ms']} {r['p99_ms']} {r['lag_p99_ms']} | "
              f"{txm:9.0f}（最大 {max(tx) if tx else float('nan'):.0f}），{txm * 1024 * 8 / 1e9:.3f}，{txm / ok if ok else float('nan'):.1f} | "
              f"{mean(rx):9.0f}（{mean(rx) * 1024 * 8 / 1e9:.3f} Gbit/s，每请求 {mean(rx) / ok if ok else float('nan'):.1f} kB） | {mean(a23):5.1f}% / {mean(asoft):4.1f}% | {mean(ball):5.1f}% | "
              f"{mean(re_):7.1f}（占 oseg {mean(re_) / mean(os_) * 100 if os_ else float('nan'):.2f}%） | "
              f"{mean([x[1] for x in s]):.0f}、{mean([x[3] for x in s]):.3f} | warn {r['warn']}")
    n0 = {l.split()[0]: int(l.split()[1]) for l in (run / "a-nstat-start.txt").read_text().splitlines()[1:] if len(l.split()) >= 2}
    n1 = {l.split()[0]: int(l.split()[1]) for l in (run / "a-nstat-end.txt").read_text().splitlines()[1:] if len(l.split()) >= 2}
    for k in ("TcpOutSegs", "TcpRetransSegs", "TcpExtTCPLostRetransmit", "TcpExtTCPTimeouts"):
        if k in n1:
            print(f"  A nstat {k}：增量 {n1[k] - n0.get(k, 0)}")
    if "TcpOutSegs" in n1:
        print(f"  A 重传占发送段：{(n1['TcpRetransSegs'] - n0['TcpRetransSegs']) / (n1['TcpOutSegs'] - n0['TcpOutSegs']) * 100:.3f}%")


o3()
o1()
o2()
