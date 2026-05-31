"""③ 種3読み誤り(MADB+種a一致・種3別)を MADB ja-hrkt の正読で訂正。

正読 = 種a と一致する MADB ja-hrkt 読み(原文=分かち書き)。
  title_kana           = 正読(スペース除去)
  title_kana_segmented = 正読(スペースあり、 MADBの分かち書きをそのまま)
★種3 上書き(deliberate fix、 ユーザGO)。 surgical 行置換、 .new 検証→ --apply で確定。
出力: .cache/kana-corrections.tsv(レビュー用)。
"""
import pickle, csv, sqlite3, re, sys, unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PKL = Path(".cache/seed3-promote.pkl")
MADB_KANA = Path(".cache/madb-isbn-kana.tsv")
MATCH = Path(".cache/match-v14-all.tsv")
DB = Path(".cache/db-v2.sqlite")
YML = Path("data/seeds/series-supplement-v2.yml")
S = {"S180", "S150", "S130", "S100"}

# romaji→kata(_audit-kana-3source と同一)
CONSONANTS = set("kgsztcdnhfbpmyrwvj")
SYL_3 = {"kya":"キャ","kyu":"キュ","kyo":"キョ","sha":"シャ","shu":"シュ","sho":"ショ","shi":"シ","cha":"チャ","chu":"チュ","cho":"チョ","chi":"チ","tsu":"ツ","nya":"ニャ","nyu":"ニュ","nyo":"ニョ","hya":"ヒャ","hyu":"ヒュ","hyo":"ヒョ","gya":"ギャ","gyu":"ギュ","gyo":"ギョ","ja":"ジャ","ju":"ジュ","jo":"ジョ","rya":"リャ","ryu":"リュ","ryo":"リョ","bya":"ビャ","byu":"ビュ","byo":"ビョ","pya":"ピャ","pyu":"ピュ","pyo":"ピョ","mya":"ミャ","myu":"ミュ","myo":"ミョ"}
SYL_2 = {"ka":"カ","ki":"キ","ku":"ク","ke":"ケ","ko":"コ","ga":"ガ","gi":"ギ","gu":"グ","ge":"ゲ","go":"ゴ","sa":"サ","su":"ス","se":"セ","so":"ソ","za":"ザ","ji":"ジ","zu":"ズ","ze":"ゼ","zo":"ゾ","ta":"タ","te":"テ","to":"ト","da":"ダ","de":"デ","do":"ド","na":"ナ","ni":"ニ","nu":"ヌ","ne":"ネ","no":"ノ","ha":"ハ","hi":"ヒ","fu":"フ","he":"ヘ","ho":"ホ","ba":"バ","bi":"ビ","bu":"ブ","be":"ベ","bo":"ボ","pa":"パ","pi":"ピ","pu":"プ","pe":"ペ","po":"ポ","ma":"マ","mi":"ミ","mu":"ム","me":"メ","mo":"モ","ya":"ヤ","yu":"ユ","yo":"ヨ","ra":"ラ","ri":"リ","ru":"ル","re":"レ","ro":"ロ","wa":"ワ","wo":"ヲ"}
SYL_1 = {"a":"ア","i":"イ","u":"ウ","e":"エ","o":"オ","n":"ン"}
SMALL = str.maketrans("ァィゥェォッャュョ", "アイウエオツヤユヨ")


def romaji_to_kata(s):
    if not s: return ""
    s = s.lower(); out = []; i = 0
    while i < len(s):
        c = s[i]
        if not c.isalpha(): i += 1; continue
        if i+1 < len(s) and c == s[i+1] and c in CONSONANTS: out.append("ッ"); i += 1; continue
        if s[i:i+3] in SYL_3: out.append(SYL_3[s[i:i+3]]); i += 3; continue
        if s[i:i+2] in SYL_2: out.append(SYL_2[s[i:i+2]]); i += 2; continue
        if c in SYL_1: out.append(SYL_1[c]); i += 1; continue
        i += 1
    return "".join(out)


