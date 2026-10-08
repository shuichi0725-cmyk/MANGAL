#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要素付与 (element-assign) の実行体 = 要素収集(_element-harvest.py)の束から「付与案」を作る。 2026-10-09 新設。

流れ(★AIは読んで選ぶだけ。 候補づくり・根拠の検査・表づくりは道具):
  1) 道具: AniList のタグを票で機械的に仕分ける(表に出す / 控え)。 信頼源のジャンルも機械で決める
  2) 道具: 今の語彙の語を材料から一字一句で拾い、候補にする(意味が違う物が混ざる = 「ドラマCD」「葉山グループ」)
  3) モデル: 候補ごとに 芯/在る/違う を判定し、材料の一節を根拠に抜く。 語彙に在る別の語・新しい語も根拠つきで挙げる
  4) 道具: 根拠が材料に一字一句あるか等を検査し、付与案(assign-proposal.md)を書く
  ★ここは「案」を作るだけ。 本番データ・seed には一切書かない(試行中)。

モデルの呼び方 = `claude -p` を道具なし・短いシステム文で1回(会話の土台を読まない。 実測: 土台 約7万 → 約700トークン)。

usage:
  python scripts/_element-assign.py run <stem> [--model claude-sonnet-5-5]   候補づくり→判定→検査→付与案
  python scripts/_element-assign.py prepare <stem>                          モデルに渡す文面だけ作る(呼ばない)
  python scripts/_element-assign.py check <stem> [--answer <json>]          保存済みの答えを検査し直して付与案を作る
  python scripts/_element-assign.py show <stem>                             付与案を表示
  python scripts/_element-assign.py apply <stem> --go "<ユーザのGo発話>"     「表に出す案」と足すジャンルを seed へ書く(反映は別)
"""
import argparse, ast, datetime, json, os, re, shutil, subprocess, sys, time, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "v0.9"  # v0.9: 関連作から引き継ぐのは本筋のエントリだけ(票は収集の道具 v0.5 が絞る。 ジャンルもそろえる)/ 使わなかったタグを付与案に見せる  # v0.8: 表に出すのは強い順に最大10語・語彙と訳が在る語だけ / AniList と材料が一致した語を先に / 隠して持つ語を欄に分ける  # v0.7: ネタバレ印は「その語を持つエントリの半分以上に付いている時だけ」有効 / 呼び出しは共通部品(_lean_claude)  # v0.6: 作品ごとのユーザ裁定(rulings.yml)を付与案より優先 / apply のジャンル追記を二重にしない  # v0.5: apply(表に出す案を seed へ書く口。ユーザの Go 発話の引用が必須)  # v0.4(2026-10-09 ユーザ裁定): ネタバレ印の語は表に出さない(控えへ)/ 控えはサイトに出さず記録だけ  # v0.2: 指示文から試金石の語の例を外す / タグ一覧の語を候補に / ありふれた名詞を候補から外す
ME = "python scripts/_element-assign.py"
TEST_ROOT = os.environ.get("EH_ROOT")
BASE = TEST_ROOT or os.path.join(ROOT, ".cache", "element-harvest")
LEDGER_DIR = TEST_ROOT or os.path.join(ROOT, "data", "element-harvest")
MODEL = "claude-sonnet-5-5"

# ── 方針(★ユーザ裁定待ちの物は案。 変える時はここだけ直す) ──
ANI_SHOW = {"Theme": 60, "Cast": 70, "Setting": 70}  # AniList の票がこの線以上 = 表に出す案(今の取り込みの足切りと同じ)
ANI_KEEP = 40                                         # この線以上 = 控えに残す
SPOILER_TO_SUB = True                                # ★ユーザ裁定 2026-10-09「いらない」= ネタバレ印の語は表に出さず控えへ
# ★ただし AniList の印は粗い(三角関係の印は関連7件中1件だけだった)。 その語を持つエントリの「半分以上」に印が在る時だけ有効にする
#   (俺ガイルの4語へのユーザの反応と全部合う: 三角関係1/7=出す・更生1/2=控え・片思い2/3=控え・悲劇1/1=控え)
MAX_SHOW = 10                                        # 1頁に出す要素の上限(強い順)。 あふれた語は「隠して持つ」へ
HIDE_ALWAYS = {"Nudity"}                             # 票が高くても表には出さない AniList タグ(性的な描写の有無。 お色気はジャンルで足りる)
GENERIC = {"drama", "comedy", "romance", "slice-of-life", "action"}  # 汎用ジャンル = 信頼源(AniList)が言う時だけ。モデルには判定させない
A2M = {"Romance": "romance", "Comedy": "comedy", "Drama": "drama", "Action": "action", "Fantasy": "fantasy",
       "Slice of Life": "slice-of-life", "Adventure": "adventure", "Sci-Fi": "sci-fi", "Mystery": "mystery",
       "Horror": "horror", "Sports": "sports", "Mecha": "mecha", "Music": "music", "Thriller": "suspense",
       "Supernatural": "supernatural", "Ecchi": "ecchi", "Psychological": "mind-game", "Mahou Shoujo": "mahou-shoujo"}
# AniList タグの訳の読み替え案(直訳だと日本語の意味とずれる物)。 School Club=ユーザ「日本だと部活」/ Hikikomori=定義が「社会生活から身を引く人物」
JA_OVERRIDE = {"School Club": "部活", "Hikikomori": "ぼっち"}
# 対訳表(tag-i18n.yml)に訳が無い AniList タグの仮の訳。 付与案を読めるようにするためだけの物(正式な訳は対訳表に足す=ユーザ裁定)
JA_DRAFT = {"Chuunibyou": "中二病", "Femboy": "男の娘", "Bisexual": "バイセクシャル", "Urban": "都会", "Ensemble Cast": "群像劇",
            "Tomboy": "ボーイッシュ", "Teacher": "教師", "Gyaru": "ギャル"}
# どの学園もの・恋愛ものにも当てはまる名詞(語彙には在るが、付けても探す手がかりにならない)= 候補にしない
TOO_COMMON = {"高校生", "中学生", "小学生", "大学生", "少女", "少年", "美少女", "美少年", "女性", "男性", "ヒロイン", "主人公", "イケメン", "女子高生", "男子高校生", "青年"}

SCHEMA = {"type": "object", "required": ["judged", "added", "new_words"], "properties": {
    "judged": {"type": "array", "items": {"type": "object", "required": ["word", "tier", "pick", "quote", "why"], "properties": {
        "word": {"type": "string"}, "tier": {"type": "string", "enum": ["芯", "在る", "違う"]},
        "pick": {"type": "string"}, "quote": {"type": "string"}, "why": {"type": "string"}}}},
    "added": {"type": "array", "items": {"type": "object", "required": ["word", "tier", "pick", "quote", "why"], "properties": {
        "word": {"type": "string"}, "tier": {"type": "string", "enum": ["芯", "在る"]},
        "pick": {"type": "string"}, "quote": {"type": "string"}, "why": {"type": "string"}}}},
    "new_words": {"type": "array", "items": {"type": "object", "required": ["word", "tier", "pick", "quote", "why"], "properties": {
        "word": {"type": "string"}, "tier": {"type": "string", "enum": ["芯", "在る"]},
        "pick": {"type": "string"}, "quote": {"type": "string"}, "why": {"type": "string"}}}}}}

RULES = """あなたは漫画データベースの分類の助手。下の「材料」だけを根拠に、この漫画に付ける語を判定する。
自分の知識は使わない(この作品を知っていても、材料に書いていないことは根拠にしない)。

