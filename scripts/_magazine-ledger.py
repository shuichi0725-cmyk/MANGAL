"""連載誌の根拠台帳 = 頁ごとに「どこで調べて・何が出たか・いつ」を貯め、 一覧表(漫画名/著者/原作/作画/連載誌/根拠/確認日)を作る。

★目的 = 「まだ調べていない」と「調べたが見つからなかった」を分ける(どちらも本番では同じ空欄に見える)。
★値の正本は今まで通り 種3 + data/seeds/magazine-corrections.yml(promote が読む)。 この台帳は**根拠**の正本で、 本番には何も書かない。

台帳(正本・git) = data/seeds/magazine-evidence/<source>.jsonl
  一括型 = 1行目 {"_meta": {...}}、 以降 **調べた頁ごとに1行** {"slug", "hits": [...]}  (hits が空 = 調べたが見つからず)。
           取り直すとファイルごと置き換え(前の版は git 履歴に残る)。  madb-shoshutsu / madb-mokuji / rakuten-caption
  追記型 = 1行 = 1回の確認 {"slug", "hits", "at", "ref"}。  wiki-list / wiki-article / manual
  hits の1件 = {"mag": 雑誌マスタのkey または "?誌名"(マスタに無い), "raw": ソースに書かれた誌名, "n": 回数/冊数, "ref": 抜粋}
  ★失敗(429・瞬断)は書かない。 書いてよい「見つからず」は、 手元の完全なデータを引いて無かった時 / 相手が正常に応答して空だった時だけ。
表(写し) = docs/production-diagnostics/magazine-ledger.tsv + magazine-ledger-summary.tsv(build が毎回作り直す。 手で直さない)

使い方:
  python scripts/_magazine-ledger.py sweep-madb      # MADB 単行本の初出欄 + 雑誌目次(手元 .cache/magazine-lists/madb-*.jsonl)
  python scripts/_magazine-ledger.py sweep-rakuten   # 楽天の商品説明(手元 .cache/rakuten-isbn-delta.jsonl)
  python scripts/_magazine-ledger.py sweep-wiki-local          # Wikipedia 作品記事: 手元に在る本文だけで判定(ネットに出ない)
  python scripts/_magazine-ledger.py sweep-wiki-fetch [--limit N]  # まだ見ていない頁の記事を取る(10件ずつ・3秒・429で停止→再開可)。 後で sweep-wiki-local
  python scripts/_magazine-ledger.py sweep-wiki-dump           # ★本命: 本文ダンプ(4.9GB・.cache/jawiki-dump)で全頁を判定(API は15回ほどで429になる)
  python scripts/_magazine-ledger.py sweep-wiki-absent         # 題名の記事が全題名ダンプに無い頁を「記事なし」と記録(取得と判定の後)
  python scripts/_magazine-ledger.py import-legacy   # 2026-11-04 までの Wikipedia 照合 / 上書きの根拠を取り込む(1回だけ)
  python scripts/_magazine-ledger.py build           # 一覧表 + 集計
NDL は連載誌を持たない(2026-11-04 実測: MADB 内の NDL 由来 29,398 冊で初出 0 / live 5 冊も type:book だけ)= ソースにしない。
"""
import ast, collections, datetime, glob, json, os, re, sqlite3, sys, unicodedata
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, "data", "seeds", "magazine-evidence")
OUT = os.path.join(ROOT, "docs", "production-diagnostics")
LISTS = os.path.join(ROOT, ".cache", "magazine-lists")
TODAY = datetime.date.today().isoformat()

SOURCES = [  # (key, 表の列名, 強い根拠か)
    ("madb-shoshutsu", "MADB初出", True),
    ("madb-mokuji", "MADB目次", True),
    ("wiki-list", "Wiki一覧", True),
    ("wiki-article", "Wiki記事", True),
    ("manual", "人の裁定", True),
    ("rakuten-caption", "楽天説明", False),   # 弱い = 作者の前作の誌を書いている説明が混ざる
]
SWEEP = {"madb-shoshutsu", "madb-mokuji", "rakuten-caption"}


def load_yaml(p):
    import yaml
    return yaml.safe_load(open(p, encoding="utf-8"))


MAG = load_yaml(os.path.join(ROOT, "data", "magazines.yml"))


# ---------------------------------------------------------------- 誌名 → 雑誌マスタ key
# ★2026-11-07: 11/4 の照合関数(wiki_mag_lib.canon)は 週刊/月刊 と「+」を落としていたため、 月刊少年ジャンプ・少年ジャンプ+ が
#   週刊少年ジャンプに、 月刊少年チャンピオンが週刊少年チャンピオンに寄っていた。 ここでは**落とさない**。 表記ゆれは明示の別名表だけで吸収し、
#   1つの書き方が2誌に当たったら「?」にする(黙って片方に寄せない)。
def nrm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[\s・･「」『』\"'“”‘’!?.。、,]", "", s)


def _literal(path, names):
    """台本を実行せずに、 中の別名表(dict リテラル)だけ取り出す。"""
    out = {}
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except OSError:
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", "") in names:
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def build_resolver():
    cand = defaultdict(set)
    for k, v in MAG.items():
        cand[nrm(v["name"])].add(k)
        cand[nrm(k)].add(k)
    mv = os.path.join(ROOT, "scripts", "magazine-verify")
    lit = {}
    for f, names in (("madb_mag_match.py", {"ALIAS"}), ("madb_serial_match.py", {"MAGMAP"}), ("madb_apply.py", {"NEW_MAGS", "EXTRA_ALIAS"})):
        lit.update({f + ":" + n: v for n, v in _literal(os.path.join(mv, f), names).items()})
    for key, tbl in lit.items():
        if key.endswith("NEW_MAGS"):
            for k, v in tbl.items():
                for n in v[3:]:
                    cand[nrm(n)].add(k)
        else:
            for n, k in tbl.items():
                cand[nrm(n)].add(k)
    for n, k in EXTRA.items():
        cand[nrm(n)].add(k)
    ap = os.path.join(EV, "aliases.yml")             # 雑誌マスタ第3弾(mag_master_3.py)が Wikipedia の誌の記事で確かめた別名
    if os.path.exists(ap):
        for n, k in (load_yaml(ap) or {}).items():
            cand[nrm(str(n))].add(k)
    table = {}
    amb = {}
    for n, ks in cand.items():
        ks = {k for k in ks if k in MAG}
        if len(ks) == 1:
            table[n] = next(iter(ks))
        elif len(ks) > 1:
            amb[n] = sorted(ks)
    return table, amb


