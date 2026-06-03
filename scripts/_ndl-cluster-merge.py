"""NDL書誌(典拠ID+正規化主題)で series 分裂を再クラスタ → series-merge 提案を生成 (dry-run)。

入力:
  - .cache/ndl-sru-raw-cache.json   = NDL SRU dcndl 生応答 (ISBN→XML)。 検証で蓄積済。
    (将来は OAI-PMH ハーベストした全国書誌 dcndl をここに足す)
  - .cache/frag-sample-2000.json     = 検証用の分裂群サンプル (= 同著者+同norm題で別sid)
  - .cache/db-v2.sqlite              = 種2 (sid→series_key)
  - data/seeds/series-merge-auto.json + series-merge.yml = 既存merge

処理:
  1. cache を parse → 各ISBNの (著者典拠ID集合, 正規化主題) を得る
  2. 各分裂群の断片を NDL鍵で統一判定 (= 主題一致 ∧ 典拠overlap、 [[ndl-clustering-design]])
  3. ★既存merge(AUTO+hand)と突合 → 「既に統合済」 vs 「★NDL純増(未統合の分裂)」を分離
  4. NDL純増分の series-merge エントリを ★提案として出力 (= 適用しない。 人がレビュー)

出力: .cache/ndl-merge-proposed.json (= 提案 + 根拠)

★これは dry-run。 series-merge.yml は変更しない。 NDL照会も行わない (cache のみ)。
使い方: python scripts/_ndl-cluster-merge.py
"""
import sys
import re
import json
import unicodedata
import sqlite3
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SRU_CACHE = ROOT / ".cache" / "ndl-sru-raw-cache.json"
FRAG = ROOT / ".cache" / "frag-sample-2000.json"
OUT = ROOT / ".cache" / "ndl-merge-proposed.json"

HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})


def parse_record(xml: str):
    """NDL dcndl 生応答から (著者典拠ID集合, dc:title) を抽出。"""
    auths = frozenset(re.findall(r"id\.ndl\.go\.jp/auth/entity/(\d+)", xml))
    tb = re.search(r"<dc:title>(.*?)</dc:title>", xml, re.S)
    title = ""
    if tb:
        v = re.search(r"<rdf:value>(.*?)</rdf:value>", tb.group(1), re.S)
        title = re.sub(r"<[^>]+>", "", (v.group(1) if v else tb.group(1))).strip()
    return auths, title


def norm_main(t: str) -> str:
    """正規化主題 = 副題前 + 小文字 + ひら→カナ + 中黒/括弧グロス/記号 吸収。"""
    t = unicodedata.normalize("NFKC", t or "").lower().translate(HIRA)
    t = re.split(r"[:：]", t)[0]
    t = re.sub(r"[（(][^）)]*[）)]", "", t)
    return re.sub(r"[・･\s　\.\-,，。!！?？=]", "", t)


def load_existing_merge_group():
    """series_key → 既存merge群ID (AUTO+hand)。 未統合keyは自身がID。"""
    key2grp = {}
    auto = json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]
    for g in auto:
        mk = g.get("merge_keys") or []
        for k in mk:
            key2grp[k] = mk[0]
    import yaml
    hand = yaml.safe_load((ROOT / "data/seeds/series-merge.yml").read_text(encoding="utf-8")) or []
    for e in hand:
        if isinstance(e, dict):
            mk = e.get("merge_keys") or []
            if len(mk) >= 2:
                for k in mk:
                    key2grp[k] = mk[0]
    return key2grp


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cache = json.load(SRU_CACHE.open(encoding="utf-8"))
    samp = json.load(FRAG.open(encoding="utf-8"))
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    sid2key = {sid: k for sid, k in con.execute("SELECT id, series_key FROM series")}
    key2grp = load_existing_merge_group()

    # ISBN → cluster key
    isbn_key = {}
    for isbn, xml in cache.items():
        if not xml:
            continue
        a, t = parse_record(xml)
        if a or t:
            isbn_key[isbn] = (a, norm_main(t))

    proposed = []         # NDL純増 (未統合の分裂を統合)
    already = 0           # 既に統合済
    no_unify = 0          # NDL鍵が割れた (統一せず)
    no_data = 0
    for g in samp:
        frags = []
        for fr in g["sids"]:
            ck = isbn_key.get(fr["isbn"])
            key = sid2key.get(fr["sid"])
            if ck and key:
                frags.append((key, fr["sid"], fr["title"], ck))
        if len(frags) < 2:
            no_data += 1
            continue
        # NDL統一判定: 主題一致 ∧ 典拠 全ペアoverlap
        mains = {ck[1] for _, _, _, ck in frags}
        overlap = all(frags[0][3][0] & f[3][0] for f in frags)
        if not (len(mains) == 1 and overlap):
            no_unify += 1
            continue
        # 既存mergeで既に同群か
        grps = {key2grp.get(key, key) for key, _, _, _ in frags}
        if len(grps) == 1:
            already += 1
            continue
        # ★NDL純増: 未統合の断片を統合提案
        proposed.append({
            "merge_keys": [key for key, _, _, _ in frags],
            "ndl_key": {"auths": sorted(frags[0][3][0]), "main": frags[0][3][1]},
            "titles": [t for _, _, t, _ in frags],
            "note": "NDL clustering(典拠+主題)による分裂統合提案 dry-run",
        })

    json.dump(proposed, OUT.open("w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("=== NDL clustering → series-merge 提案 (dry-run) ===")
    print(f"  検証群: {len(samp)}")
    print(f"  NDL統一 & 既存mergeで統合済(AUTOが既に解決): {already}")
    print(f"  ★NDL統一 & 未統合 = 純増の統合提案: {len(proposed)}")
    print(f"  NDL鍵が割れた(統一せず): {no_unify}")
    print(f"  cache不足: {no_data}")
    print(f"  → {OUT}")
    print("\n■ 純増提案サンプル(NDLが新たに統合する分裂):")
    for p in proposed[:12]:
        print(f"   {p['titles']}  ← 典拠{p['ndl_key']['auths']} 主題「{p['ndl_key']['main'][:16]}」")


if __name__ == "__main__":
    main()