■ 3段階
- 芯   = 材料が「この作品はそれを描いている/それが主軸・主な舞台・主人公を決定づける性質だ」と述べている
- 在る = 作中にくり返し出る要素や、主要人物(主人公・ヒロイン級)の属性として書かれているが、作品の中心ではない
- 違う = 語は材料に出るが、付ける根拠にならない。 次はすべて「違う」:
    ・別の語や名前の一部(「ドラマCD」のドラマ、「葉山グループ」のループ)
    ・人名・あだ名・題名・店名・他作品の題の中に出るだけ
    ・脇役1人だけの性質、1回きりの出来事、たとえ話、冗談、将来の夢
    ・書誌・放送・商品の説明の中の語

■ 決まり
- 根拠(quote)は材料から一字一句で抜く(15〜70字。 言い換えない・足さない)。 pick には抜いた材料の番号(P3 や T9)を書く
- 「他サイトのタグ一覧」(番号が T で始まる材料)だけが根拠なら、最高でも「在る」
- 候補のうち[タグ一覧の語]は、他サイトの利用者がこの作品や主要人物に付けたタグ。 人物の性質・境遇を表す一般的な語なら「在る」、
  人名・あだ名・声優名・作品固有の名(部や学校の名)・その人物だけの言い回しは「違う」。 quote にはその語をそのまま書く
- ジャンルのうち ドラマ・コメディ・恋愛・日常・アクション は判定しない(別の仕組みで決める)。 それ以外のジャンルは、材料に明記がある時だけ
- added = 候補に無いが「使える語の一覧」に在る語で、材料がはっきり支えるもの(言い換えで支えていてもよい。 例: 材料「人として変わっていく姿を描く」→ 成長物語)。 迷う物は挙げない
- new_words = 「使える語の一覧」に無い語で、材料にその語が一字一句で出ており、他の漫画にも使える一般的な言葉(例: 社畜、毒親、余命)。
  この作品だけの固有名(部の名前・学校名・人名・技名)は挙げない。 quote にはその語を必ず含める
- why は判定の理由を20字以内で

