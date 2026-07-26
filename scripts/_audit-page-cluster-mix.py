"""★1頁に「別作品」が潰れて入っている頁を検出(= 過剰統合の型)。

背景(2026-07-26 名探偵ホームズで発覚):
  1つの頁に **5つの別series** が同居していた:
    絵コンテ全集 / 徳間アニメ絵本 / おもしろ漫画文庫 / JNコミックス /
    「ふしぎの国のアリス 名探偵ホームズ」(著者=川端康成)
  著者が コナン・ドイル / 川端康成 / 木の実和 とばらばらで、series_key の qid は
  ★**Q55400 = 宮崎駿(著者QID)**。 種2の qid は作品でなく**著者**なので([[shu2_qid_is_author]])、
  「同じ著者の別作品」が同一クラスタに吸い込まれる経路がある。

判定(= 保守的に「明らかな別物」だけ挙げる):
  頁を構成する種2 series を集め、
    ①**著者集合が互いに素**(共通著者ゼロ)の series が2つ以上ある
    ②かつ **正規化題が違う**(巻数/版表記/空白/カナ揺れを吸収しても一致しない)
  を満たす頁を flag。 版違い統合(同一著者)・題名変遷(同一著者)は素通しする。

★これは read-only。 直し方は per-case(non-manga-drop / edition-overrides / volume-exclude)。

出力: docs/production-diagnostics/page-cluster-mix.tsv
usage: python scripts/_audit-page-cluster-mix.py [--limit N]
"""
import argparse
import collections
import glob
import re
import sys
import sqlite3
import unicodedata
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SRC = ROOT / "data" / "manga.v2"
OUT = ROOT / "docs" / "production-diagnostics" / "page-cluster-mix.tsv"
try:
    from yaml import CSafeLoader as L
except ImportError:
    L = yaml.SafeLoader

# 版・巻の表記は題の同一性判定から外す(= 版違いは統合が正しい)
DROP_WORDS = re.compile(
    r"(新装版|完全版|愛蔵版|文庫版|ワイド版|豪華版|特装版|decoded|オリジナル版|復刻版|総集編|"
    r"第[0-9一二三四五六七八九十]+部|[0-9]+|[･・、。!！?？:：;；~〜ー\-\s.,]+)")
# ★括弧内は「よみ・別称」であることが多く(EVOL(イーヴォー)/私の身体(からだ))、
#   同一作の表記ゆれを別作に見せる最大の要因なので落とす。 副題区切りの〜…〜も同様。
PAREN = re.compile(r"[（(][^）)]*[）)]|【[^】]*】|〜[^〜]*〜|～[^～]*～")


def norm_title(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return DROP_WORDS.sub("", PAREN.sub("", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    print("[1/3] 種2 を読む ...", flush=True)
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    # sid -> 著者名集合 (mangaka.name。 qid ではなく名前で比べる = 表記は後で正規化)
    auth = collections.defaultdict(set)
    for sid, nm in con.execute(
            "SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"):
        if nm:
            auth[sid].add(unicodedata.normalize("NFKC", nm).replace(" ", "").replace("　", ""))
    stitle = {sid: t for sid, t in con.execute("SELECT id,title FROM series")}
    skey = {sid: k for sid, k in con.execute("SELECT id,series_key FROM series")}
    isbn2sid = {}
    for ib, sid in con.execute(
            "SELECT v.isbn13, e.series_id FROM volumes v JOIN editions e ON e.id=v.edition_id "
            "WHERE v.isbn13 IS NOT NULL"):
        isbn2sid[ib] = sid
    print(f"  series {len(stitle):,} / ISBN {len(isbn2sid):,}", flush=True)

    print("[2/3] 本番頁を走査 ...", flush=True)
    rows, n = [], 0
    for p in glob.glob(str(SRC / "*.yml")):
        n += 1
        if n % 20000 == 0:
            print(f"    ...{n:,}", flush=True)
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not d:
            continue
        sids = set()
        for ed in (d.get("editions") or []):
            for v in (ed.get("volumes") or []):
                s = isbn2sid.get(str(v.get("isbn13") or ""))
                if s:
                    sids.add(s)
        if len(sids) < 2:
            continue
        # ★互いに素な著者集合 かつ 正規化題が違う 組を探す
        info = [(s, stitle.get(s, ""), auth.get(s, set())) for s in sids]
        groups = []                     # [(代表題, 著者集合, [sid...])]
        for s, t, au in info:
            nt = norm_title(t)
            for g in groups:
                # 著者が重なる or 題が同じ なら同じ作品として畳む
                if (au and g[1] and (au & g[1])) or nt == norm_title(g[0]):
                    g[1].update(au)
                    g[2].append(s)
                    break
            else:
                groups.append([t, set(au), [s]])
        if len(groups) < 2:
            continue
        rows.append((
            d.get("slug"), d.get("title"), str(len(groups)), str(len(sids)),
            " || ".join(f"{g[0]}〈{'/'.join(sorted(g[1])) or '著者不明'}〉" for g in groups[:5]),
            " ".join(skey.get(s, "") for g in groups for s in g[2][:1])[:200],
        ))
    rows.sort(key=lambda r: -int(r[2]))
    if a.limit:
        rows = rows[:a.limit]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("slug\ttitle\tgroups\tsids\tbreakdown\tseries_keys\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"\n[3/3] === 1頁に別作品が同居している疑い ===")
    print(f"  ★{len(rows):,} 頁 → {OUT}")
    c = collections.Counter(int(r[2]) for r in rows)
    print("  同居グループ数の分布:", dict(sorted(c.items())))
    for r in rows[:20]:
        print(f"   {r[2]}群 {r[0][:38]:40s} {r[4][:110]}")


if __name__ == "__main__":
    main()
