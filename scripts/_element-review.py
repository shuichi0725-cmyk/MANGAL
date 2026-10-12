#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ジャンル・要素の見直しを、見直しの表(_gen-element-review-queue.py)の順に N 件ずつ流す。 2026-10-12 新設。

  run [--n 100] [--loops 1] [--parallel 3] [--model claude-haiku-5-5] [--route L]
        表の「未」を順番どおりに N 件: 手元の材料で束を作る → モデルが判定 → 道具が検査 → 付与案 + 台帳。 --loops で続けて何回も
  summary [--batch <名前>]     回ごとの結果を1枚(TSV)に / 名前なしで回の一覧
  sample <batch> [--k 50]      点検用に無作為に抜く(付与案の要点と根拠)

★案を作るだけ。 本番データ・seed には書かない(書くのは _element-assign.py apply。 ユーザの Go が要る)。
★モデルは毎回「土台なし」で1回だけ呼ぶ(会話を持ち越さない)。 進み具合は台帳に残るので、止めても次は続きから。
★材料は人が書いた一次の文だけ(楽天・BookLive の紹介文)。 AI が書いたキャッチ・あらすじ・巻説明は根拠にしない。
  判定の決まり・検査・付与案の仕分けは _element-assign.py と同じもの(ここは束づくりと流し方だけ)。

