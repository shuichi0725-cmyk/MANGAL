"""★頁メタ×巻データの矛盾監査 (= page-meta-conflict / READ-ONLY / 外部照会ゼロ)。

■ 何を見るか
  1頁(work)は year_started / year_ended / status / publisher(=publisher_key) という
  **頁レベルのメタ**を持つ。これらは promote (_promote-bulk-v2.py L2818-2894, L3026-3037) が
  **巻データから導出**する値である。にもかかわらず巻と食い違っている頁が在る。
  食い違いの出所は3つしかない:
    (a) edition-overrides / status-corrections / 種3 の **手入力値が古い**(巻が増えたのに追随していない)
    (b) 版の再構築で巻が入れ替わったが頁メタが取り残された
    (c) 巻側の日付が壊れている(= 別familyだが、ここで症状として浮く)
  ★どちらが悪いかは検出器では決めない。**矛盾の事実と証拠**だけを出す。

■ 判定(★「論理的にありえない向き」だけを取る)
  連載年と単行本の発売年はズレるのが普通(連載開始1976・1巻1977 は正当)なので、
  「巻より後に連載が始まる」「完結後に新刊が出る」方向だけを矛盾とする。

  YS_LATE          year_started > 最古巻の発売年。promote は min(全巻年) を入れるので
                   **この向きは導出上ありえない**。逆向き(year_started < 最古巻年)は
                   連載先行=正当なので取らない。
  YE_EARLY         year_ended < 「最大巻番号の初版年」(= promote の year_ended 定義そのもの)。
                   = 完結年より後に**その版の新しい巻**が出ている。
                   ★版ごとの初版min(per_vol_min_date)で見るので、新装版/復刻の再版では鳴らない。
                   ★standard版が在ればstandard版のみ(= 文庫/愛蔵版の後年刊行で誤爆させない)。
  YE_LT_YS         year_ended < year_started。巻を見るまでもなく矛盾。
  ONGOING_HAS_YE   status=ongoing なのに year_ended が入っている。promote は ongoing なら
                   year_ended=null にする(L2892-2894)ので、在ること自体が注入の痕跡。
  COMPLETED_FUTURE status=completed なのに**未来の初版**が在る。promote は「直近12ヶ月に
                   新しい初版が出ていれば completed→ongoing に戻す」(L2884-2890)ので、
                   未来巻付きで completed のままなのは status-corrections の固着 = 矛盾。
  ONGOING_STALE    status=ongoing なのに最終初版が15年以上前。★既存機構(completion-judge /
                   _check-ongoing-continuation.py)の担当領域なので**参考出力**。既定では
                   25年以上だけを出す(--stale-years で変更可)。
  PUB_ABSENT       頁の publisher_key が、その頁の**どの版の出版社**にも解決しない。
                   promote は publishers.yml/publisher-aliases.yml で版の生社名→キー解決し
                   最多巻のキーを頁 publisher にする(L3026-3037)ので、集合外の値は
                   種3/override由来の取り残し。
  PUB_NOT_MAJORITY 集合内には在るが**最多巻の社ではない**(= 代表が入れ替わったのに追随せず)。
                   軽度。参考出力。

■ 既にカバー済みなので**やらない**こと(重複回避)
  - ISBN出版者記号 vs 出版社名   → _audit-publisher-vs-isbn.py(年別多数決で社名変遷も吸収)
  - 版内のISBN出版者記号の混在   → _audit-edition-mix.py
  - 巻番号 vs 発売日の逆行       → _audit-vol-date-regression.py / _audit-date-disorder.py
  - ISBN国コード非9784の外国版   → _audit-foreign-editions.py
  ここは**頁レベルのメタ**と巻の突合に限定する(上記はどれも巻×巻 or 巻×ISBNの突合)。

■ 既知の偽陽性型
  - **1980年代以前の巻に西暦のみ('1978')の日付**が混じる頁: 年だけなので月日の粒度で判定できない。
    年単位の比較しかしていないので実害は小さいが、delta=1年の YS_LATE/YE_EARLY は
    「連載年 vs 発売年の1年ズレ」で正当なことが多い。★既定では **delta>=2年** を確度高とする。
  - **壊れた巻日付**(1900未満/2035超)が最古巻になると YS_LATE が巨大 delta で鳴る。
    → 年の有効域を 1868..(今年+3) に限り、域外は集計から外す。
  - **PUB_ABSENT** は publishers.yml 未登録の long-tail 出版社(820キーしか無い)で鳴りうる。
    → 「版の社名が1つも解決しない頁」は判定不能として除外し、1つでも解決した頁だけ見る。
  - **ONGOING_STALE** は古書のみ流通・電子移行で市場から消えた作品を含む。単独では完結の証拠にならない。

■ 是正先(この検出器は一切書き換えない)
  - YS_LATE / YE_EARLY / YE_LT_YS → data/seeds/edition-overrides.json の year_started/year_ended、
    または status-corrections。値を消せば promote が巻から再導出する。
  - ONGOING_HAS_YE / COMPLETED_FUTURE → status-corrections の固着解除。
  - PUB_ABSENT → data/publishers.yml へのキー追加(★ISBN出版者記号一致で実体確認した時のみ)、
    もしくは種3 publisher_key の除去。

■ 入力/出力
  入力: .cache/volume-flat.tsv (本番全巻フラット / 270,009行) + data/publishers.yml + publisher-aliases.yml
  出力: docs/production-diagnostics/page-meta-conflict.tsv
  usage: python scripts/_audit-page-meta-conflict.py [--stale-years 25]
"""
import argparse
import collections
import csv
import datetime
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "page-meta-conflict.tsv")

