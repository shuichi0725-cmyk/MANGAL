"""日本語 Wikipedia を手元の本文ダンプから引く(★Wikipedia の本文・分類・転送・QID はまずこれ)。2026-11-07 新設。

背景: ja.wikipedia の API は 10件ずつ3秒間隔でも約15回で 429 になる(11/4・11/7 実測)。 本文ダンプ(毎月1日・20日ごろ更新)を
手元に置き、 記事の本文・転送・分類・Wikidata QID を引く。 ★置き場は C: のリポジトリ .cache/jawiki-dump(D: は使わない)。

  python scripts/_wiki_local.py status            # 手元の版 / 配布元の最新版
  python scripts/_wiki_local.py update            # 新しい版が出ていれば落として作り直す(無ければ何もしない)。 約1時間(落とす18分+作る40分)
  python scripts/_wiki_local.py get <記事名>       # 本文(転送を辿る)
  python scripts/_wiki_local.py text <記事名>      # 平文(見出しつき)
  python scripts/_wiki_local.py cats <記事名> / members <分類> / qid <記事名>

道具から:
  sys.path.insert(0, "scripts"); import _wiki_local as W
  W.get("ONE PIECE")          -> ("ONE PIECE", wikitext) / None
  W.resolve(title)            -> 転送後の記事名 / None
  W.text(title, intro=False)  -> 平文(「== 見出し ==」を残す)/ None
  W.categories(title) / W.members(cat) / W.qid(title) / W.links(title) / W.prefix(head) / W.is_disambig(title) / W.dump_date()
★分類は本文に書かれた [[Category:…]] だけ(テンプレートが付ける分類・隠し分類は入らない)。 全文検索は無い(記事名と転送で引く)。
"""
import bz2, datetime, gzip, html, json, os, re, shutil, sqlite3, sys, time, unicodedata, urllib.request
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", "jawiki-dump")
BASE = "https://dumps.wikimedia.org/jawiki/latest/"
FILES = {"art": "jawiki-latest-pages-articles-multistream.xml.bz2",
         "idx": "jawiki-latest-pages-articles-multistream-index.txt.bz2",
         "props": "jawiki-latest-page_props.sql.gz"}
DB = "jawiki.sqlite"
MANGA_ARTS = "manga-articles.jsonl"     # 漫画の Infobox を持つ記事(_magazine-ledger.py が読む)
REDIRECTS = "redirects.tsv"             # 標準名前空間の転送(_magazine-ledger.py が読む)
META = "meta.json"
UA = "MANGAL-research/1.0 (manga catalogue; jawiki dump)"
DISAMBIG = re.compile(r"\{\{\s*(?:aimai|Aimai|曖昧さ回避|Disambig|disambig|人名の曖昧さ回避|地名の曖昧さ回避)")
CAT_RE = re.compile(r"\[\[\s*(?:Category|カテゴリ)\s*:\s*([^\]|\n]+)", re.I)


def _assert_c_drive(p):
    """★D: に置かない(ユーザ裁定 2026-11-07)。 解決後のパスが C: でなければ止める。"""
    real = os.path.realpath(p)
    if not real.upper().startswith("C:"):
        sys.exit(f"★置き場が C: でない({real})。 D: は使わない = 中止")


def _p(name, d=None):
    return os.path.join(d or DIR, name)


def norm_title(t):
    t = unicodedata.normalize("NFC", (t or "").replace("_", " ")).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:1].upper() + t[1:] if t else t


# ---------------------------------------------------------------- 読む側
_con = None
_streams = OrderedDict()


def _db():
    global _con
    if _con is None:
        path = _p(DB)
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} が無い = python scripts/_wiki_local.py update を先に")
        _con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    return _con


def dump_date():
    m = _meta()
    return m.get("dump_date", "")


def _meta(d=None):
    p = _p(META, d)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def resolve(title, hops=3):
    """転送を辿った記事名。 無ければ None。"""
    t = norm_title(title)
    con = _db()
    for _ in range(hops + 1):
        r = con.execute("select 1 from page where title=?", (t,)).fetchone()
        rd = con.execute("select target from redirect where title=?", (t,)).fetchone()
        if rd:
            t = norm_title(rd[0].split("#")[0])
            continue
        return t if r else None
    return None


def exists(title):
    return resolve(title) is not None


