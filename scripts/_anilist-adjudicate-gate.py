"""AniListリンク疑惑の機械裁定 (= 計画② [[anilist_link_verification_plan]])。

入力 = .cache/anilist-gate.tsv の FAIL / SUSPECT。
機械チャネル(確証ベース・保守的):
  1. dump全体(v3+delta重ね)の 強正規化 native/english/synonym == 頁題(+副題) を候補化
  2. Wikidata P8731 逆引きラベル(work-qid-map)== 頁題 も候補化
  3. ★著者overlap 必須(同名異作ガード=recovery と同じ安全弁)
  4. 一意候補のみ採用(複数候補=曖昧→AI行き)
提案:
  relink: 一意候補 != 現リンク → 付け替え
  drop  : FAIL かつ 候補なし(強負・題確証なしの高確信誤り = 6/13 の drop374 と同クラス)
  ai    : SUSPECT かつ 候補なし → AIワークシート行き
出力(読み取りのみ・適用は別途):
  .cache/anilist-gate-adjudication.tsv   = 全裁定
  .cache/anilist-gate-ai-worksheet.tsv   = AI裁定用スライス素材
"""
import csv
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
ROMAN = {"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
         "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10"}
NONAUTH = re.compile(r"translat|letter|assist|editor|design|proofread|adapt", re.I)


def tnorm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    for k, v in ROMAN.items():
        s = s.replace(k, v)
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龯]", "", s.lower())


def anorm(s):
    if not s:
        return ""
    return re.sub(r"[\s　・･.,，、]+", "", unicodedata.normalize("NFKC", s).translate(HIRA)).lower()


def staff_forms(d):
    forms = set()
    for e in (d.get("staff") or {}).get("edges", []):
        if NONAUTH.search(e.get("role", "") or ""):
            continue
        nm = (e.get("node") or {}).get("name") or {}
        for n in (nm.get("native"), nm.get("full")):
            a = anorm(n)
            if len(a) >= 2:
                forms.add(a)
        full = (nm.get("full") or "").strip()
        if full:
            sn = full.split()[-1].lower()
            if len(sn) >= 3:
                forms.add(sn)
    return forms