TODAY = datetime.date.today().isoformat()
YEAR_MIN, YEAR_MAX = 1868, datetime.date.today().year + 3

ap = argparse.ArgumentParser()
ap.add_argument("--stale-years", type=int, default=25,
                help="ONGOING_STALE の閾値(年)。既存機構と重複するため既定は保守的な25年")
ap.add_argument("--flat", default=FLAT)
ARGS = ap.parse_args()


# ---- publishers.yml / publisher-aliases.yml → 生社名→キー (promote の _norm_pub と同一実装) ----
def _norm_pub(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\(\[（【].{0,6}?(発売|発行|製作|配給).{0,2}?[\)\]）】]", "", s)
    s = re.sub(r"(株式会社|有限会社|合同会社|\(株\)|\(有\)|㈱|㈲)", "", s)
    s = re.sub(r"[\s・･,，\.\-—–]", "", s).strip()
    return s


def _load_pubkey() -> dict:
    import yaml
    m = {}
    pub = yaml.safe_load(open(os.path.join(ROOT, "data", "publishers.yml"), encoding="utf-8")) or {}
    for k, v in pub.items():
        nm = (v or {}).get("name") if isinstance(v, dict) else None
        if nm:
            m[_norm_pub(nm)] = k
    ali = os.path.join(ROOT, "data", "publisher-aliases.yml")
    if os.path.exists(ali):
        for nm, key in (yaml.safe_load(open(ali, encoding="utf-8")) or {}).items():
            m[_norm_pub(str(nm))] = key
    return m


PUBKEY = _load_pubkey()


def _load_status_corr() -> set:
    """status-corrections.yml のキー集合。COMPLETED_FUTURE の「告知済み最終巻」印に使う。"""
    import yaml
    fp = os.path.join(ROOT, "data", "seeds", "status-corrections.yml")
    if not os.path.exists(fp):
        return set()
    d = yaml.safe_load(open(fp, encoding="utf-8")) or {}
    return set((d.get("corrections") or {}).keys())


STATUS_CORR = _load_status_corr()


def pub_key_of(name):
    if not name:
        return None
    return PUBKEY.get(_norm_pub(name))


def yr(s):
    """'YYYY-MM-DD' 等 → int年。有効域外/不正は None。"""
    s = str(s or "")
    if len(s) < 4 or not s[:4].isdigit():
        return None
    y = int(s[:4])
    return y if YEAR_MIN <= y <= YEAR_MAX else None


def iso_low(s):
    """比較用に**最も早い日**へ丸める(= 未来判定を保守的にする)。'2026'→'2026-01-01'。"""
    s = str(s or "").strip()
    if len(s) < 4 or not s[:4].isdigit():
        return ""
    if len(s) == 4:
        return s + "-01-01"
    if len(s) == 7:
        return s + "-01"
    return s[:10]