def _stream(off):
    if off in _streams:
        _streams.move_to_end(off)
        return _streams[off]
    with open(_p(FILES["art"]), "rb") as f:
        f.seek(off)
        dec, buf = bz2.BZ2Decompressor(), []
        while not dec.eof:
            chunk = f.read(262144)
            if not chunk:
                break
            buf.append(dec.decompress(chunk))
    xml = b"".join(buf).decode("utf-8", "replace")
    pages = {}
    for m in re.finditer(r"<page>.*?</page>", xml, re.S):
        pg = m.group(0)
        tm = re.search(r"<title>(.*?)</title>", pg)
        x = re.search(r"<text[^>]*>(.*?)</text>", pg, re.S)
        if tm:
            pages[html.unescape(tm.group(1))] = html.unescape(x.group(1)) if x else ""
    _streams[off] = pages
    if len(_streams) > 64:
        _streams.popitem(last=False)
    return pages


def get(title):
    """→ (転送後の記事名, wikitext) / None。"""
    t = resolve(title)
    if not t:
        return None
    r = _db().execute("select off from page where title=?", (t,)).fetchone()
    if not r:
        return None
    wt = _stream(r[0]).get(t)
    return (t, wt) if wt is not None else None


def is_disambig(title):
    g = get(title)
    return bool(g and DISAMBIG.search(g[1]))


def categories(title):
    t = resolve(title)
    return [r[0] for r in _db().execute("select cat from cat where title=?", (t,))] if t else []


def members(cat, kind="page"):
    """分類に入る記事(kind="page")か下位分類(kind="subcat" = 「Category:」を外した名)。"""
    c = norm_title(re.sub(r"^(?:Category|カテゴリ)\s*:", "", cat, flags=re.I))
    rows = [r[0] for r in _db().execute("select title from cat where cat=? order by title", (c,))]
    if kind == "subcat":
        return [t.split(":", 1)[1] for t in rows if t.startswith("Category:")]
    return [t for t in rows if not t.startswith("Category:")]


def qid(title):
    t = resolve(title)
    if not t:
        return None
    r = _db().execute("select q.qid from page p join qid q on q.id=p.id where p.title=?", (t,)).fetchone()
    return r[0] if r else None


def prefix(head, limit=20):
    """記事名が head で始まる標準名前空間の記事(短い順)。 全文検索の代わり(API の list=search は使わない)。"""
    h = norm_title(head)
    if len(h) < 1:
        return []
    rows = _db().execute("select title from page where title >= ? and title < ? limit 2000", (h, h + "􏿿")).fetchall()
    out = [r[0] for r in rows if not re.match(r"[^:]{1,20}:", r[0]) or r[0].startswith(h)]
    return sorted(out, key=len)[:limit]


def links(title):
    g = get(title)
    if not g:
        return []
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]", g[1]):
        t = m.group(1).strip()
        if ":" in t and re.match(r"(?i)(category|カテゴリ|file|ファイル|画像|image|template|wikipedia|help|portal|ポータル)\s*:", t):
            continue
        out.append(norm_title(t))
    return list(dict.fromkeys(out))


def _strip_templates(s):
    for _ in range(8):
        s2 = re.sub(r"\{\{[^{}]*\}\}", "", s)
        if s2 == s:
            break
        s = s2
    return s


def to_text(wt):
    """wikitext → 平文(「== 見出し ==」は残す)。 API の extracts(explaintext・exsectionformat=wiki)に近い形。"""
    s = re.sub(r"<!--.*?-->", "", wt, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\|.*?\|\}", "", s, flags=re.S)                  # 表
    s = _strip_templates(s)
    s = re.sub(r"\[\[(?:File|ファイル|画像|Image)\s*:[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", s, flags=re.I)
    s = re.sub(r"\[\[(?:Category|カテゴリ)\s*:[^\]]*\]\]", "", s, flags=re.I)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"(?m)^\s*[*#:;]+\s*", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def text(title, intro=False):
    g = get(title)
    if not g:
        return None
    t = to_text(g[1])
    if intro:
        t = re.split(r"(?m)^==[^=]", t)[0].strip()
    return t