■ 出力
judged = 「候補」の語すべてについて1件ずつ(違う も必ず書く)。 added と new_words は該当があるものだけ。"""


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def die(msg):
    print("✖ " + msg)
    sys.exit(1)


def stop(msg):
    print("■ 中断: " + msg + "\n  ★何も記録していない。 繰り返し叩かず、このまま報告する。")
    sys.exit(2)


def squash(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s or "")))


def wdir(stem):
    return os.path.join(BASE, stem)


def adir(stem):
    d = os.path.join(wdir(stem), "assign")
    os.makedirs(d, exist_ok=True)
    return d


# ───────── 語彙 ─────────
def load_vocab():
    import yaml
    with open(os.path.join(ROOT, "data", "genres.yml"), encoding="utf-8") as f:
        gy = yaml.safe_load(f)
    genres = {k: (v.get("name") if isinstance(v, dict) else v) for k, v in gy.items()}
    with open(os.path.join(ROOT, "data", "enrich-out-2026-07", "theme-vocab-ja.json"), encoding="utf-8") as f:
        ai = set(json.load(f))  # 今までAIが選べた159語
    with open(os.path.join(ROOT, "data", "seeds", "tag-i18n.yml"), encoding="utf-8") as f:
        ti = yaml.safe_load(f)
    ti = ti.get("tags", ti)
    tag_ja = {n: (v.get("ja") if isinstance(v, dict) else v) for n, v in ti.items()}
    with open(os.path.join(ROOT, "scripts", "_build-list-index.py"), encoding="utf-8") as f:
        src = f.read()
    old = ast.literal_eval(re.search(r"ANILIST_TAG_JA = (\{.*?\n\})", src, re.S).group(1))
    noise = ast.literal_eval(re.search(r"NOISE_TAGS = (\{.*?\})", src, re.S).group(1))
    tag_ja = {**old, **{k: v for k, v in tag_ja.items() if v}}
    with open(os.path.join(ROOT, "data", "seeds", "wamei-tags.yml"), encoding="utf-8") as f:
        w = yaml.safe_load(f) or {}
    allow, alias = set(w.get("allow") or []), dict(w.get("alias") or {})
    gnames = set(genres.values())
    display = (set(tag_ja.values()) | allow) - gnames - {None, ""}
    display -= {tag_ja[n] for n in noise if tag_ja.get(n)} | TOO_COMMON  # 男性主人公・異性愛 など出さない決まりの語と、ありふれた名詞
    for en, ja in JA_OVERRIDE.items():  # 読み替え(学園クラブ→部活)は、旧い訳を別名にして1語にまとめる
        was = tag_ja.get(en)
        if was and was != ja:
            alias[was] = ja
            display.discard(was)
    return {"genres": genres, "ai": ai, "display": display, "alias": alias, "tag_ja": tag_ja, "noise": set(noise), "allow": allow}


def word_status(word, V):
    return "語彙内" if word in V["ai"] else "表示できる語" if word in V["display"] else "新しい語"


# ───────── 束を読む ─────────
def load_material(stem):
    p = os.path.join(wdir(stem), "material.json")
    if not os.path.exists(p):
        die(f"材料の束が無い: {os.path.relpath(p, ROOT)}\n  先に要素収集を done まで: python scripts/_element-harvest.py status {stem}")
    with open(p, encoding="utf-8") as f:
        m = json.load(f)
    dom = {s["id"]: s for s in m["sources"]}
    for p_ in m["picks"]:
        s = dom.get(p_["src"], {})
        p_["pid"] = ("T" if p_["as"] == "タグ" else "P") + str(p_["id"])
        p_["domain"] = s.get("domain", "?")
    return m


# ───────── 1) AniList を票で仕分ける(機械) ─────────
def anilist_part(m, V):
    items, skipped, weak = [], [], []
    for r in m["anilist"]["tags"]:
        best = max(r["self"], r["novel"], r["anime"])  # 自分・原作小説・アニメ(本筋のエントリ)から引き継ぐ(他の漫画=アンソロジー等は使わない)
        spoiler = (r["ns"] * 2 >= r["n"]) if r.get("n") else r["spoiler"]  # n/ns が無い古い束は従来どおり
        name, cat = r["name"], r["category"]
        base = cat.split("-")[0]
        if name in V["noise"] or name.startswith("Primarily ") or cat == "Demographic" or r["adult"] or base in ("Sexual Content", "Technical") or cat.startswith("Theme-Game-Sport"):
            skipped.append(name)
            continue
        if best < ANI_KEEP:
            if r.get("weak", 0) >= ANI_KEEP:  # 登録者の少ない関連作・おまけ映像にしか無い票 = 使わない(見えるようにだけする)
                weak.append(f"{JA_OVERRIDE.get(name) or V['tag_ja'].get(name) or name}{r['weak']}")
            continue
        ja = JA_OVERRIDE.get(name) or V["tag_ja"].get(name)
        draft = not ja and name in JA_DRAFT
        ja = ja or JA_DRAFT.get(name)
        if ja in set(V["genres"].values()):  # 学園 など = ジャンルと同じ語
            skipped.append(name)
            continue
        tier = "芯" if best >= ANI_SHOW.get(base, 999) else "在る"
        if tier == "芯" and spoiler and SPOILER_TO_SUB:
            tier = "在る"
        items.append({"word": ja or name, "en": name, "tier": tier, "votes": best, "by": {"自分": r["self"], "小説": r["novel"], "アニメ": r["anime"]},
                      "spoiler": spoiler, "no_ja": not ja, "draft": draft, "reread": name in JA_OVERRIDE, "category": cat})
    fam = [e for e in m["anilist"]["entries"] if e.get("main", True) and (e["group"] in ("自分", "小説") or (e["group"] == "アニメ" and e.get("format") == "TV"))]
    gkeys = {}
    for e in fam:
        for g in e.get("genres") or []:
            k = A2M.get(g)
            if k:
                gkeys.setdefault(k, set()).add(e["group"])
    return items, gkeys, skipped, weak


# ───────── 2) 語彙の語を材料から機械で拾う ─────────
KATA = re.compile(r"[ァ-ヶー]")


def mask_titles(text, card):
    """この作品の題と『』の中(題名)は根拠にしないので、同じ長さの記号に置き換えてから探す。"""
    for t in sorted({card["title"], re.split(r"[-‐―—@~〜(\[【]", card["title"])[0]}, key=len, reverse=True):
        if len(t) >= 4:
            text = text.replace(t, "〓" * len(t))
    return re.sub(r"『[^』]{1,40}』", lambda mm: "〓" * len(mm.group(0)), text)


def sentence_at(text, i, j, width=44):
    a = max(text.rfind("。", 0, i), text.rfind("\n", 0, i)) + 1
    b = min([x for x in (text.find("。", j), text.find("\n", j)) if x != -1] or [len(text)])
    a, b = max(a, i - width), min(b + 1, j + width)
    return text[a:b].strip()


def find_candidates(m, V):
    words = {}
    for k, name in V["genres"].items():
        if k not in GENERIC and k != "other":
            words[name] = ("ジャンル", name)
    for w in V["display"]:
        words.setdefault(w, ("要素", w))
    for a, tgt in V["alias"].items():
        words.setdefault(a, ("要素", tgt))
    gname = set(V["genres"].values())
    have = {V["genres"].get(g, g) for g in m["card"]["genres"]}  # もう付いているジャンルは判定させない
    words = {w: ("ジャンル" if canon in gname else kind, canon) for w, (kind, canon) in words.items()
             if canon not in have and canon not in TOO_COMMON}
    cands = {}
    for p in m["picks"]:
        masked = mask_titles(p["text"], m["card"])
        for w, (kind, canon) in words.items():
            if len(w) < 2:
                continue
            for mm in re.finditer(re.escape(w), masked):
                i, j = mm.start(), mm.end()
                if KATA.fullmatch(w[0]) and KATA.fullmatch(w[-1]):  # カタカナ語は前後がカタカナ/英数なら別の語の一部
                    if (i > 0 and KATA.fullmatch(masked[i - 1])) or (j < len(masked) and (KATA.fullmatch(masked[j]) or masked[j].isascii() and masked[j].isalnum())):
                        continue
                c = cands.setdefault(canon, {"word": canon, "kind": kind, "hits": []})
                if len(c["hits"]) < 3 and not any(h["pick"] == p["pid"] for h in c["hits"]):
                    c["hits"].append({"pick": p["pid"], "sent": sentence_at(p["text"], i, j)})
    names = squash(m["card"]["title"] + "".join(m["card"]["authors"] + m["card"]["original_authors"]))
    for p in m["picks"]:  # タグ一覧(T)の語は、語彙に無くても1語ずつ候補にする
        if p["as"] != "タグ":
            continue
        for tok in p["text"].split():
            tok = V["alias"].get(tok, tok)
            if not (2 <= len(tok) <= 12) or tok in TOO_COMMON or tok in have or squash(tok) in names:
                continue
            c = cands.setdefault(tok, {"word": tok, "kind": "タグ一覧の語", "hits": []})
            for q in m["picks"]:
                if q["as"] != "タグ" and len(c["hits"]) < 2 and not any(h["pick"] == q["pid"] for h in c["hits"]):
                    i = mask_titles(q["text"], m["card"]).find(tok)
                    if i != -1:
                        c["hits"].append({"pick": q["pid"], "sent": sentence_at(q["text"], i, i + len(tok))})
            if not any(h["pick"] == p["pid"] for h in c["hits"]):
                c["hits"].append({"pick": p["pid"], "sent": tok})
    return sorted(cands.values(), key=lambda c: (c["kind"] != "ジャンル", c["kind"] == "タグ一覧の語", -len(c["hits"]), c["word"]))


# ───────── 3) モデルに渡す文面 ─────────
def build_prompt(m, V, cands):
    c = m["card"]
    gnow = "、".join(V["genres"].get(g, g) for g in c["genres"]) or "なし"
    L = [RULES, "", "■ 作品", f"題: {c['title']} / 著者: {'・'.join(c['authors'])} / 原作: {'・'.join(c['original_authors']) or '-'} / {c.get('publisher')} "
         f"/ {c.get('year_started')}年〜 / 全{c['volumes']}巻 / 今のジャンル: {gnow}", "", "■ 材料(番号で引く。 T で始まる番号は他サイトのタグ一覧)"]
    cats = (m.get("wikipedia") or {}).get("categories") or []
    for p in m["picks"]:
        L.append(f"[{p['pid']}] ({p['domain']} / {p['as']}{' / 終盤までの展開' if p['spoiler'] else ''}) {p['text']}")
    if cats:
        L.append(f"[C0] (Wikipedia のカテゴリ) {' / '.join(cats)}")
    L += ["", "■ 候補(道具が「使える語」を材料から機械で拾ったもの。 意味が違う物が混ざっている。 全部に判定を書く)"]
    for x in cands:
        L.append(f"- {x['word']}[{x['kind']}] " + " ／ ".join(f"{h['pick']}「…{h['sent']}…」" for h in x["hits"]))
    spec = [n for k, n in V["genres"].items() if k not in GENERIC and k != "other"]
    L += ["", "■ 使える語の一覧(added はここから選ぶ)", "ジャンル: " + "、".join(spec), "要素: " + "、".join(sorted(V["display"]))]
    return "\n".join(L)


def call_model(prompt, model):
    """道具なし・短いシステム文で1回だけ呼ぶ(会話の土台を読ませない)。 → (答え, 使用量)"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import _lean_claude
    try:
        return _lean_claude.ask(prompt, SCHEMA, model, system="あなたは漫画データベースの分類の助手。指示された JSON の形だけで答える。")
    except _lean_claude.LeanError as e:
        stop(str(e))