# ---------------------------- 1パス読み込み ----------------------------
pages = {}   # slug -> dict(meta..., eds={ed_idx: {...}})
n_rows = 0
with open(ARGS.flat, encoding="utf-8", newline="") as fp:
    rd = csv.DictReader(fp, delimiter="\t")
    for r in rd:
        n_rows += 1
        if r.get("is_version") == "1":
            continue
        slug = r["slug"]
        p = pages.get(slug)
        if p is None:
            p = pages[slug] = {
                "title": r["title"], "status": r["status"],
                "ys": r["year_started"], "ye": r["year_ended"],
                "pub": r["publisher_key"], "eds": {},
            }
        ei = r["ed_idx"]
        e = p["eds"].get(ei)
        if e is None:
            e = p["eds"][ei] = {"type": r["ed_type"], "label": r["ed_label"],
                                "imprint": r["ed_imprint"], "publisher": r["ed_publisher"],
                                "nums": {}, "years": [], "n": 0}
        e["n"] += 1
        y = yr(r["release_date"])
        if y:
            e["years"].append(y)
        num = r["number"]
        d = iso_low(r["release_date"])
        if num and num.strip() and d:
            try:
                nn = int(float(num))
            except ValueError:
                nn = None
            if nn is not None:
                cur = e["nums"].get(nn)
                if cur is None or d < cur:      # ★per-number 初版min (promote と同じ意味論)
                    e["nums"][nn] = d

print(f"読込: {n_rows:,}行 → 頁 {len(pages):,} (is_version除外)", flush=True)

# ---------------------------- 判定 ----------------------------
rows = []
counts = collections.Counter()
stale_all = 0

for slug, p in pages.items():
    eds = p["eds"]
    if not eds:
        continue
    all_years = [y for e in eds.values() for y in e["years"]]
    n_vols = sum(e["n"] for e in eds.values())
    std = {k: e for k, e in eds.items() if e["type"] == "standard"}
    target = std if std else eds
    # target 全体の per-number 初版min (promote 同様に版をまたいで最小を取る)
    per_num = {}
    for e in target.values():
        for nn, d in e["nums"].items():
            if nn not in per_num or d < per_num[nn]:
                per_num[nn] = d
    exp_ye = None
    latest_first = ""
    if per_num:
        exp_ye = yr(per_num[max(per_num)])
        latest_first = max(per_num.values())
    if not latest_first:
        latest_first = max((iso_low(str(y)) for y in all_years), default="")

    ys = int(p["ys"]) if p["ys"].isdigit() else None
    ye = int(p["ye"]) if p["ye"].isdigit() else None
    st = p["status"]
    edsum = " | ".join(
        f"[{e['type']}]{e['imprint'] or e['label']}/{e['publisher']}"
        f" {min(e['years']) if e['years'] else '?'}-{max(e['years']) if e['years'] else '?'}"
        f" n={e['n']}" for e in eds.values())

    def add(t, sev, detail, ev, sub="", _p=p, _slug=slug, _st=st, _nv=n_vols, _ne=len(eds)):
        counts[(t, sub)] += 1
        rows.append({"type": t, "subtype": sub, "severity": sev, "slug": _slug, "title": _p["title"],
                     "status": _st, "year_started": _p["ys"], "year_ended": _p["ye"],
                     "publisher_key": _p["pub"], "n_vols": _nv, "n_eds": _ne,
                     "detail": detail, "evidence": ev})

    # ---- ① year_started が最古巻より後 ----
    if ys is not None and all_years:
        mn = min(all_years)
        if ys > mn:
            # subtype: promote L2835 の既定値 2000 / 頁生成時の「今年」固着 / それ以外
            sub = ("dummy2000" if ys == 2000
                   else "page_gen_year" if ys >= int(TODAY[:4]) else "seed_stale")
            add("YS_LATE", ys - mn,
                f"year_started={ys} > 最古巻年={mn} ({ys - mn}年後)", edsum, sub)

    # ---- ② year_ended が「最大巻番号の初版年」より前 ----
    if ye is not None and exp_ye is not None and ye < exp_ye:
        mx = max(per_num)
        # ★偽陽性の切り分け(2026-08-29 実地検証で確定した3層):
        #   solo_reprint  = 単巻頁。「種3の連載年 vs 数十年後の復刻1冊」= ほぼ偽陽性。
        #   serial_multied= 版が複数。standard版が**後年の復刻**だと promote の year_ended
        #                   定義(最大巻の初版年)の方が誤りで、種3の連載終了年が正しい
        #                   (影狩り=1972-73連載 / standard=SPコミックス1998-99復刻)。低確度。
        #   serial_1ed    = 版が1つだけ。逃げ場がなく **year_ended が明白に古い**。★高確度。
        #                   (千紘くんは、あたし中毒 = ye 2020 / 単一standard版が2019-11〜2025-03)
        sub = ("solo_reprint" if (mx == 1 and n_vols <= 2)
               else "serial_1ed" if len(eds) == 1 else "serial_multied")
        add("YE_EARLY", exp_ye - ye,
            f"year_ended={ye} < 最大巻#{mx}の初版年={exp_ye} ({exp_ye - ye}年後に新刊)",
            f"#{mx}={per_num[mx]} :: " + edsum, sub)

    # ---- ③ year_ended < year_started ----
    if ye is not None and ys is not None and ye < ys:
        add("YE_LT_YS", ys - ye, f"year_ended={ye} < year_started={ys}", edsum)

    # ---- ④ ongoing なのに year_ended 有り ----
    if st == "ongoing" and ye is not None:
        add("ONGOING_HAS_YE", 1, f"status=ongoing なのに year_ended={ye}", edsum)

    # ---- ⑤ completed なのに未来の初版 ----
    if st == "completed" and latest_first and latest_first > TODAY:
        mxn = max((n for n, d in per_num.items() if d == latest_first), default="")
        # ★偽陽性型: 未来巻が「告知済みの最終巻」なら completed は正しい。
        #   status-corrections に載っていれば裏取り済み=除外候補として印を付ける。
        sub = "has_completion_evidence" if slug in STATUS_CORR else "no_evidence"
        add("COMPLETED_FUTURE", int(latest_first[:4]) - int(TODAY[:4]) + 1,
            f"status=completed なのに未来の初版 #{mxn}={latest_first}", edsum, sub)

    # ---- ⑥ ongoing なのに最終初版が古い(参考: 既存機構と重複) ----
    if st == "ongoing" and latest_first:
        gap = int(TODAY[:4]) - int(latest_first[:4])
        if gap >= 15:
            stale_all += 1
        if gap >= ARGS.stale_years:
            add("ONGOING_STALE", gap, f"status=ongoing だが最終初版={latest_first} ({gap}年前)", edsum)

    # ---- ⑦ publisher_key が版の出版社に解決しない ----
    if p["pub"]:
        cnt = collections.Counter()
        unresolved = []
        for e in eds.values():
            k = pub_key_of(e["publisher"])
            if k:
                cnt[k] += e["n"]
            elif e["publisher"]:
                unresolved.append(e["publisher"])
        if cnt:
            if p["pub"] not in cnt:
                # ★偽陽性/責任分界: 版側の社名が「(発売)」= 発売元リークなら
                #   是正先は版側 (_audit-publisher-vs-isbn.py の領域)。印を付けて分ける。
                _leak = any("発売" in (e["publisher"] or "") for e in eds.values())
                add("PUB_ABSENT", 3,
                    f"publisher_key={p['pub']} が版の出版社集合 {sorted(cnt)} に無い",
                    ("未解決社名=" + "/".join(sorted(set(unresolved))) + " :: " if unresolved else "") + edsum,
                    "hanbaimoto_leak" if _leak else "")
            elif cnt.most_common(1)[0][0] != p["pub"]:
                add("PUB_NOT_MAJORITY", 1,
                    f"publisher_key={p['pub']} だが最多巻は {cnt.most_common(1)[0][0]}"
                    f" ({cnt.most_common(1)[0][1]}巻 vs {cnt[p['pub']]}巻)", edsum)

