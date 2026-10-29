#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web 材料の器 = Haiku が Web で集めた情報を、漫画ごとに「いつ・どこで・何を」付きで貯める。 2026-10-29 新設。

  python scripts/_web-material.py status                 # 器の中身と、次に集める作品
  python scripts/_web-material.py run --n 20             # 次の20作を集める(1作ずつ・続きから・集めるだけ = 判定しない)
  python scripts/_web-material.py run --stems a,b        # 作品を指して集める(--redo で集め直し = 前の回も器に残る)
  python scripts/_web-material.py show <stem> [--text]   # 1作の中身(--text で採った段落の原文も)
  python scripts/_web-material.py import <EH_ROOT>       # 別の置き場で集めた結果を器へ移す(試し30頁など)

★器はこのPCのローカルだけ(ユーザ裁定 2026-10-29「非公開、ローカルだけでよい」)= git に入れない。
  置き場 .cache\\web-material\\(C のリポジトリ内・git 管理外。 ユーザ裁定 2026-10-29「DはつかわないでCでよい」)
    store\\<stem>.json  … 器の本体。 1作1ファイル。 集めた回(runs)を全部残す(集め直しても前の回は消さない)
    work\\              … 収集の作業場(_element-harvest.py の EH_ROOT)。 取得した頁の全文(raw)もここ
    runs.jsonl          … 流した記録(いつ・何作・失敗)
★集めるのは _element-harvest.py auto(Haiku が開く頁と採る段落を番号で指すだけ。 文面は道具が原文から切り出す)。
  要素・ジャンルは付けない。 付与は後で器から(_element-assign.py)。
