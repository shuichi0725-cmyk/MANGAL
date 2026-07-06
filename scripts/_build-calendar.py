#!/usr/bin/env python3
"""創刊/発売日カレンダーの per-month データを build時に manga.v2 から算出。
 ・創刊(launch) = first_volume_date(standard版1巻)。全期間。
 ・発売(release) = 各巻 release_date。★全期間(過去へも戻れる)。
 ・中身は slug 参照のみ(title/cover は索引 join = 重複なし)。
 ・日精度を派生判定: 完全日→days[DD] / 年月→unknown(日未定) / 年のみ→除外。
引数: [1]=src(既定 data/manga.v2) [2]=out(既定 public/calendar) [3]=当月 YYYY-MM(既定 today)。
"""
import sys, json, glob, os, re
from datetime import date
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L

SRC = sys.argv[1] if len(sys.argv) > 1 else "data/manga.v2"
OUT = sys.argv[2] if len(sys.argv) > 2 else "public/calendar"
CUR = sys.argv[3] if len(sys.argv) > 3 else date.today().strftime("%Y-%m")
# ★[4]=slugフィルタdir(2026-07-06 preview用): 指定ディレクトリのymlに実在するslugだけ載せる
#   =「載っている→必ず飛べる」の構造保証(previewはsubsetなのでフィルタ必須・リンク切れ根絶)
FILTER_DIR = sys.argv[4] if len(sys.argv) > 4 else None
ALLOW = None
if FILTER_DIR:
    ALLOW = set()
    for _f in glob.glob(os.path.join(FILTER_DIR, "*.yml")):
        try:
            _d = yaml.load(open(_f, encoding="utf-8"), Loader=L)
            if _d and _d.get("slug"): ALLOW.add(_d["slug"])
        except Exception: pass

DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MON_RE = re.compile(r"^(\d{4})-(\d{2})$")

launch, release = {}, {}
# 日付override(楽天salesDate由来・完全日) = 月のみ/抜けを完全日に格上げ(純粋追加・ISBN keyed)
_ovp = "data/seeds/release-date-full.json"
OV = json.load(open(_ovp, encoding="utf-8")) if os.path.exists(_ovp) else {}

def eff_date(v):
    rd = v.get("release_date"); s = str(rd) if rd else ""
    ib = v.get("isbn13")
    if ib and ib in OV and ((not s) or MON_RE.match(s)): return OV[ib]
    return s

def bucket(store, ym, day, item):
    if ALLOW is not None and item[0] not in ALLOW: return
    m = store.setdefault(ym, {"days": {}, "unknown": []})
    if day: m["days"].setdefault(day, []).append(item)
    else: m["unknown"].append(item)

def fvd_of(eds):
    fvd = None
    for e in eds:
        if e.get("type") != "standard": continue
        for v in (e.get("volumes") or []):
            if v.get("number") == 1:
                s = eff_date(v)
                if s and (fvd is None or s < fvd): fvd = s
    if not fvd:
        a = [eff_date(v) for e in eds for v in (e.get("volumes") or []) if eff_date(v)]
        fvd = min(a) if a else None
    return fvd

n = 0
for f in glob.glob(os.path.join(SRC, "*.yml")):
    try: d = yaml.load(open(f, encoding="utf-8"), Loader=L)
    except: continue
    if not d or not d.get("slug"): continue
    slug = d["slug"]; eds = d.get("editions") or []
    n += 1
    # 創刊(全期間)
    fvd = fvd_of(eds)
    title = d.get("title") or slug
    if fvd:
        # ★title埋め込み(2026-07-03): 索引subset/slug改名でもタイトル表示が壊れない
        if DAY_RE.match(fvd): bucket(launch, fvd[:7], fvd[8:10], [slug, title])
        elif MON_RE.match(fvd): bucket(launch, fvd[:7], None, [slug, title])
        # 年のみ → 除外
    # 発売(当月+未来のみ)
    for e in eds:
        for v in (e.get("volumes") or []):
            rd = eff_date(v)
            if not rd: continue
            # ★全期間化(2026-07-03 ユーザ要望「月が戻る」): 過去の発売月も出す
            item = [slug, v.get("number"), title]
            if DAY_RE.match(rd): bucket(release, rd[:7], rd[8:10], item)
            elif MON_RE.match(rd): bucket(release, rd[:7], None, item)

os.makedirs(os.path.join(OUT, "launch"), exist_ok=True)
os.makedirs(os.path.join(OUT, "release"), exist_ok=True)
def cnt(data): return sum(len(v) for v in data["days"].values()) + len(data["unknown"])
for ym, data in launch.items():
    json.dump(data, open(os.path.join(OUT, "launch", ym + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
for ym, data in release.items():
    json.dump(data, open(os.path.join(OUT, "release", ym + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
# ★「以降・未定」集約(2026-07-06 5パネルUI用): 当月+4ヶ月目以降の全巻+各月の日未定を一覧化
def _next_ym(ym, k):
    y, m = int(ym[:4]), int(ym[5:7])
    m += k; y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"
_horizon = _next_ym(CUR, 4)  # これより先=「以降」
beyond = []
for ym in sorted(release.keys()):
    if ym >= _horizon:
        d0 = release[ym]
        for day in sorted(d0["days"]):
            for it in d0["days"][day]:
                beyond.append([it[0], it[1], it[2], f"{ym}-{day}"])
        for it in d0["unknown"]:
            beyond.append([it[0], it[1], it[2], ym])
json.dump({"items": beyond}, open(os.path.join(OUT, "release", "beyond.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

manifest = {
    "current": CUR,
    "launch_months": sorted(launch.keys()),
    "release_months": sorted(release.keys()),
    "launch_counts": {ym: cnt(data) for ym, data in launch.items()},
    "release_counts": {ym: cnt(data) for ym, data in release.items()},
}
json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"読込 {n} / launch月 {len(launch)} / release月 {len(release)} / 当月 {CUR}")
