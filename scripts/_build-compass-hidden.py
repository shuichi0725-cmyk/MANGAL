#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""羅針盤(/compass)の「隠し要素」= 近さの点数にだけ使う、画面には出ない要素のファイルを作る。

2026-10-09 ユーザ発案「ネタバレの要素は隠し持つことは可能か？見えないけどもってる。それによって近い物が
見つけやすい的な。羅針盤でもみえないけど近い要素でマンガ自体はつながるみたいな。」

■ 何を持つか(作品ごとの「近さの鍵」)
  ① その頁に今出ている要素(一覧索引の themes)
  ② AniList のその漫画のタグのうち、票40以上で、頁には出していないもの
     (票が線に届かない語・人物/舞台系・ネタバレ印・競技名。 成人タグ・分野・どの作品にも付く語は除く)
  ★①も入れるのは、「Aでは見えている語」と「Bでは隠れている同じ語」を突き合わせるため。

■ 形(番号だけ。 語の一覧は載せない = データを覗いても語は読めない)
  public/data/compass-hidden.v1.json
    {"v":1, "built":"YYYY-MM-DD", "k":鍵の種類数, "p":{公開slug:[番号,…]}}
  番号は 鍵の sha1 順(五十音順やアルファベット順にしない)。 ビルドのたびに振り直してよい(同じファイルの中でだけ意味を持つ)。
  ★形を変える時はファイル名の v を上げる(lib 側の取得先も同時に)= [[index_format_change_versioned_filename]]。

■ 使い方
  python scripts/_build-compass-hidden.py            # 作って統計を出す
  python scripts/_build-compass-hidden.py --dry      # 書かずに統計だけ
  python scripts/_build-compass-hidden.py --explain <slug>   # その作品の鍵を語で見る(手元の点検用。配るファイルには語は無い)

