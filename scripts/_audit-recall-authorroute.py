"""B = 著者経由 recall の実測(調査)。

A の発見: 著者照合が romaji↔カタカナ を橋渡しせず、 翻訳者混入で偽MISMATCH。
本実験: 改良著者正規化(romaji→カナ橋渡し + ひら→カナ + 翻訳者role除外)で
AniList 著者→作品 index を作り、 NO_MATCH 種3(著者有)から
「同一著者の作品に題が一致する」ものを拾えるか実測。

※調査専用。 v9 canonical も種3も変更しない。
出力: 回収件数 + サンプル(.cache/recall-authorroute.tsv)
"""
import gzip, json, csv, re, sys, unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DUMP = Path(".cache/anilist-manga-dump.jsonl.gz")
TSV = Path(".cache/match-v9-all.tsv")

# --- v9 から流用した正規化 ---
CONSONANTS = set("kgsztdnhbpmyrwfjcv")
SYL_3 = {"kya":"キャ","kyu":"キュ","kyo":"キョ","sha":"シャ","shu":"シュ","sho":"ショ",
 "cha":"チャ","chu":"チュ","cho":"チョ","tsu":"ツ","nya":"ニャ","nyu":"ニュ","nyo":"ニョ",
 "hya":"ヒャ","hyu":"ヒュ","hyo":"ヒョ","mya":"ミャ","myu":"ミュ","myo":"ミョ",
 "rya":"リャ","ryu":"リュ","ryo":"リョ","gya":"ギャ","gyu":"ギュ","gyo":"ギョ",
 "jya":"ジャ","jyu":"ジュ","jyo":"ジョ","bya":"ビャ","byu":"ビュ","byo":"ビョ",
 "pya":"ピャ","pyu":"ピュ","pyo":"ピョ","shi":"シ","chi":"チ"}
SYL_2 = {"ka":"カ","ki":"キ","ku":"ク","ke":"ケ","ko":"コ","ga":"ガ","gi":"ギ","gu":"グ",
 "ge":"ゲ","go":"ゴ","sa":"サ","si":"シ","su":"ス","se":"セ","so":"ソ","za":"ザ","zi":"ジ",
 "zu":"ズ","ze":"ゼ","zo":"ゾ","ta":"タ","ti":"チ","tu":"ツ","te":"テ","to":"ト","da":"ダ",
 "di":"ヂ","du":"ヅ","de":"デ","do":"ド","na":"ナ","ni":"ニ","nu":"ヌ","ne":"ネ","no":"ノ",
 "ha":"ハ","hi":"ヒ","fu":"フ","he":"ヘ","ho":"ホ","ba":"バ","bi":"ビ","bu":"ブ","be":"ベ",
 "bo":"ボ","pa":"パ","pi":"ピ","pu":"プ","pe":"ペ","po":"ポ","ma":"マ","mi":"ミ","mu":"ム",
 "me":"メ","mo":"モ","ya":"ヤ","yu":"ユ","yo":"ヨ","ra":"ラ","ri":"リ","ru":"ル","re":"レ",
 "ro":"ロ","wa":"ワ","wo":"ヲ","ja":"ジャ","ju":"ジュ","jo":"ジョ","fa":"ファ","fi":"フィ",
 "fe":"フェ","fo":"フォ","vu":"ヴ"}
SYL_1 = {"a":"ア","i":"イ","u":"ウ","e":"エ","o":"オ","n":"ン"}


def hepburn_to_kata(s):
    if not s: return ""
    s = s.lower().replace("-", "")
    out = []; i = 0
    while i < len(s):
        c = s[i]
        if not c.isascii(): out.append(c); i += 1; continue
        if not c.isalpha(): i += 1; continue
        if i+1 < len(s) and c == s[i+1] and c in CONSONANTS: out.append("ッ"); i += 1; continue
        if i+3 <= len(s) and s[i:i+3] in SYL_3: out.append(SYL_3[s[i:i+3]]); i += 3; continue
        if i+2 <= len(s) and s[i:i+2] in SYL_2: out.append(SYL_2[s[i:i+2]]); i += 2; continue
        if c in SYL_1: out.append(SYL_1[c]); i += 1; continue
        i += 1
    return "".join(out)


