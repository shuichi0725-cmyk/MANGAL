"""AniListリンク検証ゲート (= 計画① [[anilist_link_verification_plan]] 2026-07-18)。

enrich に流れる全リンク(v14 S + recovery + authorroute、 overrides 適用後)を
matcher スコアとは独立の証拠合議で採点し、 低信頼を enrich join から止める土台を作る。
★読み取りのみ・修正なし(出力 = .cache/anilist-gate.tsv + 集計)。

証拠チャネル(matcher とは独立に取り直す):
  T+ native_exact : 強正規化 native/english/synonym 完全一致 (+3)
  R+ romaji_skel  : a_romaji 子音骨格 == 頁ヨミ骨格(副題込みも可= S3疑惑の精緻化) (+2)
  W+ wd_label     : Wikidata P8731 逆引き(work-qid-map)の ja ラベル一致 (+3)
  A+ author       : 著者 overlap(native/full/姓romaji 橋渡し) (+1 ★同franchise誤リンクは同著者なので弱)
  Y+ year         : |s3_year - a_start.year| <= 1 (+1) / >= 4 で Y- (-1)
  V+ vols         : 巻数 |diff|<=1 (+2) / 比2倍以内 (+1)
  F- one_shot     : format ONE_SHOT なのに s3_vols >= 2 (-3)
  G- vols_gap     : s3_vols >= max(5, 4*a_vols) or a_vols >= 4*s3_vols (-2)
  C- few_chaps    : MANGA で chapters <= 6 なのに s3_vols >= 3 (-2)

verdict:
  PASS    = T+ or W+ (題レベル確証) / または合議 score >= 3
  SUSPECT = 中間(確証も強負も無い)
  FAIL    = score <= -2 (強負あり・題確証なし)

鮮度: dump v3 (5/31) に .cache/anilist-delta.jsonl (柱⑥ローリング) を in-memory 重ね掛け
(ファイル merge はしない = 蒸留時 Opus 専権 [[idle-run]])。
"""
import csv
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter
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
    """title 強正規化(_match-recover-norm.py と同軸)。"""
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


def load_links():
    """enrich builder と同じ組み立て: v14 S + recovery + authorroute → overrides 適用。"""
    sk_aid = {}
    src = {}
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["verdict"] in S and r["a_id"]:
                sk_aid[r["s3_key"]] = int(r["a_id"])
                src[r["s3_key"]] = "v14"
    for path, tag in ((".cache/match-recovery.tsv", "recovery"),
                      (".cache/match-recall-authorroute.tsv", "authorroute")):
        p = ROOT / path
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                if r.get("a_id") and r["s3_key"] not in sk_aid:
                    sk_aid[r["s3_key"]] = int(r["a_id"])
                    src[r["s3_key"]] = tag
    import yaml
    doc = yaml.safe_load((ROOT / "data/seeds/anilist-link-overrides.yml").read_text(encoding="utf-8")) or {}
    for o in (doc.get("overrides") or []):
        if not isinstance(o, dict) or not o.get("key"):
            continue
        if o.get("action") == "drop":
            sk_aid.pop(o["key"], None)
        elif o.get("action") == "relink" and o.get("to_id"):
            sk_aid[o["key"]] = int(o["to_id"])
            src[o["key"]] = src.get(o["key"], "v14") + "+relink"
    return sk_aid, src


