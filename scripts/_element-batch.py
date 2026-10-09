#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要素収集→要素付与 を、複数の作品に順番に流す(裁定なしの全自動)。 2026-10-09 新設。

  pick <name> [--n 30] [--seed 20261009]   型の違う作品を選んで一覧(list.tsv)を作る
  run <name> [--limit N] [--redo]          1作ずつ 自動収集(_element-harvest.py auto)→ 付与案(_element-assign.py run)。 再開可
  summary <name>                           結果を1枚(summary.html / summary.tsv)にまとめる

置き場: .cache/element-harvest/_batch/<name>/(list.tsv / log.txt / summary.*)
★順番に1作ずつ(並列にしない)。 外部の失敗(終了コード2)が3作続いたら止まる。 本番データには書かない。

選び方(pick): 確かさの違う3層から同数ずつ。 各層の半分は知られていそうな作品、半分は無作為。
  A = アニメ化あり(AniList に関連作がある見込み) / B = AniList に結線済み・アニメ化なし / C = AniList に結線なし
"""
import argparse, html, json, os, random, subprocess, sys, time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, ".cache", "element-harvest")
PY = sys.executable
TIER = {"A": "アニメ化あり", "B": "AniList結線・アニメ化なし", "C": "AniList結線なし"}


def bdir(name):
    d = os.path.join(BASE, "_batch", name)
    os.makedirs(d, exist_ok=True)
    return d


def read_list(name):
    p = os.path.join(bdir(name), "list.tsv")
    if not os.path.exists(p):
        print(f"✖ 一覧が無い → python scripts/_element-batch.py pick {name}")
        sys.exit(1)
    rows = []
    with open(p, encoding="utf-8-sig") as f:
        head = f.readline().rstrip("\n").split("\t")
        for ln in f:
            if ln.strip():
                rows.append(dict(zip(head, ln.rstrip("\n").split("\t"))))
    return rows


def cmd_pick(a):
    import yaml
    try:
        from yaml import CSafeLoader as L
    except ImportError:
        from yaml import SafeLoader as L
    with open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8") as f:
        idx = json.load(f)
    F = idx["f"]
    rows = [dict(zip(F, r)) for r in idx["d"]]
    rows = [r for r in rows if r.get("cover") and (r.get("total_volumes") or 0) >= 1 and "yahari-ore-no-seishun" not in r["slug"]]
    strata = {"A": [r for r in rows if r.get("popularity") and r.get("anime_adapted")],
              "B": [r for r in rows if r.get("popularity") and not r.get("anime_adapted")],
              "C": [r for r in rows if not r.get("popularity")]}
    rng = random.Random(a.seed)
    per = a.n // 3
    out = []
    for t, pool in strata.items():
        key = (lambda r: -(r.get("popularity") or 0)) if t != "C" else (lambda r: -(r.get("total_volumes") or 0))
        pool = sorted(pool, key=lambda r: (key(r), r["slug"]))
        known, rest = pool[:400], pool[400:]
        want = [("知られていそう", known, per - per // 2), ("無作為", rest, per // 2)]
        for how, src, n in want:
            src = list(src)
            rng.shuffle(src)
            got = 0
            for r in src:
                if got >= n:
                    break
                fp = os.path.join(ROOT, "data", "manga.v2", r["slug"] + ".yml")
                if not os.path.exists(fp):
                    continue  # slug とファイル名が違う頁は試しの対象にしない
                with open(fp, encoding="utf-8") as f:
                    d = yaml.load(f, Loader=L) or {}
                if d.get("adult"):
                    continue
                out.append({"tier": t, "how": how, "stem": r["slug"], "title": r["title"], "year": r.get("year_started") or "",
                            "vols": r.get("total_volumes") or "", "popularity": r.get("popularity") or "",
                            "elements_now": len(r.get("themes") or []), "genres_now": ",".join(r.get("genres") or [])})
                got += 1
    p = os.path.join(bdir(a.name), "list.tsv")
    cols = ["tier", "how", "stem", "title", "year", "vols", "popularity", "elements_now", "genres_now"]
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in out:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")
    print(f"選んだ {len(out)}作 → {os.path.relpath(p, ROOT)}(種 {a.seed})")
    for t in TIER:
        xs = [r for r in out if r["tier"] == t]
        print(f"  {t} {TIER[t]}: {len(xs)}作 / 母数 {len(strata[t])}")
        for r in xs:
            print(f"     {r['how'][:2]} {r['year']} 全{r['vols']}巻 要素{r['elements_now']} {r['title'][:34]}")


def run_one(cmd, logf):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"})
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    logf.write(f"\n$ {' '.join(cmd[1:])}\n{out}\n(exit {r.returncode} / {time.time() - t:.0f}秒)\n")
    logf.flush()
    return r.returncode, out


def cmd_run(a):
    rows = read_list(a.name)
    d = bdir(a.name)
    todo = [r for r in rows if a.redo or not os.path.exists(os.path.join(BASE, r["stem"], "assign", "assign-proposal.json"))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"対象 {len(rows)}作 / 今回 {len(todo)}作(済みは飛ばす)", flush=True)
    fails = 0
    with open(os.path.join(d, "log.txt"), "a", encoding="utf-8") as logf:
        for i, r in enumerate(todo, 1):
            t = time.time()
            stem = r["stem"]
            code, out = run_one([PY, "scripts/_element-harvest.py", "auto", stem] + (["--fresh"] if a.redo else []), logf)
            if code == 0:
                code, out2 = run_one([PY, "scripts/_element-assign.py", "run", stem], logf)
                out += out2
            if code != 0:
                why = next((ln.strip() for ln in out.splitlines() if ln.strip().startswith(("■", "✖", "★wiki"))), f"exit {code}")
                fails += 1
                print(f"[{i}/{len(todo)}] ✖ {r['tier']} {r['title'][:26]} — {why[:90]} ({time.time() - t:.0f}秒)", flush=True)
                if code == 3 or fails >= 3:
                    print("■ 外部の失敗が続いたので止める(再実行すれば続きから)", flush=True)
                    sys.exit(2)
                continue
            fails = 0
            pj = os.path.join(BASE, stem, "assign", "assign-proposal.json")
            with open(pj, encoding="utf-8") as f:
                prop = json.load(f)
            core = [e["word"] for e in prop["rows"] if e["tier"] == "芯" and e["kind"] == "要素"]
            sub = [e for e in prop["rows"] if e["tier"] == "在る" and e["kind"] == "要素"]
            print(f"[{i}/{len(todo)}] {r['tier']} {r['title'][:26]} → 表{len(core)} 隠し{sum(1 for e in sub if e['vocab'] != '新しい語')} "
                  f"新語{sum(1 for e in sub if e['vocab'] == '新しい語')} ({time.time() - t:.0f}秒) {'・'.join(core[:8])}", flush=True)
            time.sleep(2)
    print("■ 完了", flush=True)


def load_result(stem):
    wd = os.path.join(BASE, stem)
    out = {"stem": stem, "done": False}
    try:
        with open(os.path.join(wd, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        with open(os.path.join(wd, "assign", "assign-proposal.json"), encoding="utf-8") as f:
            prop = json.load(f)
    except (OSError, ValueError):
        return out
    src = {s["id"]: s for s in st["sources"]}
    kinds = {}
    for p in st["picks"]:
        k = "Wikipedia" if p["auto"] else src[p["src"]]["kind"]
        kinds[k] = kinds.get(k, 0) + p["chars"]
    rows = [e for e in prop["rows"] if e["kind"] == "要素"]
    out.update({
        "done": True, "title": st["card"]["title"], "authors": "・".join(st["card"]["authors"] + st["card"]["original_authors"]),
        "year": st["card"].get("year_started"), "vols": st["card"]["volumes"], "genres_now": prop.get("genres_now") or [],
        "genres_add": prop.get("genres_add") or [],
        "genres_mat": [e["word"] for e in prop["rows"] if e["kind"] == "ジャンル" and e["tier"] in ("芯", "在る")],
        "core": [(e["word"], "AniList" if e.get("ani") and not e.get("mat") else "両方" if e.get("ani") else "材料", e["vocab"]) for e in rows if e.get("cls") == "表"],
        "sub": [e["word"] for e in rows if e.get("cls") == "隠し" and e.get("hid") in ("上限", "在る", "ネタバレ印", "ありふれた語", "出さない語") and e["vocab"] != "新しい語"],
        "wait": [e["word"] for e in rows if e.get("cls") == "隠し" and e.get("hid") == "語彙か訳が無い"],  # 強いのに語彙か訳が無くて出せない語
        "wait_src": {e["word"]: (f"AniList {e['ani']['en']}" + ("(仮の訳)" if e["ani"].get("draft") else "(訳なし)") if e.get("ani") else "材料(語彙に無い)")
                     for e in rows if e.get("cls") == "隠し" and e.get("hid") == "語彙か訳が無い"},
        "new": [e["word"] for e in rows if e.get("cls") == "隠し" and e.get("hid") == "在る" and e["vocab"] == "新しい語"],
        "ani_entries": len((st.get("anilist") or {}).get("entries") or []), "wiki": (st.get("wiki") or {}).get("title"),
        "wiki_id": (st.get("wiki") or {}).get("identity"), "chars": sum(p["chars"] for p in st["picks"]), "kinds": kinds,
        "none": st.get("none") or {}, "tok_h": (st.get("auto_use") or {}).get("in", 0) + (st.get("auto_use") or {}).get("out", 0),
        "tok_a": (prop.get("use") or {}).get("in", 0) + (prop.get("use") or {}).get("out", 0),
        "cost": ((st.get("auto_use") or {}).get("cost_usd") or 0) + ((prop.get("use") or {}).get("cost_usd") or 0),
        "rejected": len(prop.get("rejected") or []), "not": len(prop.get("not") or [])})
    return out


def cmd_summary(a):
    with open(os.path.join(ROOT, "data", "genres.yml"), encoding="utf-8") as f:
        import yaml
        gname = {k: v["name"] for k, v in yaml.safe_load(f).items()}
    rows = read_list(a.name)
    res = [{**r, **load_result(r["stem"])} for r in rows]
    done = [r for r in res if r["done"]]
    d = bdir(a.name)
    cols = ["tier", "how", "title", "year", "vols", "elements_now", "表に出す", "隠して持つ", "新しい語", "ジャンル今", "ジャンル足す", "材料字数", "AniList関連", "Wikipedia", "材料なしの種別", "stem"]
    with open(os.path.join(d, "summary.tsv"), "w", encoding="utf-8-sig", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in done:
            f.write("\t".join(str(x) for x in [r["tier"], r["how"], r["title"], r["year"], r["vols"], r["elements_now"], "・".join(w for w, _, _ in r["core"]),
                                             "・".join(r["sub"]), "・".join(r["new"]), "・".join(gname.get(g, g) for g in r["genres_now"]),
                                             "・".join(gname.get(g, g) for g in r["genres_add"]), r["chars"], r["ani_entries"], r["wiki"] or "",
                                             "・".join(f"{k}={v}" for k, v in r["none"].items()), r["stem"]]) + "\n")
    e = html.escape
    avg = lambda xs: (sum(xs) / len(xs)) if xs else 0  # noqa: E731
    parts = [f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>要素付与の試し {e(a.name)}</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--core:#0b6b3a;--corebg:#e6f4ec;--sub:#555;--subbg:#f0f0f0;--new:#8a4b00;--newbg:#fdf0dc}}
@media(prefers-color-scheme:dark){{:root{{--bg:#15171a;--fg:#e8e8e8;--mut:#9aa0a6;--line:#333;--core:#7fd6a4;--corebg:#143524;--sub:#bbb;--subbg:#26292d;--new:#f0b860;--newbg:#3a2a10}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,"Hiragino Sans","Yu Gothic UI",sans-serif;margin:0;padding:16px;max-width:860px;margin-inline:auto}}
h1{{font-size:19px;margin:0 0 4px}}h2{{font-size:16px;margin:26px 0 6px;border-bottom:1px solid var(--line);padding-bottom:4px}}
.m{{color:var(--mut);font-size:13px}}.w{{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:10px 0}}
.t{{font-weight:600}}.r{{margin-top:6px}}.k{{display:inline-block;min-width:5.2em;color:var(--mut);font-size:13px}}
.c,.s,.n{{display:inline-block;border-radius:4px;padding:0 6px;margin:2px 3px 2px 0;font-size:14px}}
.c{{background:var(--corebg);color:var(--core)}}.s{{background:var(--subbg);color:var(--sub)}}.n{{background:var(--newbg);color:var(--new)}}
.z{{color:var(--mut)}}sup{{font-size:10px;opacity:.75;margin-left:1px}}
</style><h1>要素付与の試し({len(done)}作・裁定なしの全自動)</h1>
<p class="m">表に出す = AniList の票が線以上、または材料で「主軸」と判定された語(強い順に最大10)。隠して持つ = 上限であふれた語・作中に在るが中心でない語・ネタバレ印の語(サイトには出さない)。裁定待ち = 強いのに、語彙か日本語の訳が無くて出せない語。新しい語 = 今の語彙に無い候補(付けない)。<br>
語の右肩: A=AniList の票 / 材=日本語の材料 / 両=両方。データには何も書いていません。<br>
AniList の票は、その漫画自身と、関連作(原作小説・アニメ)のうち登録者1,000人以上の本筋のものだけを使う(おまけ映像や登録者の少ないものは使わない)。語ごとの集計は末尾。</p>
<p class="m">平均: 表に出す {avg([len(r['core']) for r in done]):.1f}語・隠して持つ {avg([len(r['sub']) for r in done]):.1f}語・新しい語 {avg([len(r['new']) for r in done]):.1f}語 /
表に出す語が0の作品 {sum(1 for r in done if not r['core'])}作 / 1作あたり 約{avg([r['tok_h'] + r['tok_a'] for r in done]) / 1000:.0f}千トークン</p>"""]
    for t in TIER:
        xs = [r for r in done if r["tier"] == t]
        parts.append(f"<h2>{t}: {TIER[t]}({len(xs)}作 / 表に出す 平均 {avg([len(r['core']) for r in xs]):.1f}語)</h2>")
        for r in xs:
            mark = {"AniList": "A", "材料": "材", "両方": "両"}
            core = "".join(f'<span class="c">{e(w)}<sup>{mark[sv]}{"・新" if vc == "新しい語" else ""}</sup></span>' for w, sv, vc in r["core"]) or '<span class="z">なし</span>'
            sub = "".join(f'<span class="s">{e(w)}</span>' for w in r["sub"]) or '<span class="z">なし</span>'
            new = "".join(f'<span class="n">{e(w)}</span>' for w in r["new"]) or '<span class="z">なし</span>'
            wait = "".join(f'<span class="n">{e(w)}</span>' for w in r["wait"])
            gadd = "".join(f'<span class="c">+{e(gname.get(g, g))}</span>' for g in r["genres_add"]) + "".join(f'<span class="n">材:{e(g)}</span>' for g in r["genres_mat"])
            src = f"AniList関連{r['ani_entries']}件" + (f"・Wikipedia" if r["wiki"] else "・Wikipediaなし") + f"・材料{r['chars']}字"
            none = ("・材料なし=" + "/".join(r["none"])) if r["none"] else ""
            parts.append(f"""<div class="w"><div class="t">{e(r['title'])}</div>
<div class="m">{e(r['authors'])} / {r['year'] or '?'}年 / 全{r['vols']}巻 / {r['how']} / 今の要素 {r['elements_now']}個<br>{src}{e(none)}</div>
<div class="r"><span class="k">表に出す</span>{core}</div><div class="r"><span class="k">隠して持つ</span>{sub}</div>
{f'<div class="r"><span class="k">裁定待ち</span>{wait}</div>' if wait else ''}
<div class="r"><span class="k">新しい語</span>{new}</div>
<div class="r"><span class="k">ジャンル</span>{e('・'.join(gname.get(g, g) for g in r['genres_now']))} {gadd}</div></div>""")
    # 語ごとの集計(作品ごとでなく、語ごとに決めれば全作品に効くもの)
    cnt = lambda pairs: sorted(((w, [t for w2, t in pairs if w2 == w]) for w in dict.fromkeys(w for w, _ in pairs)), key=lambda x: (-len(x[1]), x[0]))  # noqa: E731
    short = lambda t: t[:10] + ("…" if len(t) > 10 else "")  # noqa: E731
    wsrc = {}
    for r in done:
        wsrc.update(r["wait_src"])
    waits = cnt([(w, r["title"]) for r in done for w in r["wait"]])
    shown = [x for x in cnt([(w, r["title"]) for r in done for w, _, _ in r["core"]]) if len(x[1]) >= 2]
    news = cnt([(w, r["title"]) for r in done for w in r["new"]])
    parts.append(f"<h2>語ごとの集計(語ごとに決めれば全作品に効く)</h2><p class='m'>強いのに出せなかった語 {len(waits)}種(訳か語彙を足せば表に出る)</p>")
    parts.append("<div class='w'>" + "".join(f"<div><span class='n'>{e(w)}</span><span class='m'>{e(wsrc.get(w, ''))} / {len(ts)}作: {e('・'.join(short(t) for t in ts[:4]))}</span></div>" for w, ts in waits) + "</div>")
    parts.append("<p class='m'>2作以上で表に出た語(ありふれた語が混じっていないかを見る)</p><div class='w'>"
                 + "".join(f"<span class='c'>{e(w)}<sup>×{len(ts)}</sup></span>" for w, ts in shown) + "</div>")
    parts.append(f"<p class='m'>新しい語の候補 {len(news)}種(付けていない。 何作にも出た語だけ採否を決める)</p><div class='w'>"
                 + "".join(f"<span class='n'>{e(w)}{f'<sup>×{len(ts)}</sup>' if len(ts) > 1 else ''}</span>" for w, ts in news) + "</div>")
    miss = [r for r in res if not r["done"]]
    if miss:
        parts.append("<h2>終わらなかった作品</h2><p class='m'>" + "、".join(e(r["title"]) for r in miss) + "</p>")
    with open(os.path.join(d, "summary.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "</html>")
    print(f"まとめた {len(done)}/{len(rows)}作 → {os.path.relpath(os.path.join(d, 'summary.html'), ROOT)} / summary.tsv")
    print(f"平均: 表 {avg([len(r['core']) for r in done]):.1f} / 隠し {avg([len(r['sub']) for r in done]):.1f} / 新語 {avg([len(r['new']) for r in done]):.1f}"
          f" / 表が0の作品 {sum(1 for r in done if not r['core'])} / トークン計 {sum(r['tok_h'] + r['tok_a'] for r in done)} / 概算費用 ${sum(r['cost'] for r in done):.2f}")
    for t in TIER:
        xs = [r for r in done if r["tier"] == t]
        print(f"  {t} {TIER[t]}: {len(xs)}作 / 表 平均 {avg([len(r['core']) for r in xs]):.1f} / 表0 {sum(1 for r in xs if not r['core'])} / 材料 平均 {avg([r['chars'] for r in xs]):.0f}字")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pick"); p.add_argument("name"); p.add_argument("--n", type=int, default=30); p.add_argument("--seed", type=int, default=20261009); p.set_defaults(f=cmd_pick)
    p = sp.add_parser("run"); p.add_argument("name"); p.add_argument("--limit", type=int, default=0); p.add_argument("--redo", action="store_true"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("summary"); p.add_argument("name"); p.set_defaults(f=cmd_summary)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
