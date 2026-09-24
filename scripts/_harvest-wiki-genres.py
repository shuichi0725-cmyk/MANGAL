"""Wikipediaジャンルカテゴリ収穫(信頼源)。 ja.wikipedia の Category:ジャンル別の漫画 を
BFSで辿り、 各カテゴリ名をキーワードでmasterキーにマップ → 所属記事(漫画題)を
db-v2 の series と題名突合 → genre-wiki.yml(series_key→add[]) を出力。

★ユーザ裁定(2026-06-13): Wiki全カテゴリ全採用。 スポーツは野球/サッカーのみサブタグ、
  他競技は sports に寄せる。 タクソノミー(master)は増やさない(warは別途追加済)。
★突合は野球/サッカーで実証済みの方式の一般化。 read-only(出力はseed、 本番不変)。
"""
import sys, json, re, time, urllib.parse, urllib.request, sqlite3
from collections import defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
API = "https://ja.wikipedia.org/w/api.php"
OUT = ROOT / "data" / "seeds" / "genre-wiki.yml"

# カテゴリ名キーワード → master キー(明白なもののみ。 不明なカテゴリはskip)
KW2M = [
    ("野球", "baseball"), ("サッカー", "soccer"),  # スポーツのサブ(先に判定)
    ("スポーツ", "sports"), ("競技", "sports"),
    ("ボーイズラブ", "bl"), ("BL", "bl"), ("やおい", "bl"),
    ("異世界", "isekai"), ("学園", "school"), ("学校", "school"),
    ("妖怪", "yokai"), ("料理", "gourmet"), ("グルメ", "gourmet"), ("食", "gourmet"),
    ("4コマ", "4-koma"), ("四コマ", "4-koma"), ("エッセイ", "essay"),
    ("戦争", "war"), ("ミリタリー", "war"), ("音楽", "music"),
    # ★「時代劇」は「時代」より先に判定(2026-09-24): 旧順では Category:時代劇漫画 が historical に入り、
    #   samurai(表示名=時代劇)が139作しか無い原因の1つだった。
    ("魔法少女", "mahou-shoujo"), ("時代劇", "samurai"), ("歴史", "historical"), ("時代", "historical"),
    ("ファンタジー", "fantasy"), ("SF", "sci-fi"), ("サイエンス", "sci-fi"),
    ("推理", "mystery"), ("ミステリ", "mystery"), ("探偵", "mystery"),
    ("ホラー", "horror"), ("恐怖", "horror"), ("サスペンス", "suspense"),
    ("ギャグ", "gag"), ("コメディ", "comedy"), ("ラブコメ", "romcom"),
    ("恋愛", "romance"), ("アクション", "action"), ("冒険", "adventure"),
    ("ロボット", "mecha"), ("メカ", "mecha"), ("超常", "supernatural"),
    ("日常", "slice-of-life"), ("お色気", "ecchi"), ("侍", "samurai"), ("剣豪", "samurai"),
]


def cat_to_master(name):
    for kw, m in KW2M:
        if kw in name:
            return m
    return None


def api(params):
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MANGAL-genre-harvest/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(2)
    return {}


def members(cat, kind):  # kind: "page"(記事) or "subcat"
    out = []
    cont = None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
             "cmlimit": "500", "cmtype": kind, "cmnamespace": "0" if kind == "page" else "14"}
        if cont:
            p["cmcontinue"] = cont
        d = api(p)
        for m in d.get("query", {}).get("categorymembers", []):
            t = m.get("title", "")
            out.append(t.replace("Category:", "") if kind == "subcat" else t)
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(0.3)
    return out


def norm(t):
    t = re.sub(r"\(.*?\)|（.*?）", "", t or "")  # 曖昧さ回避括弧 (漫画) 等
    t = re.sub(r"[\s　・:：!！?？.,。、'\"’”「」『』\-–—~〜=＝/／]", "", t)
    return t.lower()


# ★薄いジャンルの追補モード(2026-09-24 ユーザGO「方法3=Wikipediaカテゴリを取り直す」):
#   genre-wiki.yml(trusted源)に足すと promote の「信頼源があれば AI 由来ジャンルを捨てる」分岐が働き、
#   ジャンルが消える頁が出る = 付与でなく置換になる。→ genre-append.yml(union only・フラグ不変)へ候補を出す。
#   ★起点は明示(BFSの「ジャンル別の漫画」からは 4コマ漫画[漫画の形式の下]/ボーイズラブ漫画[漫画のジャンルの下]に届かない)。
#   ★下位カテゴリは1段だけ・同じキーに写るものだけ。「〜を舞台とした」系(飲食店が舞台なだけ等)は使わない。
#   ★「ロボットを題材とした漫画作品」はドラえもん/鉄腕アトムを含む = メカ(巨大ロボット)ではない → 巨大ロボットだけ。
#   ★魔法少女は漫画のカテゴリが存在しない(2026-09-24 確認)。
#   ★429(アクセス過多)は待って再試行、それでも取れなければ**止まる**(黙って0件=「新規なし」に見せない)。
#   突合は「本番索引の題名で**1作にしか当たらない**」時だけ(同名別作への誤付与を防ぐ)。
THIN_ROOTS = (
    ("時代劇漫画", "samurai"), ("4コマ漫画", "4-koma"), ("ボーイズラブ漫画", "bl"), ("野球漫画", "baseball"),
    ("サッカー漫画", "soccer"), ("戦争漫画", "war"), ("料理・グルメ漫画", "gourmet"), ("妖怪を題材とした漫画作品", "yokai"),
    ("巨大ロボットを題材とした漫画作品", "mecha"), ("音楽漫画", "music"), ("ギャグ漫画", "gag"),
)
THIN_SUB_NG = ("舞台", "ロボットを題材とした漫画作品")
CAND_TSV = ROOT / "docs" / "production-diagnostics" / "wiki-genre-append-candidates.tsv"
APPEND = ROOT / "data" / "seeds" / "genre-append.yml"


