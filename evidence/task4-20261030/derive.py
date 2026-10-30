#!/usr/bin/env python3
"""Recompute every derived number used in LAB2.md section 6 from runs/ (read-only)."""
import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"


def load(run):
    """Join steps.csv, red.csv, use.csv by step; first file wins on duplicate columns."""
    rows = {}
    order = []
    for name in ("steps", "red", "use"):
        with open(RUNS / run / f"{name}.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = r["step"]
                if name == "steps":
                    order.append(key)
                    rows[key] = {}
                for k, v in r.items():
                    rows[key].setdefault(k, v)
    return [rows[k] for k in order]


def num(r, col):
    v = r[col]
    try:
        return float(v)
    except ValueError:
        return math.nan


def step(rows, n):
    return next(r for r in rows if r["step"] == str(n))


def hist(run, route, code):
    """Cumulative buckets of http_request_duration_seconds over the run (metrics-end minus metrics-start)."""
    pat = re.compile(r'^http_request_duration_seconds_bucket\{route="%s",code="%s",le="([^"]+)"\} (\S+)$'
                     % (re.escape(route), code))
    snap = {}
    for name in ("metrics-start.txt", "metrics-end.txt"):
        snap[name] = {}
        for line in (RUNS / run / name).read_text(encoding="utf-8").splitlines():
            m = pat.match(line)
            if m:
                snap[name][math.inf if m[1] == "+Inf" else float(m[1])] = float(m[2])
    return [(le, c - snap["metrics-start.txt"].get(le, 0)) for le, c in snap["metrics-end.txt"].items()]


def counts(run, route):
    pat = re.compile(r'^http_request_duration_seconds_count\{route="%s",code="(\d+)"\} (\S+)$' % re.escape(route))
    res = {}
    for name in ("metrics-start.txt", "metrics-end.txt"):
        for line in (RUNS / run / name).read_text(encoding="utf-8").splitlines():
            m = pat.match(line)
            if m:
                res[(name, m[1])] = float(m[2])
    return {code: res.get(("metrics-end.txt", code), 0) - res.get(("metrics-start.txt", code), 0)
            for (_, code) in res}


def quantile(q, buckets):
    """Same linear interpolation as PromQL histogram_quantile."""
    total = buckets[-1][1]
    rank = q * total
    lo_le, lo_c = 0.0, 0.0
    for le, c in buckets:
        if c >= rank:
            if math.isinf(le):
                return lo_le, lo_le, le
            return lo_le + (le - lo_le) * (rank - lo_c) / (c - lo_c), lo_le, le
        lo_le, lo_c = le, c
    raise ValueError("empty histogram")


def p(fmt, *a):
    print(fmt % a)


t1, r1, r2 = load("t1-light"), load("r1-pool4"), load("r2-pool79")
w1, w2, w3 = load("w1-each"), load("w2-group"), load("w3-interval")
ROUTE_R = "/api/courses/{id}"

print("== 问题 1：资源账与每请求 CPU")
pool_cap = 4 / (num(step(t1, 3), "db_query_mean_ms") / 1000)
p("连接池推算上限 4/%.7f s = %.1f /s；R1 最大 ok_rps = %.1f，相差 %+.2f%%",
  num(step(t1, 3), "db_query_mean_ms") / 1000, pool_cap, num(step(r1, 7), "ok_rps"),
  (num(step(r1, 7), "ok_rps") / pool_cap - 1) * 100)
r1_max_ok = max(num(r, "ok_rps") for r in r1 if r["step"] != "all")
r2_max_ok = max(num(r, "ok_rps") for r in r2 if r["step"] != "all")
for label, cpu_ms in (("t1 第 3 阶段", num(step(t1, 3), "cpu_ms_per_req")),
                      ("R1 第 6 阶段", num(step(r1, 6), "cpu_ms_per_req")),
                      ("R2 第 7 阶段", num(step(r2, 7), "cpu_ms_per_req"))):
    cap = 2 / (cpu_ms / 1000)
    p("CPU 上限（%s，%.6f ms）= %.1f /s；R2 最大 ok_rps %.1f 比它 %+.1f%%",
      label, cpu_ms, cap, r2_max_ok, (r2_max_ok / cap - 1) * 100)
p("R1 最大 ok_rps %.1f；R2 最大 ok_rps %.1f", r1_max_ok, r2_max_ok)
idle = num(step(t1, 1), "cpu_cores")
p("t1 空载 cpu_cores = %.6f；摊到 100 请求/秒时每请求 %.4f ms", idle, idle / num(step(t1, 3), "server_rps") * 1000)
spin = num(step(r1, 5), "cpu_ms_per_req") * 0.8282
p("R1 第 5 阶段 spin 估计 %.4f ms，R2 第 7 阶段每请求总 CPU %.6f ms", spin, num(step(r2, 7), "cpu_ms_per_req"))
p("cpu_ms_per_req：t1 %s；R1 %s；R2 %s",
  "/".join(t1[i]["cpu_ms_per_req"] for i in (1, 2)),
  "/".join(r["cpu_ms_per_req"] for r in r1[:-1]),
  "/".join(r["cpu_ms_per_req"] for r in r2[:-1]))
p("R2 第 7 阶段相对 t1 第 2 阶段：%+.1f%%；t1 推算上限占实测上限 %.1f%%",
  (num(step(r2, 7), "cpu_ms_per_req") / num(step(t1, 2), "cpu_ms_per_req") - 1) * 100,
  2 / (num(step(t1, 3), "cpu_ms_per_req") / 1000) / r2_max_ok * 100)
dbq = lambda rows, sl: [num(r, "db_query_mean_ms") for r in rows[sl]]
p("db_query_mean_ms：R1 %.4f～%.4f；R2 第 1～7 阶段 %.4f～%.4f；R2 第 8 阶段 %.4f",
  min(dbq(r1, slice(0, 9))), max(dbq(r1, slice(0, 9))), min(dbq(r2, slice(0, 7))), max(dbq(r2, slice(0, 7))),
  num(step(r2, 8), "db_query_mean_ms"))
print("R1 连接池利用率 ρ = server_rps × db_query_mean_ms / 4 与排队：")
for r in r1[:-1]:
    rho = num(r, "server_rps") * num(r, "db_query_mean_ms") / 1000 / 4
    p("  第 %s 阶段 目标 %s（%.2f× 上限）：ρ=%.3f pool_in_use_avg/4=%.2f 排队数 inflight-in_use=%.2f pool_wait_p99=%s p99=%s",
      r["step"], r["target_rps"], float(r["target_rps"]) / pool_cap, rho, num(r, "pool_in_use_avg") / 4,
      num(r, "inflight_avg") - num(r, "pool_in_use_avg"), r["pool_wait_p99_ms"], r["p99_ms"])

print("\n== 问题 2：Little's Law（R1）")
for r in r1[:-1]:
    lam, w_mean, w99 = num(r, "server_rps"), num(r, "server_mean_ms") / 1000, num(r, "server_p99_ms") / 1000
    l_obs = num(r, "inflight_avg")
    p("  第 %s 阶段：%.3f × %.4f s = %.3f，inflight_avg %.2f，偏差 %+.1f%%；若用 p99：%.2f（%.1f 倍）",
      r["step"], lam, w_mean, lam * w_mean, l_obs, (l_obs / (lam * w_mean) - 1) * 100, lam * w99, lam * w99 / l_obs)
s1 = step(r1, 1)
p("第 1 阶段 inflight 约 25 个样本的抽样标准误 ≈ sqrt(%.3f/25) = %.2f",
  num(s1, "server_rps") * num(s1, "server_mean_ms") / 1000,
  math.sqrt(num(s1, "server_rps") * num(s1, "server_mean_ms") / 1000 / 25))

print("\n== 问题 3：写路径")
fs = 1000 / 1.235
p("W1 最大 ok_rps %.1f 与 1000/1.235=%.2f 相差 %+.2f%%", num(step(w1, 6), "ok_rps"), fs,
  (num(step(w1, 6), "ok_rps") / fs - 1) * 100)
for label, r in (("W1 第 6 阶段", step(w1, 6)), ("W2 第 7 阶段", step(w2, 7))):
    f = num(r, "fsync_per_s")
    wr, fl = num(r, "disk_w_per_s") / f, num(r, "disk_f_per_s") / f
    p("%s：每次 fsync %.2f 次写、%.2f 次 flush、%.2f kB；%.2f×%.4f + %.2f×%.4f = %.3f ms，应用 fsync_mean %.4f ms",
      label, wr, fl, num(r, "disk_wkb_per_s") / f, wr, num(r, "disk_w_await_ms"), fl, num(r, "disk_f_await_ms"),
      wr * num(r, "disk_w_await_ms") + fl * num(r, "disk_f_await_ms"), num(r, "fsync_mean_ms"))
p("disk_util 相近：W1 第 6 阶段 %.4f → ok %.1f；W2 第 7 阶段 %.4f → ok %.1f（%.2f 倍）",
  num(step(w1, 6), "disk_util"), num(step(w1, 6), "ok_rps"), num(step(w2, 7), "disk_util"),
  num(step(w2, 7), "ok_rps"), num(step(w2, 7), "ok_rps") / num(step(w1, 6), "ok_rps"))
for tgt in ("324", "648", "810"):
    a = next(r for r in w1 if r["target_rps"] == tgt)
    b = next(r for r in w2 if r["target_rps"] == tgt)
    p("  到达率 %s：W1 mean/p99 %s/%s ms，W2 %s/%s ms（p99 %+.0f%%），W2 batch %s",
      tgt, a["mean_ms"], a["p99_ms"], b["mean_ms"], b["p99_ms"],
      (num(b, "p99_ms") / num(a, "p99_ms") - 1) * 100, b["batch_mean"])
b3 = step(w2, 3)
p("5.3 预测对照（810）：batch 1.5 vs %s（%+.1f%%），mean 3 vs %s，p99 10 vs %s",
  b3["batch_mean"], (num(b3, "batch_mean") / 1.5 - 1) * 100, b3["mean_ms"], b3["p99_ms"])
p("W2 第 7 阶段 server_rps/fsync_per_s = %.3f，batch_mean %s",
  num(step(w2, 7), "server_rps") / num(step(w2, 7), "fsync_per_s"), step(w2, 7)["batch_mean"])
g7, i3, a2, i1, b1 = step(w2, 7), step(w3, 3), step(w1, 2), step(w3, 1), step(w2, 1)
p("W3 vs W2（3240）：mean %.2f/%.2f = 1/%.2f，p99 %.2f/%.2f = 1/%.2f",
  num(i3, "mean_ms"), num(g7, "mean_ms"), num(g7, "mean_ms") / num(i3, "mean_ms"),
  num(i3, "p99_ms"), num(g7, "p99_ms"), num(g7, "p99_ms") / num(i3, "p99_ms"))
p("W3 vs W1 vs W2（324）：mean %.2f/%.2f/%.2f，p99 %.2f/%.2f/%.2f",
  num(i1, "mean_ms"), num(a2, "mean_ms"), num(b1, "mean_ms"), num(i1, "p99_ms"), num(a2, "p99_ms"), num(b1, "p99_ms"))

print("\n== 问题 4：测量位置与方法")
for label, r in (("t1 第 3 阶段", step(t1, 3)), ("R1 第 5 阶段", step(r1, 5)), ("R2 第 7 阶段", step(r2, 7)),
                 ("W1 第 4 阶段", step(w1, 4)), ("W3 第 3 阶段", step(w3, 3))):
    p("  %s：客户端 mean %.2f / 服务端 %.4f（差 %+.2f）；客户端 p99 %.2f / 服务端 %.4f（差 %+.2f）",
      label, num(r, "mean_ms"), num(r, "server_mean_ms"), num(r, "mean_ms") - num(r, "server_mean_ms"),
      num(r, "p99_ms"), num(r, "server_p99_ms"), num(r, "p99_ms") - num(r, "server_p99_ms"))
for run, rows in (("t1-light", t1), ("r2-pool79", r2)):
    b = hist(run, ROUTE_R, "200")
    p("%s 全程 code=200：≤10 ms %d 个，≤20 ms %d 个，共 %d 个", run, dict(b)[0.01], dict(b)[0.02], b[-1][1])
for label, r in (("R1 第 6 阶段", step(r1, 6)), ("R1 第 7 阶段", step(r1, 7)), ("R2 第 8 阶段", step(r2, 8)),
                 ("W1 第 6 阶段", step(w1, 6))):
    p("  %s：客户端 slo_good %s，服务端 server_slo_good %s", label, r["slo_good"], r["server_slo_good"])
c = counts("r2-pool79", ROUTE_R)
a = step(r2, "all")
p("R2 服务端全程：200=%d，503=%d，499=%d；客户端：ok=%s，503=%s，超时=%s",
  c.get("200", 0), c.get("503", 0), c.get("499", 0), a["ok"], a["codes"], a["timeout"])
p("  服务端记为 200 而客户端未计入成功：%d", c.get("200", 0) - int(a["ok"]))
p("  客户端发出 %s 个，服务端处理函数记录 %d 个，从未被处理函数记录 %d 个",
  a["sent"], sum(c.values()), int(a["sent"]) - sum(c.values()))
c1 = counts("r1-pool4", ROUTE_R)
a1 = step(r1, "all")
p("R1 服务端全程：200=%d，503=%d；客户端：ok=%s，%s，发出 %s", c1["200"], c1["503"], a1["ok"], a1["codes"], a1["sent"])
p99s = [num(r, "p99_ms") for r in r1[:-1]]
oks = [num(r, "ok") for r in r1[:-1]]
p("R1 各阶段 p99 简单平均 %.2f ms，按成功数加权平均 %.2f ms，all 行 %s ms",
  sum(p99s) / len(p99s), sum(x * w for x, w in zip(p99s, oks)) / sum(oks), step(r1, "all")["p99_ms"])
p("R1 all 行 p99 的秩：ceil(0.99×%d) = %d，即最慢 %d 个成功请求",
  sum(oks), math.ceil(0.99 * sum(oks)), int(sum(oks)) - math.ceil(0.99 * sum(oks)) + 1)
p("R1 第 8、9 阶段成功请求 %d 个，p50 分别为 %s、%s ms",
  oks[7] + oks[8], step(r1, 8)["p50_ms"], step(r1, 9)["p50_ms"])
c1 = counts("r1-pool4", ROUTE_R)
b = hist("r1-pool4", ROUTE_R, "200")
q, lo, hi = quantile(0.99, b)
p("R1 metrics-end 合并直方图（code=200 共 %d 个，503 共 %d 个）：p99 落在 (%g, %g] s 桶，线性插值 %.1f ms",
  c1["200"], c1["503"], lo, hi, q * 1000)
for label, r in (("R1 第 6 阶段", step(r1, 6)), ("R1 第 7 阶段", step(r1, 7))):
    for src, col in (("客户端", "slo_good"), ("服务端", "server_slo_good")):
        bad = 1 - num(r, col)
        burn = bad / 0.01
        p("  %s %s：坏事件比例 %.4f%%，燃烧率 %.2f，30 天预算耗尽需 %.1f 天（%.1f 小时）",
          label, src, bad * 100, burn, 30 / burn, 30 * 24 / burn)

sys.exit(0)
