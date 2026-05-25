"""種2 sqlite を 走査して、 連続する 巻番号 に 抜けが出るシリーズ を 一覧化。

★ v2: cluster key を 改良 = 真の MADB 巻抜け を 抽出。

集計 key:
  (cluster_key, edition.type)
where cluster_key =
  - qid があれば 'qid:<qid>'
  - qid なくても title が qid 持ち series と完全一致 → qid 側に 引き寄せ
  - それ以外は 'title:<正規化 title>'

これにより:
  - 同じ qid で 複数 imprint に 分裂した edition を 統合
  - qid 紐付け失敗で 別 series_id に 流出した 巻も 同 cluster に統合
  - edition.type は 区別 (= standard / bunkobon / shinsoban は 別系列)

判定:
  - integer 化できる number のみ対象
  - is_extra=1 除外、 number<=0 除外
  - max が 3〜300 巻の cluster のみ (= 1-2 巻完結 と data noise 除外)
  - 1 〜 max(N) のうち 欠番を抽出

出力: top txt + 全件 csv。
"""
from __future__ import annotations
import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

DB = Path(".cache/db-v2.sqlite")
MERGE_YML = Path("data/seeds/series-merge.yml")
OUT_CSV = Path(".cache/volume-gaps.csv")
OUT_TOP = Path(".cache/volume-gaps-top.txt")
TOP_N = 100
MIN_MAX = 3
MAX_MAX = 300

NUM_RE = re.compile(r"^\s*(\d+)\s*$")


def to_int(s) -> int | None:
    if s is None:
        return None
    m = NUM_RE.match(str(s))
    return int(m.group(1)) if m else None


def _clean(s: str | None) -> str:
    """Unicode カテゴリ P* (= 句読点) / Z* (= separator) + 横棒類 を 全除去 + lowercase。

    対象例: 半角/全角の空白、 ・、 、 。 ! ? ' " . , : ; / 〜 ~ ー ― 「」 『』 等。
    これで MADB の 表記揺れ (= 末尾 .、 中黒 ありなし、 全角句読点 等) を 吸収。
    """
    if not s:
        return ""
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "Z"):
            continue
        if ch in "ー―~〜":
            continue
        out.append(ch.lower())
    return "".join(out)


