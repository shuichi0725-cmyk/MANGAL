"""⑥ 著者経由recall の適用版(慎重)。 _audit-recall-authorroute.py の調査ロジックを
適用可能形(s3_key + a_id)にし、 ★高信頼サブセットだけ採る:

  - 同一著者(romaji↔カナ橋渡し・翻訳role除外)∧ **title_key 完全一致のみ**
    (substring一致は過マッチFP源なので不採用)
  - v14 S-tier / recovery で既に結線済みは除外(増分のみ)
  - 1:1保守: a_id が既に他keyで結線済 or 同a_idに複数key競合 → skip
出力 = .cache/match-recall-authorroute.tsv(recovery と同形: s3_key,a_id,a_native,note)。
  enrich builder が recovery と同様に追加読み。 ★本番反映は次回 enrich再構築+promote。
"""
import gzip, json, csv, re, sys, unicodedata
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / ".cache/anilist-manga-dump.jsonl.gz"
V14 = ROOT / ".cache/match-v14-all.tsv"
RECOV = ROOT / ".cache/match-recovery.tsv"
OUT = ROOT / ".cache/match-recall-authorroute.tsv"
S = {"S180", "S150", "S130", "S100"}

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
    s = s.lower().replace("-", ""); out = []; i = 0
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
    s = hira_to_kata(s); s = strip_punct(s)
    s = re.sub(r"[\s　・]+", "", s)
    return s.lower()


def author_forms(name):
    if not name: return set()
    name = unicodedata.normalize("NFKC", name)
    base = re.sub(r"[\s　・･.,，、!！'’\"]+", "", name).lower()
    forms = {base}
    if re.search(r"[a-z]", base):
        k = re.sub(r"[\s　・]+", "", hepburn_to_kata(name)).lower()
        if k: forms.add(k)
    forms.add(re.sub(r"[\s　・]+", "", hira_to_kata(name)).lower())
    return {f for f in forms if len(f) >= 2}


NONAUTHOR_ROLE = re.compile(r"translat|letter|assist|editor|design|proofread", re.I)


def main():
    # AniList 著者 index: form → [(aid, native, title_key, pop)]
    author_works = defaultdict(list)
    aid_pop = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            native = (m.get("title") or {}).get("native") or ""
            tk = title_key(native)
            if not tk: continue
            aid = m.get("id"); aid_pop[aid] = m.get("popularity") or 0
            forms = set()
            for edge in ((m.get("staff") or {}).get("edges") or []):
                if NONAUTHOR_ROLE.search(edge.get("role") or ""): continue
                nm = (edge.get("node") or {}).get("name") or {}
                for v in (nm.get("native"), nm.get("full")):
                    forms |= author_forms(v)
            for fm in forms:
                author_works[fm].append((aid, native, tk))

    # 既結線(v14 S + recovery)= 除外。 a_id の占有(1:1)も記録。
    covered_keys = set(); used_aid = set()
    for r in csv.DictReader(V14.open(encoding="utf-8"), delimiter="\t"):
        if r["verdict"] in S and r["a_id"]:
            covered_keys.add(r["s3_key"]); used_aid.add(int(r["a_id"]))
    if RECOV.exists():
        for r in csv.DictReader(RECOV.open(encoding="utf-8"), delimiter="\t"):
            if r.get("a_id"):
                covered_keys.add(r["s3_key"]); used_aid.add(int(r["a_id"]))

    # 非Sを著者×exact題で回収(増分のみ)
    cand = {}      # s3_key → (aid, native)
    aid_to_keys = defaultdict(set)
    samples = []
    n_seen = 0
    for r in csv.DictReader(V14.open(encoding="utf-8"), delimiter="\t"):
        if r["verdict"] in S:
            continue
        key = r["s3_key"]
        if key in covered_keys:
            continue
        s3auth = [a for a in (r.get("s3_authors") or "").split("|") if a.strip()]
        if not s3auth:
            continue
        s3tk = title_key(r["s3_title"])
        if not s3tk or len(s3tk) < 2:
            continue
        sforms = set()
        for a in s3auth:
            sforms |= author_forms(a)
        # 同一著者の作品で title_key 完全一致(exact のみ)
        hits = {}
        for fm in sforms:
            for (aid, native, atk) in author_works.get(fm, []):
                if atk == s3tk:
                    hits[aid] = native
        if not hits:
            continue
        n_seen += 1
        # 複数 a_id 候補 → pop 最大1つ(同点は曖昧=skip)
        best = sorted(hits.items(), key=lambda kv: -aid_pop.get(kv[0], 0))
        if len(best) >= 2 and aid_pop.get(best[0][0], 0) == aid_pop.get(best[1][0], 0):
            continue  # 同点曖昧
        aid, native = best[0]
        if aid in used_aid:
            continue  # 既に他で使用=1:1保守skip
        cand[key] = (aid, native)
        aid_to_keys[aid].add(key)

    # a_id に複数 s3_key が群がる=曖昧 → 全部skip(1:1保守)
    final = {k: v for k, v in cand.items() if len(aid_to_keys[v[0]]) == 1}
    dropped_multi = len(cand) - len(final)

    with OUT.open("w", encoding="utf-8") as f:
        f.write("s3_key\ta_id\ta_native\tnote\n")
        for k, (aid, native) in sorted(final.items()):
            f.write(f"{k}\t{aid}\t{native}\tauthorroute-exact\n")

    print(f"非S×著者有×exact題一致(増分): 候補 {n_seen:,}")
    print(f"  1:1保守skip(a_id既使用/複数key群がり): {n_seen - len(final):,}(うち複数key {dropped_multi:,})")
    print(f"  ★採用(recovery-2): {len(final):,} → {OUT}")
    # FPサンプル
    import itertools
    print("\n=== 採用サンプル(FP検証用) ===")
    for k, (aid, native) in itertools.islice(sorted(final.items()), 25):
        print(f"  {k[:50]:<50} → {native} [{aid}]")


if __name__ == "__main__":
    main()
