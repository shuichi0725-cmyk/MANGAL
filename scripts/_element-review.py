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
import argparse, collections, concurrent.futures, datetime, gzip, importlib.util, json, os, random, re, subprocess, sys, threading

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
VERSION = "r0.10"  # r0.10: 票が平らなAniListエントリに印(点検で「票79(平ら)」。 芯から下げるのはユーザ裁定で止めた = _element-assign v0.18) # r0.9: 意味が重なる語の組(_element-assign v0.17 OVERLAP)/ words(語彙に無くて隠れる芯の語を数えて裁定表に)(見直しまとめて3回目) # r0.8: 表0の頁で上げる語に「片方が芯・もう片方は挙げず」を足す(点検 L-20261021-0249/0753) # r0.7: 表0の頁は2回とも「在る」の語を最大3語まで表に上げる / 材料から話数一覧(▼第N話／…)を外し、紹介文が少ない頁は1本を600字で切らない(点検9回ぶんのまとめ) # r0.6: rebuild(モデルを呼ばずに、残した答えから付与案と台帳を作り直す) # r0.5: 語に付いて返った [要素] の印を外してから2回の答えを合わせる # r0.4: 2回判定の合わせ方をゆるめる(芯+在る → 表。 表0が材料ありの2割だった)/ 材料からのジャンルは2回とも芯の時だけ / 2回とも芯の語は後ろの巻が根拠でも表に出す / 2回の生の答えを残す # r0.3: --twice(2回判定して一致した語だけ表に出す) # r0.2: 材料からのジャンルは2つ以上の紹介文に出る時だけ / --redo
BASE = os.path.join(ROOT, ".cache", "element-harvest")
LEDGER = os.path.join(ROOT, "data", "element-harvest", "review-ledger.jsonl")
CAPS = os.path.join(BASE, "_local", "captions.jsonl")
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
MAX_CHARS = 3000   # 1作に渡す材料の上限
CAP_CLIP = 600     # 1巻の紹介文の上限(紹介文が5本以上の時)。 少ない時は MAX_CHARS を本数で割った分まで(最大 CAP_SOLO)
CAP_SOLO = 1500    # ★点検9回ぶん: 紹介文1本だけの頁が600字で切れ、その4割強が表0だった(後半に作品全体の説明がある紹介文が多い)
EPISODES = re.compile(r"▼[^▼●]{1,60}(?=▼|●|$)")  # 話数一覧「▼第81話／抜き打ち調査！」= 題の羅列で物語ではない。 小学館の紹介文で先頭200字以上を占め、本文が切れていた
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
    use = [c for c in caps if not c["ad"]][:MAX_CAPS]
    clip = min(CAP_SOLO, max(CAP_CLIP, MAX_CHARS // max(1, len(use) + bool(bl))))

    def add(domain, title, text, as_):
        nonlocal total
        text = EPISODES.sub("", text).strip()[:clip]
        if len(text) < 40 or total + len(text) > MAX_CHARS:
            return
        sid = len(sources) + 1
        sources.append({"id": sid, "kind": "手元", "origin": "local", "domain": domain, "url": "", "title": title, "identity": "OK", "same": None})
        picks.append({"id": len(picks) + 1, "src": sid, "kind": "手元", "as": as_, "spoiler": as_ == "展開", "auto": True, "text": text})
        total += len(text)

    if bl:
        add("booklive(紹介文)", card["title"], bl, "物語")
    for i, c in enumerate(use):
        add("books.rakuten.co.jp", c["title"], c["cap"], "物語" if i < EARLY else "展開")
    ents = [ani] if ani else []
    a = {"entries": ents, "skipped": [], "note": "" if ani else "頁に anilist_id が無い"}
    return {"stem": card["stem"], "version": VERSION, "bundle_version": VERSION, "model": "(手元の材料・機械)", "made_at": now(), "local": True,
            "card": {k: card[k] for k in ("slug", "title", "authors", "original_authors", "publisher", "imprint", "magazine", "year_started", "year_ended",
                                          "volumes", "demographic", "genres", "anime_adapted", "synopsis", "catch")},
            "anilist": {"entries": [{k: e[k] for k in ("id", "group", "format", "year", "popularity", "title", "genres")} | {"main": True} for e in ents],
                        "tags": eh.anilist_merged(a), "skipped": []},
            "wikipedia": {"title": None, "categories": []}, "sources": sources, "picks": picks, "none": {}}, total


def bare(w):  # _element-assign.bare と同じ(語に付いて返った [要素] の印を外す)
    return re.sub(r"\s*[\[［](要素|ジャンル|タグ一覧の語)[\]］]\s*$", "", str(w or "").strip())


def agree(a1, a2, V):
    """2回の答えを1つに。 → (答え, 2回とも「芯」の語の集合, 表0の頁で上げてよい語 {語: わけ})
    上げてよい語 = 2回とも「在る」以上 / 片方が「芯」でもう片方は挙げていない(「違う」と言った語は入れない)。
    2回とも「芯」→ 芯 / 片方「芯」・もう片方「在る」→ 芯 / 片方「芯」・もう片方「違う」か挙げていない → 在る / 2回目だけが挙げた語 → 在る で足す。
    ★同じ材料でも判定は回ごとに約1割ゆれる(2026-10-12 実測: 193語中21語が片方だけ。 弱い語が中心)。
    ★r0.3 は「2回とも芯」だけを芯にしていた → 材料あり951頁のうち187頁で表が0語(カイジ=ギャンブルも隠し)。 r0.4 で 芯+在る を芯に。"""
    canon = lambda w: V["alias"].get(bare(w), bare(w))  # noqa: E731
    G = ("judged", "added", "new_words")
    rank = {"芯": 2, "在る": 1}
    t1, t2 = {}, {}
    for t, a in ((t1, a1), (t2, a2)):
        for g in G:
            for x in a.get(g) or []:
                if isinstance(x, dict):
                    w = canon(x.get("word"))
                    t[w] = max(t.get(w, 0), rank.get(x.get("tier"), 0))
    both = {w for w in t1 if t1[w] == 2 and t2.get(w) == 2}
    out = {}
    for g in G:
        rows, seen = [], set()
        for x in a1.get(g) or []:
            if not isinstance(x, dict):
                continue
            x, w = dict(x), canon(x.get("word"))
            seen.add(w)
            if x.get("tier") == "芯" and not t2.get(w):
                x["tier"], x["why"] = "在る", "(2回の判定で一致せず)" + str(x.get("why", ""))[:20]
            elif x.get("tier") == "在る" and t2.get(w) == 2:
                x["tier"] = "芯"
            rows.append(x)
        if g != "judged":
            for x in a2.get(g) or []:
                if isinstance(x, dict) and canon(x.get("word")) not in seen and x.get("tier") in ("芯", "在る"):
                    rows.append({**x, "tier": "在る"})
        out[g] = rows
    # ★r0.8: 片方だけが足した語(added・new_words)は、もう片方が「違う」と言ったのではなく思いつかなかっただけのことが多い。
    #   表0の頁でこの「芯/挙げず」を上げると 257頁・289語(抜き取り40語は大半妥当: 愛人・失格=不倫、虐殺スタジアム=デスゲーム、猫目荘=シェアハウス)。
    #   点検 L-20261021-0753 で表0の頁の芯が隠れていた(零崎双識=殺人鬼・ボクらはゆるく生きている=昆虫/動物)。
    lift = {w: "表0の頁で片方が「芯」・もう片方は挙げず" for t, o in ((t1, t2), (t2, t1)) for w in t if t[w] == 2 and w not in o}
    lift.update({w: "表0の頁で2回とも「在る」" for w in t1 if t1[w] >= 1 and t2.get(w, 0) >= 1})
    return out, both, lift


def one(stem, ctx, a, batch):
    ea, eh, V = ctx["ea"], ctx["eh"], ctx["V"]
    # ★頁のファイルが無い stem で build_card が sys.exit し、流し全体が止まった(2026-10-15 14:40・1日止まったまま)。 その頁だけ飛ばす
    if not os.path.exists(os.path.join(ROOT, "data", "manga.v2", stem + ".yml")):
        return {"stem": stem, "skip": "頁のファイルが無い(改名・削除)= 表を作り直す"}
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
    raw, both, agreed = [], None, None
    if not m["picks"]:
        ans, use = {"judged": [], "added": [], "new_words": []}, {"model": "(材料なし・モデルを呼ばない)", "sec": 0, "in": 0, "out": 0, "cost_usd": 0}
    else:
        ask = lambda: ctx["lean"].ask(ea.build_prompt(m, V, cands), ea.SCHEMA, a.model, system="あなたは漫画データベースの分類の助手。指示された JSON の形だけで答える。", effort=a.effort or None)  # noqa: E731
        ans, use = ask()
        raw, both = [ans], None
        if a.twice:  # 同じ材料でもう1回判定させ、2回とも「芯」の語だけ表に出す(片方だけの語は「在る」= 隠して持つ)
            ans2, use2 = ask()
            raw.append(ans2)
            ans, both, agreed = agree(ans, ans2, V)
            use = {"model": use["model"] + " x2", "sec": round(use["sec"] + use2["sec"], 1), "in": use["in"] + use2["in"], "out": use["out"] + use2["out"],
                   "cost_usd": (use.get("cost_usd") or 0) + (use2.get("cost_usd") or 0)}
    return settle(ea, V, stem, m, cands, card, row, ans, use, raw, both, agreed)


def settle(ea, V, stem, m, cands, card, row, ans, use, raw, both, agreed=None, save=True):
    """判定の答え → 付与案 → 台帳の1行。 ★モデルを呼ばない部分(rebuild もここを通る)。"""
    with LOCK:  # 付与案づくりは台帳・ファイルに書くので1件ずつ
        if save:
            with open(os.path.join(ea.adir(stem), "assign-answer.json"), "w", encoding="utf-8") as f:
                json.dump({"use": use, "answer": ans, "raw": raw}, f, ensure_ascii=False, indent=1)
        # ★後ろの巻の紹介文は「展開」(ネタバレ扱い)だが、2回とも芯 = 2回とも「作品全体を通して言える」と読んだ語は表に出す
        #   (r0.3 まで: カイジのギャンブル・10万分の1の闘病 が、根拠が4巻目以降というだけで隠れた。 その巻だけの出来事は判定の決まりで「違う」になる)
        # ★表が0語になる頁は、2回とも「在る」で挙げた語を表に上げる(点検9回で型6「表0で芯が隠れている」が毎回4〜7頁。 材料あり頁の18.6%が表0だった)
        out, rows, ok, bad, missing = ea.make_proposal(stem, m, V, cands, ans, use, not_spoiler=both or (), lift=agreed or ())
        with open(os.path.join(ea.adir(stem), "assign-proposal.json"), encoding="utf-8") as f:
            gadd = json.load(f).get("genres_add") or []
        gm = [e["word"] for e in rows if e["kind"] == "ジャンル"]
        gcore = lambda w: e_tier.get(w) == "芯" and (both is None or w in both)  # noqa: E731  ★ジャンルは「在る」では案にしない。 2回判定なら2回とも芯の時だけ(戦争・学園が文中の1語から付いた)
        e_tier = {e["word"]: e["tier"] for e in rows}
        nsup = lambda w: sum(w in p["text"] for p in m["picks"])  # noqa: E731  ★材料からのジャンルは、2つ以上の紹介文にその語が出る時だけ案にする(1巻だけの題材を拾わない)
        row.update({**use, "show": [e["word"] for e in rows if e.get("cls") == "表"],
                    "show_src": ["両" if e["ani"] and e["mat"] else "A" if e["ani"] else "材" for e in rows if e.get("cls") == "表"],
                    "hide": [e["word"] for e in rows if e.get("cls") == "隠し"], "new": [e["word"] for e in rows if e["vocab"] == "新しい語"],
                    "genres_now": card["genres"], "genres_add": gadd, "genres_mat": [w for w in gm if nsup(w) >= 2 and gcore(w)], "genres_mat_weak": [w for w in gm if not (nsup(w) >= 2 and gcore(w))],
                    "not": sum(1 for x in ok if x["tier"] == "違う"), "rejected": len(bad), "missing": len(missing), "elements_now": len(card["tags_on_page"])})
        with open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def uninspected(route, again=False):
    """まだ点検していない頁(材料あり)。 頁ごとに新しい行が勝つ。 判定した時刻で数える(rebuild で作り直しただけの頁は点検済みのまま)。"""
    last = {}
    for r in jl(LEDGER):
        last[r["stem"]] = r
    seen = {(x["stem"], x["at"]) for o in jl(INSP_LEDGER) for x in o["pages"]}
    return [r for r in last.values() if r.get("route") == route and str(r["chars"]) != "0" and (again or (r["stem"], r.get("judged_at") or r["at"]) not in seen)]


def run_total(a, batches, why):
    """流しの終わり(中断でも)に、今回ぶん全部の合計を1行で出す。
    ★2026-10-14: 10回ぶんの出力の末尾だけを読んだ運転者が、921件を「21件」・943件を「43件」と報告した。 報告と commit にはこの行の件数を使う。"""
    rows = [r for r in jl(LEDGER) if r.get("batch") in batches]
    print(f"\n==== 今回の合計 ==== 流した {len(rows):,}件({len(batches)}回・{why})/ 点検待ち {len(uninspected(a.route)):,}件(材料あり)"
          f" / 読み込み {sum(r.get('in') or 0 for r in rows):,}・出力 {sum(r.get('out') or 0 for r in rows):,} トークン"
          "\n★報告と commit の件数はこの行の「流した」を使う(最後の回の件数ではない)", flush=True)


AUTO_ROUTES = ("L", "A", "後")  # ★W(材料なし)は 2026-10-12 ユーザ裁定「4保留でよい」で当面流さない = 自動では選ばない


def cmd_run(a):
    if not a.route:  # ★2026-10-26 経路L を流し切った。 日課「見直し進めて」のコマンドを変えずに次の経路へ進む
        a.route = next((r for r in AUTO_ROUTES if a.stems or a.redo or next_stems(1, r)), "L")
        print(f"経路 {a.route}(--route を省いた = 「未」が残る最初の経路)", flush=True)
    ea, eh = mod("_element-assign"), mod("_element-harvest")
    import _lean_claude
    ctx = {"ea": ea, "eh": eh, "lean": _lean_claude, "V": ea.load_vocab()}
    ctx["caps"] = {o["slug"]: o["caps"] for o in jl(CAPS)}
    ctx["bl"] = {o["slug"]: o["desc"] for o in jl(os.path.join(ROOT, ".cache", "booklive-desc.jsonl")) if o.get("desc")}
    if not ctx["caps"]:
        print("✖ 手元の材料の束が無い → python scripts/_gen-element-review-queue.py --material")
        sys.exit(1)
    batches = []
    skipped = set()
    loop = 0
    while True:
        n = a.n
        if a.until:  # 点検待ちが --until 件に届くまで。 途中で止まって再開しても、足りない分だけ流す(2026-10-14: 再開のたびに新しく1,000件を始めていた)
            left = a.until - len(uninspected(a.route))
            if left <= 0:
                run_total(a, batches, f"点検待ちが {a.until:,}件に届いた → 次は点検")
                return
            n = min(n, left)
        elif loop >= a.loops:
            run_total(a, batches, "予定の回数を終えた")
            return
        loop += 1
        # ★飛ばした頁(Web の束が在る・頁のファイルが無い)は台帳に書かないので「未」のまま表の先頭に残る。 除いて取り直す
        #   (2026-10-27: 点検待ち998件で残り2件を取りに行き、先頭の飛ばす2頁だけを5秒ごとに8時間・2,310回くり返した)
        stems = sorted(set(a.stems.split(","))) if a.stems else sorted({r["stem"] for r in jl(LEDGER) if r.get("batch") == a.redo}) if a.redo else [s for s in next_stems(n + len(skipped), a.route) if s not in skipped][:n]
        if not stems:
            print("表の「未」が無い(この経路は終わり)")
            run_total(a, batches, "表の「未」が尽きた")
            return
        batch = f"{a.route}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        batches.append(batch)
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
        print(f"== 回 {batch} == {len(stems)}件・並列 {a.parallel}・{a.model}{' effort=' + a.effort if a.effort else ''}{'・2回判定' if a.twice else ''}", flush=True)
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
                except SystemExit as e:  # 道具の die/stop(その頁だけの問題)= 流しは止めない
                    print(f"  ■ {s}: 道具が止まった(台帳に書かない・終了コード {e.code})", flush=True)
                    continue
                done += 1
                if r.get("skip"):
                    skipped.add(s)
                    print(f"  - {s}: {r['skip']}", flush=True)
                else:
                    print(f"  [{done}/{len(stems)}] {r['title'][:24]}: 表 {len(r['show'])} {'・'.join(r['show'])} / 隠し {len(r['hide'])} / ジャンル+ {','.join(r['genres_add'] + r['genres_mat']) or '-'} / {r.get('sec')}秒", flush=True)
        write_summary(batch)
        if fail >= 3:
            run_total(a, batches, "■ 中断 = モデルの失敗3件")
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


def compact():
    """台帳を「頁ごとの最新の1行」だけに詰める(前の台帳は .cache に退避)。 → (前の行数, 後の行数)
    ★2026-10-26 ユーザ「詰めて良い」: rebuild のたびに全頁ぶん追記して 63.8MB(GitHub は 100MB で push 不可)。
      読む側(表・点検・作り直し)はどれも頁ごとの最新行しか使わない。 失うのは古い回の summary(--batch)と --redo の対象だけ。"""
    rows, last = 0, {}
    with open(LEDGER, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                rows += 1
                last[json.loads(l)["stem"]] = l if l.endswith("\n") else l + "\n"
    bak = os.path.join(ROOT, ".cache", f"review-ledger-bak-{datetime.datetime.now():%Y%m%d-%H%M%S}.jsonl")
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    os.replace(LEDGER, bak)
    with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(sorted(last.values(), key=lambda l: json.loads(l)["at"]))
    return rows, len(last), bak


def cmd_compact(a):
    n0, n1, bak = compact()
    print(f"== 台帳を詰めた == {n0:,}行 → {n1:,}行(頁ごとの最新)/ 前の台帳 → {os.path.relpath(bak, ROOT)}")


def cmd_rebuild(a):
    """モデルを呼ばずに、残してある2回の生の答えから付与案と台帳を作り直す(数分・0円)。
    ★機械の決まり(2回の合わせ方・ジャンル案の条件・語彙に足した語・隠す語の裁定・語の重なり)を変えた時はこれで全頁に効く。
      判定の決まり(_element-assign.RULES = 指示文)を変えた時だけ、判定し直し(run --redo / --stems)が要る。"""
    ea, eh = mod("_element-assign"), mod("_element-harvest")
    V = ea.load_vocab()
    last = {}
    for r in jl(LEDGER):
        last[r["stem"]] = r
    batch = f"{a.route}-{datetime.datetime.now():%Y%m%d-%H%M%S}-rebuild"
    n = skip = 0
    before = after = z0 = z1 = 0
    for stem, old in sorted(last.items()):
        if old.get("route") != a.route:
            continue
        ap_ = os.path.join(ea.adir(stem), "assign-answer.json")
        # ★頁のファイルが無い stem(改名・削除)で build_card が sys.exit し、作り直しが e の途中で止まった(2026-10-20。 流しの 10-15 と同じ型)
        if not os.path.exists(ap_) or not os.path.exists(os.path.join(ROOT, "data", "manga.v2", stem + ".yml")):
            skip += 1
            continue
        with open(ap_, encoding="utf-8") as f:
            d = json.load(f)
        raw = d.get("raw")
        if raw is None:  # r0.3 以前 = 合わせた後の答えしか残っていない
            skip += 1
            continue
        m = ea.load_material(stem)
        cands = ea.find_candidates(m, V)
        if len(raw) == 2:
            ans, both, agreed = agree(raw[0], raw[1], V)
        else:
            ans, both, agreed = (raw[0] if raw else {"judged": [], "added": [], "new_words": []}), None, None
        card = eh.build_card(stem)
        row = {"at": now(), "batch": batch, "stem": stem, "slug": old["slug"], "title": old["title"], "route": a.route, "version": f"{VERSION}/{ea.VERSION}", "chars": old["chars"], "judged_as": old.get("judged_as") or old["version"], "judged_at": old.get("judged_at") or old["at"]}
        use = {k: old.get(k) for k in ("model", "sec", "in", "out", "cost_usd")}
        new = settle(ea, V, stem, m, cands, card, row, ans, use, raw, both, agreed, save=False)
        n += 1
        before += len(old["show"])
        after += len(new["show"])
        z0 += str(old["chars"]) != "0" and not old["show"]
        z1 += str(new["chars"]) != "0" and not new["show"]
    print(f"== 作り直し(モデルを呼ばない){batch} == {n}頁 / 表に出す語 {before:,} → {after:,} / 表0の頁(材料あり){z0:,} → {z1:,} / 生の答えが無くて飛ばした頁 {skip}")
    write_summary(batch)
    n0, n1, _ = compact()  # 作り直しは全頁ぶん追記する = そのたびに詰める
    print(f"台帳を詰めた: {n0:,}行 → {n1:,}行")


def cmd_words(a):
    """語彙か訳が無いので隠れている「芯」の語を全頁で数え、裁定表(TSV)にする。 モデルを呼ばない。
    ★見直しまとめて3回目(2026-10-26): 点検11本の型6(表0で芯が隠れる)は、ほぼ全部これ(別れさせ屋・文化祭・霊感・Crossdressing)。
      英語のまま = AniList のタグに訳が無い(tag-i18n.yml)/ 日本語 = 語彙(wamei-tags.yml allow)に無い。 どちらも語ごとのユーザ裁定。"""
    last = {}
    for r in jl(LEDGER):
        last[r["stem"]] = r
    core, zero, ani, ex = collections.Counter(), collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for r in last.values():
        if r.get("route") != a.route or str(r["chars"]) == "0":
            continue
        p = os.path.join(BASE, r["stem"], "assign", "assign-proposal.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            rows = json.load(f)["rows"]
        for e in rows:
            if e.get("hid") == "語彙か訳が無い" and e["tier"] == "芯":
                w = e["word"]
                core[w] += 1
                zero[w] += not r["show"]
                ani[w] += bool(e.get("ani"))
                if len(ex[w]) < 3:
                    q = (e.get("mat") or [{}])[0].get("quote") or f"AniList 票{(e.get('ani') or {}).get('votes')}"
                    ex[w].append(f"{r['title']}「{q[:40]}」")
    out = os.path.join(ROOT, "data", "element-harvest", f"new-words-{a.route}.tsv")
    with open(out, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("語\t頁数\tうち表0の頁\t出どころ\t例\n")
        for w, n in core.most_common():
            if n >= a.min:
                f.write(f"{w}\t{n}\t{zero[w]}\t{'AniList' if ani[w] == n else '材料' if not ani[w] else '両方'}\t{' / '.join(ex[w])}\n")
    k = sum(1 for n in core.values() if n >= a.min)
    print(f"== 語彙か訳が無くて隠れる「芯」の語 == {len(core):,}種・のべ {sum(core.values()):,}頁(うち表0の頁 {sum(zero.values()):,})"
          f" / {a.min}頁以上 {k}種・のべ {sum(n for n in core.values() if n >= a.min):,} → {os.path.relpath(out, ROOT)}")


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
                ev = (f"AniList {e['ani']['en']} 票{e['ani']['votes']}{'(平ら)' if e['ani'].get('flat') else ''}" if e.get("ani") else "") + " ".join(f"「{x['quote'][:70]}」" for x in e.get("mat", [])[:1])
                print(f"  {'[ジ]' if e['kind'] == 'ジャンル' else '[表]'} {e['word']}: {ev}")


INSP_DIR = os.path.join(ROOT, "data", "element-harvest", "inspections")
INSP_LEDGER = os.path.join(ROOT, "data", "element-harvest", "inspect-ledger.jsonl")
INSP_TYPES = ("その巻だけの出来事が、作品の語・ジャンルになっている", "語の意味違い(団体名・人名・題名の一部を語と読んだ)", "宣伝文句の語・どの作品にも当てはまる語が表に出ている",
              "根拠の文が、その語を支えていない(たとえ話・脇役1人の性質・否定文)", "AniList の票だけが根拠で、作品と明らかに合わない語", "表に1語も出ない頁で、隠しの語のほうが芯に見える")


def _proposal(stem):
    p = os.path.join(BASE, stem, "assign", "assign-proposal.json")
    if not os.path.exists(p):
        return {"rows": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cmd_inspect(a):
    """点検の1回ぶんを用意する: まだ点検していない頁から抜き取り、数えられる物は機械で数え、報告の書き込み先(.md)を作る。
    ★点検の報告を別の窓(直す側)が読めるよう、報告はファイルに残して git に入れる(2026-10-13。 会話にしか残らず、貼り直しが要った)。"""
    if a.list:
        for f in sorted(os.listdir(INSP_DIR)) if os.path.isdir(INSP_DIR) else []:
            with open(os.path.join(INSP_DIR, f), encoding="utf-8") as fh:
                st = next((line.strip() for line in fh if line.startswith("状態:")), "状態: ?")
            print(f"{f}\t{st}")
        return
    if not a.route:
        a.route = next((r for r in AUTO_ROUTES if uninspected(r, a.again)), "L")
    pool = uninspected(a.route, a.again)
    if not pool:
        print("まだ点検していない頁が無い(流した分は点検済み)。 もう一度抜き取るなら --again")
        return
    iid = f"{a.route}-{datetime.datetime.now():%Y%m%d-%H%M}"
    rows = sorted(pool, key=lambda r: r["stem"])
    random.Random(iid).shuffle(rows)
    pick = rows[:a.k]
    n = len(pool)
    show = collections.Counter(w for r in pool for w in r["show"])
    only_a = collections.Counter(w for r in pool for w, src in zip(r["show"], r["show_src"]) if src == "A")
    gm = collections.Counter(g for r in pool for g in r["genres_mat"])
    pairs = collections.Counter()
    for r in pool:
        ws = r["show"]
        for x in ws:
            for y in ws:
                if x < y and (x in y or y in x or x[:2] == y[:2]):
                    pairs[f"{x}+{y}"] += 1
    L = [f"# 見直しの点検 {iid}", "", "状態: 未記入", "",
         f"- 対象: 経路{a.route} の、まだ点検していない {n:,}頁(道具の版 {'・'.join(f'{k} {v}頁' for k, v in collections.Counter(r['version'] for r in pool).most_common())})から {len(pick)}頁を抜き取り",
         "- 書くのは下の「報告」だけ。 「抜き取り」と「機械で数えた分」は道具が書いた(直さない)。 書き終えたら「状態: 未記入」を「状態: 報告済み」に変える", "",
         "## 機械で数えた分(対象の全頁)", "",
         f"- 表に出す語 {sum(show.values()):,}(1頁平均 {sum(show.values()) / n:.2f})/ 表が0語の頁 {sum(not r['show'] for r in pool)} / 材料からのジャンル案のある頁 {sum(bool(r['genres_mat']) for r in pool)}",
         f"- 表に多い語: {'・'.join(f'{k}{v}' for k, v in show.most_common(30))}",
         f"- AniList の票だけで表に出た語: {'・'.join(f'{k}{v}' for k, v in only_a.most_common(25))}",
         f"- 材料からのジャンル案: {'・'.join(f'{k}{v}' for k, v in gm.most_common())}",
         f"- 似た語が同じ頁に並ぶ組: {'・'.join(f'{k} {v}頁' for k, v in pairs.most_common(15)) or 'なし'}", "",
         f"## 抜き取り({len(pick)}頁)", ""]
    for i, r in enumerate(pick, 1):
        L.append(f"### {i}. {r['title']} ({r['stem']})")
        L.append(f"材料 {r['chars']}字 / 今のジャンル {','.join(r['genres_now']) or '-'} / AniList から足す {','.join(r['genres_add']) or '-'} / 材料からの案 {'・'.join(r['genres_mat']) or '-'}")
        hid = []
        for e in _proposal(r["stem"])["rows"]:
            ev = (f"AniList {e['ani']['en']} 票{e['ani']['votes']}{'(平ら)' if e['ani'].get('flat') else ''} " if e.get("ani") else "") + " ".join(f"「{x['quote'][:70]}」" for x in e.get("mat", [])[:1])
            if e["kind"] == "ジャンル":
                L.append(f"- [ジ{'・案' if e['word'] in r['genres_mat'] else '・弱'}] {e['word']}: {ev}")
            elif e.get("cls") == "表":
                L.append(f"- [表{'・上げ' if e.get('lift') else ''}] {e['word']}: {ev}")  # 上げ = 表0の頁で2回とも「在る」の語を表に上げた物(r0.7)
            elif e.get("cls") == "隠し":
                hid.append((e, ev))
        if not r["show"]:  # 表が0語の頁は、隠しの語を根拠つきで見せる(芯が隠れていないかを読むため)
            L += [f"- [隠・{e.get('hid')}] {e['word']}: {ev}" for e, ev in hid[:8]]
        elif hid:
            L.append(f"- 隠し: {'・'.join(e['word'] for e, _ in hid)}")
        L.append("")
    L += ["## 報告", "", "抜き取りのうち問題なしの頁数: ", ""]
    for i, t in enumerate(INSP_TYPES, 1):
        L += [f"### 型{i}: {t}", "", "件数: ", "", "- (題 / 語 / 根拠の文 を1行ずつ。 無ければ「なし」)", ""]
    L += ["### 単発の誤り(型に当てはまらない)", "", "- ", "", "### ありふれた語の候補(語ごとのユーザ裁定が要る。 挙げるだけ)", "", "- ", ""]
    os.makedirs(INSP_DIR, exist_ok=True)
    out = os.path.join(INSP_DIR, iid + ".md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    # ★設計どおり: 点検は約1,000頁のロットの抜き取り検査(30頁を読む + 全頁を機械で数える)= ロット全体(pool)を点検済みにする。 pick(30頁)だけにすると
    #   点検待ちが970頁残り、次の run --until 1000 が30頁しか流さない。 2026-10-21 Haiku の窓がこれを「バグ」と読み違えた(pool→pick と記録の削除を提案)。
    #   流した件数が1,000を超える(1,281件など)のは、材料なしの頁(chars 0)が点検待ちに数えられないため。
    with open(INSP_LEDGER, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"id": iid, "at": now(), "pool": n, "pages": [{"stem": r["stem"], "at": r.get("judged_at") or r["at"]} for r in pool]}, ensure_ascii=False) + "\n")
    print(f"点検 {iid}: 対象 {n:,}頁から {len(pick)}頁 → {os.path.relpath(out, ROOT)}\nこのファイルを読み、末尾の「報告」を埋める(Edit)。 終わったら 状態 を「報告済み」にして commit+push")


def main():
    ap = argparse.ArgumentParser(description="ジャンル・要素の見直しを表の順に流す")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run"); p.add_argument("--n", type=int, default=100); p.add_argument("--loops", type=int, default=1)
    p.add_argument("--until", type=int, default=0, help="点検待ちの頁(材料あり)がこの件数に届くまで流す。 再開しても足りない分だけ(--loops は見ない)")
    p.add_argument("--parallel", type=int, default=3); p.add_argument("--model", default="claude-haiku-5-5"); p.add_argument("--effort", default="low")
    p.add_argument("--route", default="", help="省くと AUTO_ROUTES の順で「未」が残る経路"); p.add_argument("--twice", action="store_true", help="2回判定して合わせる(芯+芯・芯+在る → 表 / 片方だけ → 隠し)"); p.add_argument("--redo", default="", help="この回の頁を判定し直す(道具の決まりを直した後)"); p.add_argument("--stems", default="", help="この頁だけ判定し直す(カンマ区切り。 直しの確かめ用)"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("rebuild", help="モデルを呼ばずに、残してある答えから付与案と台帳を作り直す"); p.add_argument("--route", default="L"); p.set_defaults(f=cmd_rebuild)
    p = sp.add_parser("compact", help="台帳を頁ごとの最新の1行に詰める"); p.set_defaults(f=cmd_compact)
    p = sp.add_parser("words", help="語彙か訳が無くて隠れる「芯」の語を数えて裁定表に"); p.add_argument("--route", default="L"); p.add_argument("--min", type=int, default=5); p.set_defaults(f=cmd_words)
    p = sp.add_parser("summary"); p.add_argument("--batch", default=""); p.set_defaults(f=cmd_summary)
    p = sp.add_parser("sample"); p.add_argument("batch"); p.add_argument("--k", type=int, default=50); p.add_argument("--seed", type=int, default=1); p.set_defaults(f=cmd_sample)
    p = sp.add_parser("inspect"); p.add_argument("--k", type=int, default=30); p.add_argument("--route", default="", help="省くと点検待ちが残る経路"); p.add_argument("--again", action="store_true", help="点検済みの頁からも抜き取る")
    p.add_argument("--list", action="store_true", help="点検の報告の一覧と状態"); p.set_defaults(f=cmd_inspect)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
