"""本番 v2 の表示データ監査(ユーザ実機指摘 2026-06-12 起点):
  1. authors / original_authors 内の正規化同名重複(J.P.ホーガン vs J.P. ホーガン = 空白/中黒差)
  2. synonyms / alternative_titles に日本語(CJK)が混入している件数
  3. release_date の月精度(日欠落)件数 = 表示側で要ガードの規模
読み取りのみ。 サンプルと件数を報告。
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "data" / "manga.v2"

CJK = re.compile(r"[ぁ-んァ-ヴ一-鿿]")


def norm_name(s):
    return re.sub(r"[\s　・･\.,，、]+", "", s or "").upper()


def main():
    dup_pages = []
    syn_jp_pages = 0
    syn_jp_samples = []
    month_only = 0
    total_dates = 0
    n = 0
    for f in V2.glob("*.yml"):
        n += 1
        txt = f.read_text(encoding="utf-8")
        # authors/original_authors の name: 行を雑に抽出(ブロック単位の厳密parseはコスト高)
        for block in ("authors", "original_authors"):
            m = re.search(rf"^{block}:\n((?:- .*\n(?:  .*\n)*)+)", txt, re.M)
            if not m:
                continue
            names = re.findall(r"^- name: (.+)$", m.group(1), re.M)
            cnt = Counter(norm_name(x) for x in names)
            for k, c in cnt.items():
                if c > 1 and k:
                    dup_pages.append((f.stem, block, [x for x in names if norm_name(x) == k]))
                    break
        # synonyms に日本語
        sm = re.search(r"^synonyms:\n((?:- .*\n)+)", txt, re.M)
        if sm:
            syns = re.findall(r"^- (.+)$", sm.group(1), re.M)
            jp = [s for s in syns if CJK.search(s)]
            if jp:
                syn_jp_pages += 1
                if len(syn_jp_samples) < 8:
                    syn_jp_samples.append((f.stem, jp[:3]))
        # 月精度日付
        for d in re.findall(r"release_date: '?(\d{4}-\d{2}(?:-\d{2})?)'?", txt):
            total_dates += 1
            if len(d) == 7:
                month_only += 1

    print(f"走査: {n:,} ページ")
    print(f"\n1. 著者の正規化同名重複: {len(dup_pages)} ページ")
    for s, b, names in dup_pages[:12]:
        print(f"   {s} [{b}] {names}")
    print(f"\n2. synonyms に日本語混入: {syn_jp_pages:,} ページ")
    for s, jp in syn_jp_samples:
        print(f"   {s}: {jp}")
    print(f"\n3. release_date 月精度(日欠落): {month_only:,} / {total_dates:,} ({month_only*100//max(total_dates,1)}%)")


if __name__ == "__main__":
    main()