# ---------------------------------------------------------------- 配布元と作り直し
def remote():
    out = {}
    for k, f in FILES.items():
        req = urllib.request.Request(BASE + f, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            out[k] = {"size": int(r.headers["Content-Length"]), "modified": r.headers["Last-Modified"]}
    return out


def _download(url, dest, size):
    have = os.path.getsize(dest) if os.path.exists(dest) else 0
    if have == size:
        return
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Range": f"bytes={have}-"} if have else {})})
    t0, last = time.time(), have
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "ab" if have else "wb") as f:
        while True:
            b = r.read(4 * 1024 * 1024)
            if not b:
                break
            f.write(b)
            have += len(b)
            if have - last >= 500 * 1024 * 1024:
                print(f"  {os.path.basename(dest)} {have / 1e9:.1f}/{size / 1e9:.1f}GB ({(have - last) / 1e6 / max(1, time.time() - t0):.1f}MB/s)", flush=True)
                last, t0 = have, time.time()
    if os.path.getsize(dest) != size:
        sys.exit(f"★{dest} の大きさが合わない({os.path.getsize(dest)} != {size}) = 途中で切れた。 もう一度 update で続きから")


def build(d):
    """d に落とした3ファイルから jawiki.sqlite / manga-articles.jsonl / redirects.tsv を作る(約40分)。"""
    db = _p(DB + ".tmp", d)
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.executescript("""pragma journal_mode=off; pragma synchronous=off;
        create table page(title text primary key, id integer, off integer);
        create table redirect(title text primary key, target text);
        create table cat(title text, cat text);
        create table qid(id integer primary key, qid text);""")
    print("  索引(記事名→場所)…", flush=True)
    rows = []
    with bz2.open(_p(FILES["idx"], d), "rt", encoding="utf-8") as f:
        for line in f:
            o, _, rest = line.partition(":")
            pid, _, t = rest.partition(":")
            rows.append((t.rstrip("\n"), int(pid), int(o)))
            if len(rows) >= 200000:
                con.executemany("insert or ignore into page values(?,?,?)", rows); rows = []
    con.executemany("insert or ignore into page values(?,?,?)", rows)
    print("  QID(page_props)…", flush=True)
    rx = re.compile(r"\((\d+),'wikibase_item','(Q\d+)'")
    with gzip.open(_p(FILES["props"], d), "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "wikibase_item" in line:
                con.executemany("insert or ignore into qid values(?,?)", ((int(a), b) for a, b in rx.findall(line)))
    print("  本文を1回流し読み(転送・分類・漫画記事)…", flush=True)
    n = keep = nred = 0
    fa = open(_p(MANGA_ARTS + ".tmp", d), "w", encoding="utf-8", newline="\n")
    fr = open(_p(REDIRECTS + ".tmp", d), "w", encoding="utf-8", newline="\n")
    reds, cats = [], []

    def finish(title, ns, wt):
        nonlocal keep
        for c in CAT_RE.findall(wt):                       # 記事(ns0)と分類ページ(ns14=下位分類)の [[Category:…]]
            cats.append((title, norm_title(c)))
        if ns == "0" and "Infobox animanga/Manga" in wt:
            fa.write(json.dumps({"title": title, "text": wt}, ensure_ascii=False) + "\n")
            keep += 1

    with bz2.open(_p(FILES["art"], d), "rt", encoding="utf-8") as f:
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
                        finish(title, ns, html.unescape("".join(buf)))
                continue
            s = line.lstrip()
            if s.startswith("<title>"):
                title, ns, red = html.unescape(s[7:s.find("</title>")]), None, None
                n += 1
                if n % 500000 == 0:
                    print(f"    {n:,} 頁 / 漫画記事 {keep:,} / 転送 {nred:,}", flush=True)
                    con.executemany("insert or ignore into redirect values(?,?)", reds); reds = []
                    con.executemany("insert into cat values(?,?)", cats); cats = []
            elif s.startswith("<ns>"):
                ns = s[4:s.find("</ns>")]
            elif s.startswith("<redirect title=\""):
                red = html.unescape(s[17:s.find("\"", 17)])
                reds.append((title, red))
                nred += 1
                if ns == "0":
                    fr.write(f"{title}\t{red}\n")
            elif s.startswith("<text"):
                if s.rstrip().endswith("/>"):
                    continue
                want = red is None and ns in ("0", "14")
                rest = s[s.find(">") + 1:]
                k = rest.find("</text>")
                if k >= 0:
                    if want:
                        finish(title, ns, html.unescape(rest[:k]))
                    continue
                intext, buf = True, ([rest] if want else [])
    con.executemany("insert or ignore into redirect values(?,?)", reds)
    con.executemany("insert into cat values(?,?)", cats)
    fa.close(); fr.close()
    print("  分類の索引…", flush=True)
    con.executescript("create index cat_t on cat(title); create index cat_c on cat(cat);")
    con.commit(); con.close()
    print(f"  作り終わり: {n:,} 頁 / 漫画記事 {keep:,} / 転送 {nred:,}", flush=True)
    return {"pages": n, "manga_articles": keep, "redirects": nred}


def update(force=False):
    _assert_c_drive(DIR)
    os.makedirs(DIR, exist_ok=True)
    lock = _p("update.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 6 * 3600:
        print("★別の update が動いている(update.lock)= 何もしない"); return 3
    rem = remote()
    cur = _meta()
    have_db = os.path.exists(_p(DB))
    if not force and have_db and cur.get("dump_modified") == rem["art"]["modified"]:
        print(f"最新です(手元 {cur.get('dump_date')} = 配布元)"); return 0
    open(lock, "w").write(str(os.getpid()))
    try:
        new = _p("new")
        os.makedirs(new, exist_ok=True)
        # 手元の3ファイルが配布元と同じ版なら落とし直さない(初回に既に落としてある時)
        for k, f in FILES.items():
            src, dst = _p(f), _p(f, new)
            if not os.path.exists(dst) and os.path.exists(src) and os.path.getsize(src) == rem[k]["size"] \
                    and (cur.get(k + "_modified") in (None, rem[k]["modified"])):
                shutil.copyfile(src, dst) if k != "art" else os.replace(src, dst)
        for k, f in FILES.items():
            print(f"  落とす {f}({rem[k]['size'] / 1e9:.2f}GB, {rem[k]['modified']})", flush=True)
            _download(BASE + f, _p(f, new), rem[k]["size"])
        stats = build(new)
        global _con
        if _con is not None:
            _con.close(); _con = None
        for f in list(FILES.values()):
            os.replace(_p(f, new), _p(f))
        for f in (DB, MANGA_ARTS, REDIRECTS):
            os.replace(_p(f + ".tmp", new), _p(f))
        dd = datetime.datetime.strptime(rem["art"]["modified"], "%a, %d %b %Y %H:%M:%S GMT").date().isoformat()
        meta = {"dump_date": dd, "dump_modified": rem["art"]["modified"], "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
                **{k + "_modified": v["modified"] for k, v in rem.items()}, **stats}
        json.dump(meta, open(_p(META), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        shutil.rmtree(new, ignore_errors=True)
        print(f"★更新完了: 版 {dd} / {stats}")
        return 0
    finally:
        if os.path.exists(lock):
            os.remove(lock)


def status():
    cur = _meta()
    print("置き場:", os.path.realpath(DIR))
    print("手元の版:", cur.get("dump_date") or "(無し)", "/ 作った日時:", cur.get("built_at", ""), "/", {k: cur.get(k) for k in ("pages", "manga_articles", "redirects")})
    try:
        rem = remote()
        print("配布元の最新:", rem["art"]["modified"], f"({rem['art']['size'] / 1e9:.2f}GB)",
              "= 最新" if cur.get("dump_modified") == rem["art"]["modified"] else "= ★新しい版あり(update で取り込む)")
    except Exception as e:
        print("配布元に届かない:", type(e).__name__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd == "status":
        status()
    elif cmd == "update":
        sys.exit(update("--force" in a))
    elif cmd in ("get", "text", "cats", "members", "qid") and len(a) > 1:
        arg = " ".join(a[1:])
        if cmd == "get":
            g = get(arg)
            print(f"== {g[0]}\n{g[1][:3000]}" if g else "(記事なし)")
        elif cmd == "text":
            print(text(arg) or "(記事なし)")
        elif cmd == "cats":
            print("\n".join(categories(arg)) or "(分類なし)")
        elif cmd == "members":
            print("\n".join(members(arg)) or "(記事なし)")
        else:
            print(qid(arg) or "(QIDなし)")
    else:
        sys.exit(__doc__)