def load_dump(need):
    """dump v3 + delta 重ね掛け(id 単位で後勝ち=delta 優先)。"""
    meta = {}
    with gzip.open(ROOT / ".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in need:
                meta[d["id"]] = d
    delta = ROOT / ".cache/anilist-delta.jsonl"
    n_delta = 0
    if delta.exists():
        with delta.open(encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("id") in need:
                    meta[d["id"]] = d
                    n_delta += 1
    return meta, n_delta


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
            surname = full.split()[-1].lower()
            if len(surname) >= 3:
                forms.add(surname)
    return forms


def main():
    import pykakasi
    kks = pykakasi.kakasi()

    def kana_skel(kana):
        return skel("".join(it["hepburn"] for it in kks.convert(kana or "")))

    sk_aid, src = load_links()
    need = set(sk_aid.values())
    print(f"検証対象リンク: {len(sk_aid):,} (a_id {len(need):,}種)")
    meta, n_delta = load_dump(need)
    print(f"dump hit: {len(meta):,} / delta上書き: {n_delta:,}")

    # s3側証拠 = v14 all(全種3行が s3_* を保有)
    s3 = {}
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            s3[r["s3_key"]] = r

    # ★fallback: v14 に行が無いキー(recovery系 ~11.6k)は種2 sqlite から証拠を引く
    missing = [k for k in sk_aid if k not in s3]
    if missing:
        import sqlite3
        con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
        con.text_factory = lambda b: b.decode("utf-8", "replace")
        auth = {}
        for k, nm in con.execute(
                "SELECT s.series_key, m.name FROM series s "
                "JOIN series_authors sa ON sa.series_id=s.id "
                "JOIN mangaka m ON m.id=sa.mangaka_id"):
            auth.setdefault(k, []).append(nm)
        vols = dict(con.execute(
            "SELECT s.series_key, MAX(v.number) FROM series s "
            "JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id "
            "GROUP BY s.series_key"))
        filled = 0
        for k, title, subt, kana, yr in con.execute(
                "SELECT series_key, title, subtitle, title_kana, year_started FROM series"):
            if k in sk_aid and k not in s3:
                s3[k] = {"s3_key": k, "s3_title": title or "", "s3_kana": kana or "",
                         "s3_year": str(yr or ""), "s3_vols": str(vols.get(k) or ""),
                         "s3_authors": "|".join(auth.get(k, []))}
                filled += 1
        con.close()
        print(f"sqlite fallback: {filled:,}/{len(missing):,} キーの証拠を種2から補完")

    wq = json.load((ROOT / ".cache/work-qid-map.json").open(encoding="utf-8"))
    srn = json.load((ROOT / ".cache/anilist-author-surname.json").open(encoding="utf-8"))
    syn_ja = json.loads((ROOT / "data/seeds/synopsis-ja.json").read_text(encoding="utf-8"))

    rows = []
    vc = Counter()
    sig_c = Counter()
    for key, aid in sk_aid.items():
        r = s3.get(key)
        d = meta.get(aid)
        if not r or not d:
            # relink override は 6/13 に native完全一致で人手裁定済 → dump欠け(新しめID)でも PASS 扱い
            if not d and "+relink" in src.get(key, ""):
                rows.append((key, aid, "PASS", 0, "relink_override(no_meta)", "", src.get(key, ""), "", "", "", "", ""))
                vc["PASS"] += 1
                continue
            rows.append((key, aid, "NO_DATA", 0, "no_meta" if not d else "no_s3row", "", src.get(key, ""), "", "", "", "", ""))
            vc["NO_DATA"] += 1
            continue
        t = d.get("title") or {}
        sigs = []
        score = 0
        # --- T+ 題完全一致(native/english/synonyms)
        page_t = tnorm(r["s3_title"])
        sub = ""
        m = re.search(r"\|sub:([^|]+)", key)
        if m:
            sub = m.group(1)
        cand_titles = {tnorm(t.get("native")), tnorm(t.get("english")), tnorm(t.get("romaji"))}
        cand_titles |= {tnorm(x) for x in (d.get("synonyms") or [])}
        cand_titles.discard("")
        if page_t and (page_t in cand_titles or (sub and tnorm(r["s3_title"] + sub) in cand_titles)):
            sigs.append("T+")
            score += 3
        # --- R+ romaji 骨格一致(副題込み可 = S3_romaji_tail の精緻化)
        if "T+" not in sigs:
            kana = re.sub(r"[\s　]", "", r.get("s3_kana") or "")
            ksk = kana_skel(kana)
            ksk_sub = kana_skel(kana + (sub or ""))
            ask = skel(t.get("romaji") or "")
            if ask and (ask == ksk or (sub and ask == ksk_sub)
                        or (ksk and abs(len(ask) - len(ksk)) <= max(2, len(ksk) // 6) and (ask.startswith(ksk[:6]) if len(ksk) >= 6 else ask == ksk))):
                sigs.append("R+")
                score += 2
        # --- W+ Wikidata ラベル一致
        w = wq.get(str(aid)) or {}
        wl = tnorm(w.get("label"))
        if wl and page_t and (wl == page_t or (sub and wl == tnorm(r["s3_title"] + sub))):
            sigs.append("W+")
            score += 3
        # --- A+ 著者 overlap
        a_forms = staff_forms(d)
        s_forms = set()
        for nm in (r.get("s3_authors") or "").split("|"):
            a = anorm(nm)
            if len(a) >= 2:
                s_forms.add(a)
            sn = srn.get(nm.strip())
            if sn and len(sn) >= 3:
                s_forms.add(sn)
        if a_forms & s_forms:
            sigs.append("A+")
            score += 1
        # --- Y 年
        try:
            sy = int(r.get("s3_year") or 0)
        except ValueError:
            sy = 0
        ay = ((d.get("startDate") or {}).get("year")) or 0
        if sy and ay:
            dy = abs(sy - ay)
            if dy <= 1:
                sigs.append("Y+")
                score += 1
            elif dy >= 4:
                sigs.append("Y-")
                score -= 1
        # --- V 巻数
        try:
            s3v = int(r.get("s3_vols") or 0)
        except ValueError:
            s3v = 0
        av = d.get("volumes")
        if s3v and av:
            if abs(s3v - av) <= 1:
                sigs.append("V+")
                score += 2
            elif max(s3v, av) <= 2 * min(s3v, av):
                sigs.append("V~")
                score += 1
        # --- 強負
        fmt = d.get("format")
        if fmt == "ONE_SHOT" and s3v >= 2:
            sigs.append("F-")
            score -= 3
        if av and (s3v >= max(5, 4 * av) or (s3v >= 2 and av >= 4 * s3v)):
            sigs.append("G-")
            score -= 2
        ch = d.get("chapters")
        if fmt == "MANGA" and ch and ch <= 6 and s3v >= 3:
            sigs.append("C-")
            score -= 2
        # --- verdict
        if "T+" in sigs or "W+" in sigs:
            v = "PASS"
        elif score >= 3:
            v = "PASS"
        elif score <= -2:
            v = "FAIL"
        else:
            v = "SUSPECT"
        vc[v] += 1
        for sg in sigs:
            sig_c[sg] += 1
        if v != "PASS":
            vc[f"{v}_syn"] += 1 if str(aid) in syn_ja else 0
        rows.append((key, aid, v, score, "|".join(sigs), (t.get("romaji") or "")[:50], src.get(key, ""),
                     r["s3_title"], sub, r.get("s3_year") or "", r.get("s3_vols") or "",
                     (r.get("s3_authors") or "")[:120]))

    out = ROOT / ".cache/anilist-gate.tsv"
    clean = lambda v: re.sub(r"[\t\n\r]", " ", str(v))
    with out.open("w", encoding="utf-8") as f:
        f.write("key\ta_id\tgate\tscore\tsignals\ta_romaji\tsrc\ts3_title\ts3_sub\ts3_year\ts3_vols\ts3_authors\n")
        for x in rows:
            f.write("\t".join(clean(v) for v in x) + "\n")

    print(f"\n=== 検証ゲート合議 ({len(rows):,}リンク) ===")
    for k in ("PASS", "SUSPECT", "FAIL", "NO_DATA"):
        extra = f" (うちsynopsis表示中 {vc[f'{k}_syn']:,})" if vc.get(f"{k}_syn") else ""
        print(f"  {k:8}: {vc[k]:,}{extra}")
    print("シグナル分布:", dict(sig_c.most_common()))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