# MADB の誤字・号の名(2026-11-04 実踏 = new_mags_2.py の MAP と同じもの。 あちらの鍵は canon 形なのでここで書き直す)
EXTRA = {
    "週刊ヤングシャンプ": "weekly-young-jump", "赤マルシャンプ": "akamaru-jump", "マーガーレット": "margaret",
    "ザ花とゆめ": "the-hana-to-yume", "ザ・花とゆめ": "the-hana-to-yume", "ザ マーガレット": "the-margaret", "ザマーガレット": "the-margaret",
    "ララDX": "lala-dx", "ララデラックス": "lala-dx", "クッキー": "cookie", "ちゅちゅ": "chuchu",
    "マガジンスペシャル": "magazine-special", "Asuka": "asuka", "コミックアライブ": "comic-alive", "月刊コミックアライブ": "comic-alive",
    "コロコロイチバン": "corocoro-ichiban", "MiChao!（ミチャオ）": "michao", "MiChao!(ミチャオ)": "michao",
    "月刊プレコミックブンブン": "comic-bunbun", "少年ガンガン増刊ガンガンパワード": "gangan-powered",
    "月刊少年マガジン増刊GREAT": "magazine-great", "ジャンプスクエア": "jump-sq",
    "週刊少年サンデーS": "shonen-sunday-super", "少年ガンガン": "gangan", "月刊ガンガン": "gangan", "ガンガンウイング": "gangan-wing", "月刊ガンガンウイング": "gangan-wing",
    "月刊コミック乱": "comic-ran", "月刊まんがタウン": "manga-town", "クッキーボックス": "cookie-box", "週刊少年ジャンプ増刊赤マルシャンプ": "akamaru-jump", "週刊少年ジャンプ増刊赤マルジャンプ": "akamaru-jump",
    "週刊少女コミック": "shojo-comic-legacy", "月刊テレビマガジン": "tv-magazine", "コミックジーン": "comic-gene", "ジャンプスクエア19": "jump-sq-19", "週刊少年サンデーS増刊": "shonen-sunday-super",
}
RESOLVE, AMBIG = build_resolver()


def _config_table():
    """2026-11-04 第2弾で人が決めた MADB 誌名の寄せ先(new_mags_2.py CONFIG: 鍵 = wiki_mag_lib.canon 形)。"""
    mv = os.path.join(ROOT, "scripts", "magazine-verify")
    cfg = {}
    try:
        for node in ast.parse(open(os.path.join(mv, "new_mags_2.py"), encoding="utf-8").read()).body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CONFIG":   # 値の N/M/X は名前なので literal_eval できない
                cfg = eval(compile(ast.Expression(node.value), "new_mags_2.py", "eval"), {"__builtins__": {}}, {"N": "NEW", "M": "MAP", "X": "EXCLUDE"})
    except (OSError, SyntaxError, NameError):
        cfg = {}
    if not cfg:
        return None, {}
    sys.path.insert(0, mv)
    try:
        from wiki_mag_lib import canon
    except Exception:
        return None, {}
    return canon, {c: v[1] for c, v in cfg.items() if v and v[0] in ("NEW", "MAP") and v[1] in MAG}


CANON, CONFIG_MAP = _config_table()
LOSSY = re.compile(r"^(週刊|月刊|隔週刊|季刊|隔月刊)|[+＋]|プラス|増刊号?$")


def resolve(raw):
    raw = (raw or "").strip()
    if not raw:
        return ""
    k = RESOLVE.get(nrm(raw))
    if k:
        return k
    k = RESOLVE.get(nrm(re.sub(r"\s*[（(][^)）]*[)）]$", "", raw)))  # 「ARIA (雑誌)」の曖昧さ回避
    if k:
        return k
    # canon は 週刊/月刊・「+」・末尾の増刊 を落とす = その形の名は寄せ先を取り違える(月刊少年チャンピオン→週刊)ので使わない
    if CANON and not LOSSY.search(raw):
        k = CONFIG_MAP.get(CANON(raw))
        if k:
            return k
    return "?" + raw


def magname(k):
    if not k:
        return ""
    return k if k.startswith("?") else MAG.get(k, {}).get("name", k)


# ---------------------------------------------------------------- 本番の頁
def load_pages():
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {k: i for i, k in enumerate(li["f"])}

    def names(v):
        return [str(x).split("\t")[0] if not isinstance(x, dict) else x.get("name", "") for x in (v or [])]

    pages = {}
    for r in li["d"]:
        pages[r[F["slug"]]] = {"slug": r[F["slug"]], "title": r[F["title"]], "mag": r[F["magazine"]] or "",
                               "pub": r[F["publisher"]] or "", "year": r[F["year_started"]] or 0,
                               "names": [a for a in names(r[F["authors"]]) + names(r[F["original_authors"]]) if a]}
    return pages


def page_files():
    """manga.v2 の頁ファイル → (stem→公開slug, 公開slug→著者と役割)。 editions: より上だけ読む。"""
    stem2slug, roles = {}, {}
    for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        stem = os.path.basename(p)[:-4]
        slug, cur, people = stem, None, []
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.startswith("editions:"):
                    break
                if line.startswith("slug:"):
                    slug = line[5:].strip().strip("'\"")
                elif line.startswith("authors:") or line.startswith("original_authors:"):
                    cur = "a"
                elif cur and line.startswith("- name:"):
                    people.append([line[7:].strip().strip("'\""), ""])
                elif cur and line.startswith("  role:") and people:
                    people[-1][1] = line[7:].strip().strip("'\"")
                elif line and not line.startswith((" ", "-")):
                    cur = None
        stem2slug[stem] = slug
        roles[slug] = people
    return stem2slug, roles


def isbn_to_slugs(stem2slug):
    idx = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    return {i: sorted({stem2slug.get(s, s) for s in ss}) for i, ss in idx.items()}


# ---------------------------------------------------------------- 台帳の読み書き
def write_sweep(src, meta, rows):
    os.makedirs(EV, exist_ok=True)
    p = os.path.join(EV, f"{src}.jsonl")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")
        for slug in sorted(rows):
            f.write(json.dumps({"slug": slug, "hits": rows[slug]}, ensure_ascii=False) + "\n")
    print(f"  → {os.path.relpath(p, ROOT)}  調べた頁 {len(rows):,} / 見つかった頁 {sum(1 for h in rows.values() if h):,}")


def append_log(src, rows):
    os.makedirs(EV, exist_ok=True)
    p = os.path.join(EV, f"{src}.jsonl")
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  → {os.path.relpath(p, ROOT)} に {len(rows):,} 行追記")


def read_source(src):
    """slug → (確認日, hits)。 追記型は同じ slug の最新の確認を採る。"""
    p = os.path.join(EV, f"{src}.jsonl")
    if not os.path.exists(p):
        return {}, None
    out, meta = {}, None
    for line in open(p, encoding="utf-8"):
        r = json.loads(line)
        if "_meta" in r:
            meta = r["_meta"]
            continue
        at = r.get("at") or (meta or {}).get("checked_at", "")
        prev = out.get(r["slug"])
        if meta:                                   # 一括型 = 1頁1行
            out[r["slug"]] = (at, r["hits"])
        else:                                      # 追記型 = 確認を重ねる。 後の「なし」で前の「あり」を消さない(別の記事・別の方法のことがある)
            old = prev[1] if prev else []
            out[r["slug"]] = (max(at, prev[0]) if prev else at, old + [h for h in r["hits"] if h not in old])
    return out, meta


# ---------------------------------------------------------------- sweep: MADB
TKEY_TR = re.compile(r"[\s・･!！?？。、,，.．:：;；\"'“”‘’「」『』()（）\[\]［］〜~\-‐－—―=＝/／★☆♪♡♥❤＋+×&＆]")


def _n(s):
    return TKEY_TR.sub("", unicodedata.normalize("NFKC", s or "").lower())


def tkeys(t):
    k = {_n(t), _n(re.sub(r"[(（][^)）]*[)）]", "", t)), _n(re.split(r"[ 　]+[-‐－〜~]", t)[0])}
    return {x for x in k if len(x) >= 2}


def akey(a):
    return _n(re.sub(r"\[[^\]]*\]|［[^］]*］|【[^】]*】", "", a))


SHO_SKIP = re.compile(r"記載なし|一覧|作品初出|^\s*$")