def norm_title(t: str | None, sub: str | None) -> str:
    """title + subtitle 正規化。 | で 境界保持 = subtitle 違いは別 cluster のまま。"""
    return _clean(t) + "|" + _clean(sub)


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"missing: {DB}")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # ---- series-merge.yml 読込 (= 改題 chain 統合) ----
    alias_to_main: dict[str, str] = {}
    if MERGE_YML.exists() and yaml is not None:
        with MERGE_YML.open("r", encoding="utf-8") as f:
            merge_data = yaml.safe_load(f) or []
        for entry in merge_data:
            main = entry.get("main")
            for alias in entry.get("aliases", []) or []:
                alias_to_main[alias] = main
        print(f"[info] series-merge.yml loaded: {len(alias_to_main)} aliases → main")

    # ---- series 全件 (= cluster key 解決用) ----
    series_rows = con.execute(
        "SELECT id, qid, title, subtitle FROM series"
    ).fetchall()

    # title norm → qid mapping (= qid 持ち series のみ)
    title_to_qid: dict[str, str] = {}
    for r in series_rows:
        if r["qid"]:
            # alias なら main に置換した title で 登録
            t = alias_to_main.get(r["title"], r["title"])
            key = norm_title(t, r["subtitle"])
            title_to_qid.setdefault(key, r["qid"])

    # 改題 main → qid mapping (= 親 main title が qid なくても 子側 qid を 親に引き寄せ)
    main_to_qid: dict[str, str] = {}
    for r in series_rows:
        if r["qid"] and r["title"] in alias_to_main:
            main_t = alias_to_main[r["title"]]
            main_to_qid.setdefault(main_t, r["qid"])

    # series_id → cluster_key (+ 表示 title)
    series_cluster: dict[int, tuple[str, str]] = {}
    for r in series_rows:
        # alias なら main title に置換 (= 改題 chain 統合)
        effective_title = alias_to_main.get(r["title"], r["title"])
        # cluster key 決定
        if r["qid"]:
            ckey = f"qid:{r['qid']}"
        elif effective_title in main_to_qid:
            # 親 main title の 子側 qid に 引き寄せ
            ckey = f"qid:{main_to_qid[effective_title]}"
        else:
            norm = norm_title(effective_title, r["subtitle"])
            if norm in title_to_qid:
                ckey = f"qid:{title_to_qid[norm]}"
            else:
                ckey = f"title:{norm}"
        # 表示用 title = 親 main を 優先
        display_title = effective_title or r["title"] or ""
        series_cluster[r["id"]] = (ckey, display_title)

    # ---- volume + edition 取得 ----
    rows = con.execute(
        """
        SELECT
          s.id              AS series_id,
          s.title           AS series_title,
          s.title_official_en AS title_en,
          e.id              AS edition_id,
          e.type            AS edition_type,
          v.number          AS vol_number,
          v.is_extra        AS is_extra
        FROM volumes v
        JOIN editions e ON e.id = v.edition_id
        JOIN series s   ON s.id = e.series_id
        """
    ).fetchall()

    # cluster 単位で 集計
    # key = (cluster_key, edition_type)
    buckets: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r["is_extra"]:
            continue
        n = to_int(r["vol_number"])
        if n is None or n <= 0:
            continue
        ckey, ctitle = series_cluster.get(r["series_id"], (f"id:{r['series_id']}", r["series_title"] or ""))
        edt = r["edition_type"] or "standard"
        key = (ckey, edt)
        b = buckets.setdefault(
            key,
            {
                "cluster_key": ckey,
                "edition_type": edt,
                "series_title": ctitle,
                "title_en": r["title_en"] or "",
                "series_ids": set(),
                "numbers": set(),
            },
        )
        b["series_ids"].add(r["series_id"])
        b["numbers"].add(n)
        # title 上書き (= qid:Q...の正規 title 優先したい場合は別 logic 必要だが
        # 通常 cluster 内では 主 series の title が 多数派なので問題なし)

    results = []
    for b in buckets.values():
        nums = b["numbers"]
        mx = max(nums)
        if mx < MIN_MAX or mx > MAX_MAX:
            continue
        expected = set(range(1, mx + 1))
        missing = sorted(expected - nums)
        if not missing:
            continue
        results.append(
            {
                "cluster_key": b["cluster_key"],
                "series_title": b["series_title"],
                "title_en": b["title_en"],
                "edition_type": b["edition_type"],
                "series_id_count": len(b["series_ids"]),
                "max_vol": mx,
                "present": len(nums),
                "gap_count": len(missing),
                "missing": ",".join(str(x) for x in missing),
            }
        )

    results.sort(key=lambda x: (-x["gap_count"], -x["max_vol"]))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "cluster_key",
                "series_title",
                "title_en",
                "edition_type",
                "series_id_count",
                "max_vol",
                "present",
                "gap_count",
                "missing",
            ],
        )
        w.writeheader()
        w.writerows(results)

    lines = []
    lines.append("=== 巻番号 gap 精査 v2 (= cluster 統合版) ===")
    lines.append(f"対象 cluster (= max>={MIN_MAX} かつ max<={MAX_MAX}): {len(buckets):,}")
    lines.append(f"gap あり: {len(results):,}")
    lines.append(f"csv: {OUT_CSV}")
    lines.append("")
    lines.append(f"--- top {TOP_N} (= gap 数多い順) ---")
    lines.append(f"{'gap':>4} {'max':>4} {'pres':>4} {'sid':>3}  {'edition':<10}  title  (missing)")
    lines.append("-" * 115)
    for r in results[:TOP_N]:
        title = r["series_title"]
        miss = r["missing"]
        if len(miss) > 70:
            miss = miss[:70] + "..."
        lines.append(
            f"{r['gap_count']:>4} {r['max_vol']:>4} {r['present']:>4} {r['series_id_count']:>3}  "
            f"{r['edition_type']:<10}  {title}  ({miss})"
        )
    OUT_TOP.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"target clusters: {len(buckets):,}  gap-containing: {len(results):,}")
    print(f"csv: {OUT_CSV}")
    print(f"top: {OUT_TOP}")


if __name__ == "__main__":
    main()
