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


import re
# 括弧内 (= subtitle/別名) を除去: 〜…〜 / (…) / （…） / […] / 【…】
_PAREN = re.compile(r"〜[^〜]*〜|～[^～]*～|\([^)]*\)|（[^）]*）|\[[^\]]*\]|【[^】]*】")


def clean(s: str) -> str:
    """正規化 = 括弧内除去 + 句読点/空白/横棒/記号(S)除去 + lower。
    記号 S 追加で ❤☆× 等の表記揺れ(たとえばラヴ❤ソング↔ラヴ・ソング、 ハンター×ハンター)を吸収。"""
    if not s:
        return ""
    s = _PAREN.sub("", s)
    out = []
    for ch in s:
        if unicodedata.category(ch)[0] in ("P", "Z", "S") or ch in "ー―~〜":
            continue
        out.append(ch.lower())
    return "".join(out)


def _hira2kata(s: str) -> str:
    return "".join(chr(ord(ch) + 0x60) if "ぁ" <= ch <= "ゖ" else ch for ch in s)


def kana_norm(s: str) -> str:
    """title_kana 正規化 = ひらがな→カタカナ + カナ/漢字/英数のみ残す + upper。
    ローマ字題↔カナ題(グラゼニ↔Gurazeni の kana=グラゼニ)の橋渡し用。"""
    if not s:
        return ""
    return re.sub(r"[^ァ-ヶ一-龯0-9A-Za-z]", "", _hira2kata(s)).upper()


def is_semantic_sub(s: str | None) -> bool:
    return bool(s) and any(m in s for m in SEMANTIC)


# title 内の 続編/外伝マーカー (= kana統合が base読み一致で続編を誤統合するのを防ぐ)。
_SEQ = re.compile(
    r"ACT\s*([0-9]+)|異聞|外伝|第\s*([0-9一二三四五六七八九十]+)\s*[部編章]|続編?|シーズン\s*([0-9]+)?|season\s*([0-9]+)?|[ⅡⅢⅣⅤ]|([0-9]+)(?:st|nd|rd|th)",
    re.I)


def seq_marker(t: str) -> str:
    """title から 続編/外伝シグネチャを抽出 (無ければ '')。 component 内で食い違えば別作品。
    finditer で 全マッチ文字列を採る (= 非グループ alt 異聞/Ⅱ も拾う)。"""
    if not t:
        return ""
    return "|".join(sorted(m.group(0).lower().replace(" ", "") for m in _SEQ.finditer(t)))


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


def norm_author_name(nm: str) -> str:
    """著者名正規化 = NFKC(全半角統一)+ P/Z/S・記号除去 + lower。
    マスター重複(PEACH‐PIT 全角‐ ↔ Peach-Pit 半角-)を同一視。 ※修正1(2026-05-31)。"""
    if not nm:
        return ""
    nm = unicodedata.normalize("NFKC", nm)
    out = [ch.lower() for ch in nm
           if unicodedata.category(ch)[0] not in ("P", "Z", "S") and ch not in "ー―~〜・"]
    return "".join(out)


