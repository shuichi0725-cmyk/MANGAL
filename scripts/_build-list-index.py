#!/usr/bin/env python3
"""
一覧用 軽量索引を生成 (= data/manga-list-index.json)。
一覧/トップ/フィルタ/カードが必要とする slim フィールドのみ + cover/total_volumes を事前計算。
editions/volumes全体・synopsis・tags・credits・alternative_titles 等の重い部分は除外 = props/転送を軽量化。
loadData.loadMangaListIndex() がこれを読む。検証(loadData)は別途 manga.v2 を読む promote が担保。
"""
import sys, json, glob, time, os, re
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L

# loadData が manga を弾く条件と同じ master キーで「表示対象」を絞る
DATA = os.environ.get("MANGAL_DATA_DIR", "data")
def load_keys(fn):
    p = os.path.join(DATA, fn)
    if not os.path.exists(p): p = os.path.join("data", fn)
    parsed = yaml.load(open(p, encoding="utf-8"), Loader=L) or {}
    # master は dict 形式 {key: {name:...}} (= loadData の Object.entries と同じ)
    if isinstance(parsed, dict): return set(parsed.keys())
    return set(x.get("key") for x in parsed if isinstance(x, dict))
pubKeys = load_keys("publishers.yml")
genreKeys = load_keys("genres.yml")
magKeys = load_keys("magazines.yml")

# ── 要素タグ(themes)算出 = app/manga/[slug]/page.tsx の elemItems と同じ規則 ──
#   ・tags の和訳のみ採用(英語のまま出さない)。 tag-i18n.yml 優先、 lib/anilist-i18n.ts の旧辞書 fallback。
#   ・除外: ①Demographic(分野欄に既出) ②Theme-Game-Sport*(競技は不採用) ③NOISE_TAGS ④ジャンル名と一致(畳む)
def _load_genre_names():
    p = os.path.join(DATA, "genres.yml")
    if not os.path.exists(p): p = os.path.join("data", "genres.yml")
    parsed = yaml.load(open(p, encoding="utf-8"), Loader=L) or {}
    return {k: (v.get("name") if isinstance(v, dict) else v) for k, v in parsed.items()}
GENRE_NAMES = _load_genre_names()  # key -> 表示名

def _load_tag_i18n():
    p = os.path.join(DATA, "seeds", "tag-i18n.yml")
    if not os.path.exists(p): p = os.path.join("data", "seeds", "tag-i18n.yml")
    parsed = yaml.load(open(p, encoding="utf-8"), Loader=L) or {}
    # ★実体は最上位 `tags:` キーの下にネスト (= loadData.loadTagI18n と同じ unwrap)
    table = parsed.get("tags", parsed) if isinstance(parsed, dict) else {}
    out = {}
    for name, v in table.items():
        ja = v.get("ja") if isinstance(v, dict) else v
        if ja: out[name] = ja
    return out
TAG_I18N = _load_tag_i18n()

