#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web 材料の器 = Haiku が Web で集めた情報を、漫画ごとに「いつ・どこで・何を」付きで貯める。 2026-10-29 新設。

  python scripts/_web-material.py status                 # 器の中身と、次に集める作品
  python scripts/_web-material.py run --n 20             # 次の20作を集める(1作ずつ・続きから・集めるだけ = 判定しない)
  python scripts/_web-material.py run --stems a,b        # 作品を指して集める(--redo で集め直し = 前の回も器に残る)
  python scripts/_web-material.py show <stem> [--text]   # 1作の中身(--text で採った段落の原文も)
  python scripts/_web-material.py import <EH_ROOT>       # 別の置き場で集めた結果を器へ移す(試し30頁など)
  python scripts/_web-material.py judge --n 20           # 器の材料から付与案を作る(Haiku・案だけ = 頁に書かない。 まだ案の無い作品を巻数順に)
  python scripts/_web-material.py judge --stems a,b [--redo]
  python scripts/_web-material.py rebuild [--stems a,b]  # 語彙(wamei-tags.yml)や付与の決まりを変えた後、判定済みの案を保存済みの答えから作り直す(モデルを呼ばない・0円)
  python scripts/_web-material.py second --stems a,b [--parallel 3] [--redo]  # 2回目の判定を回して1回目と合わせる(0語の頁は2回判定+lift / 語がある頁は語彙に足した語の判定だけ足す)
  python scripts/_web-material.py apply --stems a,b [--go "<Goの発話>"]  # 付与案を seed へ書く(★ユーザの Go が要る。 --go が無ければ件数だけ数えて何も書かない。 頁には書かない = 反映は別。 足すだけ)

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
import argparse, datetime, glob, importlib.util, json, os, shutil, subprocess, sys, time

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
JUDGE_MODEL = "claude-haiku-5-5"  # ★2026-10-30 ユーザ裁定「Aでいく」= 付与案は Haiku(20作の比べ: Sonnet の1/8の費用・語は多いが芯の付けすぎ → 付与 v0.21 で決まりを補強)
JUDGE_LEDGER = os.path.join(WORK, "assign-ledger.jsonl")  # _element-assign.py が EH_ROOT=WORK の時に書く台帳


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


def judged(stem):
    s = load_store(stem) or {}
    return s.get("judges") or []


def judge_one(stem):
    env = dict(os.environ, EH_ROOT=WORK, PYTHONIOENCODING="utf-8")
    args = [sys.executable, os.path.join(ROOT, "scripts", "_element-assign.py"), "run", stem, "--model", JUDGE_MODEL]
    logp = os.path.join(WORK, "_log", stem + ".txt")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    n0 = sum(1 for _ in open(JUDGE_LEDGER, encoding="utf-8")) if os.path.exists(JUDGE_LEDGER) else 0
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
            return None, f"{STEP_TIMEOUT}秒で終わらない"
    new = [json.loads(l) for i, l in enumerate(open(JUDGE_LEDGER, encoding="utf-8")) if i >= n0 and l.strip()] if os.path.exists(JUDGE_LEDGER) else []
    new = [r for r in new if r.get("stem") == stem]
    if p.returncode != 0 or not new:
        tail = open(logp, encoding="utf-8", errors="replace").read()[-300:].strip().splitlines()
        return None, f"exit {p.returncode}: {tail[-1] if tail else ''}"
    return new[-1], None


