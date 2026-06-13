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
    ("魔法少女", "mahou-shoujo"), ("歴史", "historical"), ("時代", "historical"),
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


def main():
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