def main() -> None:
    con = sqlite3.connect(DB)
    c = con.cursor()
    aname = {mid: nm for mid, nm in c.execute("SELECT id, name FROM mangaka")}
    # ★修正1: 著者名正規化で漫画家マスター重複を同一視。 mid → canonical author token。
    #   ★既定 OFF(opt-in --normalize)。 naive正規化は原作者名寄せで別翻案を
    #   over-merge する(椿姫/ああ無情/十五少年漂流記=検証で確認 2026-05-31)。
    #   有効化には別途ガード(common-primary 等)が必要。
    USE_NORM = "--normalize" in sys.argv
    acanon = {mid: (norm_author_name(nm) or f"id{mid}") for mid, nm in aname.items()}
    def atok(mid):
        return acanon[mid] if USE_NORM else mid
    # ★STEP6: sid→series_key (= 安定キー、 sid非依存)。 merge は series_key で持つ。
    sid_key = {sid: sk for sid, sk in c.execute("SELECT id, series_key FROM series")}

    def is_nonperson(mid: int) -> bool:
        nm = aname.get(mid, "")
        return any(p in nm for p in NONPERSON)

    auth = defaultdict(set)
    primary = defaultdict(set)  # sid → 作画/単独 (artist/writer_artist) の mangaka_id
    for sid, mid, role in c.execute("SELECT series_id, mangaka_id, role FROM series_authors"):
        if is_nonperson(mid):  # 非人物 (出版社/プロ等) は除外
            continue
        auth[sid].add(atok(mid))
        if role in ("artist", "writer_artist"):
            primary[sid].add(atok(mid))
    volc = defaultdict(int)
    for sid, n in c.execute(
        "SELECT e.series_id, COUNT(*) FROM editions e "
        "JOIN volumes v ON v.edition_id=e.id GROUP BY e.series_id"
    ):
        volc[sid] = n
    rows = c.execute("SELECT id, title, subtitle, qid, title_kana FROM series ORDER BY id").fetchall()

    # 各 series → 正規化キー集合 (clean title + kana)。 著者集合を持つ series のみ。
    # kana 軸でローマ字↔カナ題(グラゼニ↔Gurazeni)を橋渡し。
    KEYPOOL_CAP = 40  # キーpool が大きすぎ(汎用題/汎用kana) は連結対象外 (over-merge/O(n^2)回避)
    smeta: dict[int, dict] = {}
    key_sids: dict[str, list[int]] = defaultdict(list)
    for sid, t, s, q, tk in rows:
        a = frozenset(auth.get(sid, ()))
        if not a:
            continue  # 著者ゼロ (= 非人物のみ含む series も除外)
        keys = {"t:" + clean(t)}
        kk = kana_norm(tk)
        if kk:
            keys.add("k:" + kk)
        smeta[sid] = {"sid": sid, "title": t, "sub": s, "qid": q, "vols": volc[sid],
                      "aset": a, "primary": frozenset(primary.get(sid, ())), "keys": keys}
        for k in keys:
            key_sids[k].append(sid)

    hand_sids = load_hand_merge_sids()
    print(f"hand merge_sids 既存: {len(hand_sids)} 個 (重複 skip)", file=sys.stderr)

    # global union-find: 同一キー(title or kana)を共有 かつ 著者集合が包含関係 の sid を連結。
    #   = 入れ子(記録ムラ・片欠け)+ 表記揺れ(kana/記号/括弧)を統合、 disjoint は別ページ維持。
    parent = {sid: sid for sid in smeta}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for k, sids in key_sids.items():
        if len(sids) < 2 or len(sids) > KEYPOOL_CAP:
            continue
        for i in range(len(sids)):
            ai = smeta[sids[i]]["aset"]
            pi = smeta[sids[i]]["primary"]
            for j in range(i + 1, len(sids)):
                aj = smeta[sids[j]]["aset"]
                # 連結条件:
                #   (1) 包含関係 (= 記録ムラ・片欠け)、 or
                #   (2) ★作画/単独著者(primary)を共有 (= 部分重複でも同一作品。
                #       「原作のみ共通」= 別作画の別adaptation は primary 非共有で弾く: 小公女/椿姫/IS)
                if ai <= aj or aj <= ai or (pi & smeta[sids[j]]["primary"]):
                    ra, rb = find(sids[i]), find(sids[j])
                    if ra != rb:
                        parent[ra] = rb

    comps: dict[int, list[dict]] = defaultdict(list)
    for sid in smeta:
        comps[find(sid)].append(smeta[sid])

    entries = []
    skipped_hand = 0
    held = 0
    n_anthology = 0
    n_qidcap = 0
    for comp in comps.values():
        sids = {m["sid"] for m in comp}
        if len(sids) < 2:
            continue
        # アンソロジー/汎用題 = 別作品同題 → 統合対象外
        if any(p in m["title"] for m in comp for p in ANTHOLOGY):
            n_anthology += 1
            continue
        # ★ 共通著者ガード: component 全員が共有する著者が居ないと統合しない
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
        # ★ 続編/外伝マーカー食い違い = 別作品 (= DEAR BOYS↔ACT3 / ○○↔○○異聞) → 保留
        if len({seq_marker(m["title"]) for m in comp}) > 1:
            held += 1
            continue
        # hand 版と重複 = skip (手動優先)
        if sids & hand_sids:
            skipped_hand += 1
            continue
        comp.sort(key=lambda m: -m["vols"])
        keys = sorted(sid_key[s] for s in sids)
        entries.append({
            "main": comp[0]["title"],
            "merge_keys": keys,  # ★STEP6: series_key 参照 (sid非依存=再build耐性)
            "note": "auto: subset-author + (clean-title|kana) (_gen-author-set-merges.py)",
        })

    entries.sort(key=lambda e: e["merge_keys"][0])

    out_path = (ROOT / ".cache" / "series-merge-auto-v2.json") if "--test" in sys.argv else OUT

    doc = {
        "_README": (
            "自動生成 — 手で編集しない。生成元: scripts/_gen-author-set-merges.py / "
            "詳細: docs/series-fragmentation-analysis.md。種2 sqlite 不変・種3 不変。"
            "★STEP6: merge は merge_keys (= series_key、 sid非依存=再build耐性)。 手動版 "
            "data/seeds/series-merge.yml と重複する group は skip 済 (= 手動優先)。 db-v2 "
            "再build後も series_key は安定だが、 新規 work 反映のため再生成推奨。"
        ),
        "merges": entries,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)

    print(f"=== series-merge-auto.json 生成 (merge_keys=series_key) ===", file=sys.stderr)
    print(f"  auto 統合 group     : {len(entries):,}", file=sys.stderr)
    print(f"  hand 重複 skip      : {skipped_hand}", file=sys.stderr)
    print(f"  semantic/共通著者なし保留: {held}", file=sys.stderr)
    print(f"  アンソロジー題 除外 : {n_anthology}", file=sys.stderr)
    print(f"  qid種類過多 除外    : {n_qidcap}", file=sys.stderr)
    print(f"  統合される series   : {sum(len(e['merge_keys']) for e in entries):,}", file=sys.stderr)
    print(f"  wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
