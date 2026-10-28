"""ネタバレ印の語を頁ごとに見分ける(前提か・後の展開か)= 2026-10-28 ユーザ「語だけで判断出来ないのでは…ネタバレ的な三角関係と明らかに三角関係の作品がある」。

対象 = 今その頁に出ていて、AniList のネタバレ印だけを理由に「表示から外す」案になった語(見直しの付与案の 隠し・hid=ネタバレ印)。
  ★AniList のネタバレ印は前提の語にも付く(School Days・青のフラッグ = 三角関係)。 印だけでは外さない(_element-assign HIDE_REASONS)。

  candidates                 対象を集めて、機械で決まる物を決める(読むだけ・何も呼ばない)
  run [--parallel 3] [--limit N]   残りをモデルが頁ごとに判定(台帳 data/element-harvest/spoiler-judge.jsonl・止めても続きから)
  status                     件数
  apply [--go "<発話>"]      「展開」と決まった語を tags-hide.json に足す(--go 無し=件数だけ)

機械で決まる(モデルを呼ばない)= その語が頁のあらすじ・キャッチ、序盤の材料(紹介文)、AniList の英語のあらすじに出ている → 前提(外さない)。
モデルの判定 = 前提(1巻・あらすじの段階で分かる) / 展開(後で明かされる・結末) / 不明。 ★外すのは「展開」だけ(不明は今の本番どおり出す)。
"""
import argparse, collections, concurrent.futures, datetime, gzip, html, importlib.util, json, os, re, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import yaml

Ld = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
VERSION = "s0.2"  # s0.2: 「1巻に無い=展開」をやめる(2巻で恋敵が出るラブコメの三角関係を展開にしていた)。 展開=知ると驚きが損なわれる物だけ / --redo
DIR = os.path.join(ROOT, "data", "element-harvest")
CANDS = os.path.join(DIR, "spoiler-judge-candidates.jsonl")
LEDGER = os.path.join(DIR, "spoiler-judge.jsonl")
APPLY_LOG = os.path.join(ROOT, "data", "seeds", "element-review-apply-changelog.jsonl")
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")

# 英語のあらすじで「前提」と分かる言い方(タグ名そのものは常に見る)
EN_SYN = {
    "Love Triangle": ["love triangle", "triangle"],
    "Age Gap": ["age gap", "years older", "years younger", "older man", "older woman", "age difference"],
    "Reincarnation": ["reincarnat", "reborn", "past life", "previous life"],
    "Time Manipulation": ["time travel", "back in time", "time loop", "rewind"],
    "Revenge": ["revenge", "vengeance", "avenge"],
    "Memory Manipulation": ["memory", "memories", "amnesia"],
    "Amnesia": ["amnesia", "memory", "memories"],
    "Suicide": ["suicide"],
    "Conspiracy": ["conspiracy"],
    "Crime": ["crime", "criminal", "murder"],
    "Body Swapping": ["body swap", "swap bodies", "switch bodies", "swapped bodies"],
    "Gender Bending": ["gender", "turned into a girl", "turned into a boy", "becomes a girl", "becomes a boy"],
    "Adoption": ["adopt"],
    "Terrorism": ["terroris"],
    "Unrequited Love": ["unrequited", "one-sided"],
    "Marriage": ["marri", "wedding", "husband", "wife"],
    "Magic": ["magic", "witch", "wizard", "sorcer"],
    "Cosmic Horror": ["cosmic horror", "lovecraft"],
    "Body Horror": ["body horror"],
}


