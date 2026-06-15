"""[調査only] 巻番号順に発売日が"逆行"する作品を検出(=フィルムコミック混入/誤マージ signal)。
例: 名探偵コナン世紀末の魔術師=上1999.10/第2巻2012.09/下1999.11 → vol2(2012)がvol3(1999)より後。
本番 data/manga.v2 を走査。登録/変更なし。出力 .cache/date-order-flags.tsv
"""
import glob, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
try:
    import yaml
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

MIN_GAP_DAYS = 200  # これ以上の逆行のみ flag(同月再版ノイズ除外)


def to_days(rd):
    """YYYY / YYYY-MM / YYYY-MM-DD → 概算日数。比較用。"""
    if not rd:
        return None
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", str(rd))
    if not m:
        return None
    y = int(m.group(1)); mo = int(m.group(2) or 6); da = int(m.group(3) or 15)
    return y * 365 + mo * 30 + da


rows = []
for f in glob.glob("data/manga.v2/*.yml"):
    try:
        d = yaml.load(open(f, encoding="utf-8"), Loader=L)
    except Exception:
        continue
    if not d:
        continue
    for ed in d.get("editions") or []:
        vs = []
        for v in ed.get("volumes") or []:
            num = v.get("number")
            try:
                num = int(num)
            except (TypeError, ValueError):
                continue
            dd = to_days(v.get("release_date"))
            if dd is None:
                continue
            vs.append((num, dd, v.get("release_date")))
        if len(vs) < 2:
            continue
        vs.sort(key=lambda x: x[0])
        # 番号昇順で発売日が逆行するペア(隣接でなく全比較で最大逆行)
        worst = None
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                # i は番号が小さい, j は大きい
                gap = vs[i][1] - vs[j][1]  # >0 なら 小番号が後発=逆行
                if gap > MIN_GAP_DAYS:
                    if worst is None or gap > worst[0]:
                        worst = (gap, vs[i], vs[j])
        if worst:
            gap, a, b = worst
            rows.append((round(gap / 365, 1), d.get("slug"), d.get("title"),
                         ed.get("label"), len(vs),
                         f"#{a[0]}={a[2]}", f"#{b[0]}={b[2]}"))

rows.sort(reverse=True)
OUT = ".cache/date-order-flags.tsv"
with open(OUT, "w", encoding="utf-8") as w:
    w.write("逆行年\tslug\ttitle\t版\t巻数\t小番号(後発)\t大番号(先発)\n")
    for r in rows:
        w.write("\t".join(str(x) for x in r) + "\n")
print(f"発売日逆行 flag: {len(rows)} 版")
print("=== 上位30(逆行年数降順) ===")
for r in rows[:30]:
    print(f"  {r[0]:>5}年 {r[2]} [{r[3]}] 巻{r[4]} : 小{r[5]} > 大{r[6]}")
print(f"\nTSV → {OUT}")