入力: data/manga-list-index.json(本番の一覧索引)/ data/manga.v2/*.yml(slug と anilist_id だけ先頭から読む)/
      .cache/anilist-manga-dump-v3.jsonl.gz(AniList の全漫画タグ)/ data/seeds/tag-i18n.yml(訳)
本番データ(manga.v2 / seed / 索引)は読むだけ。 モデルは使わない。
"""
import argparse, ast, datetime, glob, gzip, hashlib, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "data", "compass-hidden.v1.json")
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
INDEX = os.path.join(ROOT, "data", "manga-list-index.json")

RANK_MIN = 40          # AniList の票がこの線以上のタグを鍵にする(要素付与の「控え」の線と同じ)
SALT = "mangal-compass-hidden-v1"
# どの作品にも付く語(近さの手がかりにならない)。 一覧索引の NOISE_TAGS と同じ考え方 + 「主に○○の登場人物」
NOISE_PREFIX = ("Primarily ",)
NOISE_NAMES = {"Nudity"}                       # 描写の有無であって、作品の中身の近さではない(要素付与の道具でも表に出さない語)
SKIP_BASE = {"Sexual Content", "Technical"}    # 性的な描写の区分・本の形式(アンソロジー・4コマ・フルカラー等)= 中身の近さではない(要素付与の道具と同じ)


def load_translation():
    """AniList タグ名 → 頁に出る日本語(一覧索引 _build-list-index.py の themes_of と同じ優先順: 訳表 → 旧辞書)。"""
    import yaml
    with open(os.path.join(ROOT, "data", "seeds", "tag-i18n.yml"), encoding="utf-8") as f:
        t = yaml.safe_load(f) or {}
    t = t.get("tags", t)
    yml = {n: (v.get("ja") if isinstance(v, dict) else v) for n, v in t.items()}
    with open(os.path.join(ROOT, "scripts", "_build-list-index.py"), encoding="utf-8") as f:
        src = f.read()
    old = ast.literal_eval(re.search(r"ANILIST_TAG_JA = (\{.*?\n\})", src, re.S).group(1))
    noise = ast.literal_eval(re.search(r"NOISE_TAGS = (\{.*?\})", src, re.S).group(1))
    ja = {**old, **{k: v for k, v in yml.items() if v}}
    with open(os.path.join(ROOT, "data", "genres.yml"), encoding="utf-8") as f:
        g = yaml.safe_load(f) or {}
    gnames = {(v.get("name") if isinstance(v, dict) else v) for v in g.values()}
    return ja, set(noise), gnames


def slug_to_aid():
    """公開slug → anilist_id。 頁ファイルを YAML として解かずに行頭の2項目だけ拾う(全6.9万頁で十数秒)。
    ★ファイルは最後まで読む: anilist_id は先頭4000字より後ろに在る頁が2,509件ある(巻の多い頁。 最も後ろは9万字目 = 2026-10-09 実測)。
      先頭だけ読む版では らんま1/2・俺ガイル が「AniList なし」になった。"""
    out = {}
    re_aid = re.compile(rb"^anilist_id:\s*(\d+)", re.M)
    re_slug = re.compile(rb"^slug:\s*['\"]?([^\s'\"]+)", re.M)
    for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        with open(p, "rb") as f:
            raw = f.read()
        m = re_aid.search(raw)
        if not m:
            continue
        s = re_slug.search(raw)
        out[s.group(1).decode("utf-8") if s else os.path.basename(p)[:-4]] = int(m.group(1))
    return out


def tag_keys(tags, ja, noise, gnames):
    """AniList のタグ列 → 近さの鍵(日本語の訳が在れば訳、無ければ en:英名)。"""
    keys = set()
    for t in tags or []:
        name, cat, rank = t.get("name"), t.get("category") or "", t.get("rank") or 0
        if not name or rank < RANK_MIN or t.get("isAdult"):
            continue
        if "Demographic" in cat or name in noise or name.startswith(NOISE_PREFIX) or name in NOISE_NAMES:
            continue
        if cat.split("-")[0] in SKIP_BASE:
            continue
        j = ja.get(name)
        if j in gnames:  # 学園・魔法少女 など = ジャンルと同じ語(近さはジャンルの重なりで別に数えている)
            continue
        keys.add(j or "en:" + name)
    return keys


def seed_keys(ja, noise, gnames):
    """要素付与(scripts/_element-assign.py apply / hidden)が書いた「隠して持つ」語 → 公開slug → 鍵。
    ani:<英名> は AniList のタグ(自分の頁だけでなく、アニメ・原作小説から引き継いだ分も入っている)。 それ以外は材料から拾った和名。"""
    p = os.path.join(ROOT, "data", "seeds", "element-hidden.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        doc = json.load(f)
    out = {}
    for slug, v in doc.items():
        ks = set()
        for k in (v or {}).get("keys") or []:
            if k.startswith("ani:"):
                name = k[4:]
                if name in noise or name.startswith(NOISE_PREFIX) or name in NOISE_NAMES:
                    continue
                k = ja.get(name) or "en:" + name
            if k not in gnames:
                ks.add(k)
        out[slug] = ks
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--explain")
    a = ap.parse_args()

    ja, noise, gnames = load_translation()
    with open(INDEX, encoding="utf-8") as f:
        idx = json.load(f)
    F = idx["f"]
    i_slug, i_themes = F.index("slug"), F.index("themes")
    visible = {r[i_slug]: [t for t in (r[i_themes] or []) if t] for r in idx["d"]}
    s2a = slug_to_aid()
    need = set(s2a.values())
    ani = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("id") in need:
                ani[d["id"]] = d.get("tags") or []

    seed = seed_keys(ja, noise, gnames)
    keys_of, n_hidden = {}, 0
    for slug, vis in visible.items():
        ks = set(vis)
        aid = s2a.get(slug)
        hid = ((tag_keys(ani.get(aid), ja, noise, gnames) if aid else set()) | seed.get(slug, set())) - ks
        n_hidden += 1 if hid else 0
        if ks or hid:
            keys_of[slug] = (ks, hid)

    if a.explain:
        v, h = keys_of.get(a.explain, (set(), set()))
        print(f"{a.explain}: 見えている {len(v)} = {'・'.join(sorted(v))}")
        print(f"  隠して持つ {len(h)} = {'・'.join(sorted(h))}")
        return

    allk = sorted({k for v, h in keys_of.values() for k in v | h}, key=lambda k: hashlib.sha1((SALT + k).encode("utf-8")).hexdigest())
    num = {k: i for i, k in enumerate(allk)}
    p = {slug: sorted(num[k] for k in v | h) for slug, (v, h) in sorted(keys_of.items())}
    obj = {"v": 1, "built": datetime.date.today().isoformat(), "k": len(allk), "p": p}
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    hid_counts = [len(h) for _, h in keys_of.values()]
    vis_counts = [len(v) for v, _ in keys_of.values()]
    freq = {}
    for v, h in keys_of.values():
        for k in h:
            freq[k] = freq.get(k, 0) + 1
    print(f"一覧索引 {len(visible)}作 / anilist_id のある頁 {len(s2a)} / AniList のタグが引けた {sum(1 for s in visible if s2a.get(s) in ani)}")
    print(f"鍵を持つ作品 {len(keys_of)}(うち隠し要素あり {n_hidden})/ 鍵の種類 {len(allk)} / 要素付与が書いた隠し要素を持つ頁 {sum(1 for s in seed if s in visible)}")
    print(f"1作あたり: 見えている 平均 {sum(vis_counts) / max(1, len(vis_counts)):.2f} / 隠し 平均 {sum(hid_counts) / max(1, len(hid_counts)):.2f}"
          f"(隠しありの作品だけなら 平均 {sum(hid_counts) / max(1, n_hidden):.2f})")
    both = [len(v) + len(h) for v, h in keys_of.values()]
    for lo, hi in ((0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 99)):
        print(f"   見えている要素 {lo}〜{hi}: {sum(1 for v in visible.values() if lo <= len(v) <= hi):>6}作  →  鍵(見える+隠し){lo}〜{hi}: "
              f"{sum(1 for s in visible if lo <= (len(keys_of[s][0]) + len(keys_of[s][1]) if s in keys_of else 0) <= hi):>6}作")
    print("隠し要素で多い鍵(上位25): " + "、".join(f"{k}{n}" for k, n in sorted(freq.items(), key=lambda x: -x[1])[:25]))
    print(f"ファイル: {len(raw):,} バイト / gzip {len(gzip.compress(raw, 6)):,} バイト")
    if a.dry:
        print("(--dry: 書いていない)")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "wb") as f:
        f.write(raw)
    os.replace(tmp, OUT)
    print(f"書いた → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
