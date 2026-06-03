"""×2 同一著者ペア(677群)を構造シグナルで分類 (read-only)。 [[merge-needs-external-proof]]。

判定:
  base = title から版マーカー(文庫/新装版/完全版/ワイド/愛蔵/DX/カラー版/復刻/合本…)と
         副題([:／空白]以降)・記号 を除去・正規化。
バケット:
  CLEAR_EDITION = 同base ∧ 版マーカー有 → 版違い(安全merge候補)
  SAME_BASE     = 同base ∧ 版マーカー無 → 巻範囲/副題ドリフト(merge候補だが要注意=悪魔くん型あり)
  DIFF_BASE     = base異 → 別作(同著者の別作品 → 分離)
出力: .cache/x2-buckets.json
"""
import json
import sys
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
STRIP = re.compile(r"[・･\s　.\-,，。!！?？=~〜:：\"'’（）()「」『』【】\[\]]")
# 版マーカー(これが付くと同一作の別版)
EDITION = ["文庫版", "コミック文庫", "文庫", "新装版", "新装", "完全版", "ワイド版", "ワイド判",
           "ワイド", "愛蔵版", "廉価版", "デラックス版", "デラックス", "カラー版", "フルカラー版",
           "新版", "復刻版", "復刻", "合本版", "合本", "特装版", "プレミアム", "保存版", "選集",
           "総合版", "オリジナル版", "普及版", "縮刷版", "新編集版", "decome", "Special edition"]
EDITION_RE = re.compile("|".join(re.escape(e) for e in EDITION))


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def base_of(t):
    t = unicodedata.normalize("NFKC", t or "").lower().translate(HIRA)
    t = re.split(r"[:：]", t)[0]                  # 副題前
    t = re.sub(r"[（(][^）)]*[）)]", "", t)        # 括弧グロス
    t = EDITION_RE.sub("", t)                     # 版マーカー除去
    return STRIP.sub("", t)


def has_edition(t):
    return bool(EDITION_RE.search(unicodedata.normalize("NFKC", t or "")))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    wl = json.load((ROOT / ".cache/merge-worklist.json").open(encoding="utf-8"))
    pairs = [r for r in wl["WIKI_NEEDED"] if r["n"] == 2]
    out = {"CLEAR_EDITION": [], "SAME_BASE": [], "DIFF_BASE": []}
    for r in pairs:
        t = [title_of(k) for k in r["pages"]]
        b = [base_of(x) for x in t]
        same_base = b[0] and (b[0] == b[1] or b[0] in b[1] or b[1] in b[0])
        ed = has_edition(t[0]) or has_edition(t[1])
        rec = {"slug": r["slug"], "pages": r["pages"], "titles": t}
        if same_base and ed:
            out["CLEAR_EDITION"].append(rec)
        elif same_base:
            out["SAME_BASE"].append(rec)
        else:
            out["DIFF_BASE"].append(rec)
    print(f"×2 同一著者ペア: {len(pairs)}群")
    for k, v in out.items():
        print(f"  {k:14}: {len(v)}群")
    for bk in out:
        print(f"\n■ {bk} の例:")
        for r in out[bk][:12]:
            print(f"   [{r['slug']}] {r['titles'][0][:20]} ┃ {r['titles'][1][:20]}")
    json.dump(out, (ROOT / ".cache/x2-buckets.json").open("w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