def cmd_judge(a):
    """器の材料から付与案(表に出す案・隠して持つ語・新しい語)を作り、器に「いつ・どのモデル・どの版」付きで残す。 頁には書かない。"""
    if a.stems:
        todo = [s for s in a.stems.split(",") if s]
    else:
        tg, _ = targets()
        todo = [x[0] for x in tg if load_store(x[0]) and not judged(x[0])
                and load_store(x[0])["runs"][-1]["chars"] > 0][:a.n]
    print(f"== 付与案 {len(todo)}作 / {JUDGE_MODEL} ==", flush=True)
    started, ok, fails, streak, cost = now(), 0, [], 0, 0.0
    for i, stem in enumerate(todo, 1):
        s = load_store(stem)
        if not s:
            print(f"[{i}/{len(todo)}] {stem} ✖ 器に無い(先に run)", flush=True)
            continue
        if judged(stem) and not a.redo:
            continue
        r, err = judge_one(stem)
        if err:
            fails.append({"stem": stem, "why": err})
            streak += 1
            print(f"[{i}/{len(todo)}] {stem} ✖ {err}", flush=True)
            if streak >= 3:
                print("✖ 3作続けて失敗 → 止める", flush=True)
                break
            continue
        streak = 0
        s.setdefault("judges", []).append({"at": r["at"], "model": r.get("model"), "version": r.get("version"), "material_at": s["runs"][-1]["collected_at"],
                                           "core": r["core"], "sub": r["sub"], "new": r["new"], "cost_usd": r.get("cost_usd")})
        tmp = store_path(stem) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
        os.replace(tmp, store_path(stem))
        ok += 1
        cost += r.get("cost_usd") or 0
        print(f"[{i}/{len(todo)}] {stem} ✔ 表に出す案 {len(r['core'])}: {'・'.join(r['core'])}", flush=True)
    log_run({"at": started, "ended": now(), "kind": "judge", "version": VERSION, "model": JUDGE_MODEL, "asked": len(todo), "ok": ok, "fails": fails, "cost_usd": round(cost, 4)})
    print(f"== 終わり: 案 {ok} / 失敗 {len(fails)} / ${cost:.3f} ==", flush=True)