# lib/anilist-i18n.ts の旧辞書(fallback)。 tag-i18n.yml 未収録 tag 用。
ANILIST_GENRE_JA = {
    "Action": "アクション", "Adventure": "冒険", "Comedy": "コメディ", "Drama": "ドラマ",
    "Ecchi": "エッチ", "Fantasy": "ファンタジー", "Hentai": "18禁", "Horror": "ホラー",
    "Mahou Shoujo": "魔法少女", "Mecha": "メカ", "Music": "音楽", "Mystery": "ミステリー",
    "Psychological": "心理", "Romance": "恋愛", "Sci-Fi": "SF", "Slice of Life": "日常",
    "Sports": "スポーツ", "Supernatural": "超常", "Thriller": "スリラー",
}
ANILIST_TAG_JA = {
    "Surreal Comedy": "シュールコメディ", "Slapstick": "スラップスティック", "Heterosexual": "異性愛",
    "Female Harem": "女子ハーレム", "Youkai": "妖怪", "Aliens": "宇宙人", "Shounen": "少年",
    "Shoujo": "少女", "Seinen": "青年", "Josei": "女性", "Kodomo": "児童", "School": "学園",
    "School Club": "学園クラブ", "Magic": "魔法", "Military": "軍事", "Police": "警察",
    "Yakuza": "ヤクザ", "Tsundere": "ツンデレ", "Yandere": "ヤンデレ", "Kuudere": "クーデレ",
    "Dandere": "ダンデレ", "Male Protagonist": "男性主人公", "Female Protagonist": "女性主人公",
    "Anti-Hero": "アンチヒーロー", "Love Triangle": "三角関係", "Animals": "動物",
    "Shapeshifting": "変身", "Episodic": "エピソード形式", "Nudity": "ヌード", "Isekai": "異世界",
    "Reincarnation": "転生", "Time Travel": "タイムトラベル", "Vampire": "吸血鬼", "Zombie": "ゾンビ",
    "Ghost": "幽霊", "Demon": "悪魔", "Cyborg": "サイボーグ", "Robot": "ロボット",
    "Samurai": "侍", "Ninja": "忍者",
}
NOISE_TAGS = {"Heterosexual", "Male Protagonist", "Female Protagonist",
              "Primarily Adult Cast", "Primarily Child Cast", "Primarily Teen Cast"}

def themes_of(d):
    # このページのジャンル名集合(畳み用) = genres(master) + genres_anilist(jaGenre)
    gnames = set()
    for g in (d.get("genres") or []):
        gnames.add(GENRE_NAMES.get(g, g))
    for g in (d.get("genres_anilist") or []):
        gnames.add(ANILIST_GENRE_JA.get(g, g))
    seen = set(); out = []
    for t in (d.get("tags") or []):
        name = t.get("name"); cat = t.get("category") or ""
        if not name: continue
        if cat == "Demographic": continue
        if cat.startswith("Theme-Game-Sport"): continue
        if name in NOISE_TAGS: continue
        from_yml = TAG_I18N.get(name)
        from_dict = ANILIST_TAG_JA.get(name)
        ja = from_yml or from_dict
        if not ja: continue
        if ja in gnames: continue
        if ja in seen: continue
        seen.add(ja); out.append(ja)
    return out

def cover_of(d):
    # primaryVolume相当: standard edition の number最小、無ければ全edition先頭の cover_url
    best = None
    for e in (d.get("editions") or []):
        for v in (e.get("volumes") or []):
            if v.get("cover_url"): return v["cover_url"]
        for ver in (e.get("versions") or []):
            for v in (ver.get("volumes") or []):
                if v.get("cover_url"): return v["cover_url"]
    return None

# ★cover軽量化: 楽天サムネの共通prefix/default suffixを剥がし可変部のみ保存(= lib/coverSlim.ts fullCover で復元)
# ★2026-07-14 判定緩和: 従来「prefix+suffix完全一致」のみ短縮→suffix無しURL(Kobo補完等)が
#   フルのまま6,100件ドリフトした。prefix一致だけで剥がす(復元は常に?_ex=200x200付与=カード200px統一)。
#   別クエリ付き(?)だけ例外でフル保持。
_RK_PRE = "https://thumbnail.image.rakuten.co.jp/@0_mall/"
_RK_SUF = "?_ex=200x200"
def slim_cover(c):
    if not c or not c.startswith(_RK_PRE):
        return c
    rest = c[len(_RK_PRE):]
    rest = re.sub(r"\?_ex=\d+x\d+$", "", rest)   # ?_ex=200x200/300x300等のリサイズ指定は剥がす(復元=200x200統一)
    if "?" in rest:
        return c   # 想定外クエリ付きはフルのまま(復元で壊さない)
    return rest

