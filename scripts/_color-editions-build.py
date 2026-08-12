#!/usr/bin/env python3
"""電子カラー版柱②: harvest生データ→シリーズ束ね→本番頁照合→seed+公開JSON生成。

入力: .cache/kobo-color-raw.jsonl(_kobo-color-harvest.py)
出力:
  - data/seeds/color-editions.yml           … slug結線済みの確定seed(全置換再生成。一次ソースはraw+本監査)
  - public/data/color-editions.json         … 頁表示用 {slug: {v,u,c,b?}} (v=巻数,u=affiliateUrl,c=cover,b=BookLive title_id)
  - docs/production-diagnostics/color-editions-unmatched.tsv … 未照合/著者不一致の裁定queue

照合規則(= 同題decoy対策。巻抜けfillの教訓を踏襲):
  - ノイズ除外: 分冊版/単話/話売り/合本版/セット を title/seriesName に含む冊は捨てる
  - シリーズ束ね key = seriesName(無ければ title の巻トークン剥がし)
  - base題 = 束ねkeyから「カラー版」系マーカーを剥がした残差 → norm完全一致で本番題/別題と照合
  - ★著者ゲート: 題一致でも著者(norm)交差ゼロなら採用しない(→unmatched TSV)
  - 試し読み(b)は 種seed data/seeds/color-tameshiyomi.jsonl(③ 別harvest・純粋追記)から結線
"""
import sys, io, json, os, re, unicodedata
from pathlib import Path
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _idx_authors import au_names  # noqa: E402

RAW = ROOT / ".cache" / "kobo-color-raw.jsonl"
SEED = ROOT / "data" / "seeds" / "color-editions.yml"
PUB = ROOT / "public" / "data" / "color-editions.json"
TAME = ROOT / "data" / "seeds" / "color-tameshiyomi.jsonl"
UNMATCHED = ROOT / "docs" / "production-diagnostics" / "color-editions-unmatched.tsv"

NOISE = re.compile(r"分冊|単話|話売|合本|セット|巻セット|【期間限定|お試し|無料|よりぬき|傑作選|特別編集")
COLOR_MARK = re.compile(r"[【\[（(［]?\s*(?:デジタル)?(?:フル|完全|オール|セミ|総)?カラー版\s*[】\])）］]?")
# ★「フルカラー」等の版なし表記(2026-08-13): harvest側は検索語に入っていたのに本判定が
#   「カラー版」substringのみで4,705冊/511群を丸ごと捨てていた。括弧付き【フルカラー】/(フルカラー)
#   と末尾裸フルカラーだけをマーカー扱い(裸カラーの誤剥がしは避ける)。採否は従来どおり
#   本番頁照合+著者ゲートが決める=紙の無いwebtoon/TL系は自然に落ちる。
FC_MARK = re.compile(r"[【（(［\[]\s*(?:デジタル)?(?:フル|完全|オール|セミ|総)カラー\s*[】）)\]］]|(?:フル|完全|オール|セミ|総)カラー\s*$")


def has_color_mark(s: str) -> bool:
    return bool(s) and ("カラー版" in s or bool(FC_MARK.search(s)))
VOL_PAT = re.compile(r"[（(【]?\s*(\d{1,3})\s*[)）】]?\s*(?:巻)?\s*$")
LEAD_BRACKET = re.compile(r"^【[^】]{1,20}】")  # 誌名prefix(【花とゆめプチ】等)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[\s　]+", "", s)
    s = re.sub(r"[〜~ー\-–—−‐‑‒・･。、．，,.:：;；!！?？'’\"”「」『』【】\[\]［］（）()/／＋+＆&☆★♪]", "", s)
    return s.lower()


def parse_vol(title: str):
    t = unicodedata.normalize("NFKC", str(title or "")).strip()
    m = VOL_PAT.search(t)
    if m:
        return t[: m.start()].strip(), int(m.group(1))
    return t, None


