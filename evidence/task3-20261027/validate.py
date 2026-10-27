import csv, hashlib, json, math, re, subprocess
from pathlib import Path
from datetime import datetime
root = Path.cwd()
e = root / "evidence/task3-20261027"
columns = "ok_rps error_rate p99_ms server_p99_ms cpu_cores fsync_per_s fsync_mean_ms batch_mean svc_cpu_busy cpu_iowait disk_w_per_s disk_w_await_ms disk_f_per_s disk_f_await_ms disk_aqu_sz disk_util".split()
results = {}
for name, n, mode in [("w1-each",8,"each"),("w2-group",7,"group"),("w3-interval",3,"interval")]:
    run = root / "runs" / name
    tables = {k:list(csv.DictReader((run / (k+".csv")).open())) for k in ("steps","red","use")}
    steps = [r for r in tables["steps"] if r["step"] != "all"]
    assert len(steps)==n, (name,"stage count")
    assert all(len(tables[k])==n for k in ("red","use")), (name,"metrics stage count")
    rows=[]
    for i,s in enumerate(steps):
        row=dict(s)
        for k in ("red","use"):
            assert tables[k][i]["step"]==s["step"]
            row.update(tables[k][i])
        for col in columns: assert math.isfinite(float(row[col])), (name,s["step"],col)
        assert int(s["end_unix"])-int(s["start_unix"])==30
        assert int(s["sent"])==sum(int(s[k]) for k in ("ok","http_err","timeout","net_err"))
        assert int(s["dropped"])==0
        assert not s["warn"], (name,s["step"],s["warn"])
        rows.append(row)
    config=json.loads((e/f"{name}-config.json").read_text())
    assert config["sync"]==mode and config["gomaxprocs"]==2
    assert config["addr"]=="127.0.0.1:18080"
    manifest=json.loads((e/f"{name}-manifest.json").read_text())
    prediction=root/manifest["prediction"]
    assert hashlib.sha256(prediction.read_bytes()).hexdigest()==manifest["prediction_sha256"]
    pred_time=re.search(r"记录时间：([^\n]+)",prediction.read_text())[1]
    assert datetime.fromisoformat(pred_time)<datetime.fromisoformat(manifest["measurement_started_at"])
    assert [int(s["target_rps"]) for s in steps]==list(map(int,manifest["rates"].split(",")))
    for position in ("before","after"):
        targets=json.loads((e/f"{name}-targets-{position}.json").read_text())["data"]["activeTargets"]
        assert len(targets)==2 and all(t["health"]=="up" for t in targets)
        assert {t["scrapeUrl"] for t in targets}=={"http://127.0.0.1:18080/metrics","http://127.0.0.1:19100/metrics"}
    table=subprocess.check_output(["scripts/table.sh",str(run),*columns],text=True)
    assert table.strip() in (root/"LAB2.md").read_text()
    assert table==(e/(name[:2]+"-table.md")).read_text()
    results[name]={"stages":n,"checks":"passed","max_ok_rps":max(float(s["ok_rps"]) for s in steps),"max_lag_p99_ms":max(float(s["lag_p99_ms"]) for s in steps),"max_generator_cpu_pct":max(float(s["gen_cpu_pct"]) for s in steps),"rows":rows}
base=subprocess.check_output(["git","show","HEAD:LAB2.md"],text=True)
current=(root/"LAB2.md").read_text()
assert base.split("## 1. 基本信息")[1].split("## 5. 任务 3")[0]==current.split("## 1. 基本信息")[1].split("## 5. 任务 3")[0]
assert base.split("## 6. 分析问题")[1]==current.split("## 6. 分析问题")[1]
section5=current.split("## 5. 任务 3")[1].split("## 6. 分析问题")[0]
assert "<填写>" not in section5
for number, filename, following in [("5.1","prediction-w1.md","5.2"),("5.3","prediction-w2.md","5.4")]:
    before=(e/filename).read_text().split("### "+number+" ",1)[1].strip()
    after=section5.split("### "+number+" ",1)[1].split("### "+following+" ",1)[0].strip()
    assert before==after, (filename,"prediction changed in report")
configs=[json.loads((e/f"{name}-config.json").read_text()) for name in results]
for key in ("addr","work","pool","db_ms","pool_timeout","sync_interval","gomaxprocs","go_version"):
    assert len({c[key] for c in configs})==1, (key,"inconsistent experiment config")
services=(e/"services-after.txt").read_text()
for pid in ("386041","386047","398247"): assert pid in services
for port in ("18080","19090","19100"): assert "127.0.0.1:"+port not in services
for doc in [root/"LAB2.md",e/"README.md"]:
    for link in re.findall(r"\]\(([^)]+)\)",doc.read_text()):
        if not link.startswith(("http:","https:","#")): assert (doc.parent/link.split("#")[0]).exists(), (doc,link)
subprocess.run(["git","diff","--check"],check=True)
subprocess.run(["git","diff","--exit-code","--","cmd","internal","deploy","Makefile","go.mod"],check=True)
(e/"validation.json").write_text(json.dumps({"validated_at":datetime.now().astimezone().isoformat(),"status":"passed","prior_tasks_preserved":True,"source_and_queries_unchanged":True,"runs":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({name:{k:v for k,v in r.items() if k!="rows"} for name,r in results.items()},ensure_ascii=False,indent=2))