def main():
    # 疑惑行
    todo = []
    with (ROOT / ".cache/anilist-gate.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["gate"] in ("FAIL", "SUSPECT"):
                todo.append(r)
    print(f"裁定対象: {len(todo):,} (FAIL {sum(1 for r in todo if r['gate']=='FAIL')} / SUSPECT {sum(1 for r in todo if r['gate']=='SUSPECT')})")

    # dump 全体 index(v3 + delta後勝ち)
    entries = {}
    with gzip.open(ROOT / ".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            entries[d["id"]] = d
    delta = ROOT / ".cache/anilist-delta.jsonl"
    if delta.exists():
        with delta.open(encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("id"):
                    entries[d["id"]] = d
    tindex = defaultdict(set)
    for i, d in entries.items():
        t = d.get("title") or {}
        for s in (t.get("native"), t.get("english")):
            n = tnorm(s)
            if n:
                tindex[n].add(i)
        for s in (d.get("synonyms") or []):
            n = tnorm(s)
            if len(n) >= 3:  # 極短synonymの誤爆防止
                tindex[n].add(i)
    print(f"dump index: {len(entries):,} entries / {len(tindex):,} title keys")

    # P8731 逆引き(label → aid)
    wq = json.load((ROOT / ".cache/work-qid-map.json").open(encoding="utf-8"))
    windex = defaultdict(set)
    for aid, v in wq.items():
        n = tnorm((v or {}).get("label"))
        if len(n) >= 3:
            windex[n].add(int(aid))

    srn = json.load((ROOT / ".cache/anilist-author-surname.json").open(encoding="utf-8"))
    staff_cache = {}

    def sforms_of(aid):
        if aid not in staff_cache:
            staff_cache[aid] = staff_forms(entries.get(aid) or {})
        return staff_cache[aid]

    out_rows = []
    ai_rows = []
    vc = Counter()
    for r in todo:
        key, cur = r["key"], int(r["a_id"])
        page_t = tnorm(r["s3_title"])
        page_ts = tnorm(r["s3_title"] + (r["s3_sub"] or ""))
        page_authors = set()
        for nm in (r["s3_authors"] or "").split("|"):
            a = anorm(nm)
            if len(a) >= 2:
                page_authors.add(a)
            sn = srn.get(nm.strip())
            if sn and len(sn) >= 3:
                page_authors.add(sn)
        # 候補収集(title完全一致)
        cands = set()
        for n in {page_t, page_ts} - {""}:
            cands |= tindex.get(n, set())
            cands |= windex.get(n, set())
        cands.discard(cur)
        # 著者ゲート
        gated = {c for c in cands if sforms_of(c) & page_authors} if page_authors else set()
        verdict, target, note = "", "", ""
        if len(gated) == 1:
            target = gated.pop()
            d = entries.get(target) or {}
            verdict = "relink"
            note = f"native/wd exact+author → {(d.get('title') or {}).get('romaji') or ''}"[:80]
        elif len(gated) >= 2:
            verdict = "ai"
            note = f"曖昧: 候補{len(gated)}件 {sorted(gated)[:4]}"
        elif r["gate"] == "FAIL":
            verdict = "drop"
            note = "強負+題確証なし+relink先なし"
        else:
            verdict = "ai"
            note = "候補なし"
        vc[verdict] += 1
        out_rows.append((key, cur, r["gate"], r["signals"], verdict, target, note))
        if verdict == "ai":
            d = entries.get(cur) or {}
            t = d.get("title") or {}
            a_staff = "|".join(sorted({(e.get('node') or {}).get('name', {}).get('full') or ''
                                       for e in (d.get('staff') or {}).get('edges', [])
                                       if not NONAUTH.search(e.get('role', '') or '')} - {''}))[:100]
            ai_rows.append((key, cur, r["gate"], r["signals"],
                            r["s3_title"], r["s3_sub"], r["s3_year"], r["s3_vols"], r["s3_authors"],
                            t.get("native") or "", t.get("romaji") or "", d.get("format") or "",
                            str(((d.get("startDate") or {}).get("year")) or ""),
                            str(d.get("volumes") or ""), str(d.get("chapters") or ""), a_staff, note))

    clean = lambda v: re.sub(r"[\t\n\r]", " ", str(v))
    adj = ROOT / ".cache/anilist-gate-adjudication.tsv"
    with adj.open("w", encoding="utf-8") as f:
        f.write("key\ta_id\tgate\tsignals\tverdict\tto_id\tnote\n")
        for x in out_rows:
            f.write("\t".join(clean(v) for v in x) + "\n")
    ws = ROOT / ".cache/anilist-gate-ai-worksheet.tsv"
    with ws.open("w", encoding="utf-8") as f:
        f.write("key\ta_id\tgate\tsignals\ts3_title\ts3_sub\ts3_year\ts3_vols\ts3_authors\t"
                "a_native\ta_romaji\ta_format\ta_year\ta_vols\ta_chaps\ta_staff\tnote\n")
        for x in ai_rows:
            f.write("\t".join(clean(v) for v in x) + "\n")

    print(f"\n=== 機械裁定 ===")
    for k in ("relink", "drop", "ai"):
        print(f"  {k:6}: {vc[k]:,}")
    print(f"→ {adj}")
    print(f"→ {ws} (AI裁定素材)")
    print("\n=== relink サンプル ===")
    n = 0
    for x in out_rows:
        if x[4] == "relink" and n < 12:
            print(f"  {x[0][:50]} : {x[1]} → {x[5]} ({x[6]})")
            n += 1


if __name__ == "__main__":
    main()