def kata_norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(chr(ord(c)+0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "P" and ch not in "ー―‐~〜　 ")
    return s.translate(SMALL)


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def compute():
    d = pickle.load(PKL.open("rb"))
    isbn_kana = {}
    with MADB_KANA.open(encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t"):
            if len(r) >= 3 and r[2]:
                isbn_kana[r[0]] = [k for k in r[2].split("|") if k]
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    sk_madb = defaultdict(list)   # series_key → [(orig_spaced, norm)]
    for sk, isbn in con.execute("""SELECT s.series_key, v.isbn13 FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE v.isbn13 IS NOT NULL"""):
        for k in isbn_kana.get(str(isbn).replace("-", "").strip(), []):
            sk_madb[sk].append((k, kata_norm(k)))
    con.close()
    sk_a = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r.get("a_romaji"):
                ar = re.split(r"[:：]\s", r["a_romaji"], 1)[0]
                sk_a[r["s3_key"]] = kata_norm(romaji_to_kata(ar))

    fixes = []  # (key, title, old_kana, correct_spaced)
    for e in d.values():
        key = e["key"]; kana = e.get("title_kana") or ""
        if not kana: continue
        k3 = kata_norm(kana)
        madb = sk_madb.get(key, []); a = sk_a.get(key)
        if not madb or not a: continue
        norms = {m for _, m in madb}
        if k3 in norms:   # ① 正当
            continue
        # ③ = 種3≠MADB だが MADB に種a一致読みあり → その原文を正読に
        cand = [orig for orig, m in madb if m == a]
        if cand:
            correct = max(cand, key=len)   # 分かち書きが残る長い方
            fixes.append((key, base_title(key), kana, correct))
    return fixes


def yaml_scalar(v):
    """正しくクォートした YAML スカラ値(文書終端 ... を含まない)。"""
    import yaml
    line = yaml.safe_dump({"_": v}, allow_unicode=True, default_flow_style=False, width=10**9)
    return line.split(":", 1)[1].strip()


def apply_fixes(fixes, commit):
    fixmap = {f[0]: f[3] for f in fixes}
    lines = YML.read_text(encoding="utf-8").splitlines(keepends=True)
    KEY = re.compile(r"^  - key: (.*)$")
    out = []; cur = None; applied = 0
    for line in lines:
        m = KEY.match(line)
        if m:
            cur = m.group(1).rstrip("\n")
            if len(cur) >= 2 and cur[0] in "\"'" and cur[-1] == cur[0]:
                inner = cur[1:-1]
                cur = inner.replace('\\"', '"') if cur[0] == '"' else inner
            out.append(line); continue
        if cur in fixmap:
            sp = fixmap[cur]
            nospace = re.sub(r"[\s　]+", "", sp)
            sm = re.match(r"^(\s+)title_kana:\s", line)
            if sm:
                out.append(f"{sm.group(1)}title_kana: {yaml_scalar(nospace)}\n"); applied += 1; continue
            sm = re.match(r"^(\s+)title_kana_segmented:\s", line)
            if sm:
                out.append(f"{sm.group(1)}title_kana_segmented: {yaml_scalar(sp)}\n"); continue
        out.append(line)
    dest = YML if commit else YML.with_suffix(".yml.new")
    dest.write_text("".join(out), encoding="utf-8")
    print(f"applied title_kana 置換: {applied} / 対象 {len(fixmap)}  → {dest.name}")


def main():
    fixes = compute()
    print(f"③ 訂正対象: {len(fixes)} 件")
    with open(".cache/kana-corrections.tsv", "w", encoding="utf-8") as f:
        f.write("key\ttitle\told_kana\tcorrect_spaced\n")
        for k, t, o, c in fixes:
            f.write(f"{k}\t{t}\t{o}\t{c}\n")
    print("wrote .cache/kana-corrections.tsv")
    if "--apply" in sys.argv or "--new" in sys.argv:
        apply_fixes(fixes, commit="--apply" in sys.argv)


if __name__ == "__main__":
    main()