def hira_to_kata(s):
    return "".join(chr(ord(c)+0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def strip_punct(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "P" and ch not in "ー―~〜")


def title_key(s):
    if not s: return ""
    s = re.split(r"[:：]", s, 1)[0]
    s = re.sub(r"[（(【\[].*?[）)】\]]", "", s)
    s = hira_to_kata(s)
    s = strip_punct(s)
    s = re.sub(r"[\s　・]+", "", s)
    return s.lower()


def author_forms(name):
    """1 著者名 → 正規化候補集合(romaji橋渡し + ひら→カナ)。"""
    if not name: return set()
    name = unicodedata.normalize("NFKC", name)
    base = re.sub(r"[\s　・･.,，、!！'’\"]+", "", name).lower()
    forms = {base}
    if re.search(r"[a-z]", base):
        k = re.sub(r"[\s　・]+", "", hepburn_to_kata(name)).lower()
        if k: forms.add(k)
    forms.add(re.sub(r"[\s　・]+", "", hira_to_kata(name)).lower())
    return {f for f in forms if len(f) >= 2}


# 翻訳/制作系 role(これらは著者として使わない)
NONAUTHOR_ROLE = re.compile(r"translat|letter|assist|editor|design|proofread", re.I)


def main():
    # AniList 著者 index(role フィルタ + 改良正規化)
    author_works = defaultdict(list)  # form → [(aid, native, romaji, year)]
    n_works = 0
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            n_works += 1
            native = (m.get("title") or {}).get("native") or ""
            romaji = (m.get("title") or {}).get("romaji") or ""
            year = (m.get("startDate") or {}).get("year")
            tk = title_key(native)
            if not tk: continue
            forms = set()
            for edge in ((m.get("staff") or {}).get("edges") or []):
                role = edge.get("role") or ""
                if NONAUTHOR_ROLE.search(role): continue
                nm = (edge.get("node") or {}).get("name") or {}
                for v in (nm.get("native"), nm.get("full")):
                    forms |= author_forms(v)
            rec = (m.get("id"), native, romaji, year, tk)
            for fm in forms:
                author_works[fm].append(rec)
    print(f"AniList works: {n_works:,}, 著者form index: {len(author_works):,}", flush=True)

    # 非Sマッチ(NO_MATCH/DISPLACED/REJECT)を著者経由で照合
    from collections import Counter
    recovered = []
    n_auth = Counter(); n_rec = Counter()
    TARGETS = {"NO_MATCH", "DISPLACED", "REJECT"}
    with TSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            v = r["verdict"]
            if v not in TARGETS: continue
            s3auth = [a for a in (r["s3_authors"] or "").split("|") if a.strip()]
            if not s3auth: continue
            n_auth[v] += 1
            s3tk = title_key(r["s3_title"])
            if not s3tk: continue
            sforms = set()
            for a in s3auth: sforms |= author_forms(a)
            cands = {}
            for fm in sforms:
                for rec in author_works.get(fm, []):
                    cands[rec[0]] = rec
            for aid, (aid2, native, romaji, year, atk) in cands.items():
                if s3tk == atk or (len(s3tk) >= 4 and (s3tk in atk or atk in s3tk)):
                    n_rec[v] += 1
                    recovered.append((v, r["s3_title"], "|".join(s3auth), native, romaji, year))
                    break

    print()
    for v in ["NO_MATCH", "DISPLACED", "REJECT"]:
        a = n_auth[v]; rc = n_rec[v]
        print(f"{v}(著者有 {a:,}) → 著者経由回収 {rc:,} ({rc*100//max(a,1)}%)")
    print(f"★合計回収可能: {len(recovered):,}")

    # 天井分析: NO_MATCH(著者有)未回収の内訳 = 著者がAniListに居るか
    author_present = author_absent = 0
    with TSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] != "NO_MATCH": continue
            s3auth = [a for a in (r["s3_authors"] or "").split("|") if a.strip()]
            if not s3auth: continue
            sforms = set()
            for a in s3auth: sforms |= author_forms(a)
            if any(fm in author_works for fm in sforms):
                author_present += 1
            else:
                author_absent += 1
    print(f"\n=== 天井分析(NO_MATCH 著者有) ===")
    print(f"  著者がAniListに実在: {author_present:,}  ← 題正規化改善で更に回収余地")
    print(f"  著者もAniListに無い: {author_absent:,}  ← 真にAniList未収録(回収不可)")

    with open(".cache/recall-authorroute.tsv", "w", encoding="utf-8") as f:
        f.write("verdict\ts3_title\ts3_authors\ta_native\ta_romaji\ta_year\n")
        for row in recovered:
            f.write("\t".join(str(x) for x in row) + "\n")
    print("wrote .cache/recall-authorroute.tsv")


if __name__ == "__main__":
    main()