def main():
    rows = [json.loads(l) for l in RAW.open(encoding="utf-8")]
    print(f"raw {len(rows)}冊")
    groups: dict[str, dict] = {}
    dropped_noise = 0
    for r in rows:
        title = r.get("title") or ""
        sname = r.get("seriesName") or ""
        if NOISE.search(title) or NOISE.search(sname):
            dropped_noise += 1
            continue
        if not (has_color_mark(title) or has_color_mark(sname)):
            # カラー表記なし(サブタイトル側hit等)は対象外
            dropped_noise += 1
            continue
        base_t, vol = parse_vol(title)
        gkey = norm(sname) if sname else norm(base_t)
        if not gkey:
            continue
        g = groups.setdefault(gkey, {"display": sname or base_t, "items": []})
        g["items"].append({**r, "_vol": vol})
    print(f"シリーズ束ね: {len(groups)}群 (ノイズ除外{dropped_noise}冊)")

    # 本番題→slug map (title + alt titles、著者付き)
    idx = json.load(open(ROOT / "data" / "manga-list-index.json", encoding="utf-8"))
    f = idx["f"]
    si, ti, ai = f.index("slug"), f.index("title"), f.index("authors")
    oi = f.index("original_authors")
    sbi = f.index("subtitle")
    by_title: dict[str, list] = {}
    slug_authors: dict[str, set] = {}
    for d in idx["d"]:
        slug, title = d[si], d[ti]
        au = {norm(n) for n in au_names(d[ai])} | {norm(n) for n in au_names(d[oi])}
        slug_authors[slug] = {a for a in au if a}
        by_title.setdefault(norm(title), []).append(slug)
        # 副題連結キー(かぐや様〜天才たちの恋愛頭脳戦〜型: Kobo題は本題+副題で来る)
        if d[sbi]:
            by_title.setdefault(norm(str(title) + str(d[sbi])), []).append(slug)
        # 末尾括弧除去キー(2.5次元の誘惑(リリサ)型: Kobo題は括弧無しで来る)
        t2 = re.sub(r"[（(][^（()）]{1,15}[)）]\s*$", "", str(title)).strip()
        if t2 and t2 != str(title):
            by_title.setdefault(norm(t2), []).append(slug)
    alt = json.load(open(ROOT / "data" / "manga-alt-index.json", encoding="utf-8"))
    for slug, alts in (alt.items() if isinstance(alt, dict) else []):
        for a in alts if isinstance(alts, list) else []:
            if isinstance(a, str) and a.strip():
                by_title.setdefault(norm(a), []).append(slug)

    # 試し読みseed(③)
    tame: dict[str, str] = {}
    if TAME.exists():
        for l in TAME.open(encoding="utf-8"):
            try:
                t = json.loads(l)
                if t.get("slug") and t.get("title_id"):
                    tame[t["slug"]] = str(t["title_id"])
            except Exception:
                pass

    matched, unmatched = [], []
    for gkey, g in sorted(groups.items()):
        items = g["items"]
        base = COLOR_MARK.sub("", g["display"])
        base = FC_MARK.sub("", base)
        base = LEAD_BRACKET.sub("", base)
        base_n = norm(base)
        vols = [i["_vol"] for i in items if i["_vol"]]
        n_vols = max(vols) if vols else len(items)
        first = min(items, key=lambda i: i["_vol"] or 999)
        g_authors = set()
        for i in items:
            for nm in re.split(r"[/,、／]", str(i.get("author") or "")):
                if norm(nm):
                    g_authors.add(norm(nm))
        cands = list(dict.fromkeys(by_title.get(base_n, [])))
        if not cands:
            # fallback: ー読み/副題ー 挟み込み除去(NARUTOーナルトー/るろうに剣心ー明治剣客浪漫譚ー型)
            b2 = re.sub(r"[ー\-−–—]\s*[^ー\-−–—]{1,25}\s*[ー\-−–—]\s*$", "", unicodedata.normalize("NFKC", base)).strip()
            if b2 and norm(b2) != base_n:
                cands = list(dict.fromkeys(by_title.get(norm(b2), [])))
        part_no = None  # 「第N部」畳み込みで結線した時の部番号(=同一slug合算merge用)
        if not cands:
            # ★追加fallback(2026-08-13。誤候補は後段の著者ゲートが落とす):
            #   ①「第N部」トークン除去 = ジョジョ第6部型(頁題=ジョジョの奇妙な冒険 ストーンオーシャン)
            #   ②「第N部」より前を全部除去 = ジョジョリオン型(頁題=部題のみ)
            #   ③中間の ー読みー 挿し込み除去 = To LOVEるーとらぶるーダークネス型(末尾でなく中間)
            nf = unicodedata.normalize("NFKC", base)
            for b3 in (
                re.sub(r"\s*第[0-9一二三四五六七八九十]{1,3}部\s*", " ", nf),
                re.sub(r"^.*?第[0-9一二三四五六七八九十]{1,3}部\s*", "", nf),
                re.sub(r"ー[^ー]{1,25}ー", "", nf, count=1),
            ):
                b3 = b3.strip()
                if b3 and norm(b3) != base_n:
                    cands = list(dict.fromkeys(by_title.get(norm(b3), [])))
                    if cands:
                        break
        if not cands:
            # ④「第N部」より前=シリーズ本題で照合(ジョジョ第1〜5部型: 紙の本編頁は部をまたぐ1シリーズ)。
            #   ★N≤5に限定=6部以降は別頁が正(ストーンオーシャン/SBR/ジョジョリオン)なので本編へ誤畳込しない。
            #   同一slugに複数部が畳まれたら後段で巻数を合算し表示題を本題+カラー版に付け替える。
            KJ = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
            m = re.match(r"^(.{2,40}?)\s*第([0-9]{1,2}|[一二三四五])部", unicodedata.normalize("NFKC", base))
            if m:
                pn = KJ.get(m.group(2)) or int(m.group(2))
                pref = m.group(1).strip()
                if pn <= 5 and pref:
                    cands = list(dict.fromkeys(by_title.get(norm(pref), [])))
                    if cands:
                        part_no = pn
                        base = pref
        hit = None
        for slug in cands:
            if g_authors & slug_authors.get(slug, set()):
                hit = slug
                break
        if hit is None and len(cands) == 1 and not g_authors:
            hit = cands[0]
        rec = {
            "display": g["display"], "base": base.strip(), "volumes": n_vols,
            "items": len(items), "publisher": first.get("publisherName"),
            "url": first.get("affiliateUrl") or first.get("itemUrl"),
            "cover": first.get("largeImageUrl"),
            "latest": max((str(i.get("salesDate") or "") for i in items), default=""),
            "authors": sorted(g_authors),
        }
        if part_no is not None:
            # 部畳み込み: 表示題=本題+カラー版(部題を出さない)。部番号は合算mergeのキー
            rec["display"] = f"{base.strip()} カラー版"
            rec["_part"] = part_no
        if hit:
            matched.append({"slug": hit, **rec})
        else:
            unmatched.append({**rec, "title_cands": "|".join(cands[:3])})

    # slug重複(同作の表記揺れ群) → 巻数最大の群を採用。★部畳み込み同士(ジョジョ1〜5部型)は巻数を合算
    by_slug: dict[str, dict] = {}
    for m in matched:
        cur = by_slug.get(m["slug"])
        if cur is not None and "_part" in m and "_part" in cur:
            keep = m if m["_part"] < cur["_part"] else cur  # 表紙/URLは若い部(=1部の1巻)を採用
            by_slug[m["slug"]] = {**keep,
                                  "volumes": cur["volumes"] + m["volumes"],
                                  "latest": max(cur["latest"], m["latest"]),
                                  "_part": min(cur["_part"], m["_part"])}
        elif cur is None or m["volumes"] > cur["volumes"]:
            by_slug[m["slug"]] = m
    print(f"照合: slug確定 {len(by_slug)}作 / unmatched {len(unmatched)}群")

    today = date.today().isoformat()
    with SEED.open("w", encoding="utf-8", newline="\n") as fo:
        fo.write("# 電子カラー版seed(自動生成: _color-editions-build.py。一次ソース=.cache/kobo-color-raw.jsonl)\n")
        fo.write(f"# 再生成しても純粋追記のtameshiyomi seedとunmatched裁定は失われない。generated_at: {today}\n")
        fo.write("entries:\n")
        for slug in sorted(by_slug):
            m = by_slug[slug]
            fo.write(f"- slug: {slug}\n")
            fo.write(f"  display: {json.dumps(m['display'], ensure_ascii=False)}\n")
            fo.write(f"  volumes: {m['volumes']}\n")
            fo.write(f"  publisher: {json.dumps(m['publisher'], ensure_ascii=False)}\n")
            fo.write(f"  url: {json.dumps(m['url'], ensure_ascii=False)}\n")
            fo.write(f"  latest: {json.dumps(m['latest'], ensure_ascii=False)}\n")
            fo.write("  store: kobo\n")

    pub = {}
    for slug, m in by_slug.items():
        e = {"v": m["volumes"], "u": m["url"], "c": m["cover"], "t": m["display"]}
        if slug in tame:
            e["b"] = tame[slug]
        pub[slug] = e
    os.makedirs(PUB.parent, exist_ok=True)
    json.dump(pub, PUB.open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"seed {len(by_slug)}作 / public JSON {os.path.getsize(PUB)}B / 試し読み結線 {sum(1 for v in pub.values() if 'b' in v)}作")

    os.makedirs(UNMATCHED.parent, exist_ok=True)
    with UNMATCHED.open("w", encoding="utf-8", newline="\n") as fo:
        fo.write("display\tbase\tvolumes\tauthors\tpublisher\tlatest\ttitle_cands\n")
        for u in sorted(unmatched, key=lambda x: -x["volumes"]):
            fo.write(f"{u['display']}\t{u['base']}\t{u['volumes']}\t{','.join(u['authors'])}\t{u['publisher']}\t{u['latest']}\t{u['title_cands']}\n")
    print(f"unmatched TSV → {UNMATCHED}")


if __name__ == "__main__":
    main()