def api_strict(params):
    """429 は待って再試行(10/30/60/120秒)、それでも駄目なら例外で止まる。1リクエストごとに1秒空ける。"""
    import urllib.error
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    for wait in (0, 10, 30, 60, 120):
        time.sleep(1.0 + wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MANGAL-genre-harvest/1.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            print(f"  429 → {wait or 10}秒待って再試行", flush=True)
    raise RuntimeError("Wikipedia API 429 が続いた = 中断(部分結果を『新規なし』扱いにしない)")


def members_strict(cat, kind):
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmlimit": "500",
             "cmtype": kind, "cmnamespace": "0" if kind == "page" else "14"}
        if cont:
            p["cmcontinue"] = cont
        d = api_strict(p)
        if "query" not in d:
            raise RuntimeError(f"categorymembers 応答異常: {cat} {str(d)[:200]}")
        for m in d["query"].get("categorymembers", []):
            t = m.get("title", "")
            out.append(t.replace("Category:", "") if kind == "subcat" else t)
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            return out


def thin_append(apply: bool):
    idx = json.loads((ROOT / "data" / "manga-list-index.json").read_text(encoding="utf-8"))
    F = idx["f"]; si, ti, gi = F.index("slug"), F.index("title"), F.index("genres")
    by_title = defaultdict(list); genres = {}
    for r in idx["d"]:
        by_title[norm(r[ti])].append(r[si]); genres[r[si]] = set(r[gi] or [])
    targets = []
    for root, key in THIN_ROOTS:
        targets.append((root, key))
        for sub in members_strict(root, "subcat"):
            if cat_to_master(sub) == key and not any(ng in sub for ng in THIN_SUB_NG):
                targets.append((sub, key))
    cand = {}  # (slug, key) -> (category, article)
    stats = []
    for cat, key in targets:
        arts = members_strict(cat, "page"); hit = amb = have = 0
        for a in arts:
            k = norm(a)
            if len(k) < 2:
                continue
            slugs = by_title.get(k) or []
            if len(slugs) != 1:
                amb += len(slugs) > 1
                continue
            s = slugs[0]
            if key in genres.get(s, set()):
                have += 1
                continue
            hit += 1
            cand.setdefault((s, key), (cat, a))
        stats.append((key, cat, len(arts), have, hit, amb))
    rows = sorted(cand.items())
    CAND_TSV.parent.mkdir(parents=True, exist_ok=True)
    CAND_TSV.write_text("".join(f"{s}\t{k}\t{c}\t{a}\n" for (s, k), (c, a) in rows), encoding="utf-8")
    print(f"候補 {len(rows)} (slug×key) → {CAND_TSV}")
    for key, cat, na, have, hit, amb in stats:
        print(f"  {key:<13} {cat[:26]:<26} 記事{na:>4} 付与済{have:>4} 新規{hit:>4} 同名で見送り{amb:>3}")
    if not apply:
        return
    import yaml
    cur = yaml.safe_load(APPEND.read_text(encoding="utf-8")) if APPEND.exists() else {}
    have_pairs = {(e.get("slug"), g) for e in (cur or {}).get("additions", []) for g in (e.get("add") or [])}
    by_slug = defaultdict(list); src = {}
    for (s, k), (c, a) in rows:
        if (s, k) not in have_pairs:
            by_slug[s].append(k); src[s] = f"wiki-category:{c}"
    lines = []
    for s in sorted(by_slug):
        lines.append(f"  - slug: {s}\n    add: [{', '.join(sorted(by_slug[s]))}]\n"
                     f"    source: {json.dumps(src[s], ensure_ascii=False)}\n")
    with APPEND.open("a", encoding="utf-8") as f:
        f.write("".join(lines))
    print(f"genre-append.yml へ追記: {len(by_slug)} slug")



_PAREN_OK = ("漫画", "アニメ", "仮題", "BL漫画")