# 引数: [1]=src manga ディレクトリ (既定 data/manga.v2)、 [2]=出力ディレクトリ (既定 DATA)。
#   プレビュー用: python _build-list-index.py .preview-data/manga public
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, "manga.v2")
if not os.path.isdir(src): src = "data/manga.v2"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else DATA
# ★増分更新(FS競合で全66k再生成が遅い対策): --update stem1,stem2 = 該当ファイルだけ再構築し既存索引にmerge。
#   --remove slug1,slug2 = 旧slug(slug変更時の旧エントリ)を除去。 使用: _build-list-index.py data/manga.v2 data --update <stems> [--remove <slugs>]
UPDATE_STEMS = None
REMOVE_SLUGS = set()
for _i, _a in enumerate(sys.argv):
    if _a == "--update" and _i + 1 < len(sys.argv):
        UPDATE_STEMS = [s.strip() for s in sys.argv[_i + 1].split(",") if s.strip()]
    if _a == "--remove" and _i + 1 < len(sys.argv):
        REMOVE_SLUGS = {s.strip() for s in sys.argv[_i + 1].split(",") if s.strip()}
_files = [os.path.join(src, st + ".yml") for st in UPDATE_STEMS] if UPDATE_STEMS is not None else glob.glob(os.path.join(src, "*.yml"))
t0 = time.time(); idx = []; sidx = []; skipped = 0
for f in _files:
    try: d = yaml.load(open(f, encoding="utf-8"), Loader=L)
    except: skipped += 1; continue
    if not d: skipped += 1; continue
    # loadData と同じ表示ガード(必須欄/master外キーは一覧にも出さない=整合)
    if not (d.get("slug") and d.get("title") and d.get("title_kana") and d.get("title_romaji")
            and d.get("authors") and d.get("year_started")):
        skipped += 1; continue
    pub = d.get("publisher")
    if pub != "(unknown)" and pub not in pubKeys: skipped += 1; continue
    if any(p not in pubKeys for p in (d.get("publishers") or [])): skipped += 1; continue
    if d.get("magazine") and d["magazine"] not in magKeys: skipped += 1; continue
    gs = d.get("genres") or []
    # ★genre空は許容(2026-07-06 予約新作=捏造しない合意。master外キーのみ拒否)
    if any(g not in genreKeys for g in gs): skipped += 1; continue
    eds = d.get("editions") or []
    tv = sum(len(e.get("volumes") or []) for e in eds)
    maxev = max((len(e.get("volumes") or []) for e in eds), default=0)
    # ★1冊しか無いのに その巻が1巻でない(= 統合失敗/取りこぼしの signal。 おーばーふろぉ[8]型)
    _nums = [v.get("number") for e in eds for v in (e.get("volumes") or []) if v.get("number")]
    solo_nonfirst = tv == 1 and bool(_nums) and _nums[0] != 1
    # ★複数巻あるのに途中の巻が抜けている(= fill漏れ/真の欠番。 vol 1,2,4 で 3 欠け)
    vol_gap = False
    for _e in eds:
        _vn = sorted({v.get("number") for v in (_e.get("volumes") or []) if v.get("number")})
        if len(_vn) >= 2 and _vn[-1] - _vn[0] + 1 > len(_vn):
            vol_gap = True; break
    # ★1冊でも書影欠け(= Kobo補完worklist用 2026-07-05)
    cover_gap = any(not v.get("cover_url") for _e in eds for v in (_e.get("volumes") or []))
    latest = ""
    for e in eds:
        for v in (e.get("volumes") or []):
            rd = v.get("release_date")
            if rd and str(rd) > latest: latest = str(rd)
    # first_volume_date = standard版 number=1 の最小 release_date (= 創刊日・発売日昇順sort key・創刊カレンダー素)。
    #   完全日/年月の精度はそのまま保持(= カレンダーが 日配置 vs 日未定 を派生判定)。無ければ全edition最古に fallback。
    fvd = None
    for e in eds:
        if e.get("type") != "standard": continue
        for v in (e.get("volumes") or []):
            if v.get("number") == 1 and v.get("release_date"):
                s = str(v["release_date"])
                if fvd is None or s < fvd: fvd = s
    if not fvd:
        _alld = [str(v["release_date"]) for e in eds for v in (e.get("volumes") or []) if v.get("release_date")]
        fvd = min(_alld) if _alld else None
    aus = d.get("authors") or []
    oaus = d.get("original_authors") or []
    # ① 一覧索引(表示用) = 検索専用フィールド(title_romaji/alternative_titles/credits)は持たない
    idx.append({
        "slug": d["slug"], "title": d["title"], "title_kana": d["title_kana"],
        "subtitle": d.get("subtitle"),
        "cover": slim_cover(cover_of(d)),
        "year_started": d["year_started"], "year_ended": d.get("year_ended"),
        "status": d.get("status"), "catch": d.get("catch"),
        # ★authors圧縮(2026-07-14): "name\tkana"パック文字列(role廃止=一覧で未使用)。復元=listIndexDecode
        "authors": [(f"{a.get('name')}\t{a.get('kana')}" if a.get("kana") else str(a.get("name"))) for a in aus],
        "original_authors": [(f"{a.get('name')}\t{a.get('kana')}" if a.get("kana") else str(a.get("name"))) for a in oaus],
        "genres": gs, "themes": themes_of(d), "demographic": d.get("demographic"),
        "publisher": pub, "publishers": d.get("publishers") or [],
        "magazine": d.get("magazine"), "awards": d.get("awards"),
        "anime_adapted": d.get("anime_adapted"),
        "total_volumes": tv, "max_edition_volumes": maxev,
        "latest_date": latest[:7] if latest else None,
        "first_volume_date": fvd,
        "popularity": d.get("popularity"), "score": d.get("score"),
        # ★診断フラグはビットフィールド1列に圧縮(2026-07-14。復元=listIndexDecode。null列5本の水増し解消)
        **({"fl": (1 if solo_nonfirst else 0) | (2 if vol_gap else 0) | (4 if cover_gap else 0)
                  | (8 if d.get("_anthology") else 0) | (16 if d.get("_slugfix") else 0)}
           if (solo_nonfirst or vol_gap or cover_gap or d.get("_anthology") or d.get("_slugfix")) else {}),
        **({"_slugfix_new": d.get("_slugfix_new")} if d.get("_slugfix") else {}),
    })
    # ② 検索索引(検索専用) = matchText が必要とする text のみ (= 検索時だけ遅延ロード)
    alt = d.get("alternative_titles") or {}
    sidx.append({
        "slug": d["slug"], "title": d["title"], "title_kana": d["title_kana"],
        "title_romaji": d["title_romaji"],
        "alt": [v for v in [alt.get("en"), alt.get("fr"), alt.get("de"), alt.get("it"), alt.get("pt")] if v]
               + [s for s in (d.get("synonyms") or []) if s]  # ★synonymsも検索可(2026-07-14: 統合頁の巻別題=ソーサリアン型)
               # ★巻の個別題(title_display)も検索可: 「副題(著者)〔新N〕」から括弧書きを剥いだ純副題を拾う
               + [t for e in (d.get("editions") or []) for v in (e.get("volumes") or [])
                  for t in [re.sub(r"[（(].*?[)）]|〔.*?〕", "", str(v.get("title_display") or "")).strip()] if t],
        "au": [a.get("name") for a in aus if a.get("name")]
              + [a.get("name") for a in oaus if a.get("name")]
              + [c.get("name") for c in (d.get("credits") or []) if c.get("name")],
    })