TYPE_ORDER = {"YE_LT_YS": 0, "ONGOING_HAS_YE": 1, "COMPLETED_FUTURE": 2, "YS_LATE": 3,
              "YE_EARLY": 4, "PUB_ABSENT": 5, "ONGOING_STALE": 6, "PUB_NOT_MAJORITY": 7}
rows.sort(key=lambda r: (TYPE_ORDER.get(r["type"], 9), -r["severity"], r["slug"]))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="") as fp:
    w = csv.DictWriter(fp, delimiter="\t", fieldnames=[
        "type", "subtype", "severity", "slug", "title", "status", "year_started", "year_ended",
        "publisher_key", "n_vols", "n_eds", "detail", "evidence"])
    w.writeheader()
    w.writerows(rows)

flagged_pages = len({r["slug"] for r in rows})
print(f"\nflag: {len(rows):,}件 / {flagged_pages:,}頁 → {OUT}")
print("\n=== 型別 ===")
for (t, sub), c in sorted(counts.items(), key=lambda x: (TYPE_ORDER.get(x[0][0], 9), -x[1])):
    print(f"  {t:18s} {sub or '-':24s} {c:7,}")
print(f"\n(参考) ONGOING_STALE 15年以上 = {stale_all:,}頁 "
      f"※既存機構 completion-judge / _check-ongoing-continuation.py の担当")

print("\n=== 上位40 ===")
for r in rows[:40]:
    print(f"  [{r['type']}:{r['subtype']}/{r['severity']}] {r['slug']} 「{r['title'][:24]}」 {r['detail']}")
