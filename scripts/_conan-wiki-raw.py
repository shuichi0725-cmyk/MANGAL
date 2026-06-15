"""[調査] コナン劇場版の各wiki記事の生wikitext(action=raw)を取得し、
ISBNを含む行を文脈ごと逐語抽出。WebFetch小モデル抽出の不安定さを回避
(ISBNは原文に literal で在るので確実)。本番未変更。出力 .cache/conan-wiki-raw.txt"""
import urllib.request, urllib.parse, re, io, sys, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

MOVIES = [
    ("01", "1997", "名探偵コナン 時計じかけの摩天楼"),
    ("02", "1998", "名探偵コナン 14番目の標的"),
    ("03", "1999", "名探偵コナン 世紀末の魔術師"),
    ("04", "2000", "名探偵コナン 瞳の中の暗殺者"),
    ("05", "2001", "名探偵コナン 天国へのカウントダウン"),
    ("06", "2002", "名探偵コナン ベイカー街の亡霊"),
    ("07", "2003", "名探偵コナン 迷宮の十字路"),
    ("08", "2004", "名探偵コナン 銀翼の奇術師"),
    ("09", "2005", "名探偵コナン 水平線上の陰謀"),
    ("10", "2006", "名探偵コナン 探偵たちの鎮魂歌"),
    ("11", "2007", "名探偵コナン 紺碧の棺"),
    ("12", "2008", "名探偵コナン 戦慄の楽譜"),
    ("13", "2009", "名探偵コナン 漆黒の追跡者"),
    ("14", "2010", "名探偵コナン 天空の難破船"),
    ("15", "2011", "名探偵コナン 沈黙の15分"),
    ("16", "2012", "名探偵コナン 11人目のストライカー"),
    ("17", "2013", "名探偵コナン 絶海の探偵"),
    ("18", "2014", "名探偵コナン 異次元の狙撃手"),
    ("19", "2015", "名探偵コナン 業火の向日葵"),
    ("20", "2016", "名探偵コナン 純黒の悪夢"),
    ("21", "2017", "名探偵コナン から紅の恋歌"),
    ("22", "2018", "名探偵コナン ゼロの執行人"),
    ("23", "2019", "名探偵コナン 紺青の拳"),
    ("24", "2021", "名探偵コナン 緋色の弾丸"),
    ("25", "2022", "名探偵コナン ハロウィンの花嫁"),
    ("26", "2023", "名探偵コナン 黒鉄の魚影"),
    ("27", "2024", "名探偵コナン 100万ドルの五稜星"),
]


def fetch_raw(title):
    url = "https://ja.wikipedia.org/w/index.php?" + urllib.parse.urlencode(
        {"title": title, "action": "raw"})
    req = urllib.request.Request(url, headers={"User-Agent": "MANGAL-research/0.1 (manga db)"})
    for a in range(3):
        try:
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except Exception as e:
            if a < 2:
                time.sleep(3)
                continue
            return f"__ERR__ {e}"


def isbn_norm(s):
    d = re.sub(r"[^0-9Xx]", "", s)
    return d


out = open(".cache/conan-wiki-raw.txt", "w", encoding="utf-8")


def w(s=""):
    print(s)
    out.write(s + "\n")


for no, year, title in MOVIES:
    txt = fetch_raw(title)
    w("=" * 70)
    w(f"#{no} {year} {title}")
    w("=" * 70)
    if txt.startswith("__ERR__") or len(txt) < 200:
        w(f"  取得失敗/空: {txt[:120]}")
        time.sleep(1.0)
        continue
    lines = txt.splitlines()

    def line_isbn(ln):
        # 大文字ISBN表記 / Cite book の isbn= / ISBN2テンプレ いずれも拾う
        for pat in (r"isbn\s*=\s*([0-9][0-9\-‐\s]{8,}[0-9Xx])",
                    r"ISBN2?\s*[:|]?\s*([0-9][0-9\-‐\s]{8,}[0-9Xx])"):
            m = re.search(pat, ln, re.I)
            if m:
                return isbn_norm(m.group(1))
        return None

    hits = [idx for idx, ln in enumerate(lines) if line_isbn(ln)]
    if not hits:
        for idx, ln in enumerate(lines):
            if re.search(r"(関連書籍|コミック|フィルム|単行本|書籍)", ln) and ln.strip().startswith("="):
                w(f"  [見出し] {ln.strip()}")
        w("  ※ISBN行なし")
        time.sleep(1.0)
        continue
    cur_head = ""
    seen = set()
    for idx, ln in enumerate(lines):
        if ln.strip().startswith("=") and ln.strip().endswith("="):
            cur_head = ln.strip().strip("=").strip()
        isbn = line_isbn(ln)
        if isbn:
            clean = re.sub(r"\{\{[Cc]ite book\s*", " ", ln)
            clean = re.sub(r"(和書|link=no|ref(name)?=[^\s|]*|title=|publisher=|date=|author=|page=|pages=|year=|isbn=)", " ", clean)
            clean = re.sub(r"[\[\]\{\}\|*#=]", " ", clean).strip()
            clean = re.sub(r"\s+", " ", clean)
            key = (isbn, clean[:30])
            if key in seen:
                continue
            seen.add(key)
            w(f"  [{cur_head}] ISBN={isbn}")
            w(f"      {clean[:120]}")
    time.sleep(1.0)

out.close()
print("\n--> .cache/conan-wiki-raw.txt", file=sys.stderr)