# ───────── 4) 検査して付与案にする ─────────
def verify(m, V, cands, ans):
    picks = {p["pid"]: p for p in m["picks"]}
    cmap = {c["word"]: c for c in cands}
    specific = {n: k for k, n in V["genres"].items() if k not in GENERIC and k != "other"}
    generic_names = {V["genres"][k] for k in GENERIC if k in V["genres"]}
    ok, bad = [], []

    def test(x, group):
        w, tier = str(x.get("word", "")).strip(), x.get("tier")
        w = V["alias"].get(w, w)
        row = {"word": w, "tier": tier, "pick": x.get("pick"), "quote": str(x.get("quote", "")).strip(), "why": str(x.get("why", ""))[:40], "group": group}
        if not w:
            return bad.append({**row, "reject": "語が空"})
        if w in TOO_COMMON:
            return bad.append({**row, "reject": "ありふれた名詞(どの作品にも当てはまる)なので付けない"})
        if w in generic_names:
            return bad.append({**row, "reject": "汎用ジャンルはモデルに判定させない(信頼源で決める)"})
        if group == "judged" and w not in cmap:
            return bad.append({**row, "reject": "候補に無い語を judged に書いた"})
        if w in specific and specific[w] in m["card"]["genres"]:
            return  # もう付いているジャンル(判定は要らない)
        row["kind"] = "ジャンル" if w in specific else "要素"
        row["vocab"] = "ジャンル" if w in specific else word_status(w, V)
        if group == "added" and row["vocab"] == "新しい語":
            group = row["group"] = "new_words"
        if group == "new_words" and row["vocab"] != "新しい語":
            group = row["group"] = "added"
        if tier == "違う":
            return ok.append(row)
        p = picks.get(str(row["pick"]).strip("[] "))
        if not p:
            return bad.append({**row, "reject": f"材料の番号 {row['pick']} が無い"})
        if len(squash(row["quote"])) < (2 if p["as"] == "タグ" else 8) or squash(row["quote"]) not in squash(p["text"]):
            return bad.append({**row, "reject": "根拠の文が、その番号の材料に一字一句で無い"})
        if group == "new_words" or (group == "judged" and row["vocab"] == "新しい語"):
            if w not in row["quote"]:
                return bad.append({**row, "reject": "新しい語なのに、根拠の文にその語が出ていない"})
            if not (2 <= len(w) <= 12) or squash(w) in squash(m["card"]["title"]) or any(w in a for a in m["card"]["authors"] + m["card"]["original_authors"]):
                return bad.append({**row, "reject": "語の長さが範囲外、または題名・著者名の一部"})
        row["domain"], row["role"] = p["domain"], p["as"]
        row["spoiler"] = bool(p["spoiler"])
        if p["as"] == "タグ" and tier == "芯":
            row["tier"], row["note"] = "在る", "タグ一覧だけが根拠なので 芯→在る に下げた"
        ok.append(row)

    for g in ("judged", "added", "new_words"):
        for x in ans.get(g) or []:
            if isinstance(x, dict):
                test(x, g)
    missing = sorted(set(cmap) - {r["word"] for r in ok if r["group"] == "judged"} - {r["word"] for r in bad})
    return ok, bad, missing


