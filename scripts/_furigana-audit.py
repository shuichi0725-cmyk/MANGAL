"""フリガナ正当性 監査 (= 月次サニティ監査の読み層)。

3ソース consensus でフリガナの真の誤りを炙り出す:
  - 種2 (MADB ja-hrkt)   = series.title_kana
  - 種3 (AI生成)         = series-supplement-v2.yml title_kana
  - NDL (公式タイトルヨミ) = ground-truth (ISBN照合, dcndl:titleTranscription)
  - AniList romaji        = 参考のみ(英語題ノイズ大、読み監査には弱い → 不採用)

Stage A (network不要) で suspect を絞る:
  - flag1 = 種2 title_kana に 漢字/ラテン/ひらがな 混入 (= 生title漏れ、読み未解決)
  - flag3 = 種2(MADB) と 種3(AI) の独立2読みが不一致 (= 当て字 or 誤りの裁定要)
Stage B (network) = suspect のみ NDL照合 → title-overlap guard 付き consensus pick。

NDL応答は .cache/ndl-yomi-cache.json に蓄積 (= resumable、月次再実行が安価)。
出力 = .cache/furigana-audit-proposed.json (= 補正候補。 人が確認後 furigana-corrections.yml へ)。

使い方: python scripts/_furigana-audit.py --set flag3 [--limit N]
        python scripts/_furigana-audit.py --set flag1
        python scripts/_furigana-audit.py --set all
"""
import json
import sys
import re
import time
import pickle
import sqlite3
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3_CACHE = ROOT / ".cache" / "seed3-promote.pkl"
NDL_CACHE = ROOT / ".cache" / "ndl-yomi-cache.json"
OUT = ROOT / ".cache" / "furigana-audit-proposed.json"

HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
SMALL = str.maketrans({"ァ": "ア", "ィ": "イ", "ゥ": "ウ", "ェ": "エ", "ォ": "オ",
                       "ッ": "ツ", "ャ": "ヤ", "ュ": "ユ", "ョ": "ヨ", "ヮ": "ワ",
                       "ヂ": "ジ", "ヅ": "ズ", "ヶ": "ケ", "ヲ": "オ"})


def kata(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(HIRA).translate(SMALL)
    return re.sub(r"[^ァ-ヶ]", "", s)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(HIRA).translate(SMALL)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\s　ー・･,，/:：!！?？.。]", "", s)


def is_pure_kana(s: str) -> bool:
    t = re.sub(r"[\s　ー・･,，/:：!！?？0-9]", "", unicodedata.normalize("NFKC", s or ""))
    if not t:
        return False
    for ch in t:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:      # 漢字
            return False
        if (0x41 <= o <= 0x5A) or (0x61 <= o <= 0x7A):  # ラテン
            return False
        if 0x3041 <= o <= 0x3096:      # ひらがな(読みには不可)
            return False
    return True


def title_kata_runs(t: str) -> list[str]:
    return [kata(m) for m in re.findall(r"[ァ-ヶ][ァ-ヶー]{1,}", unicodedata.normalize("NFKC", t))]


def shares_title(reading: str, title: str):
    runs = title_kata_runs(title)
    if not runs:
        return None
    rk = kata(reading)
    return any(run in rk for run in runs)


def clean_ndl(s: str) -> str:
    return re.split(r"[:：/]", s)[0].strip() if s else s


HAS_KANJI = re.compile(r"[一-龯]")
HAS_LATIN = re.compile(r"[A-Za-z]")
HAS_HIRA = re.compile(r"[ぁ-ゖ]")


def load_ndl_cache() -> dict:
    if NDL_CACHE.exists():
        return json.load(NDL_CACHE.open(encoding="utf-8"))
    return {}


def ndl_yomi(isbn: str, cache: dict):
    if isbn in cache:
        return cache[isbn]
    url = f"https://ndlsearch.ndl.go.jp/api/opensearch?isbn={isbn}"
    req = urllib.request.Request(url, headers={"User-Agent": "mangal-audit/1.0 (furigana-validation)"})
    try:
        d = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
        ms = re.findall(r"<dcndl:titleTranscription>(.*?)</dcndl:titleTranscription>", d)
        val = ms[0] if ms else None
    except Exception:
        val = None
    cache[isbn] = val
    time.sleep(0.4)  # NDL へ礼儀正しく
    return val