# ★増分: 再構築した作以外は既存索引から取り込む(66k全read回避)。
if UPDATE_STEMS is not None:
    _changed = {m["slug"] for m in idx} | REMOVE_SLUGS
    _exl = os.path.join(OUTDIR, "manga-list-index.json")
    if os.path.exists(_exl):
        _ex = json.load(open(_exl, encoding="utf-8"))
        for row in _ex["d"]:
            m = dict(zip(_ex["f"], row))
            if m.get("slug") not in _changed:
                idx.append(m)
    _exs_p = os.path.join(OUTDIR, "manga-search-index.json")
    if os.path.exists(_exs_p):
        _exs = json.load(open(_exs_p, encoding="utf-8"))
        for row in _exs["d"]:
            m = dict(zip(_exs["f"], row))
            if m.get("slug") not in _changed:
                sidx.append(m)
    print(f"[--update] {len(UPDATE_STEMS)}作再構築 + 既存索引merge(除去{len(REMOVE_SLUGS)})")

idx.sort(key=lambda x: (x["year_started"], x["title"]))
# ★軽量化: 配列化(キー名の65,980回重複を排除) + catch分離(別ファイル=カードは遅延ロード)。
#   読込側 useMangaIndex が {f,d}→オブジェクトに復元するので、コンポーネントは無改修。
LIST_FIELDS = [
    "slug", "title", "title_kana", "subtitle", "cover", "year_started", "year_ended",
    "status", "authors", "original_authors", "genres", "themes", "demographic",
    "publisher", "publishers", "magazine", "awards", "anime_adapted", "total_volumes",
    "max_edition_volumes", "latest_date", "first_volume_date", "popularity", "score",
    "fl", "_slugfix_new",
]
out = os.path.join(OUTDIR, "manga-list-index.json")
json.dump({"f": LIST_FIELDS, "d": [[m.get(f) for f in LIST_FIELDS] for m in idx]},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
# ★head索引(2026-07-14): 人気順先頭200件=初回描画用(~80KB)。コールドスタートの体感対策。
_head = sorted(idx, key=lambda x: -(x.get("popularity") or 0))[:200]
hout = os.path.join(OUTDIR, "manga-list-head.json")
json.dump({"f": LIST_FIELDS, "d": [[m.get(f) for f in LIST_FIELDS] for m in _head]},
          open(hout, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
catch_out = os.path.join(OUTDIR, "manga-catch-index.json")
catch_map = {m["slug"]: m["catch"] for m in idx if m.get("catch")}
# ★増分: 既存catch(別ファイル=list rowに載らない)を非変更作分だけ取り込む(catch消失防止)。
if UPDATE_STEMS is not None and os.path.exists(catch_out):
    _exc = json.load(open(catch_out, encoding="utf-8"))
    for _sl, _c in _exc.items():
        if _sl not in _changed and _sl not in catch_map:
            catch_map[_sl] = _c
json.dump(catch_map, open(catch_out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
# ★alt索引(2026-07-14): 別名・英題の2段目照合用(題名ヒット0の時だけ遅延fetch)。
aout = os.path.join(OUTDIR, "manga-alt-index.json")
json.dump({m["slug"]: m["alt"] for m in sidx if m.get("alt")},
          open(aout, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
# ★旧検索索引: 移行期間のみ出し続ける(キャッシュ済み旧HTMLが参照)。新クライアントは使わない。
#   TODO(2026-08頃): 全キャッシュ失効後にこの3行とR2上のファイルを削除
SEARCH_FIELDS = ["slug", "title", "title_kana", "title_romaji", "alt", "au"]
sout = os.path.join(OUTDIR, "manga-search-index.json")
json.dump({"f": SEARCH_FIELDS, "d": [[m.get(f) for f in SEARCH_FIELDS] for m in sidx]},
          open(sout, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
mb = os.path.getsize(out) / 1e6
smb = os.path.getsize(sout) / 1e6
cmb = os.path.getsize(catch_out) / 1e6
print(f"一覧索引: {len(idx)}作品 / {mb:.1f}MB → {out} (配列化)")
print(f"catch索引: {len(catch_map)}件 / {cmb:.1f}MB → {catch_out} (遅延)")
print(f"検索索引: {len(sidx)}作品 / {smb:.1f}MB → {sout}")
print(f"(skip {skipped}) / {time.time()-t0:.1f}秒")
