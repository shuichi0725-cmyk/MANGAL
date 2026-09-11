# -*- coding: utf-8 -*-
"""メタディスクリプションの重複監査 (= 2026-09-11 ユーザ相談「同じのが多過ぎ?」)

app/manga/[slug]/page.tsx の generateMetadata と**同じ式**で desc を再現し、
本番66k頁ぶんの重複を数える。重複は Google の「重複するメタデータ」警告と
スニペット書き換えの原因になる = 実データで規模を出してから手を打つため。

  python scripts/_audit-meta-description-dup.py            # 集計
  python scripts/_audit-meta-description-dup.py --dump N   # 上位N塊の実例をTSVへ
"""
import argparse
import collections
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, ".cache", "meta-desc-dup.tsv")


def seo_vol_phrase(m):
    """page.tsx の seoVolPhrase と同じ(nVols=巻番号の最大値・latest=発売日文字列の最大)。"""
    nums, latest = set(), None
    for e in m.get("editions") or []:
        for v in e.get("volumes") or []:
            if v.get("number") is not None:
                nums.add(v["number"])
            d = str(v.get("release_date") or "")
            if d and (latest is None or d > latest[1]):
                latest = (v.get("number"), d)
    n_vols = max(nums) if nums else 0
    parts = []
    if n_vols:
        parts.append(f"全{n_vols}巻で完結。" if m.get("status") == "completed" else f"既刊{n_vols}巻・連載中。")
    if latest and latest[0] and len(latest[1]) >= 10:
        y, mo, dy = [int(x) for x in latest[1][:10].split("-")]
        # 未来日は「発売予定」。監査では今日固定でよい(重複の形は変わらない)
        import datetime
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
        verb = "発売予定" if latest[1] > today else "発売"
        label = "最終巻" if m.get("status") == "completed" else "最新刊"
        parts.append(f"{label}{latest[0]}巻は{y}年{mo}月{dy}日{verb}。")
    return "".join(parts), n_vols


def desc_of(m):
    authors = "・".join(a.get("name", "") for a in (m.get("authors") or []))
    fallback = (m.get("catch") or m.get("synopsis")
                or f"{m.get('title')}({authors})の漫画全巻一覧・発売日・ISBN・出版社情報。楽天ブックス等の購入リンクつき。")[:120]
    phrase, n_vols = seo_vol_phrase(m)
    if n_vols:
        d = f"{phrase}{m.get('catch') or m.get('synopsis') or ''}"[:120]
        return (d or fallback), bool(m.get("catch") or m.get("synopsis"))
    return fallback, bool(m.get("catch") or m.get("synopsis"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=int, default=0)
    a = ap.parse_args()
    cnt = collections.Counter()
    members = collections.defaultdict(list)
    n = 0
    has_text = 0
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".yml"):
            continue
        try:
            m = yaml.load(io.open(os.path.join(SRC, fn), encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not m:
            continue
        n += 1
        d, ht = desc_of(m)
        has_text += 1 if ht else 0
        cnt[d] += 1
        if len(members[d]) < 6:
            members[d].append(fn[:-4])
        if n % 20000 == 0:
            print(f"  走査 {n} …", flush=True)
    uniq = len(cnt)
    dup_pages = sum(c for c in cnt.values() if c > 1)
    dup_groups = sum(1 for c in cnt.values() if c > 1)
    print(f"\n頁 {n} / 固有desc {uniq} ({uniq/n*100:.1f}%)")
    print(f"  重複している頁 : {dup_pages} ({dup_pages/n*100:.1f}%) / 重複の塊 {dup_groups}")
    print(f"  catch/synopsis を持つ頁 : {has_text} ({has_text/n*100:.1f}%)")
    print("\n★大きい塊 上位20:")
    for d, c in cnt.most_common(20):
        if c < 2:
            break
        print(f"  {c:>6}頁  「{d[:60]}」  例={members[d][0]}")
    if a.dump:
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write("頁数\tdescription\t例slug\n")
            for d, c in cnt.most_common(a.dump):
                if c < 2:
                    break
                f.write(f"{c}\t{d}\t{','.join(members[d])}\n")
        print(f"\n→ {OUT}")


if __name__ == "__main__":
    main()