def rep_isbn(con, sid: int):
    row = con.execute(
        """SELECT v.isbn13 FROM editions e JOIN volumes v ON v.edition_id=e.id
           WHERE e.series_id=? AND v.isbn13 IS NOT NULL AND v.isbn13!=''
           ORDER BY (e.type='standard') DESC, v.number ASC, v.isbn13 ASC LIMIT 1""",
        (sid,)).fetchone()
    return row[0] if row else None


def main():
    argset = "flag3"
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--set" and i + 1 < len(sys.argv):
            argset = sys.argv[i + 1]
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    seed3 = pickle.load(SEED3_CACHE.open("rb"))

    # Stage A: suspect 抽出
    rows = con.execute(
        "SELECT id, series_key, title, title_kana FROM series "
        "WHERE title_kana IS NOT NULL AND title_kana!=''").fetchall()
    suspects = []
    for sid, sk, title, s2k in rows:
        e3 = seed3.get(sk)
        if not e3:
            continue
        s3k = e3.get("title_kana") or ""
        if not s3k:
            continue
        f1 = bool(HAS_KANJI.search(s2k) or HAS_LATIN.search(s2k) or HAS_HIRA.search(s2k))
        f3 = norm(s2k) != norm(s3k)
        sel = (argset == "flag1" and f1) or (argset == "flag3" and f3) or \
              (argset == "all" and (f1 or f3))
        if sel:
            suspects.append((sid, sk, title, s2k, s3k, "f1" if f1 else "", "f3" if f3 else ""))
    if limit:
        suspects = suspects[:limit]
    print(f"Stage A suspect ({argset}): {len(suspects):,}", file=sys.stderr)

    # Stage B: NDL 照合 + consensus
    cache = load_ndl_cache()
    proposed = []
    stats = {"NDL": 0, "S3": 0, "S2": 0, "manual": 0, "no_isbn": 0}
    for i, (sid, sk, title, s2k, s3k, f1, f3) in enumerate(suspects):
        isbn = rep_isbn(con, sid)
        nd = clean_ndl(ndl_yomi(isbn, cache)) if isbn else None
        cands = [(nd, "NDL"), (s3k, "S3"), (s2k, "S2")]
        pick = src = None
        for cand, name in cands:
            if cand and is_pure_kana(cand) and shares_title(cand, title) is not False:
                pick, src = cand, name
                break
        if not isbn:
            stats["no_isbn"] += 1
        if pick is None:
            stats["manual"] += 1
            src = "manual"
        else:
            stats[src] += 1
        # 現状 種2(本番が使う値)と異なる時のみ補正候補
        changed = pick is not None and norm(pick) != norm(s2k)
        proposed.append({
            "key": sk, "title": title, "flags": (f1 + f3).strip(),
            "s2": s2k, "s3": s3k, "ndl": nd,
            "pick": pick, "src": src, "changed": changed,
        })
        if (i + 1) % 50 == 0:
            json.dump(cache, NDL_CACHE.open("w", encoding="utf-8"), ensure_ascii=False)
            print(f"  ..{i+1}/{len(suspects)}", file=sys.stderr)
    json.dump(cache, NDL_CACHE.open("w", encoding="utf-8"), ensure_ascii=False)
    json.dump(proposed, OUT.open("w", encoding="utf-8"), ensure_ascii=False, indent=0)

    changed = [p for p in proposed if p["changed"] and p["src"] != "manual"]
    print(f"\n=== 監査結果 ({argset}, {len(suspects)}件) ===")
    print(f"  選定元: {stats}")
    print(f"  ★補正候補(種2と相違・src確定): {len(changed)}")
    print(f"  要手動(全ソース無効): {stats['manual']}")
    print(f"  → {OUT}")


if __name__ == "__main__":
    main()
