"""AniList recall v2 (= 計画③ [[anilist_link_verification_plan]] 2026-07-18)。

未マッチ(v14非S・既存リンク/裁定考慮)に対し、 従来の native完全一致より広い候補チャネル:
  C1 exact   : 強正規化 native/english/romaji/synonyms == 頁題(+副題)
  C2 wd      : ★P8731全量(.cache/p8731-full-map.json)の jaラベル/別名 == 頁題(+副題)
  C3 skel    : 著者経由候補 × ローマ字子音骨格一致(かな橋渡し、副題込み可)
を集め、 検証ゲートと同じ独立証拠(著者A/年Y/巻V/読切F/乖離G)で合議。

採用階層(precision維持):
  accept: 題確証(C1/C2) ∧ 著者overlap ∧ 強負なし
          / C3骨格 ∧ 著者 ∧ (年 or 巻) ∧ 強負なし
  ai    : 題確証だがAniList側staff空(著者検証不能) ∧ (年 or 巻)
  reject: 著者矛盾(同名異作型)・証拠不足・強負あり
1:1保守: 既存リンクのa_idは不可侵。 新規内の競合は最高scoreのみ、同点skip。
★drop裁定済みkeyも対象(正しい付替先が見つかれば relink 復活候補として別出力)。

出力: .cache/match-recall-v2.tsv (s3_key,a_id,a_native,note) = enrich builder 追加読み用
      .cache/recall-drop-relinks.tsv = drop→relink 復活提案(overrides更新は別途)
      .cache/recall-ai-worksheet.tsv = AI裁定素材
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
S = {"S180", "S150", "S130", "S100"}
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


def skel(s):
    return re.sub(r"[aeiou\W_]", "", (s or "").lower())


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
    import pykakasi
    kks = pykakasi.kakasi()

    def kana_skel(kana):
        return skel("".join(it["hepburn"] for it in kks.convert(kana or "")))

    import yaml
    # --- 既存リンク集合(不可侵) & drop集合
    linked_keys = set()
    used_aids = set()
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["verdict"] in S and r["a_id"]:
                linked_keys.add(r["s3_key"])
                used_aids.add(int(r["a_id"]))
    for p in (".cache/match-recovery.tsv", ".cache/match-recall-authorroute.tsv"):
        with (ROOT / p).open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                if r.get("a_id"):
                    linked_keys.add(r["s3_key"])
                    used_aids.add(int(r["a_id"]))
    doc = yaml.safe_load((ROOT / "data/seeds/anilist-link-overrides.yml").read_text(encoding="utf-8"))
    drop_keys = {o["key"] for o in doc["overrides"] if o["action"] == "drop"}
    relink_map = {o["key"]: o["to_id"] for o in doc["overrides"] if o["action"] == "relink"}
    linked_keys |= set(relink_map)
    used_aids |= set(relink_map.values())
    linked_keys -= drop_keys

    # --- dump v3 + delta
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
    # index: tnorm(各題フィールド) → aids / 著者form → aids
    tindex = defaultdict(set)
    aindex = defaultdict(set)
    staff_cache = {}
    for i, d in entries.items():
        t = d.get("title") or {}
        for s in (t.get("native"), t.get("english"), t.get("romaji")):
            n = tnorm(s)
            if len(n) >= 2:
                tindex[n].add(i)
        for s in (d.get("synonyms") or []):
            n = tnorm(s)
            if len(n) >= 3:
                tindex[n].add(i)
        sf = staff_forms(d)
        staff_cache[i] = sf
        for fm in sf:
            aindex[fm].add(i)
    # P8731 全量: tnorm(label/alias) → aids
    p87 = json.loads((ROOT / ".cache/p8731-full-map.json").read_text(encoding="utf-8"))
    windex = defaultdict(set)
    for aid_s, v in p87.items():
        try:
            aid = int(aid_s)
        except ValueError:
            continue
        for s in [v.get("label")] + (v.get("aliases") or []):
            n = tnorm(s)
            if len(n) >= 3:
                windex[n].add(aid)
    print(f"dump {len(entries):,} / tindex {len(tindex):,} / aindex {len(aindex):,} / P8731 windex {len(windex):,}")

    srn = json.load((ROOT / ".cache/anilist-author-surname.json").open(encoding="utf-8"))

    # --- 未マッチ pool = v14全行 - linked (drop裁定済みは復活対象として別マーク)
    accepts, drop_relinks, ai_rows = [], [], []
    stats = Counter()
    cand_best = {}   # key → (score, aid, chan, sigs, row)
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            key = r["s3_key"]
            if key in linked_keys:
                continue
            stats["pool"] += 1
            title = r["s3_title"]
            page_t = tnorm(title)
            m = re.search(r"\|sub:([^|]+)", key)
            sub = m.group(1) if m else ""
            page_ts = tnorm(title + sub) if sub else ""
            if not page_t:
                continue
            kana = re.sub(r"[\s　]", "", r.get("s3_kana") or "")
            ksk = kana_skel(kana)
            ksk_sub = kana_skel(kana + sub) if sub else ""
            page_authors = set()
            for nm in (r.get("s3_authors") or "").split("|"):
                a = anorm(nm)
                if len(a) >= 2:
                    page_authors.add(a)
                sn = srn.get(nm.strip())
                if sn and len(sn) >= 3:
                    page_authors.add(sn)
            # 候補収集(★純ASCIIは正規化後3文字未満を候補化しない: MÄR→"mr"型の衝突FP防止)
            def lookable(n):
                return n and (len(n) >= 3 or (len(n) >= 2 and not n.isascii()))
            cands = {}
            for n in {page_t, page_ts} - {""}:
                if not lookable(n):
                    continue
                for i in tindex.get(n, ()):
                    cands[i] = "C1"
                for i in windex.get(n, ()):
                    cands.setdefault(i, "C2")
            if page_authors and ksk and len(ksk) >= 4:
                au_cands = set()
                for fm in page_authors:
                    au_cands |= aindex.get(fm, set())
                for i in au_cands:
                    if i in cands:
                        continue
                    rom = skel((entries[i].get("title") or {}).get("romaji") or "")
                    if rom and (rom == ksk or (ksk_sub and rom == ksk_sub)):
                        cands[i] = "C3"
            if not cands:
                continue
            # 評価
            best = None
            for aid, chan in cands.items():
                if aid in used_aids:
                    stats["skip_aid_taken"] += 1
                    continue
                d = entries.get(aid)
                if not d:
                    continue
                sigs = [chan]
                score = 3 if chan in ("C1", "C2") else 2
                sf = staff_cache.get(aid) or set()
                a_match = bool(sf & page_authors)
                if a_match:
                    sigs.append("A+")
                    score += 1
                elif sf and page_authors:
                    sigs.append("A-")
                    score -= 3   # 同名異作ガード: 両側著者ありで不一致
                try:
                    sy = int(r.get("s3_year") or 0)
                except ValueError:
                    sy = 0
                ay = ((d.get("startDate") or {}).get("year")) or 0
                if sy and ay:
                    dy = abs(sy - ay)
                    if dy <= 1:
                        sigs.append("Y+"); score += 1
                    elif dy >= 4:
                        sigs.append("Y-"); score -= 1
                try:
                    s3v = int(r.get("s3_vols") or 0)
                except ValueError:
                    s3v = 0
                av = d.get("volumes")
                if s3v and av:
                    if abs(s3v - av) <= 1:
                        sigs.append("V+"); score += 2
                    elif max(s3v, av) <= 2 * min(s3v, av):
                        sigs.append("V~"); score += 1
                fmt = d.get("format")
                if fmt == "ONE_SHOT" and s3v >= 2:
                    sigs.append("F-"); score -= 3
                if av and (s3v >= max(5, 4 * av) or (s3v >= 2 and av >= 4 * s3v)):
                    sigs.append("G-"); score -= 2
                if best is None or score > best[0]:
                    best = (score, aid, chan, sigs, a_match, sf)
            if not best:
                continue
            score, aid, chan, sigs, a_match, sf = best
            strong_neg = any(x in sigs for x in ("F-", "G-", "A-"))
            # ★Y-(開始年4年以上乖離)は V+ 裏付けが無ければ不採用(坊っちゃん型=原作者経由の別作画コミカライズ防止)
            if "Y-" in sigs and "V+" not in sigs:
                strong_neg = True
            corro = any(x in sigs for x in ("Y+", "V+", "V~"))
            d = entries[aid]
            t = d.get("title") or {}
            note = f"{chan}+{'A' if a_match else ''}|{'|'.join(sigs)}"
            if chan in ("C1", "C2") and a_match and not strong_neg:
                verdict = "accept"
            elif chan == "C3" and a_match and corro and not strong_neg:
                verdict = "accept"
            elif chan in ("C1", "C2") and not sf and corro and not strong_neg:
                verdict = "ai"   # AniList側staff空で著者検証不能 → AI
            else:
                stats["reject"] += 1
                continue
            cand_best[key] = (score, aid, verdict, note, r, t)
    # 新規内の a_id 競合解決(最高scoreのみ、同点は全skip)
    by_aid = defaultdict(list)
    for key, (score, aid, verdict, note, r, t) in cand_best.items():
        by_aid[aid].append((score, key))
    for aid, lst in by_aid.items():
        lst.sort(reverse=True)
        winners = [k for s, k in lst if s == lst[0][0]]
        for s, k in lst:
            if len(winners) > 1 or k != winners[0]:
                cand_best.pop(k, None)
                stats["skip_conflict"] += 1
    # 出力振り分け
    for key, (score, aid, verdict, note, r, t) in sorted(cand_best.items()):
        native = t.get("native") or t.get("romaji") or ""
        if verdict == "accept":
            if key in drop_keys:
                drop_relinks.append((key, aid, native, note))
            else:
                accepts.append((key, aid, native, note))
        else:
            d = entries[aid]
            ai_rows.append((key, aid, "RECALL", note, r["s3_title"],
                            re.search(r"\|sub:([^|]+)", key).group(1) if "|sub:" in key else "",
                            r.get("s3_year") or "", r.get("s3_vols") or "",
                            (r.get("s3_authors") or "")[:120],
                            t.get("native") or "", t.get("romaji") or "", d.get("format") or "",
                            str(((d.get("startDate") or {}).get("year")) or ""),
                            str(d.get("volumes") or ""), str(d.get("chapters") or ""), "", note))

    clean = lambda v: re.sub(r"[\t\n\r]", " ", str(v))
    with (ROOT / ".cache/match-recall-v2.tsv").open("w", encoding="utf-8") as f:
        f.write("s3_key\ta_id\ta_native\tnote\n")
        for x in accepts:
            f.write("\t".join(clean(v) for v in x) + "\n")
    with (ROOT / ".cache/recall-drop-relinks.tsv").open("w", encoding="utf-8") as f:
        f.write("s3_key\ta_id\ta_native\tnote\n")
        for x in drop_relinks:
            f.write("\t".join(clean(v) for v in x) + "\n")
    with (ROOT / ".cache/recall-ai-worksheet.tsv").open("w", encoding="utf-8") as f:
        f.write("key\ta_id\tgate\tsignals\ts3_title\ts3_sub\ts3_year\ts3_vols\ts3_authors\t"
                "a_native\ta_romaji\ta_format\ta_year\ta_vols\ta_chaps\ta_staff\tnote\n")
        for x in ai_rows:
            f.write("\t".join(clean(v) for v in x) + "\n")

    print(f"\n未マッチpool: {stats['pool']:,}")
    print(f"accept(新規結線): {len(accepts):,}")
    print(f"drop→relink復活提案: {len(drop_relinks):,}")
    print(f"AI裁定行き: {len(ai_rows):,}")
    print(f"reject: {stats['reject']:,} / aid占有skip: {stats['skip_aid_taken']:,} / 競合skip: {stats['skip_conflict']:,}")
    print("\n=== accept サンプル ===")
    for x in accepts[:15]:
        print(f"  {x[0][:56]} → {x[1]} {x[2][:30]} [{x[3]}]")
    print("\n=== drop→relink サンプル ===")
    for x in drop_relinks[:10]:
        print(f"  {x[0][:56]} → {x[1]} {x[2][:30]} [{x[3]}]")


if __name__ == "__main__":
    main()
