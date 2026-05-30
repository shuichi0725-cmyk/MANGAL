"""workstream D = AniList 全項目(マッチ関連)を 100 件取得し、 新項目の充足率と
マッチ価値を実測する調査ツール。

現 dump に無い高価値候補項目を追加取得:
  description / chapters / externalLinks / characters / popularity / meanScore
  / averageScore / favourites / isLicensed (現 dump は volumes/staff/synonyms 等のみ)

入力: .cache/test100.ids (= AniList ID, 1行1個)
出力: .cache/anilist-fulltest-100.jsonl + 充足率サマリ(stdout)
"""
import sys, json, urllib.request, urllib.error, time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = "MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)"
ENDPOINT = "https://graphql.anilist.co"
IDS = Path(".cache/test100.ids")
OUT = Path(".cache/anilist-fulltest-100.jsonl")

QUERY = """
query ($ids: [Int]) {
  Page(page: 1, perPage: 50) {
    media(id_in: $ids, type: MANGA) {
      id idMal
      title { romaji english native }
      synonyms
      format status source(version: 3) countryOfOrigin isAdult isLicensed
      volumes chapters
      startDate { year month day }
      endDate { year month day }
      description(asHtml: false)
      averageScore meanScore popularity favourites
      genres
      tags { name rank category }
      externalLinks { site url type language }
      characters(perPage: 8, sort: [ROLE, RELEVANCE]) {
        edges { role node { name { full native } } }
      }
      staff(perPage: 10) { edges { role node { name { full native } } } }
      relations { edges { relationType node { id format title { native } } } }
    }
  }
}
"""


def fetch(ids, max_retry=5):
    data = json.dumps({"query": QUERY, "variables": {"ids": ids}}).encode("utf-8")
    for retry in range(max_retry):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=data,
                headers={"User-Agent": UA, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["data"]["Page"]["media"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                wait = 5 * (2 ** retry)
                print(f"  HTTP {e.code}, sleep {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            print(f"  err {e}, sleep {5*(retry+1)}s", flush=True)
            time.sleep(5 * (retry + 1))
    raise RuntimeError("fetch failed")


def main():
    ids = [int(x) for x in IDS.read_text().split()]
    recs = []
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        recs.extend(fetch(batch))
        print(f"fetched {len(recs)}/{len(ids)}", flush=True)
        time.sleep(1.5)
    with OUT.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(recs)
    print(f"\n=== 取得 {n} 件、 新項目の充足率 ===")

    def has(r, k):
        v = r.get(k)
        return v is not None and v != "" and v != [] and v != {}

    def pct(c):
        return f"{c} ({c*100//n if n else 0}%)"

    print(f"  description: {pct(sum(1 for r in recs if has(r,'description')))}")
    print(f"  chapters:    {pct(sum(1 for r in recs if has(r,'chapters')))}")
    print(f"  volumes:     {pct(sum(1 for r in recs if has(r,'volumes')))}")
    vol_null_chap = sum(1 for r in recs if not has(r, "volumes") and has(r, "chapters"))
    print(f"  ★volumes空だがchapters有: {vol_null_chap}  ← 巻信号の補完余地")
    print(f"  endDate(year): {pct(sum(1 for r in recs if (r.get('endDate') or {}).get('year')))}")
    print(f"  externalLinks: {pct(sum(1 for r in recs if has(r,'externalLinks')))}")
    print(f"  characters:  {pct(sum(1 for r in recs if (r.get('characters') or {}).get('edges')))}")
    print(f"  popularity:  {pct(sum(1 for r in recs if has(r,'popularity')))}")
    print(f"  meanScore:   {pct(sum(1 for r in recs if has(r,'meanScore')))}")
    print(f"  idMal:       {pct(sum(1 for r in recs if has(r,'idMal')))}")

    # synonyms 拡充: 現 dump synonyms 数 vs full の差は別途比較
    syn_avg = sum(len(r.get("synonyms") or []) for r in recs) / n if n else 0
    print(f"  synonyms 平均数: {syn_avg:.1f}")

    # externalLinks のサイト種別分布(ISBN/出版社リンクがあるか)
    from collections import Counter
    sites = Counter()
    for r in recs:
        for el in (r.get("externalLinks") or []):
            sites[el.get("site")] += 1
    print(f"\n=== externalLinks サイト種別 top15(出版社/書店リンク=種2裏取り余地) ===")
    for s, c in sites.most_common(15):
        print(f"  {s}: {c}")

    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
