"""著者集合 + 正規化title による series 統合を自動生成 → data/seeds/series-merge-auto.yml

案A の構造解決本体。 詳細: docs/series-fragmentation-analysis.md。

- 種2 sqlite 不変・種3 不変・series_key 不変。 merge_sids lookup を 生成するだけ。
- 既存 hand 版 (data/seeds/series-merge.yml) の merge_sids と **1 sid でも重複する
  group は skip** (= 手動キュレーション優先、 うる星カラー版/SLF 等を上書きしない)。
- semantic subtitle (第/部/編/外伝/番外/章/完結) を含む混在 group は **保留**
  (= 別ページ維持が正当、 .cache/held-groups-classified.txt 参照)。 自動統合しない。

★ 重要: merge_sids は raw series.id を参照するため、 **db-v2 再 build 後は必ず再生成**
すること (= sid が変わる)。 build flow に組込推奨。

出力: data/seeds/series-merge-auto.json (= _promote-bulk-v2.py が hand yaml と両方 load)
  ※ JSON 採用理由: 約1万 group の PyYAML パースは 30-60秒 と遅い。 json.load なら <1秒。
"""
from __future__ import annotations
import json
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
HAND = ROOT / "data" / "seeds" / "series-merge.yml"
OUT = ROOT / "data" / "seeds" / "series-merge-auto.json"

SEMANTIC = ["第", "部", "編", "外伝", "前編", "後編", "番外", "スピンオフ",
            "章", "完結", "SEASON", "season", "Season", "Part", "PART"]

# アンソロジー/汎用題 = 別作品が同題を共有 → 統合しない (over-merge 防止)
ANTHOLOGY = ["アンソロジー", "セレクション", "ベスト集成", "傑作選", "傑作集", "集成",
             "本当にあった", "現代コミック", "日本の歴史", "夢幻アンソロジー", "名作",
             "コミック乱", "総集編", "競作", "オムニバス", "短編集", "選集"]

# 統合 component が持ってよい primary qid 種類の上限 (= 原作/作画/キャラ原案で最大3)
MAX_DISTINCT_QID = 3

# 非人物トークン (= 出版社/プロ/スタジオ/編集部 等)。 著者集合から除外して
# ホーム社混入等で割れた cluster を統合可能にする (= unmerged 調査 2026-05-30)。
NONPERSON = ["社", "プロ", "スタジオ", "編集", "製作", "株式", "works", "Works", "WORKS",
             "出版", "書房", "書店", "コミック", "編集部"]


def clean(s: str) -> str:
    """audit (_audit-volume-gaps._clean) と同一の正規化 = 句読点/空白/横棒除去+lower。"""
    if not s:
        return ""
    out = []
    for ch in s:
        if unicodedata.category(ch)[0] in ("P", "Z") or ch in "ー―~〜":
            continue
        out.append(ch.lower())
    return "".join(out)


def is_semantic_sub(s: str | None) -> bool:
    return bool(s) and any(m in s for m in SEMANTIC)


def load_hand_merge_sids() -> set[int]:
    """既存 hand 版 series-merge.yml の merge_sids 全 sid (= 重複 skip 用)。"""
    if not HAND.exists():
        return set()
    out: set[int] = set()
    with HAND.open(encoding="utf-8") as f:
        for e in (yaml.safe_load(f) or []):
            for sid in (e.get("merge_sids") or []):
                out.add(int(sid))
    return out