def _mod(name):
    sp = importlib.util.spec_from_file_location(name.strip("_").replace("-", "_"), os.path.join(ROOT, "scripts", name + ".py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _mods():
    os.environ["EH_ROOT"] = WORK  # _element-assign.py の置き場(import より前に決める)
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    return _mod("_element-assign"), _mod("_element-review")


def _merge(ea, rv, V, raw, mode):
    """生の答え(1回 or 2回)→ (合わせた答え, 2回とも芯の語の集合, lift の語)。 モデルを呼ばずに何度でも作り直せる(rebuild もここを通る)。
    mode=agree(1回目で表が0語だった頁): _element-review.agree = 2回とも芯・芯+在る=芯 / 片方だけ芯=在る / 表0なので lift(2回とも「在る」・片方が芯でもう片方は挙げず を3語まで表へ)
    mode=fill (語がある頁): 1回目のまま。 2回目は、1回目が見ていない候補(語彙に足した語)の判定だけ使う = 今ある語をゆらさない
    どちらも、1回目が見ていない候補は2回目の判定をそのまま入れる(agree は judged に2回目だけの語を入れないため)。"""
    if len(raw) < 2:
        return raw[0], None, None
    a1, a2 = raw[0], raw[1]
    if mode == "agree":
        ans, both, agreed = rv.agree(a1, a2, V)
    else:
        ans, both, agreed = {g: list(a1.get(g) or []) for g in ("judged", "added", "new_words")}, None, None
    canon = lambda w: V["alias"].get(ea.bare(w), ea.bare(w))  # noqa: E731
    seen = {canon(x.get("word")) for g in ("judged", "added", "new_words") for x in (a1.get(g) or []) if isinstance(x, dict)}
    for x in a2.get("judged") or []:
        if isinstance(x, dict) and canon(x.get("word")) not in seen:
            ans["judged"].append(dict(x))
    return ans, both, agreed


def _record(stem, ea, rows, use_cost, extra):
    """器の judges に1行足す(直前と同じ案なら足さない)。 → (足したか, 表に出す案, 直前の行)"""
    core = [e["word"] for e in rows if e.get("cls") == "表"]
    sub = [e["word"] for e in rows if e.get("cls") == "隠し"]
    new = [e["word"] for e in rows if e["vocab"] == "新しい語"]
    s = load_store(stem)
    last = s["judges"][-1]
    if (core, sub, new) == (last.get("core"), last.get("sub"), last.get("new")):
        return False, core, last
    s["judges"].append({"at": now(), "model": extra.pop("model", last.get("model")), "version": ea.VERSION, "material_at": s["runs"][-1]["collected_at"],
                        "core": core, "sub": sub, "new": new, "cost_usd": use_cost, **extra})
    tmp = store_path(stem) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, store_path(stem))
    return True, core, last


def cmd_rebuild(a):
    """語彙(wamei-tags.yml)や付与の決まりを変えた後、判定済みの作品の付与案を作り直す。 保存済みの答え(work/<stem>/assign/assign-answer.json)を
    検査し直すだけ = モデルを呼ばない・0円。 案が変わった作品だけ、器の judges に「作り直し」を足す。 頁には書かない。
    2回判定した作品(second)は、残してある2回の生の答えから同じ合わせ方で作り直す。
    ★語彙に足した語は、元の答えにモデルが自分で挙げていた語(新しい語)にだけ効く。 モデルが見ていなかった語は「判定が返らなかった候補」に出る(判定し直すなら second)。"""
    ea, rv = _mods()
    V = ea.load_vocab()
    names = a.stems.split(",") if a.stems else sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(STORE, "*.json")))
    todo = [s for s in names if s and judged(s)]
    print(f"== 付与案の作り直し {len(todo)}作 / 語彙 {len(V['display'])}語 / モデルは呼ばない ==", flush=True)
    changed = skipped = 0
    for stem in todo:
        ap = os.path.join(WORK, stem, "assign", "assign-answer.json")
        if not os.path.exists(ap):
            skipped += 1
            print(f"  飛ばす(保存済みの答えが無い): {stem}", flush=True)
            continue
        with open(ap, encoding="utf-8") as f:
            d = json.load(f)
        m = ea.load_material(stem)
        cands = ea.find_candidates(m, V)
        use = d.get("use") or {"model": "(保存済みの答え)"}
        ans, both, agreed = _merge(ea, rv, V, d.get("raw") or [d.get("answer", d)], d.get("mode"))
        _, rows, _, _, _ = ea.make_proposal(stem, m, V, cands, ans, use, not_spoiler=both or (), lift=agreed or ())
        did, core, last = _record(stem, ea, rows, 0, {"rebuild": True, "model": use.get("model")})
        if not did:
            continue
        changed += 1
        add = [w for w in core if w not in (last.get("core") or [])]
        gone = [w for w in (last.get("core") or []) if w not in core]
        print(f"  {stem}: 表に出す案 {len(last.get('core') or [])}→{len(core)}" + (f" 増 {'・'.join(add)}" if add else "") + (f" 減 {'・'.join(gone)}" if gone else ""), flush=True)
    print(f"== 終わり: 案が変わった {changed}作 / 変わらず {len(todo) - changed - skipped}作 / 飛ばした {skipped}作 ==", flush=True)


