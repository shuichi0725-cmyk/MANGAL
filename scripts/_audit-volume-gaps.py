"""種2 sqlite を 走査して、 連続する 巻番号 に 抜けが出るシリーズ を 一覧化。

★ v2: cluster key を 改良 = 真の MADB 巻抜け を 抽出。

集計 key:
  (cluster_key, edition.type)
where cluster_key =
  - qid があれば 'qid:<qid>'  (default = 作家 qid 統合)
  - --by-title flag = 'qid:<qid>|t:<norm_title>' (= 作家 qid 内で作品別分割、
    高橋留美子の RINNE / MAO 等の 真の抜け 露出に有効、 ただし cluster 数倍増)
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
import pickle
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

DB = Path(".cache/db-v2.sqlite")
MERGE_YML = Path("data/seeds/series-merge.yml")
AUTO_MERGE_JSON = Path("data/seeds/series-merge-auto.json")  # 案A 著者集合 merge (= _promote と同じ)
SEED3_YML = Path("data/seeds/series-supplement-v2.yml")
SEED3_CACHE = Path(".cache/seed3-keys.pkl")
SUPP_YML = Path("data/seeds/volumes-supplement.yml")
SUPP_AUTO_YML = Path("data/seeds/volumes-supplement-auto.yml")  # NDL自動登録分 (種4 auto)
OUT_CSV = Path(".cache/volume-gaps.csv")
OUT_TOP = Path(".cache/volume-gaps-top.txt")
TOP_N = 100
MIN_MAX = 3
MAX_MAX = 300

# --- filter constants (= _promote-bulk-v2.py から コピー、 CLAUDE.md L195- 準拠) ---
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
DROP_IMPRINT_PATTERNS = [
    "My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "フィルムコミック",
    "カッパ・ノベル", "カッパノベル", "カッパ・ホーム", "カッパホーム",
]
DROP_IMPRINT_LOWER_PATTERNS = ["bilingual", "english", "novel", "novels"]
DROP_IMPRINT_LOWER_PATTERNS_NO_EQ = ["complete works"]
DROP_TITLE_PREFIX_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル",
    "英訳・", "英訳",
]
DROP_TITLE_CONTAINS_PATTERNS = [
    "ガイドブック", "ファンブック", "設定資料集",
    "公式図録", "公式読本", "公式ファン", "公式コミックガイド",
    "アンソロジー",
    "キャラクター名鑑", "人物名鑑", "キャラクターブック",
    "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本",
    "解析書", "解体新書", "解体全書",
    "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖",
    "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法",
    "の秘密", "の謎", "コミック大全", "コミックスペシャル",
    "ナビゲーション", "考察",
    # 抜粋本 / 編集本 (= 本編ではない):
    "傑作選", "傑作集", "ベストセレクション", "特集号", "特別総集編",
    # 画集 / 関連書 (= 漫画でない):
    "原画集", "画集", "ポケット画廊", "うちあけ話",
]


def edition_passes(edition_type: str | None, imprint: str | None) -> bool:
    if (edition_type or "") not in KEEP_EDITION_TYPES:
        return False
    imp = imprint or ""
    imp_l = imp.lower()
    for pat in DROP_IMPRINT_PATTERNS:
        if pat in imp:
            return False
    for pat in DROP_IMPRINT_LOWER_PATTERNS:
        if pat in imp_l:
            return False
    if "=" not in imp:
        for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ:
            if pat in imp_l:
                return False
    return True


def title_passes(title: str | None) -> bool:
    if not title:
        return True
    t = title.strip()
    for pat in DROP_TITLE_PREFIX_PATTERNS:
        if t.startswith(pat):
            return False
    for pat in DROP_TITLE_CONTAINS_PATTERNS:
        if pat in t:
            return False
    return True


def load_seed3_keys() -> tuple[set, set]:
    """種3 yml から (series_keys, qids) set を 返す。 pickle cache 利用。"""
    if SEED3_CACHE.exists() and SEED3_YML.exists():
        if SEED3_CACHE.stat().st_mtime >= SEED3_YML.stat().st_mtime:
            with SEED3_CACHE.open("rb") as f:
                return pickle.load(f)
    if not SEED3_YML.exists() or yaml is None:
        return set(), set()
    with SEED3_YML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    keys = {e["key"] for e in data.get("series", [])}
    qids = set()
    for e in data.get("series", []):
        if e["key"].startswith("qid:"):
            qids.add(e["key"].split("|", 1)[0][4:])
    SEED3_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with SEED3_CACHE.open("wb") as f:
        pickle.dump((keys, qids), f)
    return keys, qids


# command-line options
NO_FILTER = "--no-filter" in sys.argv  # filter skip = 既存挙動 (= 全件)
NO_SEED3 = "--include-non-seed3" in sys.argv  # 種3 紐付き外 も含める
BY_TITLE = "--by-title" in sys.argv  # cluster_key を qid+title norm で 分割 (= 作家 qid 統合解除)
NO_HIER_DROP = "--no-hier-drop" in sys.argv  # 階層的派生本排除 を off (= 既存挙動)

# 階層的排除 = keep override patterns (= 派生候補のうち title+sub に hit したら keep)
DERIVATIVE_DROP_MAX_VOL = 2  # vol <= 2 + 同 qid 主軸あり + title prefix一致 = 派生本 drop
KEEP_OVERRIDE_PATTERNS = [
    "フルカラー", "総カラー", "オールカラー", "カラー版", "カラーエディション",
    "大全集", "復刻版", "復刊",
]


def compute_derivative_drop_sids(con) -> set[int]:
    """同 qid 内で 主軸 (= title prefix 親) を持つ sid のうち、
    vol <= DERIVATIVE_DROP_MAX_VOL (= 2) の sid を 派生候補 drop。
    ただし title+subtitle に KEEP_OVERRIDE_PATTERNS 含む sid は 除外 (= keep)。"""
    if NO_HIER_DROP:
        return set()
    from collections import defaultdict
    rows = con.execute("""
        SELECT s.id, s.qid, s.title, s.subtitle,
               COUNT(DISTINCT v.id) AS vc
        FROM series s
        LEFT JOIN editions e ON e.series_id=s.id
        LEFT JOIN volumes v ON v.edition_id=e.id AND v.is_extra=0
        WHERE s.qid IS NOT NULL
        GROUP BY s.id
    """).fetchall()
    by_qid: dict = defaultdict(list)
    for r in rows:
        by_qid[r["qid"]].append((r["id"], r["title"] or "", r["subtitle"] or "", r["vc"]))
    drop_sids: set[int] = set()
    for qid, sids in by_qid.items():
        if len(sids) < 2: continue
        main_sid, main_title, _, main_vc = max(sids, key=lambda x: x[3])
        if main_vc < 5: continue  # メイン本人 5 vol 未満 = 主軸不確定
        for sid, t, sub, vc in sids:
            if sid == main_sid: continue
            if not t.startswith(main_title): continue
            # vol 絶対値判定 (= 比率ではない、 「上下/数巻完結」 派生本検出)
            if vc > DERIVATIVE_DROP_MAX_VOL: continue
            # 派生候補 = keep override check
            combined = t + sub
            if any(p in combined for p in KEEP_OVERRIDE_PATTERNS):
                continue  # keep override で救済
            drop_sids.add(sid)
    return drop_sids

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

    # ---- series-merge.yml 読込 (= 改題 chain 統合 + sid 直接マージ + edition 統合) ----
    alias_to_main: dict[str, str] = {}
    sid_to_forced_cluster: dict[int, str] = {}  # sid → forced cluster_key (= merge_sids 由来)
    cluster_merge_editions: set[str] = set()    # cluster_key (forced) で edition.type 区別 無効

    # ★STEP6: merge_keys (= series_key、 sid非依存) を 現 sid に解決。 legacy merge_sids も対応。
    _key_to_sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}

    def _forced_sids(entry):
        out = [_key_to_sid[k] for k in (entry.get("merge_keys") or []) if k in _key_to_sid]
        out += [int(s) for s in (entry.get("merge_sids") or [])]
        return out

    # ---- auto merge (= 案A 著者集合 merge、 JSON) を先に load → hand で上書き (= 手動優先) ----
    n_auto = 0
    if AUTO_MERGE_JSON.exists():
        import json as _json
        with AUTO_MERGE_JSON.open("r", encoding="utf-8") as f:
            for entry in (_json.load(f).get("merges") or []):
                forced_sids = _forced_sids(entry)
                if not forced_sids:
                    continue
                forced_ckey = f"merge:{entry.get('main')}"
                for sid in forced_sids:
                    sid_to_forced_cluster[sid] = forced_ckey
                n_auto += 1

    if MERGE_YML.exists() and yaml is not None:
        with MERGE_YML.open("r", encoding="utf-8") as f:
            merge_data = yaml.safe_load(f) or []
        for entry in merge_data:
            main = entry.get("main")
            for alias in entry.get("aliases", []) or []:
                alias_to_main[alias] = main
            # merge_keys/merge_sids = 個別判断 直接マージ。 hand が auto を上書き。
            forced_sids = _forced_sids(entry)
            if forced_sids:
                forced_ckey = f"merge:{main}"
                for sid in forced_sids:
                    sid_to_forced_cluster[sid] = forced_ckey
                if entry.get("merge_edition_types"):
                    cluster_merge_editions.add(forced_ckey)
        print(f"[info] series-merge loaded: {len(alias_to_main)} aliases, "
              f"{len(sid_to_forced_cluster)} forced sids ({n_auto} auto groups + hand), "
              f"{len(cluster_merge_editions)} edition-merged clusters")

    # ---- 種3 yml load (= 紐付き scope filter) ----
    seed3_sids: set[int] = set()
    if not NO_SEED3:
        seed3_keys, seed3_qids = load_seed3_keys()
        if seed3_keys or seed3_qids:
            print(f"[info] seed3 loaded: {len(seed3_keys):,} keys + {len(seed3_qids):,} qids")
        else:
            print(f"[warn] seed3 not available; --include-non-seed3 effectively on")

    # ---- 階層的派生本排除 = drop_sids set 構築 ----
    derivative_drop_sids = compute_derivative_drop_sids(con)
    if derivative_drop_sids:
        print(f"[info] hierarchical drop: {len(derivative_drop_sids)} sid 派生本判定")

    # ---- series 全件 (= cluster key 解決用) ----
    series_rows = con.execute(
        "SELECT id, qid, series_key, title, subtitle FROM series"
    ).fetchall()

    # 種3 紐付き sid set 構築
    if not NO_SEED3 and (seed3_keys or seed3_qids):
        for r in series_rows:
            if r["series_key"] in seed3_keys:
                seed3_sids.add(r["id"])
            elif r["qid"] and r["qid"] in seed3_qids:
                seed3_sids.add(r["id"])
        print(f"[info] 種3 紐付き 種2 sid: {len(seed3_sids):,}")

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
        # ★ forced merge_sids が 最優先 (= 個別判断、 表記揺れ救済等)
        if r["id"] in sid_to_forced_cluster:
            ckey = sid_to_forced_cluster[r["id"]]
            display_title = ckey.split(":", 1)[1]
            series_cluster[r["id"]] = (ckey, display_title)
            continue
        # alias なら main title に置換 (= 改題 chain 統合)
        effective_title = alias_to_main.get(r["title"], r["title"])
        # cluster key 決定
        if r["qid"]:
            if BY_TITLE:
                # --by-title = 作家 qid 統合解除、 作品 title で 分割
                ckey = f"qid:{r['qid']}|t:{norm_title(effective_title, r['subtitle'])}"
            else:
                ckey = f"qid:{r['qid']}"
        elif effective_title in main_to_qid:
            # 親 main title の 子側 qid に 引き寄せ
            if BY_TITLE:
                ckey = f"qid:{main_to_qid[effective_title]}|t:{norm_title(effective_title, r['subtitle'])}"
            else:
                ckey = f"qid:{main_to_qid[effective_title]}"
        else:
            norm = norm_title(effective_title, r["subtitle"])
            if norm in title_to_qid:
                if BY_TITLE:
                    ckey = f"qid:{title_to_qid[norm]}|t:{norm}"
                else:
                    ckey = f"qid:{title_to_qid[norm]}"
            else:
                ckey = f"title:{norm}"
        # 表示用 title = 親 main を 優先
        display_title = effective_title or r["title"] or ""
        series_cluster[r["id"]] = (ckey, display_title)

    # ---- volume + edition 取得 (= imprint も filter 判定用に取得) ----
    rows = con.execute(
        """
        SELECT
          s.id              AS series_id,
          s.title           AS series_title,
          s.title_official_en AS title_en,
          e.id              AS edition_id,
          e.type            AS edition_type,
          e.imprint         AS edition_imprint,
          v.number          AS vol_number,
          v.is_extra        AS is_extra
        FROM volumes v
        JOIN editions e ON e.id = v.edition_id
        JOIN series s   ON s.id = e.series_id
        """
    ).fetchall()

    # filter 適用前後 の カウント
    n_total = len(rows)
    n_drop_extra = 0
    n_drop_seed3 = 0
    n_drop_title = 0
    n_drop_edition = 0
    n_drop_num = 0
    n_drop_hier = 0
    n_kept = 0

    # cluster 単位で 集計
    # key = (cluster_key, edition_type)
    buckets: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r["is_extra"]:
            n_drop_extra += 1
            continue
        # 種3 紐付き filter
        # ただし forced merge_sids (= 個別判断 cluster) に含まれる sid は cluster 単位で
        # 1 sid でも 種3 OK なら cluster 全 sid 採用 (= 表記揺れ救済の 安全範囲限定版)
        if not NO_SEED3 and (seed3_keys or seed3_qids):
            sid = r["series_id"]
            if sid not in seed3_sids:
                forced_ckey = sid_to_forced_cluster.get(sid)
                if forced_ckey:
                    # 同 forced cluster 内に seed3 OK sid が 1+ あるか check
                    cluster_has_seed3 = any(
                        other_sid in seed3_sids
                        for other_sid, ck in sid_to_forced_cluster.items()
                        if ck == forced_ckey
                    )
                    if not cluster_has_seed3:
                        n_drop_seed3 += 1
                        continue
                    # else: cluster 救済で keep
                else:
                    n_drop_seed3 += 1
                    continue
        # promote filter (= CLAUDE.md L195- 準拠)
        if not NO_FILTER:
            if not title_passes(r["series_title"]):
                n_drop_title += 1
                continue
            if not edition_passes(r["edition_type"], r["edition_imprint"]):
                n_drop_edition += 1
                continue
        # 階層的派生本排除 (= 同 qid 内 主軸 1% 未満 + override hit なし)
        if r["series_id"] in derivative_drop_sids:
            n_drop_hier += 1
            continue
        n = to_int(r["vol_number"])
        if n is None or n <= 0:
            n_drop_num += 1
            continue
        n_kept += 1
        ckey, ctitle = series_cluster.get(r["series_id"], (f"id:{r['series_id']}", r["series_title"] or ""))
        edt = r["edition_type"] or "standard"
        # cluster_merge_editions に登録された cluster は edition.type 統合 (= 集計 key で 区別なし)
        if ckey in cluster_merge_editions:
            edt = "*"
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

    # ---- 種4 = volumes-supplement.yml load + 補完 ----
    n_supp_applied = 0
    n_supp_unmatched = 0
    supp_records = []
    if yaml is not None:
        for _p in (SUPP_YML, SUPP_AUTO_YML):
            if _p.exists():
                with _p.open("r", encoding="utf-8") as f:
                    supp_records += (yaml.safe_load(f) or {}).get("volumes", []) or []
    if supp_records:
        # series_key → sid mapping
        sk_to_sids: dict[str, list[int]] = {}
        for sr in series_rows:
            sk_to_sids.setdefault(sr["series_key"], []).append(sr["id"])
        qid_to_sids: dict[str, list[int]] = {}
        for sr in series_rows:
            if sr["qid"]:
                qid_to_sids.setdefault(sr["qid"], []).append(sr["id"])
        for entry in supp_records:
            number = entry.get("number")
            if number is None:
                continue
            try:
                n_int = int(number)
            except (ValueError, TypeError):
                continue
            if n_int <= 0:
                continue
            edt = entry.get("edition_type") or "standard"
            sks = entry.get("series_keys") or []
            entry_qid = entry.get("qid")
            matched_sids: set[int] = set()
            for sk in sks:
                matched_sids.update(sk_to_sids.get(sk, []))
            if entry_qid and entry_qid in qid_to_sids:
                matched_sids.update(qid_to_sids[entry_qid])
            if not matched_sids:
                n_supp_unmatched += 1
                print(f"[warn] supplement entry not matched (no sid): "
                      f"keys={sks}, qid={entry_qid}, number={n_int}")
                continue
            # 各 sid の cluster_key を 取り、 該当 bucket に number 追加
            added_to = set()
            for sid in matched_sids:
                ckey_ctitle = series_cluster.get(sid)
                if not ckey_ctitle:
                    continue
                ckey, ctitle = ckey_ctitle
                effective_edt = "*" if ckey in cluster_merge_editions else edt
                key = (ckey, effective_edt)
                if key in added_to:
                    continue
                added_to.add(key)
                b = buckets.setdefault(
                    key,
                    {
                        "cluster_key": ckey,
                        "edition_type": effective_edt,
                        "series_title": ctitle,
                        "title_en": "",
                        "series_ids": set(),
                        "numbers": set(),
                    },
                )
                b["numbers"].add(n_int)
            n_supp_applied += 1
        if n_supp_applied or n_supp_unmatched:
            print(f"[info] volumes-supplement applied: {n_supp_applied} entries "
                  f"(unmatched: {n_supp_unmatched})")

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
    # filter 効果 summary を 先頭に挿入
    filter_summary = [
        "",
        "--- filter 効果 (= 全 volumes 件数 内訳) ---",
        f"全 volume record         : {n_total:,}",
        f"  ✗ is_extra=1 除外       : {n_drop_extra:,}",
        f"  ✗ 種3 紐付き外 除外     : {n_drop_seed3:,}" + (" (= --include-non-seed3 で off)" if NO_SEED3 else ""),
        f"  ✗ title filter 除外     : {n_drop_title:,}" + (" (= --no-filter で off)" if NO_FILTER else ""),
        f"  ✗ edition filter 除外   : {n_drop_edition:,}" + (" (= --no-filter で off)" if NO_FILTER else ""),
        f"  ✗ 階層的派生本 除外     : {n_drop_hier:,}" + (" (= --no-hier-drop で off)" if NO_HIER_DROP else ""),
        f"  ✗ number 不正 除外      : {n_drop_num:,}",
        f"  ✓ 集計対象              : {n_kept:,}",
        "",
    ]
    OUT_TOP.write_text("\n".join(lines[:4] + filter_summary + lines[4:]) + "\n", encoding="utf-8")
    print(f"target clusters: {len(buckets):,}  gap-containing: {len(results):,}")
    print(f"volume records: total={n_total:,}, kept={n_kept:,}, "
          f"dropped: extra={n_drop_extra:,}, seed3={n_drop_seed3:,}, "
          f"title={n_drop_title:,}, edition={n_drop_edition:,}, num={n_drop_num:,}")
    print(f"csv: {OUT_CSV}")
    print(f"top: {OUT_TOP}")


if __name__ == "__main__":
    main()
