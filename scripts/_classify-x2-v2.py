"""×2 同一著者ペアを「安全merge」と「分離」に精密再分類 (read-only)。
[[merge-needs-external-proof]]: 安全=版違い/英カナ同作/副題ドリフト。 危険=続編/アニメ/別作。

安全merge:
  EDITION       = 差分に版マーカー(文庫/新装版/完全版/ワイド/愛蔵/カラー版/復刻/合本/PREMIUM…)
  SCRIPT_VARIANT= 同一anilist_id ∧ NFKC正規化で近い(英⇄カナ等の表記違い)
  SUBTITLE_DRIFT= 一方が他方を内包(副題付加)、 ★続編数字/アニメ/外伝マーカー無
分離:
  SEQUEL    = 差分に続編マーカー(末尾数字違い/続/新/第N部/シーズン/season/II/EX/GO…)
  ANIME     = THE ANIMATION/アニメ/ANIMATION
  SPINOFF   = 外伝/番外
  DIFF      = 上記外(別作)
出力: .cache/x2-buckets-v2.json + .cache/x2-merge-queue.json
"""
import json
import sys
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
STRIP = re.compile(r"[・･\s　.\-,，。!！?？=~〜:：\"'’（）()「」『』【】\[\]/／]")
EDITION = ["文庫版", "コミック文庫", "文庫", "新装版", "新装", "完全版", "ワイド版", "ワイド判",
           "ワイド", "愛蔵版", "廉価版", "デラックス版", "カラー版", "フルカラー版", "新版",
           "復刻版", "復刻", "合本版", "合本", "特装版", "プレミアム", "premium", "保存版",
           "総合版", "普及版", "縮刷版", "オリジナル版", "collection", "選集", "definitive"]
EDITION_RE = re.compile("|".join(re.escape(e) for e in EDITION), re.I)
ANIME_RE = re.compile(r"the animation|animation|アニメ|フィルムコミック", re.I)
SPINOFF_RE = re.compile(r"外伝|番外|スピンオフ|gaiden")
ANTHOLOGY_RE = re.compile(r"アラカルト|アンソロジー|アラカルト|公式読本|ファンブック")
SEQUEL_RE = re.compile(r"続|新装|^新|シーズン|season|\bII\b|\bIII\b|ウォーズ|wars|ＷＡＲＳ|第[0-9０-９一二三四五六七八九十]+[部期章]", re.I)


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def norm(t):
    t = unicodedata.normalize("NFKC", t or "").lower().translate(HIRA)
    return STRIP.sub("", t)


def base(t):
    t = unicodedata.normalize("NFKC", t or "").lower().translate(HIRA)
    t = re.split(r"[:：]", t)[0]
    t = re.sub(r"[（(][^）)]*[）)]", "", t)
    t = EDITION_RE.sub("", t)
    return STRIP.sub("", t)


def trailing_num(t):
    m = re.search(r"([0-9０-９]+)\s*$", unicodedata.normalize("NFKC", t or ""))
    return m.group(1) if m else ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    wl = json.load((ROOT / ".cache/merge-worklist.json").open(encoding="utf-8"))
    en = json.load((ROOT / ".cache/anilist-enrich-map.json").open(encoding="utf-8"))
    pairs = [r for r in wl["WIKI_NEEDED"] if r["n"] == 2]
    out = {"EDITION": [], "SCRIPT_VARIANT": [], "SUBTITLE_DRIFT": [],
           "SEQUEL": [], "ANIME": [], "SPINOFF": [], "DIFF": []}
    for r in pairs:
        t = [title_of(k) for k in r["pages"]]
        n = [norm(x) for x in t]
        b = [base(x) for x in t]
        aids = {(en.get(k) or {}).get("anilist_id") for k in r["pages"]}
        aids = {a for a in aids if a}
        same_aid = len(aids) == 1
        rec = {"slug": r["slug"], "pages": r["pages"], "titles": t}
        # 差分判定の素材(全て先に計算 → 単一if/elif連鎖)
        anime = ANIME_RE.search(t[0]) or ANIME_RE.search(t[1])
        spin = (SPINOFF_RE.search(t[0]) is not None) != (SPINOFF_RE.search(t[1]) is not None)
        seqnum = trailing_num(t[0]) != trailing_num(t[1]) and (trailing_num(t[0]) or trailing_num(t[1]))
        sequel = (SEQUEL_RE.search(t[0]) is not None) != (SEQUEL_RE.search(t[1]) is not None)
        ed = EDITION_RE.search(t[0]) or EDITION_RE.search(t[1])
        contains = n[0] and (n[0] in n[1] or n[1] in n[0])
        same_base = b[0] and b[0] == b[1]
        anthology = (ANTHOLOGY_RE.search(t[0]) is not None) != (ANTHOLOGY_RE.search(t[1]) is not None)
        joined = unicodedata.normalize("NFKC", t[0] + "｜" + t[1])
        risky = bool(re.search(r"anthology|アンソロジー|アラカルト|画集|イラストアルバム|原画|辞典|事典|大全|大百科|ガイド|公式読本|セレクション|傑作|もっと|ネクスト|\bnext\b|スペシャル", joined, re.I))
        ln, sn = (n[0], n[1]) if len(n[0]) >= len(n[1]) else (n[1], n[0])
        tail = ln[len(sn):] if (sn and sn in ln) else ""
        single_seq = bool(tail) and bool(re.fullmatch(r"[zrswvxΣ＋\+2-9]", tail, re.I))

        if anime:
            out["ANIME"].append(rec)
        elif anthology:
            out["SPINOFF"].append(rec)
        elif ed and (same_base or contains):
            out["EDITION"].append(rec)                # 版マーカー=安全merge
        elif seqnum or (sequel and not same_base) or risky or single_seq:
            out["SEQUEL"].append(rec)                 # 続編/画集/辞典/選集/末尾単字=分離
        elif spin:
            out["SPINOFF"].append(rec)
        elif n[0] == n[1]:
            out["SUBTITLE_DRIFT"].append(rec)         # 完全一致=同作fragments(安全)
        elif same_base or (same_aid and contains):
            out["SUBTITLE_DRIFT"].append(rec)         # 同base/同aid内包=副題ドリフト
        elif same_aid:
            out["SCRIPT_VARIANT"].append(rec)         # 同aid表記違い(英カナ等)
        else:
            out["DIFF"].append(rec)

    print(f"×2 同一著者ペア {len(pairs)}群 の精密分類:")
    for k, v in out.items():
        tag = "→merge" if k in ("EDITION", "SCRIPT_VARIANT", "SUBTITLE_DRIFT") else "→分離/drop"
        print(f"  {k:15}: {len(v):3}群 {tag}")
    for bk in out:
        print(f"\n■ {bk}:")
        for r in out[bk][:10]:
            print(f"   {r['titles'][0][:22]} ┃ {r['titles'][1][:22]}")
    json.dump(out, (ROOT / ".cache/x2-buckets-v2.json").open("w", encoding="utf-8"), ensure_ascii=False)
    # 安全mergeのqueue
    q = []
    for bk in ("EDITION", "SCRIPT_VARIANT", "SUBTITLE_DRIFT"):
        for r in out[bk]:
            q.append({"slug": r["slug"], "note": f"×2同一著者ペア統合({bk}=版違い/表記揺れ/副題ドリフト) 2026-06"})
    json.dump(q, (ROOT / ".cache/x2-merge-queue.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n→ 安全merge候補 {len(q)}群 を x2-merge-queue.json に")


if __name__ == "__main__":
    main()