def cmd_second(a):
    """2回目の判定を回して、1回目と合わせる(頁には書かない)。
    ・1回目で表が0語だった頁 = 2回判定+lift(_element-review.agree)。 見直し(手元の材料)と同じ合わせ方
    ・語がある頁 = 1回目のまま、語彙に足した語など1回目が見ていない候補の判定だけ2回目から足す
    生の答えは work/<stem>/assign/assign-answer.run1.json / run2.json に残る(合わせ方を変えても rebuild でモデルを呼ばずに効く)。
    並列で回し、3作続けて失敗したら止める。 途中で止めても、2回目が済んだ作品は飛ばして続きから。"""
    import concurrent.futures
    ea, rv = _mods()
    import _lean_claude
    V = ea.load_vocab()
    todo = [s for s in a.stems.split(",") if s and judged(s)]
    print(f"== 2回目の判定 {len(todo)}作 / {JUDGE_MODEL} / 並列 {a.parallel} / 語彙 {len(V['display'])}語 ==", flush=True)
    started, ok, fails, streak, cost = now(), 0, [], 0, 0.0
    jobs, ready = [], []
    for stem in todo:
        d = os.path.join(WORK, stem, "assign")
        cur, p1, p2 = (os.path.join(d, n) for n in ("assign-answer.json", "assign-answer.run1.json", "assign-answer.run2.json"))
        if not os.path.exists(p1):
            if not os.path.exists(cur):
                fails.append({"stem": stem, "why": "1回目の答えが無い"})
                print(f"  ✖ {stem}: 1回目の答えが無い", flush=True)
                continue
            shutil.copyfile(cur, p1)  # 1回目の生の答えを守る(この後 assign-answer.json は合わせた答えで置き換わる)
        with open(p1, encoding="utf-8") as f:
            r1 = json.load(f)
        with open(cur, encoding="utf-8") as f:
            mode = json.load(f).get("mode")
        if not mode:
            mode = "fill" if (load_store(stem)["judges"][-1].get("core")) else "agree"
        m = ea.load_material(stem)
        cands = ea.find_candidates(m, V)
        job = {"stem": stem, "m": m, "cands": cands, "r1": r1, "p2": p2, "mode": mode}
        if os.path.exists(p2) and not a.redo:
            with open(p2, encoding="utf-8") as f:
                job["r2"] = json.load(f)
            ready.append(job)
        else:
            job["prompt"] = ea.build_prompt(m, V, cands)
            jobs.append(job)

    def ask(job):
        ans, use = _lean_claude.ask(job["prompt"], ea.SCHEMA, JUDGE_MODEL, system="あなたは漫画データベースの分類の助手。指示された JSON の形だけで答える。")
        return {"use": use, "answer": ans, "at": now(), "vocab": len(V["display"])}

    def settle(job):
        nonlocal ok, cost
        stem, r1, r2 = job["stem"], job["r1"], job["r2"]
        u1, u2 = r1.get("use") or {}, r2.get("use") or {}
        use = {"model": f"{u2.get('model') or JUDGE_MODEL} x2", "sec": round((u1.get("sec") or 0) + (u2.get("sec") or 0), 1), "in": (u1.get("in") or 0) + (u2.get("in") or 0),
               "out": (u1.get("out") or 0) + (u2.get("out") or 0), "cost_usd": round((u1.get("cost_usd") or 0) + (u2.get("cost_usd") or 0), 6)}
        raw = [r1.get("answer", r1), r2["answer"]]
        ans, both, agreed = _merge(ea, rv, V, raw, job["mode"])
        _, rows, ok_rows, bad, missing = ea.make_proposal(stem, job["m"], V, job["cands"], ans, use, not_spoiler=both or (), lift=agreed or ())
        with open(os.path.join(WORK, stem, "assign", "assign-answer.json"), "w", encoding="utf-8") as f:
            json.dump({"use": use, "answer": ans, "raw": raw, "mode": job["mode"]}, f, ensure_ascii=False, indent=1)
        lifted = [e["word"] for e in rows if e.get("lift")]
        did, core, last = _record(stem, ea, rows, u2.get("cost_usd") or 0, {"second": True, "mode": job["mode"], "lifted": lifted, "model": use["model"]})
        with open(JUDGE_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now(), "stem": stem, "title": job["m"]["card"]["title"], "version": ea.VERSION, **u2, "core": core,
                                "sub": [e["word"] for e in rows if e.get("cls") == "隠し"], "new": [e["word"] for e in rows if e["vocab"] == "新しい語"],
                                "not": sum(1 for x in ok_rows if x["tier"] == "違う"), "rejected": len(bad), "missing": len(missing), "second": True}, ensure_ascii=False) + "\n")
        ok += 1
        cost += u2.get("cost_usd") or 0
        add = [w for w in core if w not in (last.get("core") or [])]
        gone = [w for w in (last.get("core") or []) if w not in core]
        print(f"[{ok + len(fails)}/{len(todo)}] {stem} ✔ {job['mode']} 表に出す案 {len(last.get('core') or [])}→{len(core)}" + (f" 増 {'・'.join(add)}" if add else "")
              + (f" 減 {'・'.join(gone)}" if gone else "") + (f" (lift {'・'.join(lifted)})" if lifted else ""), flush=True)

    for job in ready:  # 2回目が済んでいる作品は合わせ直すだけ
        settle(job)
    if jobs:
        with concurrent.futures.ThreadPoolExecutor(a.parallel) as ex:
            futs = {ex.submit(ask, j): j for j in jobs}
            for fu in concurrent.futures.as_completed(futs):
                job = futs[fu]
                try:
                    r2 = fu.result()
                except Exception as e:  # LeanError・時間切れなど
                    fails.append({"stem": job["stem"], "why": str(e)[:200]})
                    streak += 1
                    print(f"[{ok + len(fails)}/{len(todo)}] {job['stem']} ✖ {str(e)[:120]}", flush=True)
                    if streak >= 3:
                        print("✖ 3作続けて失敗 → 止める(モデルの不調。 様子を見てから同じコマンドで続きから)", flush=True)
                        for f2 in futs:
                            f2.cancel()
                        break
                    continue
                streak = 0
                with open(job["p2"], "w", encoding="utf-8") as f:
                    json.dump(r2, f, ensure_ascii=False, indent=1)
                job["r2"] = r2
                settle(job)
    log_run({"at": started, "ended": now(), "kind": "second", "version": VERSION, "model": JUDGE_MODEL, "asked": len(todo), "ok": ok, "fails": fails, "cost_usd": round(cost, 4)})
    print(f"== 終わり: 合わせた {ok} / 失敗 {len(fails)} / ${cost:.3f} ==", flush=True)