def load_rulings(stem):
    """作品ごとのユーザ裁定(data/element-harvest/rulings.yml)。 付与案の仕分けより優先する。
    → ({表に出す語: 引用}, {出さない語: 引用})"""
    import yaml
    p = os.path.join(ROOT, "data", "element-harvest", "rulings.yml")
    show, hide = {}, {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for r in doc.get("rulings") or []:
            if stem in (r.get("stems") or []):
                for w in r.get("show") or []:
                    show[w] = r.get("quote") or ""
                    hide.pop(w, None)
                for w in r.get("hide") or []:
                    hide[w] = r.get("quote") or ""
                    show.pop(w, None)
    return show, hide


def make_proposal(stem, m, V, cands, ans, use):
    ani, gkeys, ani_skip, ani_weak = anilist_part(m, V)
    ok, bad, missing = verify(m, V, cands, ans)
    c = m["card"]
    merged = {}  # 語 → 1行(AniList と材料の根拠をまとめる)
    for a in ani:
        merged[a["word"]] = {"word": a["word"], "kind": "要素", "tier": a["tier"], "vocab": "訳の無いAniListタグ" if a["no_ja"] else word_status(a["word"], V),
                             "ani": a, "mat": [], "spoiler": a["spoiler"]}
    for r in ok:
        if r["tier"] == "違う":
            continue
        e = merged.setdefault(r["word"], {"word": r["word"], "kind": r["kind"], "tier": r["tier"], "vocab": r["vocab"], "ani": None, "mat": [], "spoiler": False})
        e["mat"].append(r)
        e["kind"] = r["kind"]
        if r["tier"] == "芯":
            e["tier"] = "芯"
        if not e["ani"]:
            e["spoiler"] = all(x["spoiler"] for x in e["mat"])
    for e in merged.values():  # 根拠が終盤の展開だけの語も、表には出さない
        if e["spoiler"] and e["tier"] == "芯" and SPOILER_TO_SUB:
            e["tier"] = "在る"
    show, hide = load_rulings(stem)  # ★ユーザ裁定が最優先(票の線・ネタバレ印より上)
    unruled = []
    for w, q in show.items():
        if w in merged:
            merged[w]["tier"], merged[w]["ruled"] = "芯", f"ユーザ裁定で表に出す「{q}」"
        else:
            unruled.append(w)  # 根拠(AniList の票も材料も)が無い語は、裁定があっても付与案に載せられない
    for w, q in hide.items():
        if w in merged:
            merged[w]["tier"], merged[w]["ruled"] = "在る", f"ユーザ裁定で出さない「{q}」"
    def strength(e):
        """強さ: ユーザ裁定 > AniList と材料が一致(票順) > AniList だけ(票順) > 材料だけ(根拠の数)"""
        v = e["ani"]["votes"] if e["ani"] else 0
        return (0 if e.get("ruled") else 1, 0 if (e["ani"] and e["mat"]) else 1 if e["ani"] else 2, -v, -len(e["mat"]), e["word"])

    n_show = 0
    for e in sorted(merged.values(), key=strength):
        if e["kind"] != "要素":
            continue
        a = e["ani"] or {}
        if e["tier"] != "芯":
            e["cls"], e["hid"] = "隠し", "ネタバレ印" if e["spoiler"] and a.get("votes", 0) >= ANI_SHOW.get(a.get("category", "").split("-")[0], 999) else "在る"
        elif a.get("en") in HIDE_ALWAYS and not e.get("ruled"):
            e["cls"], e["hid"] = "隠し", "出さない語"
        elif e["vocab"] not in ("語彙内", "表示できる語") or a.get("no_ja") or a.get("draft"):
            e["cls"], e["hid"] = "隠し", "語彙か訳が無い"  # 強い語なのに出せない = 語ごとの裁定の候補
        elif n_show >= MAX_SHOW and not e.get("ruled"):
            e["cls"], e["hid"] = "隠し", "上限"
        else:
            e["cls"], e["hid"] = "表", ""
            n_show += 1
    rows = sorted(merged.values(), key=lambda e: (e.get("cls") != "表", strength(e)))
    gnow = [V["genres"].get(g, g) for g in c["genres"]]
    gadd = [(V["genres"][k], sorted(v)) for k, v in sorted(gkeys.items()) if k not in c["genres"]]
    out = [f"# 付与案: {c['title']} ({stem})", f"道具 {VERSION} / 判定 {use.get('model')} / {now()} / 読み込み {use.get('in')}・出力 {use.get('out')} トークン / {use.get('sec')}秒", "",
           "★これは案。 データには何も書いていない。", "", "## ジャンル", f"- 今: {'・'.join(gnow)}"]
    out.append("- 足す案(信頼源): " + ("、".join(f"{n}(AniList の{'・'.join(v)})" for n, v in gadd) or "なし"))
    gm = [e for e in rows if e["kind"] == "ジャンル"]
    out.append("- 材料から(具体的なジャンル): " + ("、".join(f"{e['word']}({'主軸' if e['tier'] == '芯' else '在る'})" for e in gm) or "なし"))

    def ev(e):
        parts = []
        if e["ani"]:
            a = e["ani"]
            parts.append(f"AniList {a['en']} 票{a['votes']}" + ("・読み替え案" if a["reread"] else "") + ("・訳なし" if a["no_ja"] else "") + ("・仮の訳" if a.get("draft") else ""))
        for r in e["mat"][:2]:
            parts.append(f"{r['domain']}「{r['quote'][:60]}」" + (f"〔{r['note']}〕" if r.get("note") else ""))
        return " / ".join(parts)

    n = 0
    isnew = lambda e: e["vocab"] == "新しい語"  # noqa: E731
    hid = lambda e, *why: e.get("cls") == "隠し" and e.get("hid") in why  # noqa: E731
    for title, pick in ((f"表に出す案(強い順に最大{MAX_SHOW}語)= サイトに出すのはここだけ", lambda e: e.get("cls") == "表"),
                        ("隠して持つ: 強いが上限であふれた語", lambda e: hid(e, "上限")),
                        ("隠して持つ: 強いが語彙か訳が無くて出せない語(語ごとの裁定の候補)", lambda e: hid(e, "語彙か訳が無い")),
                        ("隠して持つ: ネタバレ印・出さない決まりの語", lambda e: hid(e, "ネタバレ印", "出さない語")),
                        ("隠して持つ: 作中に在るが中心でない語", lambda e: hid(e, "在る") and not isnew(e)),
                        ("新しい語の候補(在る・付けずに貯めて、何作にも出た語だけ採否を決める)", lambda e: hid(e, "在る") and isnew(e))):
        out += ["", f"## {title}"]
        for e in [x for x in rows if pick(x) and x["kind"] == "要素"]:
            n += 1
            mark = "" if e["vocab"] == "語彙内" else f"〔{e['vocab']}〕"
            out.append(f"{n}. **{e['word']}**{mark}{'(ネタバレ印)' if e['spoiler'] else ''} — {ev(e)}"
                       + (f" 〔{e['ruled']}〕" if e.get("ruled") else ""))
    out += ["", "## 付けない(語は材料に在るが、根拠にならないとモデルが判定)"]
    for r in [x for x in ok if x["tier"] == "違う" and x["word"] not in merged]:
        out.append(f"- {r['word']}: {r['why']}")
    if bad:
        out += ["", "## 道具が弾いた答え"]
        for r in bad:
            out.append(f"- {r['word']}({r.get('tier')}): {r['reject']} / 「{r['quote'][:40]}」")
    if missing:
        out += ["", "## 判定が返らなかった候補", "- " + "、".join(missing)]
    if unruled:
        out += ["", "## ユーザ裁定で「表に出す」とされたが、根拠が無くて載せられなかった語", "- " + "、".join(unruled)]
    if ani_weak:
        out += ["", "## 使わなかった AniList の票(登録者の少ない関連作・おまけ映像にしか無い)", "- " + "、".join(ani_weak)]
    out += ["", f"(AniList で対象外にしたタグ: {'、'.join(ani_skip) or 'なし'} / 表に出す線: 主題60・人物70・舞台70 / 控えの線: {ANI_KEEP})"]
    d = adir(stem)
    with open(os.path.join(d, "assign-proposal.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join(d, "assign-proposal.json"), "w", encoding="utf-8") as f:
        json.dump({"stem": stem, "version": VERSION, "use": use, "genres_now": c["genres"], "genres_add": sorted(k for k in gkeys if k not in c["genres"]),
                   "rows": rows, "rejected": bad, "not": [x for x in ok if x["tier"] == "違う"], "missing": missing, "ani_weak": ani_weak}, f, ensure_ascii=False, indent=1)
    return out, rows, ok, bad, missing


def cmd_prepare(a):
    V = load_vocab()
    m = load_material(a.stem)
    cands = find_candidates(m, V)
    prompt = build_prompt(m, V, cands)
    d = adir(a.stem)
    with open(os.path.join(d, "assign-prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)
    with open(os.path.join(d, "assign-cands.json"), "w", encoding="utf-8") as f:
        json.dump(cands, f, ensure_ascii=False, indent=1)
    print(f"候補 {len(cands)}語(ジャンル {sum(1 for c in cands if c['kind'] == 'ジャンル')}・要素 {sum(1 for c in cands if c['kind'] == '要素')})"
          f" / モデルに渡す文面 {len(prompt)}字 → {os.path.relpath(os.path.join(d, 'assign-prompt.txt'), ROOT)}")
    return V, m, cands, prompt


def finish(a, V, m, cands, ans, use, record=True):
    out, rows, ok, bad, missing = make_proposal(a.stem, m, V, cands, ans, use)
    core = [e["word"] for e in rows if e.get("cls") == "表"]
    sub = [e["word"] for e in rows if e.get("cls") == "隠し"]
    new = [e["word"] for e in rows if e["vocab"] == "新しい語"]
    print(f"== 要素付与の案 ({VERSION} / {use.get('model')}) ==\n作品: {m['card']['title']} ({a.stem})")
    print(f"表に出す案 {len(core)}: {'・'.join(core)}\n隠して持つ {len(sub)}: {'・'.join(sub)}\n新しい語 {len(new)}: {'・'.join(new) or 'なし'}")
    print(f"付けない {sum(1 for x in ok if x['tier'] == '違う')} / 道具が弾いた {len(bad)} / 判定なし {len(missing)}"
          f" / 読み込み {use.get('in')}・出力 {use.get('out')} トークン・{use.get('sec')}秒")
    print(f"付与案 → {os.path.relpath(os.path.join(adir(a.stem), 'assign-proposal.md'), ROOT)}")
    if not record:
        return
    os.makedirs(LEDGER_DIR, exist_ok=True)
    with open(os.path.join(LEDGER_DIR, "assign-ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), "stem": a.stem, "title": m["card"]["title"], "version": VERSION, **use, "core": core, "sub": sub, "new": new,
                            "not": sum(1 for x in ok if x["tier"] == "違う"), "rejected": len(bad), "missing": len(missing)}, ensure_ascii=False) + "\n")
    with open(os.path.join(LEDGER_DIR, "word-candidates.jsonl"), "a", encoding="utf-8") as f:  # 新しい語の候補(付けずに貯める)
        for e in rows:
            if e["vocab"] == "新しい語":
                r = e["mat"][0] if e["mat"] else {}
                f.write(json.dumps({"word": e["word"], "stem": a.stem, "tier": e["tier"], "quote": r.get("quote"), "domain": r.get("domain"),
                                    "anilist": (e["ani"] or {}).get("en"), "at": now(), "model": use.get("model"), "version": VERSION}, ensure_ascii=False) + "\n")


def cmd_run(a):
    V, m, cands, prompt = cmd_prepare(a)
    ans, use = call_model(prompt, a.model)
    with open(os.path.join(adir(a.stem), "assign-answer.json"), "w", encoding="utf-8") as f:
        json.dump({"use": use, "answer": ans}, f, ensure_ascii=False, indent=1)
    finish(a, V, m, cands, ans, use, record=not a.no_record)


def cmd_check(a):
    V = load_vocab()
    m = load_material(a.stem)
    cands = find_candidates(m, V)
    p = a.answer or os.path.join(adir(a.stem), "assign-answer.json")
    if not os.path.exists(p):
        die(f"答えが無い: {p}")
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    finish(a, V, m, cands, d.get("answer", d), d.get("use") or {"model": "(保存済みの答え)"}, record=False)


# ───────── 5) 付与案を seed へ書く(★ユーザの Go が要る。 ここは seed に足すだけで、頁への反映は _reflect-targeted.py) ─────────
def _rw_same_newline(path, add_text):
    """既存ファイルの改行(CRLF/LF)に合わせて末尾へ追記する。"""
    with open(path, "rb") as f:
        raw = f.read()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    body = add_text.replace("\r\n", "\n").encode("utf-8").replace(b"\n", nl)
    with open(path, "ab") as f:
        f.write((b"" if raw.endswith(nl) or not raw else nl) + body)


def cmd_apply(a):
    V = load_vocab()
    pj = os.path.join(adir(a.stem), "assign-proposal.json")
    if not os.path.exists(pj):
        die(f"付与案がまだ無い → {ME} run {a.stem}")
    if len((a.go or "").strip()) < 2:
        die('--go "<ユーザのGo発話の引用>" が要る(案を本番の seed に書くのはユーザの承認があった時だけ)')
    with open(pj, encoding="utf-8") as f:
        prop = json.load(f)
    core = [e for e in prop["rows"] if (e.get("cls") == "表" if any("cls" in x for x in prop["rows"]) else e["tier"] == "芯" and e["kind"] == "要素")]
    names, blocked = [], []
    for e in core:
        ani = e.get("ani") or {}
        # 対訳表で表示できる AniList タグは英名で書く。 読み替え・仮の訳・材料由来の語は和名で書く(和名タグの allow に在る語だけ)
        if ani and not ani.get("reread") and not ani.get("no_ja") and not ani.get("draft") and V["tag_ja"].get(ani["en"]):
            names.append(ani["en"])
        elif e["word"] in V["allow"]:
            names.append(e["word"])
        else:
            blocked.append(e["word"])
    if blocked:
        die("表に出す案のうち、まだ語彙(data/seeds/wamei-tags.yml の allow)に無い語がある: " + "・".join(blocked)
            + "\n  語彙に足すのはユーザ裁定。 足してから apply し直す(足さない語は付けない)")
    page = os.path.join(ROOT, "data", "manga.v2", a.stem + ".yml")
    if not os.path.exists(page):
        die(f"頁が無い: {page}")
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(ROOT, ".cache", f"element-assign-bak-{ts}")
    os.makedirs(bak, exist_ok=True)
    shutil.copyfile(page, os.path.join(bak, a.stem + ".yml"))
    # 要素: tags-enrich-2425.json(slug → タグ名の配列。 promote が union する。 書式=1行・区切りに空白なし)
    tp = os.path.join(ROOT, "data", "seeds", "tags-enrich-2425.json")
    with open(tp, encoding="utf-8") as f:
        raw = f.read()
    tags = json.loads(raw)
    if json.dumps(tags, ensure_ascii=False, separators=(",", ":")) != raw:
        die("tags-enrich-2425.json の書式が想定と違う(書き戻すと全体が変わる)→ 何も書かずに止める")
    before = list(tags.get(a.stem) or [])
    after = names + [n for n in before if n not in names]  # 並びは付与案の順(票の高い順)。 前から在った語は後ろに残す
    # ジャンル: genre-append.yml(足すだけ・出所つき。 同じ slug に同じジャンルを二重に足さない)
    import yaml
    with open(os.path.join(ROOT, "data", "seeds", "genre-append.yml"), encoding="utf-8") as f:
        done = {g for e in (yaml.safe_load(f) or {}).get("additions") or [] if e.get("slug") == a.stem for g in e.get("add") or []}
    gadd = [g for g in prop.get("genres_add") or [] if g in V["genres"] and g not in (prop.get("genres_now") or []) and g not in done]
    if after == before and not gadd:
        print(f"{a.stem}: seed は既に付与案どおり(何も書かない・記録も足さない)")
        return
    tags[a.stem] = after
    with open(tp, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(tags, ensure_ascii=False, separators=(",", ":")))
    if gadd:
        _rw_same_newline(os.path.join(ROOT, "data", "seeds", "genre-append.yml"),
                         f"  - slug: {a.stem}\n    add: [{', '.join(gadd)}]\n    source: \"element-assign:{prop['version']} anilist-family\"\n")
    line = {"slug": a.stem, "op": "element-assign apply", "at": now(), "version": VERSION, "proposal_version": prop["version"],
            "judge_model": (prop.get("use") or {}).get("model"), "go": a.go.strip(),
            "before": {"tags_enrich": before, "genres": prop.get("genres_now")},
            "after": {"tags_enrich": after, "genre_append": gadd},
            "shown_words": [e["word"] for e in core], "backup": os.path.relpath(os.path.join(bak, a.stem + ".yml"), ROOT).replace("\\", "/"),
            "revert": "tags-enrich-2425.json からこの slug の追加分を消し、genre-append.yml の source=element-assign の行を消して反映し直す"}
    with open(os.path.join(ROOT, "data", "seeds", "element-assign-changelog.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"seed に書いた: {a.stem}\n  要素 +{len(after) - len(before)}: {'・'.join(n for n in after if n not in before)}"
          f"\n  ジャンル +{len(gadd)}: {'・'.join(V['genres'][g] for g in gadd) or 'なし'}\n  退避: {line['backup']}")
    print(f"次: python scripts/_reflect-targeted.py --only {a.stem} --commit-only -m \"…\"(頁への反映。 テスト環境へは .preview-data へのコピーが要る)")


def cmd_show(a):
    p = os.path.join(adir(a.stem), "assign-proposal.md")
    if not os.path.exists(p):
        die(f"付与案がまだ無い → {ME} run {a.stem}")
    with open(p, encoding="utf-8") as f:
        print(f.read())


def main():
    ap = argparse.ArgumentParser(description="要素付与(付与案づくり)。 正本 = skill element-assign")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run"); p.add_argument("stem"); p.add_argument("--model", default=MODEL)
    p.add_argument("--no-record", action="store_true", help="台帳に書かない(道具の試し用)"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("prepare"); p.add_argument("stem"); p.set_defaults(f=cmd_prepare)
    p = sp.add_parser("check"); p.add_argument("stem"); p.add_argument("--answer"); p.set_defaults(f=cmd_check)
    p = sp.add_parser("show"); p.add_argument("stem"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("apply"); p.add_argument("stem"); p.add_argument("--go", default=""); p.set_defaults(f=cmd_apply)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
