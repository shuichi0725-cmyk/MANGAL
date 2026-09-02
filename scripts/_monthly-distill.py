#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月次蒸留オーケストレータ (2026-09-02 新設 = 弱モデル耐性)。

★狙い: 1.2.17〜1.2.19 の実走は env override 付きの手打ちコマンド列だった
  (MADB_META101_CLEAN=… python _build-series-v2.py / cp db-v2 → MADB_DB=… _populate-v2.py / merge …)。
  その手打ちが「cleanを別ディレクトリに置いて出版社(unknown)1,182頁」「manifest名が1つ前のtag」
  「temp DB既定名が1217固定」「populateを正規DBに撃つ余地」を生んだ。
  以後は **db-v2 を書くのは phase2 の merge --apply だけ**、それ以外は全部読み取り専用に畳む。

  python scripts/_monthly-distill.py status                 # 取込済tag / GitHub最新tag / 成果物 / 次にやること
  python scripts/_monthly-distill.py phase1 [--tag T]       # Phase0→DL→unzip→clean→種1diff→temp build→merge dry-run→差分report
                                                            #   (★db-v2 も正規パス(.cache/madb/metadata101*.json) も一切書かない)
  python scripts/_monthly-distill.py phase2 --tag T --go "<ユーザのGo発話をそのまま>"
                                                            # merge --apply → 正規パス差替(旧は -<旧tag> 温存) → マーカー/台帳更新
  python scripts/_monthly-distill.py run intake|anilist|sanity   # 長時間ジョブをデタッチ起動(Bashのtimeoutで殺されない)
  python scripts/_monthly-distill.py run custom -- <cmd...>      # 任意コマンドを同様にデタッチ起動
  python scripts/_monthly-distill.py sanity [--heavy]        # 月次サニティ検出器を順に回し、前回比(Δ)を表で出す(前景)
  python scripts/_monthly-distill.py promote-made            # 頁化(genpages --run)で作った源頁だけ promote --only-file
  python scripts/_monthly-distill.py seed1-diff --old A --new B   # 種1差分だけ(検算用)

成果物の置き場(全部 tag 付き名 = 旧成果物を上書きしない):
  .cache/madb/metadata101_json-<tag>.zip / metadata504_json-<tag>.zip
  .cache/madb/metadata101-<tag>.json / metadata504-<tag>.json / metadata101-clean-<tag>.json
  .cache/madb-distill/series-v2-<tag>.json / db-v2-<tag>-temp.sqlite / phase1-<tag>.json
  .cache/madb-distill/merge-manifest-<tag>-<date>.json (merge --apply が書く・revert用)
  .cache/madb-distill/run-<stage>-<ts>.log (末尾 `# … EXIT=n` が完了印) / run-<stage>.pid
  data/madb-intake-state.yml (git追跡マーカー) / data/madb-distill-ledger.jsonl (取込台帳・純追記)
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PY = sys.executable
MADB = ROOT / ".cache" / "madb"
DIST = ROOT / ".cache" / "madb-distill"
DB = ROOT / ".cache" / "db-v2.sqlite"
MARKER = ROOT / ".cache" / "madb-last-release.txt"
STATE_YML = ROOT / "data" / "madb-intake-state.yml"
LEDGER = ROOT / "data" / "madb-distill-ledger.jsonl"
DIAG = ROOT / "docs" / "production-diagnostics"
REPO = "mediaarts-db/dataset"
UA = "MANGAL-distill/1.0 (mailto:shuichi0725@gmail.com)"
JST = dt.timezone(dt.timedelta(hours=9))
CANON = {"metadata101.json": "raw101", "metadata101-clean.json": "clean101", "metadata504.json": "raw504"}


def now() -> str:
    return dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def ts() -> str:
    return dt.datetime.now(JST).strftime("%Y%m%d-%H%M%S")


def die(msg: str, code: int = 1) -> None:
    print(f"\n✗ ABORT: {msg}")
    sys.exit(code)