def _applied_stems():
    """seed へ付与済みの頁(element-assign-changelog.jsonl に「element-assign apply」の行が在る頁)"""
    p = os.path.join(ROOT, "data", "seeds", "element-assign-changelog.jsonl")
    out = set()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    d = json.loads(ln)
                    if d.get("op") == "element-assign apply":
                        out.add(d.get("slug"))
    return out


def cmd_apply(a):
    """器の付与案を本番の seed へ書く(★ユーザの Go が要る。 --go が無ければ件数だけ数えて何も書かない)。 頁(manga.v2)・索引は触らない = 頁への反映は別(_reflect-targeted.py)。
    1作ずつ _element-assign.py apply に任せる(同じ計算 plan_apply): 要素 → tags-enrich-2425.json / ジャンル → genre-append.yml / 隠し要素 → element-hidden.json / 記録 → element-assign-changelog.jsonl。
    ★足すだけ: 要素・ジャンルは今あるものを消さない。 隠し要素(羅針盤の近さにだけ使う)も「付与案の鍵 + 今ある鍵」にして置き換えない(今回表に上がった語は鍵から外す)。
    書く前に4つの seed を丸ごと .cache/web-material-apply-bak-<時刻>/ に退避する。 済んだ作品は「既に付与案どおり」で飛ぶ = 止めても同じコマンドで続きから。"""
    import collections, contextlib, io, re
    import yaml
    ea, _ = _mods()
    V = ea.load_vocab()
    ea.load_vocab = lambda: V  # 作品ごとに語彙を読み直さない
    S = os.path.join(ROOT, "data", "seeds")
    seeds = [os.path.join(S, n) for n in ("tags-enrich-2425.json", "genre-append.yml", "element-hidden.json", "element-assign-changelog.jsonl")]
    todo = [s for s in a.stems.split(",") if s]
    go = (a.go or "").strip()

    def hidden_now(pub):
        if not os.path.exists(ea.HIDDEN_SEED):
            return []
        with open(ea.HIDDEN_SEED, encoding="utf-8") as f:
            return list((json.load(f).get(pub) or {}).get("keys") or [])

    if not go:  # 試運転 = 数えるだけ
        with open(seeds[0], encoding="utf-8") as f:
            tags = json.load(f)
        gdone = collections.defaultdict(set)
        with open(seeds[1], encoding="utf-8") as f:
            for e in (yaml.safe_load(f) or {}).get("additions") or []:
                gdone[e.get("slug")].update(e.get("add") or [])
        n = collections.Counter()
        add_w, gen_w, blocked_all, missing = collections.Counter(), collections.Counter(), [], []
        for stem in todo:
            pj = os.path.join(WORK, stem, "assign", "assign-proposal.json")
            page = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
            if not os.path.exists(pj) or not os.path.exists(page):
                missing.append(stem)
                continue
            with open(pj, encoding="utf-8") as f:
                prop = json.load(f)
            with open(page, encoding="utf-8") as f:
                ptags = (yaml.load(f, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader)) or {}).get("tags") or []
            names, blocked, _h, _k = ea.plan_apply(prop, V, ptags)
            if blocked:
                blocked_all.append((stem, blocked))
            before = list(tags.get(stem) or [])
            new = [x for x in names if x not in before]
            gadd = [g for g in prop.get("genres_add") or [] if g in V["genres"] and g not in (prop.get("genres_now") or []) and g not in gdone[stem]]
            n["頁"] += 1
            n["要素を足す頁"] += bool(new)
            n["足す語"] += len(new)
            n["ジャンルを足す頁"] += bool(gadd)
            add_w.update(V["tag_ja"].get(x) or x for x in new)
            gen_w.update(gadd)
        print(f"== 付与(試運転・何も書かない) {len(todo)}作 ==")
        print(" / ".join(f"{k} {v:,}" for k, v in n.items()) + f" / 付与案か頁が無い {len(missing)}")
        print("足す語の多い順:", "・".join(f"{w}{c}" for w, c in add_w.most_common(30)))
        print("足すジャンル:", "・".join(f"{V['genres'].get(g, g)}{c}" for g, c in gen_w.most_common()) or "なし")
        for stem, b in blocked_all:
            print(f"  ✖ 語彙に無くて足せない語: {stem} {'・'.join(b)}")
        for stem in missing:
            print(f"  ✖ 付与案か頁が無い: {stem}")
        print('★書くには --go "<ユーザのGo発話>"(本番の seed に書く。 頁への反映は別)')
        return

    # 隠し要素は置き換えず、今ある鍵を残す(足すだけ。 _element-assign.py の hidden_keys を、この実行の間だけ差し替える)
    orig, cur = ea.hidden_keys, {}

    def keep_hidden(prop):
        new = orig(prop)
        shown = set()
        for e in prop["rows"]:
            if e.get("cls") == "表":
                shown.add(e["word"])
                if (e.get("ani") or {}).get("en"):
                    shown.add("ani:" + e["ani"]["en"])
        return new + [k for k in cur.get("old", []) if k not in new and k not in shown]

    ea.hidden_keys = keep_hidden
    started = now()
    bak = os.path.join(ROOT, ".cache", f"web-material-apply-bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    os.makedirs(bak, exist_ok=True)
    for p in seeds:
        shutil.copyfile(p, os.path.join(bak, os.path.basename(p)))
    rel = os.path.relpath(bak, ROOT).replace("\\", "/")
    print(f"== 付与 {len(todo)}作 / 退避 {rel} / 頁・索引は触らない ==", flush=True)
    wrote = noop = 0
    added = gen = 0
    fails = []
    for i, stem in enumerate(todo, 1):
        cur["old"] = hidden_now(ea.load_material(stem)["card"]["slug"])
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                ea.cmd_apply(argparse.Namespace(stem=stem, go=go))
        except SystemExit:
            fails.append({"stem": stem, "why": buf.getvalue().strip()[-300:]})
            print(f"[{i}/{len(todo)}] {stem} ✖ {buf.getvalue().strip()[-200:]}", flush=True)
            print("✖ 止める(直さずに流し直さない。 済んだ作品は同じコマンドで飛ばして続きから)", flush=True)
            break
        out = buf.getvalue()
        if "既に付与案どおり" in out:
            noop += 1
            continue
        wrote += 1
        m1, m2 = re.search(r"要素 \+(\d+): (.*)", out), re.search(r"ジャンル \+(\d+): (.*)", out)
        added += int(m1.group(1)) if m1 else 0
        gen += int(m2.group(1)) if m2 else 0
        print(f"[{i}/{len(todo)}] {stem} ✔ 要素 +{m1.group(1) if m1 else 0}" + (f": {m1.group(2)}" if m1 and m1.group(1) != "0" else "")
              + (f" / ジャンル +{m2.group(1)}: {m2.group(2)}" if m2 and m2.group(1) != "0" else ""), flush=True)
    ea.hidden_keys = orig
    log_run({"at": started, "ended": now(), "kind": "apply", "version": VERSION, "asked": len(todo), "ok": wrote, "noop": noop, "fails": fails, "go": go, "backup": rel})
    print(f"== 終わり: 書いた {wrote}作(要素 +{added}語・ジャンル +{gen}) / 既に付与案どおり {noop}作 / 止まった {len(fails)}作 ==", flush=True)
    print("次: 頁への反映は別(「反映して」= _reflect-targeted.py)。 羅針盤の配布ファイル = python scripts/_build-compass-hidden.py(反映と一緒に commit)", flush=True)


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
    nj = sum(1 for x in done if judged(x[0]))
    na = sum(1 for x in done if x[0] in _applied_stems())
    print(f"付与案あり {nj:,}作 / うち seed へ付与済み {na:,}作(頁への反映は別)")
    nxt = [x for x in tg if x[0] not in have][:5]
    print("次: " + " / ".join(f"{t}({v}巻)" for _, t, v in nxt))
    if os.path.exists(RUNS):
        last = [json.loads(l) for l in open(RUNS, encoding="utf-8") if l.strip()][-2:]
        for o in last:
            print(f"最後の{ {'judge': '付与案', 'second': '2回目', 'apply': '付与'}.get(o.get('kind'), '収集') } {o['at']}〜{o['ended'][11:]} {o['ok']}/{o['asked']} 失敗 {len(o['fails'])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run"); p.add_argument("--n", type=int, default=20); p.add_argument("--stems"); p.add_argument("--redo", action="store_true"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("import"); p.add_argument("root"); p.set_defaults(f=cmd_import)
    p = sp.add_parser("show"); p.add_argument("stem"); p.add_argument("--text", action="store_true"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("status"); p.set_defaults(f=cmd_status)
    p = sp.add_parser("judge"); p.add_argument("--n", type=int, default=20); p.add_argument("--stems"); p.add_argument("--redo", action="store_true"); p.set_defaults(f=cmd_judge)
    p = sp.add_parser("rebuild"); p.add_argument("--stems"); p.set_defaults(f=cmd_rebuild)
    p = sp.add_parser("second"); p.add_argument("--stems", required=True); p.add_argument("--parallel", type=int, default=3); p.add_argument("--redo", action="store_true"); p.set_defaults(f=cmd_second)
    p = sp.add_parser("apply"); p.add_argument("--stems", required=True); p.add_argument("--go", default=""); p.set_defaults(f=cmd_apply)
    a = ap.parse_args()
    a.f(a)