置き場: 台帳 = data/element-harvest/review-ledger.jsonl(git 追跡)/ 束と付与案 = .cache/element-harvest/<stem>/ / 回の要約 = .cache/element-harvest/_review/
"""
import argparse, collections, concurrent.futures, datetime, gzip, importlib.util, json, os, random, subprocess, sys, threading

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
VERSION = "r0.1"
BASE = os.path.join(ROOT, ".cache", "element-harvest")
LEDGER = os.path.join(ROOT, "data", "element-harvest", "review-ledger.jsonl")
CAPS = os.path.join(BASE, "_local", "captions.jsonl")
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
MAX_CHARS = 3000   # 1作に渡す材料の上限
CAP_CLIP = 600     # 1巻の紹介文の上限
EARLY = 3          # 先頭からこの数の紹介文 = 物語。 それより後の巻 = 展開(ネタバレ扱い = その語は表に出さない)
MAX_CAPS = 8
LOCK = threading.Lock()


def mod(name):
    spec = importlib.util.spec_from_file_location(name.strip("_").replace("-", "_"), os.path.join(ROOT, "scripts", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def jl(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    yield json.loads(l)


def next_stems(n, route):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_gen-element-review-queue.py"), "--next", str(n), "--route", route],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        print(r.stderr)
        sys.exit(1)
    return [s for s in r.stdout.split() if s]


def anilist_self(aids):
    """dump から、その漫画自身のエントリだけ引く(関連作は辿らない = API を使わない)。 → {id: entry}"""
    out, need = {}, set(aids)
    if not need or not os.path.exists(DUMP):
        return out
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("id") in need:
                out[e["id"]] = {"id": e["id"], "group": "自分", "type": e.get("type"), "format": e.get("format"),
                                "year": (e.get("startDate") or {}).get("year"), "popularity": e.get("popularity"),
                                "title": (e.get("title") or {}).get("native"), "genres": e.get("genres") or [],
                                "tags": [{"name": t["name"], "rank": t.get("rank") or 0, "category": t.get("category") or "", "adult": bool(t.get("isAdult")),
                                          "spoiler": bool(t.get("isMediaSpoiler") or t.get("isGeneralSpoiler"))} for t in (e.get("tags") or []) if isinstance(t, dict)]}
                if len(out) == len(need):
                    break
    return out


def local_bundle(eh, card, caps, bl, ani):
    """手元の材料だけで、要素付与の道具が読める束(material.json と同じ形)を作る。"""
    sources, picks, total = [], [], 0

    def add(domain, title, text, as_):
        nonlocal total
        text = text[:CAP_CLIP]
        if len(text) < 40 or total + len(text) > MAX_CHARS:
            return
        sid = len(sources) + 1
        sources.append({"id": sid, "kind": "手元", "origin": "local", "domain": domain, "url": "", "title": title, "identity": "OK", "same": None})
        picks.append({"id": len(picks) + 1, "src": sid, "kind": "手元", "as": as_, "spoiler": as_ == "展開", "auto": True, "text": text})
        total += len(text)

    if bl:
        add("booklive(紹介文)", card["title"], bl, "物語")
    for i, c in enumerate([c for c in caps if not c["ad"]][:MAX_CAPS]):
        add("books.rakuten.co.jp", c["title"], c["cap"], "物語" if i < EARLY else "展開")
    ents = [ani] if ani else []
    a = {"entries": ents, "skipped": [], "note": "" if ani else "頁に anilist_id が無い"}
    return {"stem": card["stem"], "version": VERSION, "bundle_version": VERSION, "model": "(手元の材料・機械)", "made_at": now(), "local": True,
            "card": {k: card[k] for k in ("slug", "title", "authors", "original_authors", "publisher", "imprint", "magazine", "year_started", "year_ended",
                                          "volumes", "demographic", "genres", "anime_adapted", "synopsis", "catch")},
            "anilist": {"entries": [{k: e[k] for k in ("id", "group", "format", "year", "popularity", "title", "genres")} | {"main": True} for e in ents],
                        "tags": eh.anilist_merged(a), "skipped": []},
            "wikipedia": {"title": None, "categories": []}, "sources": sources, "picks": picks, "none": {}}, total


def one(stem, ctx, a, batch):
    ea, eh, V = ctx["ea"], ctx["eh"], ctx["V"]
    card = eh.build_card(stem)
    cap = ctx["caps"].get(card["slug"]) or ctx["caps"].get(stem) or []
    bundle, chars = local_bundle(eh, card, cap, ctx["bl"].get(card["slug"]), ctx["ani"].get(int(card["anilist_id"])) if card.get("anilist_id") else None)
    d = eh.wdir(stem)
    os.makedirs(d, exist_ok=True)
    mp = os.path.join(d, "material.json")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            if not json.load(f).get("local"):  # Web で集めた束が在る頁は上書きしない
                return {"stem": stem, "skip": "Web の束が在る"}
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=1)
    m = ea.load_material(stem)
    cands = ea.find_candidates(m, V)
    row = {"at": now(), "batch": batch, "stem": stem, "slug": card["slug"], "title": card["title"], "route": a.route, "version": f"{VERSION}/{ea.VERSION}", "chars": chars}
    if not m["picks"]:
        ans, use = {"judged": [], "added": [], "new_words": []}, {"model": "(材料なし・モデルを呼ばない)", "sec": 0, "in": 0, "out": 0, "cost_usd": 0}
    else:
        ans, use = ctx["lean"].ask(ea.build_prompt(m, V, cands), ea.SCHEMA, a.model, system="あなたは漫画データベースの分類の助手。指示された JSON の形だけで答える。", effort=a.effort or None)
    with LOCK:  # 付与案づくりは台帳・ファイルに書くので1件ずつ
        with open(os.path.join(ea.adir(stem), "assign-answer.json"), "w", encoding="utf-8") as f:
            json.dump({"use": use, "answer": ans}, f, ensure_ascii=False, indent=1)
        out, rows, ok, bad, missing = ea.make_proposal(stem, m, V, cands, ans, use)
        with open(os.path.join(ea.adir(stem), "assign-proposal.json"), encoding="utf-8") as f:
            gadd = json.load(f).get("genres_add") or []
        row.update({**use, "show": [e["word"] for e in rows if e.get("cls") == "表"],
                    "show_src": ["両" if e["ani"] and e["mat"] else "A" if e["ani"] else "材" for e in rows if e.get("cls") == "表"],
                    "hide": [e["word"] for e in rows if e.get("cls") == "隠し"], "new": [e["word"] for e in rows if e["vocab"] == "新しい語"],
                    "genres_now": card["genres"], "genres_add": gadd, "genres_mat": [e["word"] for e in rows if e["kind"] == "ジャンル"],
                    "not": sum(1 for x in ok if x["tier"] == "違う"), "rejected": len(bad), "missing": len(missing), "elements_now": len(card["tags_on_page"])})
        with open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def cmd_run(a):
    ea, eh = mod("_element-assign"), mod("_element-harvest")
    import _lean_claude
    ctx = {"ea": ea, "eh": eh, "lean": _lean_claude, "V": ea.load_vocab()}
    ctx["caps"] = {o["slug"]: o["caps"] for o in jl(CAPS)}
    ctx["bl"] = {o["slug"]: o["desc"] for o in jl(os.path.join(ROOT, ".cache", "booklive-desc.jsonl")) if o.get("desc")}
    if not ctx["caps"]:
        print("✖ 手元の材料の束が無い → python scripts/_gen-element-review-queue.py --material")
        sys.exit(1)
    for loop in range(a.loops):
        stems = next_stems(a.n, a.route)
        if not stems:
            print("表の「未」が無い(この経路は終わり)")
            return
        batch = f"{a.route}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        aids = {}
        for s in stems:  # 頁の anilist_id だけ先に引く(dump は1回の走査で済ませる)
            p = os.path.join(ROOT, "data", "manga.v2", s + ".yml")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("anilist_id:"):
                            v = line.split(":", 1)[1].strip()
                            if v.isdigit():
                                aids[s] = int(v)
                            break
        ctx["ani"] = anilist_self(aids.values())
        print(f"== 回 {batch} == {len(stems)}件・並列 {a.parallel}・{a.model}{' effort=' + a.effort if a.effort else ''}", flush=True)
        done = fail = 0
        with concurrent.futures.ThreadPoolExecutor(a.parallel) as ex:
            futs = {ex.submit(one, s, ctx, a, batch): s for s in stems}
            for fu in concurrent.futures.as_completed(futs):
                s = futs[fu]
                try:
                    r = fu.result()
                except _lean_claude.LeanError as e:
                    fail += 1
                    print(f"  ■ {s}: モデルの失敗(台帳に書かない): {e}", flush=True)
                    if fail >= 3:
                        print("■ 中断: モデルの失敗が3件。 残りは次の回に回る(使用量の上限かもしれない)", flush=True)
                        for f2 in futs:
                            f2.cancel()
                        break
                    continue
                done += 1
                if r.get("skip"):
                    print(f"  - {s}: {r['skip']}", flush=True)
                else:
                    print(f"  [{done}/{len(stems)}] {r['title'][:24]}: 表 {len(r['show'])} {'・'.join(r['show'])} / 隠し {len(r['hide'])} / ジャンル+ {','.join(r['genres_add'] + r['genres_mat']) or '-'} / {r.get('sec')}秒", flush=True)
        write_summary(batch)
        if fail >= 3:
            sys.exit(2)


def write_summary(batch):
    rows = [r for r in jl(LEDGER) if r.get("batch") == batch]
    d = os.path.join(BASE, "_review")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, batch + ".tsv")
    with open(p, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("stem\ttitle\t材料字数\t今の要素数\t表に出す\t出どころ\t隠して持つ\t新しい語\t今のジャンル\t足すジャンル(AniList)\t材料からのジャンル\t弾き\t秒\n")
        for r in rows:
            f.write("\t".join(str(x) for x in (r["stem"], r["title"], r["chars"], r["elements_now"], "・".join(r["show"]), "".join(r["show_src"]), "・".join(r["hide"]),
                                               "・".join(r["new"]), ",".join(r["genres_now"]), ",".join(r["genres_add"]), "・".join(r["genres_mat"]), r["rejected"], r.get("sec"))) + "\n")
    n = len(rows) or 1
    w = collections.Counter(x for r in rows for x in r["show"])
    print(f"== 回 {batch} の要約 == {len(rows)}件 / 表に出す語 平均 {sum(len(r['show']) for r in rows) / n:.1f}・表0の頁 {sum(not r['show'] for r in rows)}"
          f" / ジャンルを足す案のある頁 {sum(bool(r['genres_add'] or r['genres_mat']) for r in rows)} / 新しい語 {sum(len(r['new']) for r in rows)}"
          f" / 読み込み {sum(r.get('in') or 0 for r in rows):,}・出力 {sum(r.get('out') or 0 for r in rows):,} トークン・${sum(r.get('cost_usd') or 0 for r in rows):.2f}"
          f"\n多い語: {'・'.join(f'{k}{v}' for k, v in w.most_common(20))}\n→ {os.path.relpath(p, ROOT)}", flush=True)


def cmd_summary(a):
    if a.batch:
        return write_summary(a.batch)
    c = collections.Counter(r.get("batch") for r in jl(LEDGER))
    for b, n in sorted(c.items()):
        print(f"{b}\t{n}件")


def cmd_sample(a):
    rows = [r for r in jl(LEDGER) if r.get("batch") == a.batch]
    random.Random(a.seed).shuffle(rows)
    for r in rows[:a.k]:
        print(f"\n■ {r['title']} ({r['stem']}) 材料{r['chars']}字 / 今のジャンル {','.join(r['genres_now'])} / 足す {','.join(r['genres_add'])} / 材料から {'・'.join(r['genres_mat'])}")
        p = os.path.join(BASE, r["stem"], "assign", "assign-proposal.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            pr = json.load(f)
        for e in pr["rows"]:
            if e.get("cls") == "表" or e["kind"] == "ジャンル":
                ev = (f"AniList {e['ani']['en']} 票{e['ani']['votes']}" if e.get("ani") else "") + " ".join(f"「{x['quote'][:70]}」" for x in e.get("mat", [])[:1])
                print(f"  {'[ジ]' if e['kind'] == 'ジャンル' else '[表]'} {e['word']}: {ev}")


def main():
    ap = argparse.ArgumentParser(description="ジャンル・要素の見直しを表の順に流す")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run"); p.add_argument("--n", type=int, default=100); p.add_argument("--loops", type=int, default=1)
    p.add_argument("--parallel", type=int, default=3); p.add_argument("--model", default="claude-haiku-5-5"); p.add_argument("--effort", default="low")
    p.add_argument("--route", default="L"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("summary"); p.add_argument("--batch", default=""); p.set_defaults(f=cmd_summary)
    p = sp.add_parser("sample"); p.add_argument("batch"); p.add_argument("--k", type=int, default=50); p.add_argument("--seed", type=int, default=1); p.set_defaults(f=cmd_sample)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