def mod(name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", name + ".py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def jl(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def cmd_candidates(a):
    ea = mod("_element-assign")
    V = ea.load_vocab()
    last = {}
    for r in jl(os.path.join(DIR, "review-ledger.jsonl")):
        last[r["stem"]] = r
    pages = {}
    for stem, r in sorted(last.items()):
        if r.get("route") not in ("L", "A", "後"):
            continue
        pj = os.path.join(ea.adir(stem), "assign-proposal.json"); pg = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
        if not (os.path.exists(pj) and os.path.exists(pg)):
            continue
        prop = json.load(open(pj, encoding="utf-8"))
        rows = [e for e in prop["rows"] if e.get("cls") == "隠し" and e.get("hid") == "ネタバレ印" and e.get("kind") == "要素" and e.get("ani")]
        if not rows:
            continue
        doc = yaml.load(open(pg, encoding="utf-8"), Loader=Ld) or {}
        have = {t.get("name") for t in doc.get("tags") or [] if isinstance(t, dict) and t.get("category") != "Demographic"}
        ws = [(e["word"], e["ani"]["en"]) for e in rows if e["ani"].get("en") in have]
        if ws:
            pages[stem] = (doc, ws)
    need = {d.get("anilist_id") for d, _ in pages.values() if d.get("anilist_id")}
    desc = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("id") in need:
                desc[e["id"]] = strip_html(e.get("description"))
    out, c = [], collections.Counter()
    for stem, (doc, ws) in pages.items():
        ja_txt = (doc.get("synopsis") or "") + " " + (doc.get("catch") or "")
        mp = os.path.join(ea.wdir(stem), "material.json")
        if os.path.exists(mp):
            m = json.load(open(mp, encoding="utf-8"))
            ja_txt += " " + " ".join(p["text"] for p in m.get("picks") or [] if not p.get("spoiler") and p.get("as") != "タグ")
        en = desc.get(doc.get("anilist_id"), "")
        enl = en.lower()
        words = []
        for ja, tag in ws:
            how = ""
            if ja and ja in ja_txt:
                how = "日本語のあらすじ・紹介文に在る"
            elif any(k in enl for k in [tag.lower()] + EN_SYN.get(tag, [])):
                how = "AniListのあらすじに在る"
            words.append({"ja": ja, "en": tag, "auto": how})
            c["前提(機械)" if how else "モデルへ"] += 1
        out.append({"stem": stem, "slug": doc.get("slug") or stem, "title": doc.get("title"), "aid": doc.get("anilist_id"), "words": words})
    with open(CANDS, "w", encoding="utf-8", newline="\n") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    pg_model = sum(1 for x in out if any(not w["auto"] for w in x["words"]))
    print(f"頁 {len(out):,} / 語 {sum(c.values()):,} / 前提と機械で決まった {c['前提(機械)']:,} / モデルへ {c['モデルへ']:,}語({pg_model:,}頁)")
    print("→", os.path.relpath(CANDS, ROOT))


SCHEMA = {"type": "object", "required": ["words"], "properties": {"words": {"type": "array", "items": {
    "type": "object", "required": ["word", "verdict", "why"],
    "properties": {"word": {"type": "string"}, "verdict": {"type": "string", "enum": ["前提", "展開", "不明"]}, "why": {"type": "string"}}}}}}

RULES = """漫画の頁に出す「要素」の語が、その作品にとってネタバレかを判定する。
- 展開 = 知ってしまうと、読む時の驚きが損なわれること。 結末・主要人物の死・正体・裏切り・黒幕・どんでん返し・隠された過去の真相。
- 前提 = 展開でないもの。 1巻・作品紹介の段階で分かる設定や関係。 加えて、物語の中心として続く関係・題材は、2巻以降に出てきても前提
  (例: ラブコメで2巻から恋敵が出て三角関係になる = 作品紹介でふつうに語られる中心の要素なので前提)。
- 「1巻の紹介文に書いていない」だけでは展開にしない。 展開にするのは、隠されていた事実が明かされる・取り返しのつかない出来事が起きる時。
- 不明 = 材料からも作品の知識からも決められない。 迷ったら不明。
- 材料(あらすじ・紹介文)を第一の根拠にする。 作品を知っている場合は知識も使ってよいが、why に「知識」と書く。
- why は20字以内。"""


def build_prompt(x, doc, en, ja_mat):
    L = [RULES, "", "■ 作品", f"題: {x['title']} / {doc.get('year_started') or '?'}年〜",
         f"頁のあらすじ: {doc.get('synopsis') or '-'}", f"頁のキャッチ: {doc.get('catch') or '-'}"]
    if ja_mat:
        L.append("紹介文(序盤): " + ja_mat[:1200])
    if en:
        L.append("AniList のあらすじ(英語): " + en[:1000])
    L += ["", "■ 判定する語(AniList の利用者がネタバレ印を付けた語)"]
    for w in x["words"]:
        if not w["auto"]:
            L.append(f"- {w['ja']}({w['en']})")
    return "\n".join(L)


def cmd_run(a):
    import _lean_claude
    ea = mod("_element-assign")
    latest = {}
    for r in jl(LEDGER):
        latest[(r["stem"], r["en"])] = r
    redo = set(a.redo.split(",")) if a.redo else set()
    # --redo 展開 = 前の版で「展開」と出た語だけを今の版で判定し直す(台帳は足すだけ・新しい行が勝つ)
    done = {k for k, r in latest.items() if not (r["verdict"] in redo and r.get("version") != VERSION)}
    todo = [x for x in jl(CANDS) if any(not w["auto"] and (x["stem"], w["en"]) not in done for w in x["words"])]
    if a.limit:
        todo = todo[:a.limit]
    need = {x["aid"] for x in todo if x.get("aid")}
    desc = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("id") in need:
                desc[e["id"]] = strip_html(e.get("description"))
    print(f"モデルで判定する頁 {len(todo):,}(並列 {a.parallel})", flush=True)
    lock = threading.Lock(); fails = [0]; c = collections.Counter(); cost = [0.0]; n = [0]

    def one(x):
        if fails[0] >= 3:
            return
        doc = yaml.load(open(os.path.join(ROOT, "data", "manga.v2", x["stem"] + ".yml"), encoding="utf-8"), Loader=Ld) or {}
        mp = os.path.join(ea.wdir(x["stem"]), "material.json")
        ja_mat = ""
        if os.path.exists(mp):
            m = json.load(open(mp, encoding="utf-8"))
            ja_mat = " / ".join(p["text"] for p in m.get("picks") or [] if not p.get("spoiler") and p.get("as") != "タグ")
        x = dict(x, words=[w for w in x["words"] if not w["auto"] and (x["stem"], w["en"]) not in done])
        try:
            ans, use = _lean_claude.ask(build_prompt(x, doc, desc.get(x.get("aid"), ""), ja_mat), SCHEMA, a.model, effort="low",
                                        system="あなたは漫画データベースの分類の助手。指示された JSON の形だけで答える。")
        except _lean_claude.LeanError as e:
            with lock:
                fails[0] += 1
                print(f"  失敗 {x['stem']}: {e}", flush=True)
            return
        got = {str(r.get("word", "")).split("(")[0].strip(): r for r in ans.get("words") or []}
        with lock:
            with open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
                for w in x["words"]:
                    r = got.get(w["ja"]) or got.get(w["en"]) or {}
                    v = r.get("verdict") if r.get("verdict") in ("前提", "展開", "不明") else "不明"
                    c[v] += 1
                    f.write(json.dumps({"stem": x["stem"], "ja": w["ja"], "en": w["en"], "verdict": v, "why": str(r.get("why", ""))[:60],
                                        "model": a.model, "version": VERSION, "at": now()}, ensure_ascii=False) + "\n")
            cost[0] += use.get("cost_usd") or 0; n[0] += 1
            if n[0] % 50 == 0:
                print(f"  {n[0]:,}/{len(todo):,}頁 {dict(c)} ${cost[0]:.2f}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(a.parallel) as ex:
        list(ex.map(one, todo))
    print(f"==== 今回の合計 ==== 頁 {n[0]:,} / {dict(c)} / ${cost[0]:.2f}" + (" / ■ 中断(モデルの失敗3件)" if fails[0] >= 3 else ""))


def verdicts():
    v = {}
    for x in jl(CANDS):
        for w in x["words"]:
            if w["auto"]:
                v[(x["stem"], w["en"])] = ("前提", "機械: " + w["auto"])
    for r in jl(LEDGER):
        v[(r["stem"], r["en"])] = (r["verdict"], r["why"])
    return v


def cmd_status(a):
    cands = jl(CANDS)
    tot = sum(len(x["words"]) for x in cands)
    v = verdicts()
    c = collections.Counter(k for k, _ in v.values())
    print(f"対象 {len(cands):,}頁・{tot:,}語 / 決まった {len(v):,}語 {dict(c)} / 残り {tot - len(v):,}語")
    words = collections.Counter(); ten = collections.Counter()
    ja = {(x["stem"], w["en"]): w["ja"] for x in cands for w in x["words"]}
    for k, (vv, _) in v.items():
        words[ja.get(k)] += 1
        if vv == "展開":
            ten[ja.get(k)] += 1
    print("展開(外す)の多い語:", "・".join(f"{w}{ten[w]}/{words[w]}" for w, _ in ten.most_common(20)))


def cmd_apply(a):
    ea = mod("_element-assign")
    v = verdicts()
    hide = json.load(open(ea.TAGS_HIDE_SEED, encoding="utf-8")) if os.path.exists(ea.TAGS_HIDE_SEED) else {}
    add = collections.defaultdict(list)
    for (stem, en), (vv, why) in v.items():
        if vv == "展開" and en not in (hide.get(stem) or []):
            add[stem].append(en)
    print(f"tags-hide に足す: {len(add):,}頁・{sum(map(len, add.values())):,}語" + ("" if a.go else "(試運転・何も書かない)"))
    if not a.go or not add:
        return
    import shutil
    bak = os.path.join(ROOT, ".cache", f"spoiler-judge-apply-bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    os.makedirs(bak, exist_ok=True)
    if os.path.exists(ea.TAGS_HIDE_SEED):
        shutil.copyfile(ea.TAGS_HIDE_SEED, os.path.join(bak, "tags-hide.json"))
    at = now()
    with open(APPLY_LOG, "a", encoding="utf-8", newline="\n") as f:
        for stem, ens in sorted(add.items()):
            before = list(hide.get(stem) or [])
            hide[stem] = sorted(set(before) | set(ens))
            f.write(json.dumps({"slug": stem, "op": "spoiler-judge apply", "version": VERSION, "before": {"tags_hide": before},
                                "after": {"tags_hide": hide[stem]}, "at": at, "go": a.go.strip(), "backup": os.path.relpath(bak, ROOT).replace("\\", "/")},
                               ensure_ascii=False) + "\n")
    tmp = ea.TAGS_HIDE_SEED + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(hide.items())), f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, ea.TAGS_HIDE_SEED)
    print(f"書いた / 退避 {os.path.relpath(bak, ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("candidates")
    p = sp.add_parser("run"); p.add_argument("--parallel", type=int, default=3); p.add_argument("--limit", type=int, default=0)
    p.add_argument("--model", default="claude-haiku-5-5")
    p.add_argument("--redo", default="", help="前の版でこの判定だった語を判定し直す(例 展開)")
    sp.add_parser("status")
    p = sp.add_parser("apply"); p.add_argument("--go", default="")
    a = ap.parse_args()
    {"candidates": cmd_candidates, "run": cmd_run, "status": cmd_status, "apply": cmd_apply}[a.cmd](a)


if __name__ == "__main__":
    main()