def wiki_article_ok(article, page_authors):
    """記事名の曖昧さ回避括弧で同一作品かを確かめる(2026-09-24 実踏)。
    「八犬伝 (碧也ぴんくの漫画)」→あべ美幸版に当たっていた / 「花音 (漫画雑誌)」→さいとうちほの少女漫画に当たっていた。
    採る: 括弧なし・(漫画)(アニメ)(仮題)(BL漫画)・(〈作者〉の漫画)で作者が頁の著者と一致。その他の括弧は採らない。"""
    m = re.search(r"[（(]([^()（）]*)[)）]\s*$", article or "")
    if not m:
        return True
    p = m.group(1).strip()
    if p in _PAREN_OK:
        return True
    if p.endswith("の漫画"):
        a = norm(p[:-3])
        return any(a and (a in norm(x) or norm(x) in a) for x in page_authors if x)
    return False


def thin_append_apply():
    """候補TSV(--thin-append の出力)を読み、同一作品チェックを通したものだけ genre-append.yml へ追記(再収穫しない)。"""
    import yaml
    idx = json.loads((ROOT / "data" / "manga-list-index.json").read_text(encoding="utf-8"))
    F = idx["f"]; si, ai = F.index("slug"), F.index("authors")
    authors = {r[si]: [a.split("\t")[0] for a in (r[ai] or [])] for r in idx["d"]}
    rows = [l.split("\t") for l in CAND_TSV.read_text(encoding="utf-8").splitlines() if l.strip()]
    cur = yaml.safe_load(APPEND.read_text(encoding="utf-8")) if APPEND.exists() else {}
    have_pairs = {(e.get("slug"), g) for e in (cur or {}).get("additions", []) for g in (e.get("add") or [])}
    by_slug = defaultdict(list); src = {}; skipped = []
    for s, k, c, a in rows:
        if s not in authors:
            skipped.append((s, a, "索引に無い")); continue
        if not wiki_article_ok(a, authors[s]):
            skipped.append((s, a, "括弧の作品違い")); continue
        if (s, k) in have_pairs or k in by_slug[s]:
            continue
        by_slug[s].append(k); src.setdefault(s, f"wiki-category:{c}")
    lines = []
    for s in sorted(by_slug):
        if not by_slug[s]:
            continue
        lines.append(f"  - slug: {s}\n    add: [{', '.join(sorted(by_slug[s]))}]\n"
                     f"    source: {json.dumps(src[s], ensure_ascii=False)}\n")
    with APPEND.open("a", encoding="utf-8") as f:
        f.write("".join(lines))
    n = sum(len(v) for v in by_slug.values())
    print(f"genre-append.yml へ追記: {len([s for s in by_slug if by_slug[s]])} slug / {n} 付与 / 見送り {len(skipped)}")
    for s, a, why in skipped:
        print(f"  見送り {why}: {a} → {s}")

def main():
    if "--thin-append-apply" in sys.argv:
        return thin_append_apply()
    if "--thin-append" in sys.argv:
        return thin_append(apply=False)  # 候補TSVだけ。適用は --thin-append-apply(同一作品チェックつき)
    # db: 正規化title -> [series_key]
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
    title2keys = defaultdict(list)
    for sk, t in con.execute("SELECT series_key, title FROM series"):
        title2keys[norm(t)].append(sk)

    # BFS: ジャンル別の漫画 → サブカテゴリ(深さ2まで)
    seen_cat = set(); queue = [("ジャンル別の漫画", 0)]
    additions = defaultdict(set)
    report = []
    while queue:
        cat, depth = queue.pop(0)
        if cat in seen_cat or depth > 2:
            continue
        seen_cat.add(cat)
        m = cat_to_master(cat)
        # サブカテゴリを辿る
        for sub in members(cat, "subcat"):
            if sub not in seen_cat:
                queue.append((sub, depth + 1))
        if not m:
            continue  # master未対応カテゴリ=記事は拾わない(辿るだけ)
        arts = members(cat, "page")
        matched = 0
        for a in arts:
            keys = title2keys.get(norm(a))
            if keys:
                matched += 1
                for k in keys:
                    additions[k].add(m)
        report.append((cat, m, len(arts), matched))
        time.sleep(0.2)

    # 出力(series_key -> sorted add)
    lines = ["# Wikipediaジャンルカテゴリ突合(自動生成 _harvest-wiki-genres.py)。",
             "# Category:ジャンル別の漫画 BFS→キーワードでmaster→db題名突合。 promoteがtrusted源として採用。",
             "additions:"]
    for k in sorted(additions):
        kq = json.dumps(k, ensure_ascii=False)
        vs = json.dumps(sorted(additions[k]), ensure_ascii=False)
        lines.append(f"  - {{series_key: {kq}, add: {vs}}}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"カテゴリ走査: {len(report)} (master対応) / 辿った総カテゴリ {len(seen_cat)}")
    print(f"突合できた series_key: {len(additions):,} → {OUT}")
    print("\n=== カテゴリ別(master / 記事数 / 突合) ===")
    for cat, m, na, mt in sorted(report, key=lambda x: -x[3]):
        print(f"  {m:<14} {cat[:24]:<24} 記事{na:>4} 突合{mt:>4}")


if __name__ == "__main__":
    main()