def main() -> None:
    con = sqlite3.connect(DB)
    c = con.cursor()
    aname = {mid: nm for mid, nm in c.execute("SELECT id, name FROM mangaka")}

    def is_nonperson(mid: int) -> bool:
        nm = aname.get(mid, "")
        return any(p in nm for p in NONPERSON)

    auth = defaultdict(set)
    for sid, mid in c.execute("SELECT series_id, mangaka_id FROM series_authors"):
        if not is_nonperson(mid):  # 非人物 (出版社/プロ等) を著者集合から除外
            auth[sid].add(mid)
    volc = defaultdict(int)
    for sid, n in c.execute(
        "SELECT e.series_id, COUNT(*) FROM editions e "
        "JOIN volumes v ON v.edition_id=e.id GROUP BY e.series_id"
    ):
        volc[sid] = n
    rows = c.execute("SELECT id, title, subtitle, qid FROM series").fetchall()

    # 正規化 title (= clean) で 一次グループ化。 著者集合を持つ series のみ。
    bytitle: dict[str, list[dict]] = defaultdict(list)
    for sid, t, s, q in rows:
        a = frozenset(auth.get(sid, ()))
        if not a:
            continue  # 著者ゼロ (= 非人物のみ含む series も除外)
        bytitle[clean(t)].append(
            {"sid": sid, "title": t, "sub": s, "qid": q, "vols": volc[sid], "aset": a}
        )

    hand_sids = load_hand_merge_sids()
    print(f"hand merge_sids 既存: {len(hand_sids)} 個 (重複 skip)", file=sys.stderr)

    # 各 title グループ内で union-find: 著者集合が 包含関係 (subset/superset) なら連結。
    #   = 入れ子 (記録ムラ・片側欠け・同一集合) を統合、
    #     disjoint / 部分重複のみ (原作共通-作画別 等) は連結せず別ページ維持。
    def find(p, x):
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    entries = []
    skipped_hand = 0
    held = 0
    n_anthology = 0
    n_qidcap = 0
    for nt, members in bytitle.items():
        if len(members) < 2:
            continue
        # アンソロジー/汎用題 = 別作品同題 → 統合対象外
        if any(p in m["title"] for m in members for p in ANTHOLOGY):
            n_anthology += 1
            continue
        parent = {m["sid"]: m["sid"] for m in members}
        for i in range(len(members)):
            ai = members[i]["aset"]
            for j in range(i + 1, len(members)):
                aj = members[j]["aset"]
                if ai <= aj or aj <= ai:  # 包含関係 (どちらか subset)
                    ra, rb = find(parent, members[i]["sid"]), find(parent, members[j]["sid"])
                    if ra != rb:
                        parent[ra] = rb
        comps: dict[int, list[dict]] = defaultdict(list)
        for m in members:
            comps[find(parent, m["sid"])].append(m)
        for comp in comps.values():
            sids = {m["sid"] for m in comp}
            if len(sids) < 2:
                continue
            # ★ 共通著者ガード: component 全員が共有する著者が居ないと統合しない
            #   (= subset の連鎖で A⊆B,C⊆B 間接連結された「日本の歴史」等の汎用題
            #    over-merge を排除。 入れ子は最小集合が共通なので非空で通る)
            common = set.intersection(*[set(m["aset"]) for m in comp])
            if not common:
                held += 1
                continue
            # primary qid 種類が多すぎ = アンソロジー的 over-merge → 弾く
            distinct_qids = {m["qid"] for m in comp if m["qid"]}
            if len(distinct_qids) > MAX_DISTINCT_QID:
                n_qidcap += 1
                continue
            # semantic subtitle 混在 = 保留 (別ページ維持)
            nonsem = {m["sid"] for m in comp if not is_semantic_sub(m["sub"])}
            if any(is_semantic_sub(m["sub"]) for m in comp) and len(nonsem) < len(sids):
                held += 1
                continue
            # hand 版と重複 = skip (手動優先)
            if sids & hand_sids:
                skipped_hand += 1
                continue
            comp.sort(key=lambda m: -m["vols"])
            entries.append({
                "main": comp[0]["title"],
                "merge_sids": sorted(sids),
                "note": "auto: subset-author-set + clean-title (_gen-author-set-merges.py)",
            })

    entries.sort(key=lambda e: e["merge_sids"][0])

    doc = {
        "_README": (
            "自動生成 — 手で編集しない。生成元: scripts/_gen-author-set-merges.py / "
            "詳細: docs/series-fragmentation-analysis.md。種2 sqlite 不変・種3 不変・"
            "series_key 不変。手動版 data/seeds/series-merge.yml と重複する group は skip 済"
            "(= 手動優先)。★ db-v2 再 build 後は sid が変わるため必ず再生成すること。"
        ),
        "merges": entries,
    }
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)

    print(f"=== series-merge-auto.json 生成 ===", file=sys.stderr)
    print(f"  auto 統合 group     : {len(entries):,}", file=sys.stderr)
    print(f"  hand 重複 skip      : {skipped_hand}", file=sys.stderr)
    print(f"  semantic/共通著者なし保留: {held}", file=sys.stderr)
    print(f"  アンソロジー題 除外 : {n_anthology}", file=sys.stderr)
    print(f"  qid種類過多 除外    : {n_qidcap}", file=sys.stderr)
    print(f"  統合される series   : {sum(len(e['merge_sids']) for e in entries):,}", file=sys.stderr)
    print(f"  wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
