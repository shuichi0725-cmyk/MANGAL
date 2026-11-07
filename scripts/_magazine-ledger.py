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
    "少年ガンガン": "gangan", "週刊少年ジャンプ増刊赤マルシャンプ": "akamaru-jump", "週刊少年ジャンプ増刊赤マルジャンプ": "akamaru-jump",
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
        if prev is None or at >= prev[0]:
            out[r["slug"]] = (at, r["hits"])
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


def build():
    pages = load_pages()
    _, roles = page_files()
    corr = load_yaml(os.path.join(ROOT, "data", "seeds", "magazine-corrections.yml"))["corrections"]
    src = {k: read_source(k) for k, _, _ in SOURCES}
    cols = ["slug", "漫画名", "著者", "原作", "作画", "その他の役割", "出版社", "開始年", "今の連載誌", "上書き", "状態", "根拠の誌", "強い根拠の数"]
    cols += [c for _, c, _ in SOURCES] + ["最終確認日", "未調査のソース"]
    st_count, per_mag = Counter(), defaultdict(Counter)
    out = []
    for slug, p in sorted(pages.items()):
        ppl = roles.get(slug) or [[n, ""] for n in p["names"]]
        by = defaultdict(list)
        for n, r in ppl:
            by[ROLE.get(r, "その他" if r else "役割不明")].append(n if r in ROLE or not r else f"{n}({r})")
        cur = p["mag"]
        strong, weak = Counter(), Counter()
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
            if not hs:
                cells[col] = f"なし({at})"
                continue
            use = [h for h in hs if h.get("main")] if key == "madb-mokuji" else hs
            if key == "madb-shoshutsu":
                use = hs[:1] if len(hs) == 1 or hs[0]["n"] > hs[1]["n"] else [h for h in hs if h["n"] == hs[0]["n"]]
            for h in {h["mag"]: h for h in use}.values():
                (strong if is_strong else weak)[h["mag"]] += 1
            cells[col] = " / ".join(f'{magname(h["mag"])}×{h["n"]}' for h in hs[:4]) + f"({at})"
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
    print(f"  → {os.path.relpath(p, ROOT)} {len(out):,} 頁 / {os.path.getsize(p)/1e6:.1f}MB")
    print(f"  → {os.path.relpath(sp, ROOT)}")
    for s, n in st_count.most_common():
        print(f"    {s}\t{n:,}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if AMBIG and cmd != "build":
        print("  ※2誌に当たる書き方(使わない):", AMBIG)
    {"sweep-madb": sweep_madb, "sweep-rakuten": sweep_rakuten, "import-legacy": import_legacy, "build": build}.get(cmd, lambda: sys.exit(__doc__))()