def vkey(tag: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", str(tag)))


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def paths(tag: str) -> dict:
    return {
        "zip101": MADB / f"metadata101_json-{tag}.zip",
        "zip504": MADB / f"metadata504_json-{tag}.zip",
        "raw101": MADB / f"metadata101-{tag}.json",
        "raw504": MADB / f"metadata504-{tag}.json",
        "clean101": MADB / f"metadata101-clean-{tag}.json",
        "series": DIST / f"series-v2-{tag}.json",
        "tempdb": DIST / f"db-v2-{tag}-temp.sqlite",
        "phase1": DIST / f"phase1-{tag}.json",
    }


def marker_tag() -> str | None:
    return MARKER.read_text(encoding="utf-8").strip() if MARKER.exists() else None


def state_tag() -> str | None:
    if not STATE_YML.exists():
        return None
    m = re.search(r'^\s*release_tag:\s*"?([0-9][0-9.]*)"?', STATE_YML.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def git_dirty() -> tuple[list[str], list[str]]:
    """(tracked変更, untracked) を返す。tracked変更=abort対象、untracked=警告のみ。"""
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    return [l for l in lines if not l.startswith("??")], [l for l in lines if l.startswith("??")]


def run(cmd: list[str], env: dict | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    e.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    if env:
        e.update(env)
    print(f"  $ {' '.join(str(c) for c in cmd)}", flush=True)
    if capture:
        return subprocess.run([str(c) for c in cmd], cwd=str(ROOT), env=e, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    return subprocess.run([str(c) for c in cmd], cwd=str(ROOT), env=e)


# ---------------------------------------------------------------- GitHub release
def gh_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def latest_release() -> tuple[str | None, str, str]:
    """(tag, published(YYYY-MM-DD), name or error)"""
    try:
        j = gh_json(f"https://api.github.com/repos/{REPO}/releases/latest")
        return j["tag_name"], (j.get("published_at") or "")[:10], j.get("name") or ""
    except Exception as e:  # noqa: BLE001
        return None, "", f"GitHub API 取得失敗: {e}"


def release_assets(tag: str) -> dict:
    try:
        j = gh_json(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
        return {a["name"]: (a["browser_download_url"], int(a.get("size") or 0)) for a in j.get("assets", [])}
    except Exception as e:  # noqa: BLE001
        print(f"  ! release assets 取得失敗({e}) → URL規約で代替")
        return {}


def download(url: str, dest: Path, size: int | None) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000 and (not size or dest.stat().st_size == size):
        print(f"  skip DL(在): {dest.name} {dest.stat().st_size:,}B")
        return
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, 4):
        try:
            print(f"  DL {url} → {dest.name}", flush=True)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if size and part.stat().st_size != size:
                raise IOError(f"size mismatch {part.stat().st_size} != {size}")
            os.replace(part, dest)
            print(f"  DL完了 {dest.name} {dest.stat().st_size:,}B")
            return
        except Exception as e:  # noqa: BLE001
            print(f"  DL失敗({attempt}/3): {e}")
            time.sleep(5)
    die(f"DL失敗: {url}")


def unzip_one(zp: Path, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  skip unzip(在): {dest.name}")
        return
    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".json")]
        if len(names) != 1:
            die(f"zip内の .json が1個でない: {zp.name} → {names}")
        part = dest.with_name(dest.name + ".part")
        with z.open(names[0]) as src, open(part, "wb") as f:
            shutil.copyfileobj(src, f, 1 << 20)
    os.replace(part, dest)
    print(f"  unzip {zp.name} → {dest.name} {dest.stat().st_size:,}B")


def run_clean(raw: Path, clean: Path, force: bool) -> float:
    if clean.exists() and not force and clean.stat().st_mtime >= raw.stat().st_mtime and clean.stat().st_size > 100_000_000:
        print(f"  skip clean(在・raw以上に新しい): {clean.name}")
        return 0.0
    tsx = ROOT / "node_modules" / "tsx" / "dist" / "cli.mjs"
    node = shutil.which("node")
    if not node or not tsx.exists():
        die("node / node_modules/tsx が無い(npm install)")
    t0 = time.time()
    r = run([node, tsx, SCRIPTS / "clean-madb-seed.ts", "--in", raw, "--out", clean],
            env={"NODE_OPTIONS": "--max-old-space-size=12288"})
    if r.returncode != 0:
        die(f"clean-madb-seed 失敗 exit {r.returncode}")
    if not clean.exists() or clean.stat().st_size < 100_000_000:
        die(f"clean 出力が小さすぎる: {clean}")
    return time.time() - t0


# ---------------------------------------------------------------- 種1 / 504 diff
def scan101(path: Path, old_ids: set | None = None) -> dict:
    """metadata101 を ijson で流し読み(668MB≈6秒)。ID/ISBN13集合 + 新ID(old_idsに無い)の未来日付/成年数。"""
    import ijson  # noqa: WPS433
    pop = load_module("pop_v2_scan", SCRIPTS / "_populate-v2.py")
    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    ids: set = set()
    isbns: set = set()
    n = new_future = new_adult = 0
    with open(path, "rb") as f:
        for rec in ijson.items(f, "@graph.item"):
            n += 1
            mid = rec.get("schema:identifier")
            mid = str(mid) if mid else None
            if mid:
                ids.add(mid)
            b = rec.get("schema:isbn")
            for x in (b if isinstance(b, list) else [b]):
                if isinstance(x, str) and x:
                    nb = pop.normalize_isbn(x)
                    if nb:
                        isbns.add(nb)
            if old_ids is not None and mid and mid not in old_ids:
                dp = rec.get("schema:datePublished")
                if isinstance(dp, str) and dp[:10] > today:
                    new_future += 1
                cr = rec.get("schema:contentRating")
                if isinstance(cr, str) and "成年" in cr:
                    new_adult += 1
    return {"n": n, "ids": ids, "isbns": isbns, "new_future": new_future, "new_adult": new_adult}


def scan504(path: Path) -> set:
    with open(path, "rb") as f:
        j = json.load(f)
    return {str(r.get("@id", "")).rsplit("/", 1)[-1] for r in j.get("@graph", []) if r.get("@id")}


def seed1_diff(old: Path | None, new: Path) -> dict:
    t0 = time.time()
    o = scan101(old) if old and old.exists() else None
    nw = scan101(new, o["ids"] if o else set())
    d = {"new_total": nw["n"], "new_future_dated": nw["new_future"], "new_adult_rating": nw["new_adult"],
         "new_isbn13_total": len(nw["isbns"]), "secs": round(time.time() - t0, 1)}
    if o:
        d.update({"old_total": o["n"], "new_ids": len(nw["ids"] - o["ids"]), "new_isbns": len(nw["isbns"] - o["isbns"]),
                  "vanished_ids": len(o["ids"] - nw["ids"]), "vanished_isbns": len(o["isbns"] - nw["isbns"])})
    else:
        d.update({"old_total": None, "new_ids": None, "new_isbns": None, "vanished_ids": None, "vanished_isbns": None,
                  "note": "旧raw無し=差分算出不可(総数のみ)"})
    return d


# ---------------------------------------------------------------- temp build / merge
def build_series(clean: Path, raw504: Path, series: Path, force: bool) -> float:
    if series.exists() and not force and series.stat().st_mtime >= clean.stat().st_mtime:
        print(f"  skip build-series(在): {series.name}")
        return 0.0
    t0 = time.time()
    r = run([PY, SCRIPTS / "_build-series-v2.py"],
            env={"MADB_META101_CLEAN": str(clean), "MADB_META504": str(raw504), "MADB_SERIES_V2_OUT": str(series)})
    if r.returncode != 0 or not series.exists():
        die(f"_build-series-v2 失敗 exit {r.returncode}")
    return time.time() - t0


def populate_temp(series: Path, tempdb: Path, force: bool) -> float:
    if tempdb.exists() and not force and tempdb.stat().st_mtime >= max(series.stat().st_mtime, DB.stat().st_mtime):
        print(f"  skip populate(在・series/db-v2以上に新しい): {tempdb.name}")
        return 0.0
    t0 = time.time()
    shutil.copyfile(DB, tempdb)  # mtime=now (copy2 だと旧mtimeを引き継ぎ鮮度判定が狂う)
    print(f"  copy db-v2 → {tempdb.name} (schema+mangaka継承)")
    r = run([PY, SCRIPTS / "_populate-v2.py"], env={"MADB_DB": str(tempdb), "MADB_SERIES_V2": str(series)})
    if r.returncode != 0:
        die(f"_populate-v2 失敗 exit {r.returncode}")
    return time.time() - t0


MERGE_RE = {
    "cur_series": r"現db-v2: series ([\d,]+)", "cur_isbn": r"/ ISBN ([\d,]+)", "cur_madb": r"madb_book ([\d,]+)",
    "new_series": r"新series ([\d,]+)", "append_series": r"既存series追記 ([\d,]+)",
    "vol_new_series": r"新volume\(新series\) ([\d,]+)", "vol_append": r"追記volume\(既存series\) ([\d,]+)",
    "ed_new": r"新edition ([\d,]+)", "skip_isbn_dup": r"ISBN既存 ([\d,]+)", "skip_madb_dup": r"madb既存 ([\d,]+)",
    "skip_no_change": r"変化なしseries ([\d,]+)", "total_new_vol": r"純増volume合計: ([\d,]+)",
}


def parse_merge(out: str) -> dict:
    d = {}
    for k, rx in MERGE_RE.items():
        m = re.search(rx, out)
        d[k] = int(m.group(1).replace(",", "")) if m else None
    m = re.search(r"^backup: (.+)$", out, re.M)
    d["backup"] = m.group(1).strip() if m else None
    m = re.search(r"manifest: (.+)$", out, re.M)
    d["manifest"] = m.group(1).strip() if m else None
    return d


def merge_run(tempdb: Path, tag: str, apply: bool) -> dict:
    cmd = [PY, SCRIPTS / "_distill-incremental-merge.py", tempdb, "--tag", tag] + (["--apply"] if apply else [])
    t0 = time.time()
    r = run(cmd, capture=True)
    out = (r.stdout or "") + (r.stderr or "")
    print("\n".join("    " + l for l in out.strip().splitlines()[-12:]))
    if r.returncode != 0:
        die(f"merge {'apply' if apply else 'dry-run'} 失敗 exit {r.returncode}")
    d = parse_merge(out)
    if d["new_series"] is None or d["total_new_vol"] is None:
        die("merge 出力の解析に失敗(書式変更?) → 上の出力を読む")
    d["secs"] = round(time.time() - t0, 1)
    return d


def db_counts(p: Path) -> dict:
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("series", "editions", "volumes")}
    finally:
        con.close()


# ---------------------------------------------------------------- phase0 / status
def phase0() -> bool:
    print("▶ Phase0 前提確認 (_monthly-phase0.py)")
    r = run([PY, SCRIPTS / "_monthly-phase0.py"])
    return r.returncode == 0


def job_state(stage: str) -> dict | None:
    pidf = DIST / f"run-{stage}.pid"
    if not pidf.exists():
        return None
    try:
        j = json.loads(pidf.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    log = Path(j.get("log", ""))
    tail, exit_line = "", None
    if log.exists():
        with open(log, "rb") as f:
            f.seek(max(0, log.stat().st_size - 2000))
            lines = [l for l in f.read().decode("utf-8", "replace").splitlines() if l.strip()]
        tail = " | ".join(l.strip()[:80] for l in lines[-2:])
        for l in reversed(lines):
            if "EXIT=" in l:
                exit_line = l.strip()
                break
    j.update({"alive": alive(j.get("pid")), "tail": tail, "exit": exit_line})
    return j


def status() -> None:
    mk, st = marker_tag(), state_tag()
    latest, pub, name = latest_release()
    print("=" * 72)
    print(f"月次蒸留 status  [{now()}]")
    print("=" * 72)
    print(f"  取込済 tag  : .cache/madb-last-release.txt = {mk}   / data/madb-intake-state.yml = {st}"
          + ("" if mk == st else "   ★不一致(phase2が両方書く。手で直すな=どちらが正か台帳で確認)"))
    print(f"  GitHub最新  : {latest or '?'} (published {pub}) {name if not latest else ''}")
    for stage in ("intake", "anilist", "sanity", "custom"):
        js = job_state(stage)
        if js:
            print(f"  job {stage:<8}: pid {js['pid']} {'RUNNING' if js['alive'] else 'ended'} "
                  f"{js.get('exit') or ''}  log={Path(js['log']).name}\n              tail: {js['tail']}")
    if not latest:
        print("\n→ GitHub API が読めない。ネットワーク回復後に再実行(--tag で手動指定も可)。")
        return
    if mk and vkey(latest) <= vkey(mk):
        print(f"\n★新releaseなし({latest} = 取込済)。今 月次蒸留を回しても種2は何も変わらない → 終了(次は次リリース 毎月17〜22日頃)。")
        return
    p = paths(latest)
    print(f"\n  成果物({latest}): " + " / ".join(f"{k}={'✓' if v.exists() else '-'}" for k, v in p.items()))
    manifests = sorted(DIST.glob(f"merge-manifest-{latest}-*.json"))
    if manifests:
        print(f"  merge manifest: {', '.join(m.name for m in manifests)} (= phase2 適用済み?)")
    if p["phase1"].exists():
        j = json.loads(p["phase1"].read_text(encoding="utf-8"))
        md = j.get("merge_dry", {})
        print(f"  phase1 済 ({j.get('at')}): 新series +{fmt(md.get('new_series'))} / 純増volume +{fmt(md.get('total_new_vol'))}")
        print(f"\n→ 次: ユーザのGoサインを受領してから\n   python scripts/_monthly-distill.py phase2 --tag {latest} --go \"<ユーザの発話をそのまま>\"")
    else:
        print(f"\n→ 次: python scripts/_monthly-distill.py phase1 --tag {latest}   (読み取り専用・数十分)")


# ---------------------------------------------------------------- phase1
def phase1(a) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    MADB.mkdir(parents=True, exist_ok=True)
    if not phase0():
        die("Phase0 不成立 → 欠けをユーザ報告して終了(自動fallback禁止)")
    mk = marker_tag()
    latest, pub, name = latest_release()
    tag = a.tag or latest
    if not tag:
        die(f"tag が決まらない({name}) → --tag で指定")
    if latest and tag != latest:
        print(f"  ! 指定tag {tag} ≠ GitHub最新 {latest}")
    if mk and vkey(tag) <= vkey(mk) and not a.rehearsal:
        print(f"\n★{tag} は取込済({mk})。今 月次蒸留を回しても種2は何も変わらない。終了。"
              f"\n  (手順の検算だけしたい時は --rehearsal)")
        return
    if mk and vkey(tag) < vkey(mk):
        die(f"tag {tag} < 取込済 {mk}(後退取込は不可)")
    p = paths(tag)
    print("=" * 72)
    print(f"▶ Phase1 {mk} → {tag}  (published {pub if tag == latest else '?'})  [{now()}]  ★読み取り専用")
    print("=" * 72)
    dur = {}
    assets = release_assets(tag)

    print("\n[1/6] DL (metadata101_json / metadata504_json)")
    for asset, key in (("metadata101_json.zip", "zip101"), ("metadata504_json.zip", "zip504")):
        url, size = assets.get(asset, (f"https://github.com/{REPO}/releases/download/{tag}/{asset}", None))
        download(url, p[key], size)

    print("\n[2/6] unzip")
    unzip_one(p["zip101"], p["raw101"])
    unzip_one(p["zip504"], p["raw504"])

    print("\n[3/6] clean (clean-madb-seed.ts、~5分)")
    dur["clean"] = run_clean(p["raw101"], p["clean101"], a.force)

    print("\n[4/6] 種1 diff (現 raw vs 新 raw、~15秒)")
    old_raw = MADB / "metadata101.json"
    s1 = seed1_diff(old_raw if old_raw.exists() else None, p["raw101"])
    old504 = MADB / "metadata504.json"
    s504 = {"new_total": None, "new_ids": None}
    try:
        new_c = scan504(p["raw504"])
        s504["new_total"] = len(new_c)
        if old504.exists():
            s504["new_ids"] = len(new_c - scan504(old504))
    except Exception as e:  # noqa: BLE001
        s504["error"] = str(e)
    print(f"  種1: 総{fmt(s1['new_total'])} 新ID+{fmt(s1['new_ids'])} 新ISBN+{fmt(s1['new_isbns'])} "
          f"上流消失ID{fmt(s1['vanished_ids'])}/ISBN{fmt(s1['vanished_isbns'])}  504: 新C-id+{fmt(s504['new_ids'])}")

    print("\n[5/6] temp build (build-series → db-v2 copy → populate。既定パスは一切書かない)")
    dur["build_series"] = build_series(p["clean101"], p["raw504"], p["series"], a.force)
    dur["populate"] = populate_temp(p["series"], p["tempdb"], a.force)

    print("\n[6/6] merge dry-run (series_key突合・INSERT only設計・db-v2不変)")
    md = merge_run(p["tempdb"], tag, apply=False)

    rec = {"tag": tag, "prev_tag": mk, "published": pub if tag == latest else None, "at": now(), "rehearsal": bool(a.rehearsal),
           "seed1": s1, "seed504": s504, "merge_dry": md, "durations_sec": {k: round(v, 1) for k, v in dur.items()},
           "paths": {k: str(v) for k, v in p.items()}}
    p["phase1"].write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f"月次蒸留 Phase1 差分report  {mk} → {tag}" + ("  (★rehearsal=検算のみ)" if a.rehearsal else ""))
    print("=" * 72)
    print(f"  MADB release {tag} (published {pub if tag == latest else '?'})")
    print(f"  種1 (metadata101): 総 {fmt(s1['new_total'])} / 新ID +{fmt(s1['new_ids'])} / 新ISBN +{fmt(s1['new_isbns'])} / "
          f"上流消失 ID {fmt(s1['vanished_ids'])}・ISBN {fmt(s1['vanished_isbns'])} (取込には無関係)")
    print(f"       新IDのうち 未来発売日 {fmt(s1['new_future_dated'])} / 成年contentRating {fmt(s1['new_adult_rating'])}")
    print(f"  種504 (作者master): 新C-id +{fmt(s504.get('new_ids'))} (総 {fmt(s504.get('new_total'))})")
    print(f"  種2 (db-v2 dry-run): 現 series {fmt(md['cur_series'])} → 新series +{fmt(md['new_series'])} / 既存series追記 {fmt(md['append_series'])} / "
          f"★純増volume +{fmt(md['total_new_vol'])} (新series分 {fmt(md['vol_new_series'])} + 追記 {fmt(md['vol_append'])}) / 新edition {fmt(md['ed_new'])}")
    print(f"       skip: ISBN既存 {fmt(md['skip_isbn_dup'])} / madb既存 {fmt(md['skip_madb_dup'])} / 変化なし {fmt(md['skip_no_change'])}")
    print("  種3 (series-supplement-v2): AI fill batch = 不要 (v2機構: kana=頁化時NDL確定 / genre・synopsis=enrich系) → 予想cost 0")
    print("  削除予測: 0 件 (merge は INSERT only・既存行不変。上流消失は取込に影響しない)")
    print(f"  所要(今回): clean {dur.get('clean', 0):.0f}s / build-series {dur.get('build_series', 0):.0f}s / populate {dur.get('populate', 0):.0f}s / dry-run {md['secs']}s")
    print("  この後の見込み: phase2 数分 → intake ~2.5h(matcher20分+promote+durability) → AniListフルダンプ ~2.5h(任意) → 頁化+監査 数十分")
    if a.rehearsal:
        print("\n→ rehearsal: 期待値は 新series 0 / 純増volume 0 (取込済tagの再計算)。phase2 は不要。")
        return
    print("\n★「進めて OK？」— ユーザの明示的肯定(OK/進めて/ゴー等)を受領するまで phase2 に進まない。受領後:")
    print(f"   python scripts/_monthly-distill.py phase2 --tag {tag} --go \"<ユーザの発話をそのまま引用>\"")


# ---------------------------------------------------------------- phase2
def swap_canonical(tag: str, prev: str | None) -> list[str]:
    """新 -<tag> を正規パスへ。旧正規は -<prev> 名で温存(既に在れば .dup-<ts>)。★削除はしない。"""
    notes = []
    p = paths(tag)
    for canon_name, key in CANON.items():
        canon = MADB / canon_name
        new = p[key]
        if not new.exists():
            die(f"新ファイルが無い: {new}")
        if canon.exists():
            keep = MADB / canon_name.replace(".json", f"-{prev or 'prev'}.json")
            if keep.exists():
                keep = MADB / canon_name.replace(".json", f"-{prev or 'prev'}.dup-{ts()}.json")
            os.replace(canon, keep)
            notes.append(f"{canon_name} → {keep.name}")
        os.replace(new, canon)
        notes.append(f"{new.name} → {canon_name}")
    raw, clean = MADB / "metadata101.json", MADB / "metadata101-clean.json"
    if clean.stat().st_mtime < raw.stat().st_mtime:  # 鮮度ガード(Phase0/intake)用: clean は raw 以上に新しく
        os.utime(clean, None)
        notes.append("metadata101-clean.json mtime を更新(鮮度ガード整合)")
    return notes


def write_state_yml(tag: str, prev: str | None, pub: str | None, md: dict, go: str, p1: dict) -> None:
    import yaml  # noqa: WPS433
    hist = []
    if STATE_YML.exists():
        try:
            old = yaml.safe_load(STATE_YML.read_text(encoding="utf-8")) or {}
            hist = list(old.get("history") or [])
        except Exception:  # noqa: BLE001
            hist = []
    entry = {"tag": tag, "at": now()[:10], "new_series": md.get("new_series"), "append_series": md.get("append_series"),
             "total_new_vol": md.get("total_new_vol"), "prev_tag": prev}
    hist = [entry] + [h for h in hist if not (isinstance(h, dict) and h.get("tag") == tag)]
    doc = {
        "last_intake": {
            "source_repo": REPO, "release_tag": tag, "release_published": pub or "", "db_built_at": now()[:10],
            "prev_tag": prev, "asset": "metadata101_json.zip + metadata504_json.zip",
            "merge_manifest": md.get("manifest"), "db_backup": md.get("backup"),
            "stats": {k: md.get(k) for k in ("new_series", "append_series", "vol_new_series", "vol_append", "ed_new", "total_new_vol")},
            "seed1": {k: p1.get("seed1", {}).get(k) for k in ("new_ids", "new_isbns", "vanished_ids", "vanished_isbns")},
            "go_sign": go,
        },
        "history": hist[:24],
    }
    head = ("# MADB 取込ベースライン状態(git追跡=永続。 .cache/madb-last-release.txt の正本バックアップ)\n"
            "# ★scripts/_monthly-distill.py phase2 が自動更新する(手編集しない)。全件台帳= data/madb-distill-ledger.jsonl\n"
            "# 取込手順の正本= .claude/skills/monthly-distill/SKILL.md (status→phase1→Goサイン→phase2→run intake…)\n"
            "# リリースは月次(毎月17〜22日頃)。GitHub release 経路は月次で十分(日次=楽天予約/NDL新着の別経路)。\n")
    STATE_YML.write_text(head + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def phase2(a) -> None:
    go = (a.go or "").strip()
    if not go:
        die("--go にユーザのGoサイン発話をそのまま引用する(無しに phase2 は動かない)", 2)
    tag = a.tag
    p = paths(tag)
    if not p["phase1"].exists():
        die(f"phase1-{tag}.json が無い → 先に phase1 --tag {tag}")
    p1 = json.loads(p["phase1"].read_text(encoding="utf-8"))
    if p1.get("rehearsal"):
        die("phase1 が rehearsal(検算)だった → 本番の phase1 を回し直す")
    mk = marker_tag()
    if mk and vkey(tag) <= vkey(mk):
        die(f"{tag} は取込済({mk})")
    if not p["tempdb"].exists():
        die(f"temp db が無い: {p['tempdb']}")
    tracked, untracked = git_dirty()
    if tracked:
        die("git に未コミットの変更がある(混ざる)→ commit/stash してから: " + " / ".join(tracked[:5]))
    if untracked:
        print("  ! untracked ファイルあり(無視して続行。git add -A は使わない): " + " / ".join(untracked[:5]))

    print("=" * 72)
    print(f"▶ Phase2 {mk} → {tag}  [{now()}]  Go=「{go}」")
    print("=" * 72)
    print("\n[1/5] dry-run 再計算 → phase1 と一致確認 (db-v2/temp が変わっていないか)")
    md0 = merge_run(p["tempdb"], tag, apply=False)
    exp = p1["merge_dry"]
    for k in ("new_series", "append_series", "total_new_vol", "ed_new"):
        if md0.get(k) != exp.get(k):
            die(f"phase1 と不一致: {k} phase1={exp.get(k)} now={md0.get(k)} → phase1 --force からやり直す")
    pre = db_counts(DB)
    print(f"  一致 ✓  現DB: {pre}")

    print("\n[2/5] merge --apply (backup 自動・INSERT only)")
    md = merge_run(p["tempdb"], tag, apply=True)
    post = db_counts(DB)
    exp_vol = (md["vol_new_series"] or 0) + (md["vol_append"] or 0)
    bad = []
    if post["series"] - pre["series"] != md["new_series"]:
        bad.append(f"series Δ{post['series'] - pre['series']} ≠ {md['new_series']}")
    if post["volumes"] - pre["volumes"] != exp_vol:
        bad.append(f"volumes Δ{post['volumes'] - pre['volumes']} ≠ {exp_vol}")
    if post["editions"] - pre["editions"] != md["ed_new"]:
        bad.append(f"editions Δ{post['editions'] - pre['editions']} ≠ {md['ed_new']}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    qc = con.execute("PRAGMA quick_check").fetchone()[0]
    con.close()
    if qc != "ok":
        bad.append(f"quick_check={qc}")
    if bad:
        bk = md.get("backup")
        if bk and Path(bk).exists():
            shutil.copyfile(bk, DB)
            print(f"  ★検証NG → backup から db-v2 を復元した: {bk}")
        die("apply 後の件数検証NG: " + " / ".join(bad))
    print(f"  検証 ✓ series +{md['new_series']} / editions +{md['ed_new']} / volumes +{exp_vol}  quick_check=ok")
    print(f"  backup={md.get('backup')}\n  manifest={md.get('manifest')}")

    print("\n[3/5] 正規パス差替 (.cache/madb/metadata101.json / -clean / metadata504.json ← 新tag、旧は -<旧tag> 温存)")
    for n in swap_canonical(tag, mk):
        print(f"  {n}")

    print("\n[4/5] マーカー/台帳更新")
    MARKER.write_text(tag + "\n", encoding="utf-8")
    write_state_yml(tag, mk, p1.get("published"), md, go, p1)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), "tag": tag, "prev_tag": mk, "go": go, "phase1_at": p1.get("at"),
                            "stats": {k: md.get(k) for k in ("new_series", "append_series", "vol_new_series", "vol_append", "ed_new", "total_new_vol")},
                            "seed1": {k: p1.get("seed1", {}).get(k) for k in ("new_ids", "new_isbns", "vanished_ids", "vanished_isbns")},
                            "backup": md.get("backup"), "manifest": md.get("manifest"), "db_counts_after": post},
                           ensure_ascii=False) + "\n")
    print(f"  {MARKER.name}={tag} / {STATE_YML.name} / {LEDGER.name} 追記")

    print("\n[5/5] 完了。★次の順(各コマンドの終了を待ってから次へ):")
    print(f"   git add data/madb-intake-state.yml data/madb-distill-ledger.jsonl && git commit -m \"月次蒸留 {tag}: 種2純増 series+{md['new_series']}/vol+{exp_vol} (INSERT only)\" && git push")
    print("   python scripts/_monthly-distill.py run intake      # ~2.5h デタッチ。status で完了(EXIT=0)確認。★途中killしない")
    print("   python scripts/_monthly-distill.py run anilist     # ~2.5h(任意・並走可)。dump backup→フル再取得→enrich/status map")
    print("   python scripts/_torikoboshi-genpages.py --list      # 頁化(最新manifest自動)。--run 後は skill 6b/6c の後始末")
    print("   python scripts/_monthly-distill.py run sanity      # 月次サニティ(前回比Δ)")
    print("   python scripts/_monthly-postflight.py               # 成功判定(exit 0 が完了条件)")