★順番 = 巻数5以上・見える要素3以下の頁を巻数の多い順(ユーザ指示 2026-10-29「巻数の多いものから」)。
★流し方の罠(2026-10-29 実踏): 子の標準入力は切る(DEVNULL。 継ぐと claude -p が固まる)/ 1作15分で打ち切り / 3作続けて失敗したら止める。
"""
import argparse, datetime, glob, json, os, shutil, subprocess, sys, time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.environ.get("WEB_MATERIAL_ROOT") or os.path.join(ROOT, ".cache", "web-material")
STORE = os.path.join(HOME, "store")
WORK = os.path.join(HOME, "work")
RUNS = os.path.join(HOME, "runs.jsonl")
MODEL = "claude-haiku-5-5"
VERSION = "w0.1"
STEP_TIMEOUT = 900
MIN_VOLS, MAX_ELEMS = 5, 3


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def store_path(stem):
    return os.path.join(STORE, stem + ".json")


def load_store(stem):
    p = store_path(stem)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def to_record(st, work_dir):
    """収集の state.json → 器の1回ぶん。 採った段落は原文のまま、出所ごとに いつ・どこで を付ける。"""
    picks_by_src = {}
    for p in st.get("picks") or []:
        picks_by_src.setdefault(p.get("src"), []).append({
            "paras": p.get("paras"), "role": p.get("as"), "label": p.get("label"), "text": p.get("text"),
            "chars": p.get("chars"), "truncated": p.get("truncated"), "spoiler": p.get("spoiler"), "scope": p.get("scope"),
            "by": "道具(機械)" if p.get("auto") or p.get("mech") else "モデル", "at": p.get("at")})
    sources = []
    for s in st.get("sources") or []:
        sources.append({
            "id": s.get("id"), "kind": s.get("kind"), "origin": s.get("origin"), "ref": s.get("ref"),
            "url": s.get("url"), "final_url": s.get("final_url"), "domain": s.get("domain"), "page_title": s.get("title"),
            "fetched_at": s.get("at"), "status": s.get("status"), "why": s.get("why") or None, "skip": s.get("skip"),
            "identity": s.get("identity"), "page_chars": s.get("chars"), "sha1": s.get("sha1"),
            "raw": os.path.join(work_dir, "raw", f"{s.get('id')}.txt") if s.get("status") == "fetched" else None,
            "adopted": picks_by_src.get(s.get("id"), [])})
    ani = st.get("anilist") or {}
    return {
        "collected_at": st.get("done_at"), "opened_at": st.get("opened_at"), "tool": f"_element-harvest {st.get('version')} / 器 {VERSION}",
        "model": st.get("model"), "card_title": (st.get("card") or {}).get("title"), "page_title": (st.get("card") or {}).get("page_title"),
        "anilist": ani if isinstance(ani, dict) else None, "wikipedia": st.get("wiki"),
        "searches": [{"id": q.get("id"), "kind": q.get("kind"), "q": q.get("q"), "at": q.get("at"),
                      "results": [{"n": r.get("n"), "url": r.get("url"), "title": r.get("title")} for r in q.get("results") or []]}
                     for q in st.get("searches") or []],
        "none": st.get("none") or {}, "sources": sources, "use": st.get("auto_use") or {},
        "chars": sum(len(p.get("text") or "") for p in st.get("picks") or []),
    }


def put(stem, title, rec):
    os.makedirs(STORE, exist_ok=True)
    cur = load_store(stem) or {"stem": stem, "title": title, "runs": []}
    if any(r.get("collected_at") == rec.get("collected_at") for r in cur["runs"]):
        return False  # 同じ回は二度入れない(import のやり直しで重ならない)
    cur["title"] = title or cur.get("title")
    cur["runs"].append(rec)
    tmp = store_path(stem) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
    os.replace(tmp, store_path(stem))
    return True


def targets():
    """巻数5以上・見える要素3以下の頁を、巻数の多い順(同数は stem 順)。 索引 = 本番の一覧索引。"""
    with open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8") as f:
        d = json.load(f)
    I = {k: i for i, k in enumerate(d["f"])}
    rows = [r for r in d["d"] if (r[I["max_edition_volumes"]] or 0) >= MIN_VOLS and len(r[I["themes"]] or []) <= MAX_ELEMS]
    rows.sort(key=lambda r: (-(r[I["max_edition_volumes"]] or 0), r[I["slug"]]))
    out = []
    for r in rows:
        slug = r[I["slug"]]
        if os.path.exists(os.path.join(ROOT, "data", "manga.v2", slug + ".yml")):  # ★stem = ファイル名。 公開slugが違う頁は今は飛ばす(数える)
            out.append((slug, r[I["title"]], r[I["max_edition_volumes"]]))
    return out, len(rows)


def log_run(o):
    os.makedirs(HOME, exist_ok=True)
    with open(RUNS, "a", encoding="utf-8") as f:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")


def collect(stem, redo):
    env = dict(os.environ, EH_ROOT=WORK, PYTHONIOENCODING="utf-8")
    args = [sys.executable, os.path.join(ROOT, "scripts", "_element-harvest.py"), "auto", stem, "--model", MODEL] + (["--fresh"] if redo else [])
    os.makedirs(os.path.join(WORK, "_log"), exist_ok=True)
    logp = os.path.join(WORK, "_log", stem + ".txt")
    t = time.time()
    with open(logp, "a", encoding="utf-8") as lf:
        lf.write(f"\n===== {now()} {' '.join(args[2:])}\n")
        lf.flush()
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT, env=env)
        try:
            p.wait(timeout=STEP_TIMEOUT)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            else:
                p.kill()
            return None, f"{STEP_TIMEOUT}秒で終わらない", round(time.time() - t)
    stp = os.path.join(WORK, stem, "state.json")
    if p.returncode != 0 or not os.path.exists(stp):
        tail = open(logp, encoding="utf-8", errors="replace").read()[-300:].strip().splitlines()
        return None, f"exit {p.returncode}: {tail[-1] if tail else ''}", round(time.time() - t)
    with open(stp, encoding="utf-8") as f:
        st = json.load(f)
    if not st.get("done_at"):
        return None, "done まで行かなかった", round(time.time() - t)
    return st, None, round(time.time() - t)


def cmd_run(a):
    if a.stems:
        todo = [(s, None, None) for s in a.stems.split(",") if s]
    else:
        tg, _ = targets()
        todo = [x for x in tg if not os.path.exists(store_path(x[0]))][:a.n]
    print(f"== 器へ集める {len(todo)}作 / {MODEL} / 置き場 {HOME} ==", flush=True)
    started, ok, fails, streak = now(), 0, [], 0
    for i, (stem, title, vols) in enumerate(todo, 1):
        if not a.redo and os.path.exists(store_path(stem)) and not a.stems:
            continue
        print(f"[{i}/{len(todo)}] {stem}{f' ({vols}巻)' if vols else ''} {now()[11:]}", flush=True)
        st, err, sec = collect(stem, a.redo)
        if err:
            fails.append({"stem": stem, "why": err})
            streak += 1
            print(f"   ✖ {err}", flush=True)
            if streak >= 3:
                print("✖ 3作続けて失敗 → 止める(外部サイトかモデルの不調。 様子を見てから run で続きから)", flush=True)
                break
            continue
        streak = 0
        rec = to_record(st, os.path.join(WORK, stem))
        put(stem, title or (st.get("card") or {}).get("title"), rec)
        ok += 1
        u = rec["use"]
        got = sorted({s["domain"] for s in rec["sources"] if s["adopted"]})
        print(f"   ✔ 材料 {rec['chars']:,}字 / 出所 {len(got)}({'・'.join(got) or 'なし'}) / {sec}秒・読み込み {u.get('in', 0):,}・${u.get('cost_usd', 0):.4f}", flush=True)
    log_run({"at": started, "ended": now(), "version": VERSION, "model": MODEL, "asked": len(todo), "ok": ok, "fails": fails})
    print(f"== 終わり: 入れた {ok} / 失敗 {len(fails)} ==", flush=True)


def cmd_import(a):
    n = 0
    for stp in sorted(glob.glob(os.path.join(a.root, "*", "state.json"))):
        d = os.path.dirname(stp)
        stem = os.path.basename(d)
        with open(stp, encoding="utf-8") as f:
            st = json.load(f)
        if not st.get("done_at"):
            print(f"  飛ばす(done まで行っていない): {stem}")
            continue
        dst = os.path.join(WORK, stem)
        if not os.path.exists(dst):  # 作業場ごと移す(raw の全文を器から辿れるように)
            shutil.copytree(d, dst)
        if put(stem, (st.get("card") or {}).get("title"), to_record(st, dst)):
            n += 1
    print(f"器へ入れた {n}作 → {STORE}")


def cmd_show(a):
    s = load_store(a.stem)
    if not s:
        print(f"器に無い: {a.stem}")
        return
    print(f"■ {s['title']} ({s['stem']}) / 集めた回 {len(s['runs'])}")
    for r in s["runs"]:
        print(f"\n— 回 {r['collected_at']} / {r['model']} / {r['tool']} / 材料 {r['chars']:,}字"
              + (f" / 検索用の題「{r['card_title']}」(頁の題「{r['page_title']}」)" if r.get("page_title") else ""))
        if r.get("wikipedia"):
            print(f"  Wikipedia「{r['wikipedia'].get('title')}」同定 {r['wikipedia'].get('identity')}")
        for q in r["searches"]:
            print(f"  検索 {q['at'][11:]} [{q['kind']}]「{q['q']}」→ {len(q['results'])}件")
        for s2 in r["sources"]:
            ad = s2["adopted"]
            print(f"  出所{s2['id']} {s2['fetched_at']} [{s2['kind']}] {s2['domain']} 「{(s2['page_title'] or '')[:40]}」 同定={(s2.get('identity') or {}).get('verdict')}"
                  + (f" → 採用 {sum(len(p['text'] or '') for p in ad):,}字({'・'.join(sorted({p['role'] or '' for p in ad}))})" if ad else f" → 不採用 {s2.get('skip') or s2.get('why') or s2.get('status')}"))
            print(f"     {s2['final_url'] or s2['url']}")
            if a.text:
                for p in ad:
                    print(f"     〔{p['role']}{'・ネタバレ' if p['spoiler'] else ''}〕{p['text']}")
        if r["none"]:
            print("  見つからなかった: " + " / ".join(f"{k}={v}" for k, v in r["none"].items()))


def cmd_status(a):
    tg, n_all = targets()
    have = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(STORE, "*.json"))}
    done = [x for x in tg if x[0] in have]
    chars = zero = 0
    for x in done:
        r = load_store(x[0])["runs"][-1]
        chars += r["chars"]
        zero += r["chars"] == 0
    print(f"対象(巻数{MIN_VOLS}以上・見える要素{MAX_ELEMS}以下) {n_all:,}頁 / うちファイル名=公開slug {len(tg):,}頁")
    print(f"器に在る {len(done):,}作(材料0字 {zero})・材料 計{chars:,}字 / 器の全作品 {len(have):,}")
    nxt = [x for x in tg if x[0] not in have][:5]
    print("次: " + " / ".join(f"{t}({v}巻)" for _, t, v in nxt))
    if os.path.exists(RUNS):
        last = [json.loads(l) for l in open(RUNS, encoding="utf-8") if l.strip()][-1:]
        for o in last:
            print(f"最後に流した回 {o['at']}〜{o['ended'][11:]} 入れた {o['ok']}/{o['asked']} 失敗 {len(o['fails'])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run"); p.add_argument("--n", type=int, default=20); p.add_argument("--stems"); p.add_argument("--redo", action="store_true"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("import"); p.add_argument("root"); p.set_defaults(f=cmd_import)
    p = sp.add_parser("show"); p.add_argument("stem"); p.add_argument("--text", action="store_true"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("status"); p.set_defaults(f=cmd_status)
    a = ap.parse_args()
    a.f(a)
