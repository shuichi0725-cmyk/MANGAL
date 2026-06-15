"""[調査] _conan-wiki-raw.txt(wiki逐語ISBN)を構造化し、
 [漫画]=コミカライズ(KEEP候補) / [フィルムブック]=フィルムコミック(DROP候補) に分類。
 我々のDBクラスタ(.cache/conan-movie-class.json)と突合して
   ・DB内ISBN  ・DB未収録の漫画版(=種4候補)  ・DB内のフィルムコミック(=drop対象)
 を明示。読みやすいTSV + テキスト表を出力。本番未変更。"""
import json, re, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW = ".cache/conan-wiki-raw.txt"

# --- wiki逐語をパース: 映画ごとに section→[(isbn, title)] ---
movies = {}  # key: "NN YEAR title"
cur = None
cur_sec = None
pending_isbn = None
with open(RAW, encoding="utf-8") as fh:
    lines = fh.readlines()
i = 0
while i < len(lines):
    ln = lines[i].rstrip("\n")
    m = re.match(r"^#(\d+)\s+(\d{4})\s+(.+)$", ln)
    if m:
        cur = ln.strip()
        movies[cur] = []
        i += 1
        continue
    m = re.match(r"^\s+\[(.*?)\]\s+ISBN=(\w+)$", ln)
    if m and cur:
        cur_sec = m.group(1)
        isbn = m.group(2)
        title = ""
        if i + 1 < len(lines):
            title = lines[i + 1].strip()
        movies[cur].append((cur_sec, isbn, title))
        i += 2
        continue
    i += 1

# --- 我々のDBクラスタ(楽天分類)のISBN集合 ---
db = {}
if os.path.exists(".cache/conan-movie-class.json"):
    cls = json.load(open(".cache/conan-movie-class.json", encoding="utf-8"))
    for sub, entries in cls.items():
        for e in entries:
            db[str(e["isbn"])] = (sub, e.get("rk_title", ""))
db_isbns = set(db)

NOISE_SEC = {"出典本", "概要", "沿革", "脚本", "概説", "ストーリー", "メインキャラクター",
             "参考文献", "元脚本からのストーリー変更点", ""}

out = open(".cache/conan-wiki-table.txt", "w", encoding="utf-8")
tsv = open(".cache/conan-wiki-keepdrop.tsv", "w", encoding="utf-8")
tsv.write("movie\tdecision\tcategory\tisbn\tin_db\ttitle\n")


def w(s=""):
    print(s)
    out.write(s + "\n")


w("コナン劇場版 漫画版(KEEP) / フィルムコミック(DROP) 確定表  [出典=ja.wikipedia 各作品記事 逐語]")
w("凡例: ◎=DB収録済 / ＋=DB未収録(種4候補) / 漫画=コミカライズ(阿部ゆたか・丸伝次郎 作画) / film=フィルムコミック(上下/完全版)")
w("=" * 78)

tot_keep_db = tot_keep_new = tot_drop_db = 0
for k in sorted(movies):
    rows = movies[k]
    manga = [(i_, t) for sec, i_, t in rows if sec == "漫画"]
    film = [(i_, t) for sec, i_, t in rows if sec in ("フィルムブック", "フィルムコミック")]
    if not manga and not film:
        continue
    w(f"\n■ {k}")
    if manga:
        w("  【漫画版 = KEEP】")
        for isbn, t in manga:
            mark = "◎収録" if isbn in db_isbns else "＋未収録(種4候補)"
            if isbn in db_isbns:
                tot_keep_db += 1
            else:
                tot_keep_new += 1
            short = re.sub(r"原案.*?作画／|青山剛昌（案）、|青山 剛昌.*?（画）|、丸伝次郎（画）", "", t)
            w(f"     {mark}  {isbn}  {short[:46]}")
            tsv.write(f"{k}\tKEEP\t漫画\t{isbn}\t{'1' if isbn in db_isbns else '0'}\t{t[:60]}\n")
    else:
        w("  【漫画版 = なし(コミカライズ未刊)】")
    if film:
        w("  【フィルムコミック = DROP】")
        for isbn, t in film:
            mark = "◎収録" if isbn in db_isbns else "－(DB外)"
            if isbn in db_isbns:
                tot_drop_db += 1
            w(f"     {mark}  {isbn}  {t[:46]}")
            tsv.write(f"{k}\tDROP\tfilm\t{isbn}\t{'1' if isbn in db_isbns else '0'}\t{t[:60]}\n")

w("\n" + "=" * 78)
w(f"集計: 漫画版KEEP = {tot_keep_db}(DB収録) + {tot_keep_new}(種4候補) / フィルムコミックDROP(DB内) = {tot_drop_db}")
out.close()
tsv.close()
print("\n--> .cache/conan-wiki-table.txt , .cache/conan-wiki-keepdrop.tsv", file=sys.stderr)