# ---------------------------------------------------------------- detached runner
def alive(pid) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        import ctypes  # noqa: WPS433
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION (★os.kill(pid,0) はWindowsでは殺す=使用禁止)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259
    return Path(f"/proc/{pid}").exists()


def spawn_detached(stage: str, cmd: list[str]) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    js = job_state(stage)
    if js and js.get("alive"):
        die(f"{stage} は実行中(pid {js['pid']})。二重起動しない。log={js['log']}")
    log = DIST / f"run-{stage}-{ts()}.log"
    child = [PY, str(Path(__file__).resolve()), "_child", "--log", str(log), "--", *cmd]
    kw = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(child, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, **kw)
    (DIST / f"run-{stage}.pid").write_text(json.dumps({"pid": proc.pid, "log": str(log), "cmd": cmd, "at": now()},
                                                      ensure_ascii=False), encoding="utf-8")
    print(f"▶ {stage} をデタッチ起動 pid={proc.pid}\n  log: {log}\n  監視: python scripts/_monthly-distill.py status  (末尾 `EXIT=0` で完了)")


def child_main(log: Path, cmd: list[str]) -> None:
    with open(log, "ab") as f:
        f.write(f"# {now()} start: {' '.join(cmd)}\n".encode("utf-8"))
        f.flush()
        env = dict(os.environ)
        env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        rc = subprocess.call(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        f.write(f"\n# {now()} EXIT={rc}\n".encode("utf-8"))
    sys.exit(rc)


def anilist_seq() -> None:
    """AniListフルダンプ列: backup → progress消去 → dump(~2.5h) → enrich map → status map。縮小なら復元してabort。"""
    out = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
    prog = ROOT / ".cache" / "anilist-dump-v3-progress.json"
    old = out.stat().st_size if out.exists() else 0
    bak = None
    if out.exists():
        bak = out.with_name(out.name + f".bak-{ts()}")
        shutil.copy2(out, bak)
        print(f"backup: {bak.name} ({old:,}B)")
    if prog.exists():
        prog.unlink()
        print("progress 消去(フル再取得)")
    r = run([PY, SCRIPTS / "_anilist-dump-v3.py"])
    new = out.stat().st_size if out.exists() else 0
    if r.returncode != 0 or new < old * 0.98:
        if bak:
            shutil.copy2(bak, out)
            print(f"★dump 失敗/縮小({old:,}→{new:,}B) → backup から復元した")
        die(f"AniList dump exit {r.returncode} / size {new:,}")
    for s in ("_build-anilist-enrich-map.py", "_gen-anilist-status-map.py"):
        if run([PY, SCRIPTS / s]).returncode != 0:
            die(f"{s} 失敗")
    print("✓ AniList フルダンプ + enrich map + status map 完了")


# ---------------------------------------------------------------- sanity
# (name, cmd, tsv(docs/production-diagnostics 配下) or None, heavy)  ★全部 read-only(--apply は付けない)
DETECTORS = [
    ("isbn-loss", ["_audit-isbn-loss.py"], "isbn-loss.tsv", False),
    ("solo-truncated", ["_audit-solo-truncated.py"], "solo-truncated.tsv", False),
    ("volume-numbering", ["_audit-volume-numbering.py"], None, False),
    ("title-eq-author", ["_audit-title-eq-author.py"], "title-eq-author.tsv", False),
    ("foreign-editions", ["_audit-foreign-editions.py"], None, False),
    ("price-pack", ["_audit-price-pack.py"], "price-pack.tsv", False),
    ("vol0-hidden-first", ["_audit-vol0-hidden-first.py"], "vol0-hidden-first.tsv", False),
    ("orphan-new-series", ["_audit-orphan-new-series.py", "--rebuild"], "orphan-new-series.tsv", False),
    ("edition-canonical", ["_check-edition-canonical.py"], None, False),
    ("year-suffix-dup", ["_audit-year-suffix-dup.py"], "year-suffix-dup.tsv", False),
    ("canonical-imprint-split", ["_audit-canonical-imprint-split.py"], "canonical-imprint-split.tsv", False),
    ("edition-run-split", ["_audit-edition-run-split.py"], "edition-run-split.tsv", False),
    ("numeral-variant-split", ["_audit-numeral-variant-split.py"], "numeral-variant-split.tsv", False),
    ("vol-date-regression", ["_audit-vol-date-regression.py"], "vol-date-regression.tsv", False),
    ("deluxe-label-split", ["_audit-deluxe-label-split.py"], "deluxe-label-split.tsv", False),
    ("cover-dup", ["_audit-cover-dup.py"], "cover-dup.tsv", False),
    ("kana-from-other-volume", ["_audit-kana-from-other-volume.py"], "kana-from-other-volume.tsv", False),
    ("excerpt-subtitle", ["_audit-excerpt-subtitle.py"], "excerpt-subtitle.tsv", True),
    ("edition-mix", ["_audit-edition-mix.py"], "edition-mix.tsv", True),
    ("author-not-in-volumes", ["_audit-author-not-in-volumes.py"], "author-not-in-volumes.tsv", True),
]


def promote_made(a) -> None:
    """頁化(_torikoboshi-genpages --run)で作った源頁だけ promote --only-file で本番yml化(手打ちの --only 連結を廃止)。"""
    gp = ROOT / ".cache" / "torikoboshi" / "genpages-last.json"
    if not gp.exists():
        die("genpages-last.json が無い(先に _torikoboshi-genpages.py --run)")
    j = json.loads(gp.read_text(encoding="utf-8")) or {}
    made = [s for s in (j.get("made") or []) if s]
    if not made:
        die("genpages-last.json の made が空(今回の頁化なし)")
    lst = gp.with_suffix(".slugs")
    lst.write_text("\n".join(made) + "\n", encoding="utf-8")
    age_h = (time.time() - gp.stat().st_mtime) / 3600
    print(f"頁化 {len(made)} 頁 (genpages-last.json {age_h:.1f}h前) → promote --only-file {lst.name}")
    r = run([PY, SCRIPTS / "_promote-bulk-v2.py", "--only-file", lst])
    if r.returncode != 0:
        die(f"promote exit {r.returncode}")
    missing = [s for s in made if not (ROOT / "data" / "manga.v2" / f"{s}.yml").exists()]
    print(f"✓ 生成 {len(made) - len(missing)} / 未生成 {len(missing)}" + (f": {', '.join(missing[:8])}" if missing else ""))
    print("次(skill test-deploy): .preview-data/manga へ copy → _build-list-index.py .preview-data/manga .preview-data → commit/push →"
          " レビュー(slug英綴り/書影/コンビニ再録)→ 公開前rename。本番公開は週次蒸留。")


def tsv_rows(name: str | None) -> int | None:
    if not name:
        return None
    p = DIAG / name
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return max(0, sum(1 for l in f if l.strip()) - 1)


def sanity(a) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    prev_files = sorted(DIST.glob("sanity-*.json"))
    prev = json.loads(prev_files[-1].read_text(encoding="utf-8")) if prev_files else {}
    prev_res = prev.get("results", {})
    res = {}
    print("=" * 72)
    print(f"月次サニティ  [{now()}]  前回={prev_files[-1].name if prev_files else '無し'}  ★全detector read-only")
    print("=" * 72)
    for name, cmd, tsv, heavy in DETECTORS:
        if heavy and not a.heavy:
            res[name] = {"skipped": "heavy(--heavy で実行)"}
            continue
        if a.only and name not in a.only:
            continue
        t0 = time.time()
        r = run([PY, SCRIPTS / cmd[0], *cmd[1:]], capture=True)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        lines = [l for l in out.splitlines() if l.strip()]
        rows = tsv_rows(tsv)
        extra = {}
        m = re.search(r"AUTO_FIXED\D{0,20}?([\d,]+)", out)
        if m:
            extra["auto_fixed"] = int(m.group(1).replace(",", ""))
        m = re.search(r"\bNG\D{0,10}?(\d+)", out)
        if name == "edition-canonical" and m:
            extra["ng"] = int(m.group(1))
        res[name] = {"rc": r.returncode, "rows": rows, "secs": round(time.time() - t0, 1),
                     "tail": [l.strip()[:160] for l in lines[-2:]], **extra}
        pr = prev_res.get(name) or {}
        d = None if rows is None or pr.get("rows") is None else rows - pr["rows"]
        flag = "" if r.returncode == 0 else "  ★rc≠0"
        print(f"  {name:<24} rc={r.returncode} rows={fmt(rows) if rows is not None else '-':>7} Δ={('%+d' % d) if d is not None else '-':>6} "
              f"{res[name]['secs']:>6.0f}s {('AUTO_FIXED=' + str(extra['auto_fixed'])) if 'auto_fixed' in extra else ''}"
              f"{('NG=' + str(extra['ng'])) if 'ng' in extra else ''}{flag}", flush=True)
        for l in res[name]["tail"]:
            print(f"      {l}")
    outp = DIST / f"sanity-{ts()}.json"
    outp.write_text(json.dumps({"at": now(), "tag": marker_tag(), "results": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n保存: {outp}  (次回この結果が前回比の基準になる)")
    print("読み方: Δ>0 の検出器 = 今月増えた型 → 該当skill/CLAUDE.md月次サニティ節の是正へ。rc≠0 は検出器自体の故障。")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="月次蒸留オーケストレータ")
    sp = ap.add_subparsers(dest="cmd")
    sp.add_parser("status")
    p1 = sp.add_parser("phase1")
    p1.add_argument("--tag")
    p1.add_argument("--force", action="store_true", help="成果物が在っても作り直す")
    p1.add_argument("--rehearsal", action="store_true", help="取込済tagで手順を検算(期待=純増0)")
    p2 = sp.add_parser("phase2")
    p2.add_argument("--tag", required=True)
    p2.add_argument("--go", required=True, help="ユーザのGoサイン発話をそのまま")
    pr = sp.add_parser("run")
    pr.add_argument("stage", choices=["intake", "anilist", "sanity", "custom"])
    pr.add_argument("rest", nargs=argparse.REMAINDER)
    ps = sp.add_parser("sanity")
    ps.add_argument("--heavy", action="store_true")
    ps.add_argument("--only", nargs="*", default=None)
    sd = sp.add_parser("seed1-diff")
    sd.add_argument("--old", required=True)
    sd.add_argument("--new", required=True)
    sp.add_parser("anilist-seq")
    sp.add_parser("promote-made")
    pc = sp.add_parser("_child")
    pc.add_argument("--log", required=True)
    pc.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()

    if a.cmd == "status" or a.cmd is None:
        status()
    elif a.cmd == "phase1":
        phase1(a)
    elif a.cmd == "phase2":
        phase2(a)
    elif a.cmd == "run":
        if a.stage == "intake":
            cmd = [PY, str(SCRIPTS / "intake.py"), "--run"]
        elif a.stage == "anilist":
            cmd = [PY, str(Path(__file__).resolve()), "anilist-seq"]
        elif a.stage == "sanity":
            cmd = [PY, str(Path(__file__).resolve()), "sanity"]
        else:
            rest = [x for x in a.rest if x != "--"]
            if not rest:
                die("run custom -- <cmd...>", 2)
            cmd = rest
        spawn_detached(a.stage, cmd)
    elif a.cmd == "sanity":
        sanity(a)
    elif a.cmd == "seed1-diff":
        d = seed1_diff(Path(a.old), Path(a.new))
        print(json.dumps(d, ensure_ascii=False, indent=1))
    elif a.cmd == "anilist-seq":
        anilist_seq()
    elif a.cmd == "promote-made":
        promote_made(a)
    elif a.cmd == "_child":
        child_main(Path(a.log), [x for x in a.rest if x != "--"])


if __name__ == "__main__":
    main()