def shoshutsu_names(text):
    """「初出：「週刊少年ジャンプ」2010年43～52号」 → ['週刊少年ジャンプ']。 初出一覧あり/[記載なし] は誌名にしない。"""
    m = re.search(r"初出\s*[:：]?(.*)", text or "")
    if not m:
        return []
    body = m.group(1)
    if SHO_SKIP.search(body[:12]):
        return []
    names = re.findall(r"[「『]([^」』「『]{2,40})[」』]", body)
    if not names:
        m2 = re.match(r"\s*([^\d\s「『（(,、.:：]{2,30}?)\s*(?:\d|増刊|$)", body)
        names = [m2.group(1)] if m2 else []
    return [x.strip() for x in names if x.strip()]


def sweep_madb():
    pages = load_pages()
    stem2slug, _ = page_files()
    i2s = isbn_to_slugs(stem2slug)
    # 初出欄: ISBN で頁へ。 調べた範囲 = 種2(MADB)に巻が1冊でも在る頁
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    madb_isbn = {r[0] for r in con.execute("select isbn13 from volumes where isbn13 is not null and madb_book_id is not null")}
    scope = set()
    for i in madb_isbn:
        for s in i2s.get(i, []):
            if s in pages:
                scope.add(s)
    per = defaultdict(lambda: defaultdict(lambda: [0, (9999, ""), ""]))   # 誌名 → [冊数, (最小の巻, 発売日), 抜粋]
    for line in open(os.path.join(LISTS, "madb-shoshutsu.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        if r.get("kind") != "book" or not r.get("isbn"):
            continue
        vol = int(re.sub(r"\D", "", r.get("vol") or "")[:4] or 0)
        for s in i2s.get(r["isbn"], []):
            if s not in pages:
                continue
            scope.add(s)
            for nm in dict.fromkeys(shoshutsu_names(r["text"])):
                e = per[s][nm]
                e[0] += 1
                if (vol, r.get("date", "")) < e[1]:
                    e[1] = (vol, r.get("date", ""))
                    e[2] = f'{r.get("title","")} {r.get("vol","")} {r.get("date","")}: {r["text"][:90]}'
    rows = {}
    for s in scope:
        hs = [{"mag": resolve(nm), "raw": nm, "n": n, "ref": ref} for nm, (n, _, ref) in per.get(s, {}).items()]
        rows[s] = sorted(hs, key=lambda h: -h["n"])
    write_sweep("madb-shoshutsu", {"source": "madb-shoshutsu", "checked_at": TODAY, "data_as_of": "MADB 1.2.21 (cm101 単行本の初出欄)",
                                   "method": "頁の巻ISBN × MADB単行本の初出欄。 調べた頁 = MADBに巻が1冊でも在る頁(★2020年以降はNDL由来で初出欄が無い)",
                                   "via": "scripts/_magazine-ledger.py sweep-madb"}, rows)

    # 雑誌目次: 題+著者+年で MADB の連載(cm106)と突合(scripts/magazine-verify/madb_serial_match.py と同じ規則)。 調べた範囲 = 全頁
    by_t = defaultdict(list)
    for p in pages.values():
        for k in tkeys(p["title"]):
            by_t[k].append(p)
    hits = defaultdict(list)
    for line in open(os.path.join(LISTS, "madb-serial.jsonl"), encoding="utf-8"):
        s = json.loads(line)
        if not s["mags"]:
            continue
        aks = {akey(a) for a in s["creators"] if len(akey(a)) >= 2}
        if not aks:
            continue
        y0 = int(s["mags"][0][2][:4]) if s["mags"][0][2][:4].isdigit() else 0
        cand = {p["slug"]: p for k in tkeys(s["name"]) for p in by_t.get(k, [])}
        for p in cand.values():
            pa = {akey(a) for a in p["names"]}
            if not any(a in b or b in a for a in aks for b in pa if len(b) >= 2):
                continue
            if p["year"] and y0 and not (y0 - 1 <= p["year"] <= y0 + 4):
                continue
            hits[p["slug"]].append(s)
    rows = {}
    for slug in pages:
        tot, first = Counter(), {}
        for s in hits.get(slug, []):
            for name, n, d in s["mags"]:
                tot[name] += n
                if name not in first or d < first[name]:
                    first[name] = d
        allv = sum(tot.values())
        rows[slug] = [{"mag": resolve(nm), "raw": nm, "n": n, "ref": f"{first[nm][:7]}〜 {n}回 / 全{allv}回",
                       **({"main": True} if n >= 5 and n * 2 >= allv else {})} for nm, n in tot.most_common()]
    write_sweep("madb-mokuji", {"source": "madb-mokuji", "checked_at": TODAY, "data_as_of": "MADB 1.2.21 (cm106 連載 × metadata108 目次 × cm102 号)",
                                "method": "題(正規化)+著者+年(連載開始-1〜+4)で突合。 main = その誌に5回以上かつ全掲載の半分以上。 "
                                          "★目次が在るのは約40誌(ジャンプ/マガジン/サンデー/チャンピオン/花とゆめ/りぼん/なかよし/ちゃお/ビッグコミック等)だけ。 "
                                          "目次の無い誌の作品は出張掲載だけが見える(写輪眼伝型)",
                                "via": "scripts/_magazine-ledger.py sweep-madb"}, rows)


# ---------------------------------------------------------------- sweep: 楽天
KW = r"(?:誌上?)?\s*(?:で|にて|に|の|より|から)?\s*(?:大?人気|好評|話題|絶賛|超人気|大好評|人気)?\s*(?:連載|掲載|発|新連載|連載中|掲載中)"
Q = re.compile(r"[「『【]([^」』】\n]{2,30})[」』】]" + KW)
NQ = re.compile(r"((?:週刊|月刊|隔週刊|別冊|増刊)?[^\s「」『』、。！!？?\n]{1,12}(?:ジャンプ\+?|ジャンプ＋|マガジン|サンデー|チャンピオン|ガンガン|エース|コミック|ゆめ|LaLa|ララ|マーガレット|"
                r"フレンド|りぼん|なかよし|ちゃお|Sho-Comi|モーニング|アフタヌーン|ビッグコミック[^\s、。]{0,8}|スピリッツ|ヤングジャンプ|バンチ|ライバル|シリウス|"
                r"アライブ|ブレイド|コロコロ|ボンボン|ゴラク|アクション|ヒバナ|ゲッサン|クラブサンデー|ウェブコミック|ONLINE|オンライン))" + KW)


def sweep_rakuten():
    pages = load_pages()
    stem2slug, _ = page_files()
    i2s = isbn_to_slugs(stem2slug)
    want = {i: [s for s in ss if s in pages] for i, ss in i2s.items()}
    want = {i: ss for i, ss in want.items() if ss}
    src = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")
    as_of = datetime.date.fromtimestamp(os.path.getmtime(src)).isoformat()
    scope, per = set(), defaultdict(lambda: defaultdict(lambda: [0, ""]))
    unresolved = Counter()
    n = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            isbn = line[10:23]
            if isbn not in want:
                continue
            try:
                it = json.loads(line)["item"]
            except (ValueError, KeyError):
                continue          # 壊れた行 = 調べていない扱い(見つからずにしない)
            n += 1
            for s in want[isbn]:
                scope.add(s)
            cap = (it.get("itemCaption") or "") + "\n" + (it.get("contents") or "")
            found = {}
            for rx in (Q, NQ):
                for m in rx.finditer(cap):
                    nm = re.sub(r"^(?:【[^】]*】|[（(【「『])+", "", m.group(1).strip())
                    k = resolve(nm)
                    if k.startswith("?"):
                        unresolved[nm] += 1
                        continue          # マスタに無い名は採らない(「小説家になろう」連載=原作小説 / 作品名 / 「編集担当からのおすすめ情報」が大半)
                    found.setdefault(k, (nm, cap[max(0, m.start() - 20):m.end() + 10].replace("\n", " ")))
            for k, (nm, ctx) in found.items():
                for s in want[isbn]:
                    e = per[s][k]
                    e[0] += 1
                    if not e[1]:
                        e[1] = f"{isbn}: …{ctx}…"
    rows = {}
    for s in scope:
        rows[s] = sorted([{"mag": k, "raw": magname(k) if not k.startswith("?") else k[1:], "n": c, "ref": ref}
                          for k, (c, ref) in per.get(s, {}).items()], key=lambda h: -h["n"])
    write_sweep("rakuten-caption", {"source": "rakuten-caption", "checked_at": TODAY, "data_as_of": f"楽天キャッシュ {as_of}",
                                    "method": "頁の巻ISBN × 楽天 itemCaption/contents の「〜で連載/掲載」。 調べた頁 = 巻が1冊でもキャッシュに在る頁。 "
                                              "★弱い根拠: 作者の前作の誌(「『○○』(ジャンプ連載)の作者が贈る」)も拾う",
                                    "via": "scripts/_magazine-ledger.py sweep-rakuten", "items_read": n}, rows)
    print("  マスタに無い誌名(上位):", unresolved.most_common(25))


# ---------------------------------------------------------------- sweep: Wikipedia 作品記事(Infobox の掲載誌)
# 欄の選び方は scripts/magazine-verify/wiki_mag_judge2.py と同じ: 欄の題が頁の題と合う + 作画者(作者/作画/漫画/著者)が合う欄。
# ★原作者だけ合う欄は採らない(別の漫画版のことがある = 伝説の勇者の伝説)。 QID でつながった記事で欄が1つだけの時は作者照合なしで採る。
WIKI_CACHE = os.path.join(ROOT, ".cache", "magazine-wiki")       # この道具が取った本文(safe_key(記事名).txt + index.json)
SEP = r"[\s　・:：\-‐－〜~～「」『』()（）!！?？]"
DISAMBIG = re.compile(r"\{\{\s*(?:aimai|Aimai|曖昧さ回避|Disambig|disambig|人名の曖昧さ回避)")


def _wl():
    sys.path.insert(0, os.path.join(ROOT, "scripts", "magazine-verify"))
    import wiki_mag_lib
    return wiki_mag_lib


def tsim(W, pt, bt):
    """題が同じか、 片方がもう片方の中に区切りで挟まれて現れる時だけ同じ作品(ホクサイと飯 ⊂ ホクサイと飯さえあれば = 別作)。"""
    braw = re.sub(r"<nowiki>|</nowiki>|<br\s*/?>", " ", W.plain(bt)).strip()
    a, b = W.norm(pt), W.norm(braw)
    if not a or not b:
        return False
    if a == b:
        return True

    def bounded(small, big):
        for m in re.finditer(re.escape(small), big):
            l = big[m.start() - 1] if m.start() > 0 else " "
            r = big[m.end()] if m.end() < len(big) else " "
            if re.match(SEP, l) and re.match(SEP, r):
                return True
        return False
    p2 = unicodedata.normalize("NFKC", pt).strip()
    b2 = unicodedata.normalize("NFKC", braw)
    return (len(p2) >= 2 and bounded(p2, b2)) or (len(b2) >= 2 and bounded(b2, p2))


def _artists(W, b):
    s = " ".join(b.get(k, "") for k in ("作者", "作画", "漫画", "著者"))
    names = [x for pair in W.links(s) for x in pair] + [x for x in re.split(r"[、,/・\s]|<br\s*/?>", W.plain(s)) if x]
    return {W.norm(x) for x in names if len(W.norm(x)) >= 2}


def judge_article(W, title, art, orig, article, wt, by_qid, bl=None):
    """→ ("hit", [hits]) / ("none", 理由)。 bl = 先に切り出した Infobox 欄(ダンプ判定用)。"""
    bl = W.blocks(wt) if bl is None else bl
    if not bl:
        return "none", "漫画のInfoboxなし"
    best = None
    for b in bl:
        mv = b.get("掲載誌") or b.get("掲載サイト") or b.get("掲載誌（又は連載）") or ""
        bt = b.get("タイトル") or re.sub(r"\s*\([^)]*\)$", "", article)
        single_q = by_qid and len(bl) == 1
        if not tsim(W, title, bt) and not single_q:
            continue
        ar, allp = _artists(W, b), W.people(b)
        lvl = 2 if any(a in x or x in a for a in art for x in ar) else (1 if any(a in x or x in a for a in (art | orig) for x in allp) else 0)
        if single_q and lvl == 0 and not allp:
            lvl = 1                                # QID でつながり欄が1つ・作者欄が空 = その作品の欄
        if lvl == 0 or (art and lvl < 2 and not single_q):
            continue
        c = (-lvl, 0 if mv.strip() else 1, b, mv)
        if best is None or c[:2] < best[:2]:
            best = c
    if best is None:
        return "none", "作画者の合う欄なし"
    mv = best[3]
    if not mv.strip():
        return "none", "掲載誌の欄なし"
    raw = W.strip_markup(mv)
    raw = re.sub(r"\{\{\s*(?:Plainlist|plainlist|Unbulleted list|ubl)\s*\|", "", raw)
    segs = [x for x in re.split(r"<br\s*/?>|→|&#8594;|\n\s*\*|、|，|,|／", raw.strip().lstrip("*").strip()) if x.strip()]
    hits = []
    for sg in segs[:5]:
        fm = W.first_mag(sg)
        if not fm:
            continue
        target, disp, after = fm
        k = resolve(disp)
        if k.startswith("?") and target != disp:
            k2 = resolve(target)
            k = k2 if not k2.startswith("?") else k
        if re.match(r"(.*増刊|別冊|臨時)", after or "") and not k.startswith("?"):
            k = "?" + disp + after                 # 「○○増刊」= 別の誌(親誌に寄せない)
        h = {"mag": k, "raw": disp, "n": 1, "ref": f"{article}: {raw[:100]}".replace("\n", " ")}
        if hits:
            h["sub"] = True                        # 2つ目以降 = 移籍先など。 強い根拠に数えるのは先頭(初出誌)だけ
        if all(x["mag"] != k for x in hits):
            hits.append(h)
    return ("hit", hits) if hits else ("none", "掲載誌を読めない: " + raw[:60].replace("\n", " "))


def _page_people(pages, roles):
    out = {}
    for slug, p in pages.items():
        ppl = roles.get(slug)
        if ppl:
            art = {_n(n) for n, r in ppl if r in ("artist", "writer_artist", "") and len(_n(n)) >= 2}
            orig = {_n(n) for n, r in ppl if r not in ("artist", "writer_artist", "") and len(_n(n)) >= 2}
        else:
            art, orig = {_n(n) for n in p["names"] if len(_n(n)) >= 2}, set()
        out[slug] = (art, orig)
    return out


def _wiki_done():
    """判定済みの (slug|記事名)。 同じ本文を2回判定しない(再開用)。"""
    p = os.path.join(EV, "wiki-article.jsonl")
    done = set()
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            done.update(json.loads(line).get("keys", []))
    return done


def _wiki_index():
    p = os.path.join(WIKI_CACHE, "index.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"titles": {}, "by_slug": {}}


def sweep_wiki_local():
    """手元に在る記事本文だけで判定(ネットに出ない)。 置き場 = 素材ハーベスト(QID) / Wiki蒸留(題) / この道具の取得分。"""
    W = _wl()
    pages = load_pages()
    stem2slug, roles = page_files()
    pp = _page_people(pages, roles)
    done = _wiki_done()
    cands = defaultdict(list)                     # slug → [(記事名, 本文path, QIDか)]
    mat = os.path.join(ROOT, ".cache", "enrich-material")
    for line in open(os.path.join(mat, "wiki-links.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        f = os.path.join(mat, "wiki", f'{r["slug"]}.wiki.txt')
        if r.get("article") and os.path.exists(f):
            cands[stem2slug.get(r["slug"], r["slug"])].append((r["article"], f, True))
    for stem, _t, _v, w in json.load(open(os.path.join(ROOT, ".cache", "jawiki-title-hits.json"), encoding="utf-8")):
        f = os.path.join(ROOT, ".cache", "wiki-sweep", W.safe_key(w) + ".txt")
        if os.path.exists(f):
            cands[stem2slug.get(stem, stem)].append((w, f, False))
    idx = _wiki_index()
    for slug, arts in idx["by_slug"].items():
        for w in arts:
            f = os.path.join(WIKI_CACHE, W.safe_key(w) + ".txt")
            if os.path.exists(f):
                cands[slug].append((w, f, False))
    sweep_dir = os.path.join(ROOT, ".cache", "wiki-sweep")        # Wiki蒸留の本文を題の表記ゆれからも引く
    have = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(sweep_dir, "*.txt"))}
    for slug, p in pages.items():
        for v in _title_variants(p["title"]):
            if W.safe_key(v) in have:
                cands[slug].append((v, os.path.join(sweep_dir, W.safe_key(v) + ".txt"), False))
    rows, c = [], Counter()
    for slug, lst in cands.items():
        if slug not in pages:
            continue
        arts = {}
        for w, f, q in lst:
            arts[w] = (f, q or arts.get(w, ("", False))[1])
        art, orig = pp[slug]
        hits, reasons, keys, at = [], [], [], ""
        for w, (f, q) in arts.items():
            key = f"{slug}|{w}"
            if key in done:
                continue
            keys.append(key)
            at = max(at, datetime.date.fromtimestamp(os.path.getmtime(f)).isoformat())
            wt = open(f, encoding="utf-8").read()
            if DISAMBIG.search(wt):
                reasons.append(f"{w}: 曖昧さ回避の頁")
                continue
            kind, v = judge_article(W, pages[slug]["title"], art, orig, w, wt, q)
            if kind == "hit":
                hits += [h for h in v if all(h["mag"] != x["mag"] for x in hits)]
            else:
                reasons.append(f"{w}: {v}")
        if not keys:
            continue
        for i, h in enumerate(hits):               # 記事が複数ある時も強い根拠は先頭の誌だけ
            if i and not h.get("sub"):
                h["sub"] = True
        rows.append({"slug": slug, "hits": hits, "at": at, "ref": "" if hits else " / ".join(reasons)[:200],
                     "keys": keys, "via": "sweep-wiki-local"})
        c["hit" if hits else "none"] += 1
    append_log("wiki-article", rows)
    print(f"  掲載誌あり {c['hit']:,} / 記事は在るが掲載誌なし・欄が合わない {c['none']:,}")


def _title_variants(t):
    v = [t]
    for x in (t.replace("!", "！").replace("?", "？"), t.replace("！", "!").replace("？", "?")):
        if x != t:
            v.append(x)
    v.append(t + " (漫画)")
    base = re.split(r"[ 　]+[-‐－〜~]", t)[0].strip()
    if base and base != t:
        v += [base, base + " (漫画)"]
    return list(dict.fromkeys(v))


def _dump_key(t):
    t = unicodedata.normalize("NFC", t).strip().replace(" ", "_")
    return t[:1].upper() + t[1:] if t[:1].isascii() else t


def sweep_wiki_fetch(limit=None):
    """まだ記事を見ていない頁の題(と表記ゆれ・「(漫画)」)を全題名ダンプで引き、 在る記事だけ本文を取る(10件ずつ・3秒間隔)。
    取った本文は .cache/magazine-wiki/ に貯め、 判定は sweep-wiki-local がする。 429 = 冷却を焼いて exit 2(同じコマンドで再開)。"""
    import gzip, time, urllib.error, urllib.parse, urllib.request
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from _wiki_host import acquire, cooldown_check, cooldown_set, release
    W = _wl()
    pages = load_pages()
    wiki_src, _ = read_source("wiki-article")
    dump = os.path.join(ROOT, ".cache", "jawiki-dump", "jawiki-latest-all-titles-in-ns0.gz")
    print("  ダンプ読み込み …", flush=True)
    titles = set(gzip.open(dump, "rt", encoding="utf-8").read().split("\n"))
    idx = _wiki_index()
    os.makedirs(WIKI_CACHE, exist_ok=True)
    want = defaultdict(set)                        # 記事名 → slugs
    for slug, p in pages.items():
        if slug in wiki_src and any(not h.get("sub") for h in wiki_src[slug][1]):
            continue                               # 掲載誌が取れた頁は取りに行かない
        for v in _title_variants(p["title"]):
            if _dump_key(v) in titles:
                want[v].add(slug)
    have = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(ROOT, ".cache", "wiki-sweep", "*.txt"))}
    todo = [t for t in want if t not in idx["titles"] and W.safe_key(t) not in have]   # Wiki蒸留が取った本文は sweep-wiki-local が読む
    print(f"  記事名が在る題 {len(want):,}(頁 {len({s for ss in want.values() for s in ss}):,})/ まだ取っていない {len(todo):,}", flush=True)
    if limit:
        todo = todo[:limit * 10]
    UA = {"User-Agent": "MANGAL-research/1.0 (manga catalogue; magazine check)"}

    def save_index():
        for t, ss in want.items():
            fin = idx["titles"].get(t, {}).get("final")
            if fin:
                for s in ss:
                    lst = idx["by_slug"].setdefault(s, [])
                    if fin not in lst:
                        lst.append(fin)
        tmp = os.path.join(WIKI_CACHE, "index.json.tmp")
        json.dump(idx, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, os.path.join(WIKI_CACHE, "index.json"))

    cooldown_check()
    acquire("magazine-ledger")
    got_n = 0
    try:
        for i in range(0, len(todo), 10):
            b = todo[i:i + 10]
            q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "format": "json",
                                        "formatversion": "2", "redirects": "1", "titles": "|".join(b)})
            req = urllib.request.Request("https://ja.wikipedia.org/w/api.php", data=q.encode(), headers=UA)
            try:
                d = json.load(urllib.request.urlopen(req, timeout=60))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    cooldown_set(60, "magazine-ledger")
                    print("  ★429 → 冷却60分を焼いて停止(同じコマンドで続きから)", flush=True)
                    save_index()
                    sys.exit(2)
                print(f"  HTTP {e.code} → この10件は記帳せず飛ばす", flush=True)
                time.sleep(3)
                continue
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                print(f"  通信失敗 {e} → この10件は記帳せず飛ばす", flush=True)
                time.sleep(10)
                continue
            q2 = d.get("query", {})
            nm = {x["from"]: x["to"] for x in q2.get("normalized", [])}
            rd = {x["from"]: x["to"] for x in q2.get("redirects", [])}
            pages_ = {p["title"]: p for p in q2.get("pages", [])}
            for t in b:
                f = nm.get(t, t)
                f = rd.get(f, f)
                p = pages_.get(f)
                if p is None:
                    continue                       # 応答に無い = 記帳しない(次回また取る)
                if p.get("missing"):
                    idx["titles"][t] = {"final": None, "missing": True}
                    continue
                if not p.get("revisions"):
                    continue
                wt = p["revisions"][0]["slots"]["main"]["content"]
                open(os.path.join(WIKI_CACHE, W.safe_key(f) + ".txt"), "w", encoding="utf-8").write(wt)
                idx["titles"][t] = {"final": f, "missing": False}
                got_n += 1
            if (i // 10) % 20 == 0:
                save_index()
                print(f"  {min(i + 10, len(todo)):,}/{len(todo):,}(本文 {got_n:,})", flush=True)
            time.sleep(3)
    finally:
        save_index()
        release("magazine-ledger")
    print(f"  取得完了: 本文 {got_n:,} → 続けて sweep-wiki-local で判定")


DUMP_DIR = os.path.join(ROOT, ".cache", "jawiki-dump")
ART_DUMP = os.path.join(DUMP_DIR, "jawiki-latest-pages-articles-multistream.xml.bz2")
MANGA_ARTS = os.path.join(DUMP_DIR, "manga-articles.jsonl")       # 漫画の Infobox を持つ記事だけ {title, text}
REDIRECTS = os.path.join(DUMP_DIR, "redirects.tsv")               # 記事名 → 転送先(標準名前空間すべて)


def _extract_dump():
    """本文ダンプを1回だけ流し読みし、 漫画 Infobox を持つ記事とリダイレクトだけ書き出す(20〜40分)。"""
    import bz2, html
    n = keep = nred = 0
    tmp_a, tmp_r = MANGA_ARTS + ".tmp", REDIRECTS + ".tmp"
    with bz2.open(ART_DUMP, "rt", encoding="utf-8") as f, open(tmp_a, "w", encoding="utf-8", newline="\n") as fa, \
            open(tmp_r, "w", encoding="utf-8", newline="\n") as fr:
        title = ns = red = None
        intext, want, buf = False, False, []
        for line in f:
            if intext:
                i = line.find("</text>")
                if want:
                    buf.append(line if i < 0 else line[:i])
                if i >= 0:
                    intext = False
                    if want:
                        wt = html.unescape("".join(buf))
                        if "Infobox animanga/Manga" in wt:
                            fa.write(json.dumps({"title": title, "text": wt}, ensure_ascii=False) + "\n")
                            keep += 1
                continue
            s = line.lstrip()
            if s.startswith("<title>"):
                title, ns, red = html.unescape(s[7:s.find("</title>")]), None, None
                n += 1
                if n % 200000 == 0:
                    print(f"  {n:,} 頁 / 漫画記事 {keep:,} / 転送 {nred:,}", flush=True)
            elif s.startswith("<ns>"):
                ns = s[4:s.find("</ns>")]
            elif s.startswith("<redirect title=\""):
                red = html.unescape(s[17:s.find("\"", 17)])
                if ns == "0":
                    fr.write(f"{title}\t{red}\n")
                    nred += 1
            elif s.startswith("<text"):
                if s.rstrip().endswith("/>"):
                    continue
                want = ns == "0" and red is None
                j = s.find(">") + 1
                rest = s[j:]
                k = rest.find("</text>")
                if k >= 0:
                    if want and "Infobox animanga/Manga" in rest:
                        fa.write(json.dumps({"title": title, "text": html.unescape(rest[:k])}, ensure_ascii=False) + "\n")
                        keep += 1
                    continue
                intext, buf = True, ([rest] if want else [])
    os.replace(tmp_a, MANGA_ARTS)
    os.replace(tmp_r, REDIRECTS)
    print(f"  抜き出し完了: {n:,} 頁 → 漫画記事 {keep:,} / 転送 {nred:,}", flush=True)


def sweep_wiki_dump():
    """本文ダンプ(漫画 Infobox を持つ記事)で全頁を判定。 記事の探し方 = 題と表記ゆれ(転送も辿る)+ Infobox の題からの逆引き。
    どの探し方でも記事が無い頁は「記事なし」と記録する(題名違いの記事は拾えない = ref に明記)。"""
    W = _wl()
    if not os.path.exists(MANGA_ARTS) or os.path.getmtime(MANGA_ARTS) < os.path.getmtime(ART_DUMP):
        _extract_dump()
    as_of = datetime.date.fromtimestamp(os.path.getmtime(ART_DUMP)).isoformat()
    pages = load_pages()
    _, roles = page_files()
    pp = _page_people(pages, roles)
    done = _wiki_done()
    wiki_src, _ = read_source("wiki-article")
    arts, rev = {}, defaultdict(set)
    for line in open(MANGA_ARTS, encoding="utf-8"):
        r = json.loads(line)
        if DISAMBIG.search(r["text"]):
            continue
        bl = W.blocks(r["text"])
        arts[r["title"]] = bl
        for k in {W.norm(re.sub(r"\s*\([^)]*\)$", "", r["title"]))} | {W.norm(W.plain(b.get("タイトル", ""))) for b in bl}:
            if len(k) >= 2:
                rev[k].add(r["title"])
    red = {}
    for line in open(REDIRECTS, encoding="utf-8"):
        a, _, b = line.rstrip("\n").partition("\t")
        if b.split("#")[0] in arts:
            red[a] = b.split("#")[0]
    print(f"  漫画記事 {len(arts):,} / それへの転送 {len(red):,}", flush=True)
    rows, c = [], Counter()
    for slug, p in pages.items():
        cand = []
        for v in _title_variants(p["title"]):
            t = v.replace("_", " ")
            if t in arts:
                cand.append(t)
            elif t in red:
                cand.append(red[t])
        cand += sorted(rev.get(W.norm(p["title"]), ()))
        cand = list(dict.fromkeys(cand))
        if not cand:
            if slug not in wiki_src:
                rows.append({"slug": slug, "hits": [], "at": as_of, "via": "sweep-wiki-dump", "ref": "漫画の記事なし(本文ダンプ)"})   # 意味は README
                c["absent"] += 1
            continue
        art, orig = pp[slug]
        hits, reasons, keys = [], [], []
        for w in cand:
            key = f"{slug}|{w}"
            if key in done:
                continue
            keys.append(key)
            kind, v = judge_article(W, p["title"], art, orig, w, "", False, bl=arts[w])
            if kind == "hit":
                hits += [h for h in v if all(h["mag"] != x["mag"] for x in hits)]
            else:
                reasons.append(f"{w}: {v}")
        if not keys:
            continue
        for i, h in enumerate(hits):
            if i and not h.get("sub"):
                h["sub"] = True
        rows.append({"slug": slug, "hits": hits, "at": as_of, "ref": "" if hits else " / ".join(reasons)[:200],
                     "keys": keys, "via": "sweep-wiki-dump"})
        c["hit" if hits else "none"] += 1
    append_log("wiki-article", rows)
    print(f"  掲載誌あり {c['hit']:,} / 記事はあるが掲載誌なし・欄が合わない {c['none']:,} / 漫画の記事なし {c['absent']:,}")


def sweep_wiki_absent():
    """題(と表記ゆれ・「(漫画)」)のどれも全題名ダンプに無い頁 = 「Wikipedia に記事名なし」と記録する。
    ダンプは ja.wikipedia の全記事名の完全な一覧 = 手元で引いて無かった、 は書いてよい「見つからず」。 ただし題名違いの記事は拾えない(ref に明記)。"""
    import gzip
    W = _wl()
    pages = load_pages()
    wiki_src, _ = read_source("wiki-article")
    dump = os.path.join(ROOT, ".cache", "jawiki-dump", "jawiki-latest-all-titles-in-ns0.gz")
    as_of = datetime.date.fromtimestamp(os.path.getmtime(dump)).isoformat()
    titles = set(gzip.open(dump, "rt", encoding="utf-8").read().split("\n"))
    rows = []
    for slug, p in pages.items():
        if slug in wiki_src:
            continue
        if any(_dump_key(v) in titles for v in _title_variants(p["title"])):
            continue                               # 記事名は在る = 本文を取って sweep-wiki-local が判定する
        rows.append({"slug": slug, "hits": [], "at": as_of, "ref": f"題名の記事なし(全題名ダンプ {as_of}・題/表記ゆれ/(漫画) で照合。 題名違いの記事は未確認)",
                     "keys": [f"{slug}|(dump-absent)"], "via": "sweep-wiki-absent"})
    append_log("wiki-article", rows)


# ---------------------------------------------------------------- 11/4 までの結果の取り込み(1回だけ)
WIKI_LIST = {"wsj-list": ("weekly-shonen-jump", "週刊少年ジャンプ連載作品の一覧"),
             "wsm-list": ("weekly-shonen-magazine", "週刊少年マガジン連載作品の一覧"),
             "wss-list": ("weekly-shonen-sunday", "週刊少年サンデー連載作品の一覧"),
             "champion-list": ("champion", "週刊少年チャンピオン連載作品の一覧"),
             "wyj": ("weekly-young-jump", "週刊ヤングジャンプ"), "jump-plus": ("shonen-jump-plus", "少年ジャンプ+"),
             "ultra-jump": ("ultra-jump", "ウルトラジャンプ"), "monthly-jump": ("monthly-shonen-jump", "月刊少年ジャンプ"),
             "jump-sq": ("jump-sq", "ジャンプスクエア"), "saikyo-jump": ("saikyo-jump", "最強ジャンプ"), "v-jump": ("v-jump", "Vジャンプ"),
             "fresh-jump": ("fresh-jump", "フレッシュジャンプ"), "wsj-zokan": ("?週刊少年ジャンプ増刊", "週刊少年ジャンプ増刊")}


def import_legacy():
    for src in ("wiki-list", "wiki-article", "manual"):
        if os.path.exists(os.path.join(EV, f"{src}.jsonl")):
            sys.exit(f"{src}.jsonl が既に在る = 取り込み済み。 やり直す時はファイルを消してから")
    pages = load_pages()
    # ① Wikipedia 雑誌の掲載作品一覧 13記事(2026-11-04)= 当たった頁だけ(当たらなかった頁は未調査のまま扱う: 当時の照合範囲を道具で再現できないため)
    mem = json.load(open(os.path.join(LISTS, "membership.json"), encoding="utf-8"))
    rows = []
    for slug, lists in mem.items():
        hs = []
        for lk, rws in lists.items():
            mk, art = WIKI_LIST[lk]
            hs.append({"mag": mk, "raw": art, "n": len(rws), "ref": (rws[0] if rws else "")[:160]})
        rows.append({"slug": slug, "hits": hs, "at": "2026-11-04", "ref": "ja.wikipedia 掲載作品一覧13記事(記事の1行に題と著者が並ぶ)"})
    append_log("wiki-list", rows)

    # ② Wikipedia 作品記事の Infobox(2026-11-04 の検証表)+ per-case の wiki-verified(8〜9月)
    import csv
    rows = []
    tsv = os.path.join(OUT, "magazine-verify-2026-11-04.tsv")
    lines = [l for l in open(tsv, encoding="utf-8") if not l.startswith("#")]
    for r in csv.DictReader(lines, delimiter="\t"):
        if (r.get("段階") or "").startswith("Z"):
            continue                       # Z = Wiki未取得 = 調べていない
        w = r.get("Wikipedia") or ""
        hs = []
        for t, d in re.findall(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", w):
            nm = (d or t).strip()
            k = resolve(nm)
            if k.startswith("?") and d:
                k2 = resolve(t)
                k = k2 if not k2.startswith("?") else k
            hs.append({"mag": k, "raw": nm, "n": 1, "ref": w[:160]})
        rows.append({"slug": r["slug"], "hits": hs, "at": "2026-11-04", "ref": "ja.wikipedia 作品記事 Infobox の掲載誌(magazine-verify-2026-11-04.tsv)"})
    corr = load_yaml(os.path.join(ROOT, "data", "seeds", "magazine-corrections.yml"))["corrections"]
    man = []
    for slug, v in corr.items():
        src = v.get("source")
        h = [{"mag": v["magazine"], "raw": magname(v["magazine"]), "n": 1, "ref": str(v.get("evidence", ""))[:200]}]
        if src == "wiki-verified":
            rows.append({"slug": slug, "hits": h, "at": str(v.get("added_at", "")), "ref": "per-case: ja.wikipedia を読んで上書き(magazine-corrections.yml)"})
        elif src in ("manual", "rakuten-verified"):
            man.append({"slug": slug, "hits": h, "at": str(v.get("added_at", "")), "ref": f"magazine-corrections.yml source={src}"})
    append_log("wiki-article", rows)
    append_log("manual", man)
    miss = [r for r in rows + man if r["slug"] not in pages]
    if miss:
        print(f"  ※本番の索引に無い slug {len(miss)} 件(頁の統合・改名・非掲載): {[r['slug'] for r in miss[:10]]}")


# ---------------------------------------------------------------- build: 一覧表
ROLE = {"writer": "原作", "artist": "作画", "writer_artist": "著者"}


JUNK_MAG = re.compile(r"^\s*$|^\d|^[\[［(（]|^(単行本|全編|完全)?(描き下ろし|書き下ろし)|^掲載誌$|^雑誌連載$|コミックス$|^web$|^Web$|^不明|^未定")


def clean_hits(hs):
    """表を作る時の後始末: 誌名でない書き込み(「単行本描き下ろし」「1995年」等)を捨て、 「?誌名」は今の別名表で引き直す
    (別名を足した後に取り直さなくてよいように)。 台帳そのものは書き換えない。"""
    out = []
    for h in hs:
        raw = re.sub(r"[（(][^)）]*\d{4}[^)）]*[)）]\s*$", "", (h.get("raw") or "")).strip()   # 「誌名(2011年 - 2012年)」の期間を外す
        if h["mag"].startswith("?"):
            if JUNK_MAG.search(raw):
                continue
            k = resolve(raw)
            if not k.startswith("?") or raw != h.get("raw"):
                h = {**h, "mag": k}
        out.append(h)
    return out


def evidence_of(slug, src):
    """1頁の根拠を数える(表の「状態」と是正の判定が同じ数え方を使う)。
    strong = 強い根拠の誌 → それを言うソースの数 / by_src = 誌 → ソース名 / secondary = 主でない記載(移籍先・出張掲載・2番目に多い初出)
    weak = 楽天説明の誌 / cells = 表のソース列の文字。"""
    strong, weak, by_src, secondary = Counter(), Counter(), defaultdict(list), set()
    cells, unchecked, checked_any, wiki_checked, last = {}, [], False, False, ""
    for key, col, is_strong in SOURCES:
        rec = src[key][0].get(slug)
        if rec is None:
            cells[col] = ""
            unchecked.append(col)
            continue
        at, hs = rec
        checked_any = True
        last = max(last, at)
        if key.startswith("wiki-"):
            wiki_checked = True
        hs = clean_hits(hs)
        if not hs:
            cells[col] = f"なし({at})"
            continue
        use = [h for h in hs if h.get("main")] if key == "madb-mokuji" else [h for h in hs if not h.get("sub")]
        if key == "madb-shoshutsu":
            use = hs[:1] if len(hs) == 1 or hs[0]["n"] > hs[1]["n"] else [h for h in hs if h["n"] == hs[0]["n"]]
        used = {h["mag"] for h in use}
        for m in used:
            (strong if is_strong else weak)[m] += 1
            if is_strong:
                by_src[m].append(key)
        secondary |= {h["mag"] for h in hs} - used
        cells[col] = " / ".join(f'{magname(h["mag"])}×{h["n"]}' for h in hs[:4]) + f"({at})"
    return {"strong": strong, "weak": weak, "by_src": by_src, "secondary": secondary, "cells": cells, "unchecked": unchecked,
            "checked_any": checked_any, "wiki_checked": wiki_checked, "last": last}


def build():
    pages = load_pages()
    _, roles = page_files()
    corr = load_yaml(os.path.join(ROOT, "data", "seeds", "magazine-corrections.yml"))["corrections"]
    src = {k: read_source(k) for k, _, _ in SOURCES}
    cols = ["slug", "漫画名", "著者", "原作", "作画", "その他の役割", "出版社", "開始年", "今の連載誌", "上書き", "状態", "根拠の誌", "強い根拠の数"]
    cols += [c for _, c, _ in SOURCES] + ["最終確認日", "未調査のソース"]
    st_count, per_mag = Counter(), defaultdict(Counter)
    missing = defaultdict(lambda: [0, []])          # 雑誌マスタに無い誌 → [頁数, 例]
    out = []
    for slug, p in sorted(pages.items()):
        ppl = roles.get(slug) or [[n, ""] for n in p["names"]]
        by = defaultdict(list)
        for n, r in ppl:
            by[ROLE.get(r, "その他" if r else "役割不明")].append(n if r in ROLE or not r else f"{n}({r})")
        cur = p["mag"]
        E = evidence_of(slug, src)
        strong, weak, cells, unchecked = E["strong"], E["weak"], E["cells"], E["unchecked"]
        checked_any, wiki_checked, last = E["checked_any"], E["wiki_checked"], E["last"]
        ev = set(strong)
        manual = src["manual"][0].get(slug)
        if manual and manual[1] and manual[1][0]["mag"] == cur:
            state = "人が裁定"
        elif not ev:
            # MADB は全頁を照合済み = 「MADBに無い」だけでは調べ尽くしていない。 次の手(Wikipedia)を打ったかで分ける
            looked = "Wikiまで調べたが見つからず" if wiki_checked else ("Wiki未調査(MADB・楽天には無い)" if checked_any else "未調査")
            if not cur:
                state = "空欄・楽天にだけ記載" if weak else "空欄・" + looked
            elif cur in weak:
                state = "根拠なし・楽天だけ一致"
            elif weak:
                state = "根拠なし・楽天は別誌"
            else:
                state = "根拠なし・" + looked
        elif not cur:
            state = "空欄・根拠あり(マスタに無い誌)" if all(k.startswith("?") for k in ev) else "空欄・根拠あり"
        elif cur in ev:
            state = "一致・別誌の記載も(移籍/増刊/スピンオフ)" if len(ev) > 1 else ("一致(根拠2つ以上)" if strong[cur] >= 2 else "一致(根拠1つ)")
        else:
            state = "食い違い"
        st_count[state] += 1
        per_mag[cur or "(空)"][state] += 1
        for k in strong:
            if k.startswith("?"):
                missing[k[1:]][0] += 1
                if len(missing[k[1:]][1]) < 3:
                    missing[k[1:]][1].append(p["title"])
        c = corr.get(slug)
        row = {"slug": slug, "漫画名": p["title"], "著者": "、".join(by.get("著者", []) + by.get("役割不明", [])),
               "原作": "、".join(by.get("原作", [])), "作画": "、".join(by.get("作画", [])), "その他の役割": "、".join(by.get("その他", [])),
               "出版社": p["pub"], "開始年": p["year"] or "", "今の連載誌": magname(cur),
               "上書き": f'{c.get("source")}({c.get("added_at")})' if c else "", "状態": state,
               "根拠の誌": "、".join(f"{magname(k)}×{n}" for k, n in strong.most_common()) +
                           ("" if not weak else ("、" if strong else "") + "、".join(f"楽天:{magname(k)}" for k in weak)),
               "強い根拠の数": strong[cur] if cur else sum(strong.values()), **cells, "最終確認日": last, "未調査のソース": "、".join(unchecked)}
        out.append(row)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "magazine-ledger.tsv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(cols) + "\n")
        for r in out:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ").replace("\n", " ") for c in cols) + "\n")
    metas = {k: (read_source(k)[1] or {}) for k in SWEEP}
    sp = os.path.join(OUT, "magazine-ledger-summary.tsv")
    states = [s for s, _ in st_count.most_common()]
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 連載誌の根拠台帳の集計 {TODAY}(scripts/_magazine-ledger.py build が作る写し。 正本 = data/seeds/magazine-evidence/)\n")
        for k, m in metas.items():
            if m:
                f.write(f"# {k}: 確認 {m.get('checked_at')} / データ {m.get('data_as_of')}\n")
        f.write("今の連載誌\t頁数\t" + "\t".join(states) + "\n")
        f.write("(全体)\t" + str(len(out)) + "\t" + "\t".join(str(st_count[s]) for s in states) + "\n")
        for mk, cnt in sorted(per_mag.items(), key=lambda x: -sum(x[1].values())):
            f.write(f"{magname(mk) if mk != '(空)' else mk}\t{sum(cnt.values())}\t" + "\t".join(str(cnt[s]) for s in states) + "\n")
    mp = os.path.join(OUT, "magazine-ledger-missing-mags.tsv")
    with open(mp, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 根拠に出てくるのに雑誌マスタ(data/magazines.yml)に無い誌 {TODAY}。 マスタに足す/既存誌の別名にする は人が決める\n")
        f.write("誌名(ソースの表記)\t頁数\t例\n")
        for nm, (n, exs) in sorted(missing.items(), key=lambda x: -x[1][0]):
            f.write(f"{nm}\t{n}\t{' / '.join(exs)}\n")
    print(f"  → {os.path.relpath(p, ROOT)} {len(out):,} 頁 / {os.path.getsize(p)/1e6:.1f}MB")
    print(f"  → {os.path.relpath(mp, ROOT)} マスタに無い誌 {len(missing):,}")
    print(f"  → {os.path.relpath(sp, ROOT)}")
    for s, n in st_count.most_common():
        print(f"    {s}\t{n:,}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if AMBIG and cmd != "build":
        print("  ※2誌に当たる書き方(使わない):", AMBIG)
    if cmd == "sweep-wiki-fetch":
        lim = sys.argv[sys.argv.index("--limit") + 1] if "--limit" in sys.argv else None
        sweep_wiki_fetch(int(lim) if lim else None)
    else:
        {"sweep-madb": sweep_madb, "sweep-rakuten": sweep_rakuten, "sweep-wiki-local": sweep_wiki_local, "sweep-wiki-absent": sweep_wiki_absent, "sweep-wiki-dump": sweep_wiki_dump,
         "import-legacy": import_legacy, "build": build}.get(cmd, lambda: sys.exit(__doc__))()
