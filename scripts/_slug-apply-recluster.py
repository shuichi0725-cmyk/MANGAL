"""Stage D: option2 NDL再クラスタ 31ページを data/manga.v2 へ生成。
著者確定 = .cache/ndl-recluster-full.json (dc:creator 役割付き) を採用。db-v2 は購入メタのみ。

作画家判定(優先順):
  1. role=="artist"(漫画/作画/画) の creator → 作画
  2. 無ければ: base群で「複数slugに跨る共有creator」(=原作: 山田風太郎/Key/任天堂/August等)を除いた
     当slug専有creator → 作画
  3. それでも一意に決まらない(複数作画 or 全員共有) → 全員listしFLAG
原作 = 作画に選ばれなかった creator。
combined文字列("出月こーじ, 任天堂") は読点/カンマ分割、先頭=作画候補。
title/name は二重HTMLエスケープを解く。volume は NDL vol、無ければ release昇順1..N。
出力後 .cache/recluster-authors-review.tsv に検証表(FLAG付)。
"""
import sys, os, json, csv, sqlite3, re, html
from collections import Counter, defaultdict
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, "data", "seeds", "slug-recluster-candidates.tsv")
NDL = os.path.join(ROOT, ".cache", "ndl-recluster-full.json")
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
OUTDIR = os.path.join(ROOT, "data", "manga.v2")

ndl = json.load(open(NDL, encoding="utf-8"))
rows = list(csv.DictReader(open(CAND, encoding="utf-8"), delimiter="\t"))
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row

def clean(s):
    if not s:
        return ""
    return html.unescape(html.unescape(s)).strip()

# かな(ひら/カタ)→ ローマ字: sakuga key 照合用(完全でなくて良い、 かな名のみ対象)
_R2 = {
    "きゃ":"kya","きゅ":"kyu","きょ":"kyo","しゃ":"sha","しゅ":"shu","しょ":"sho",
    "ちゃ":"cha","ちゅ":"chu","ちょ":"cho","にゃ":"nya","にゅ":"nyu","にょ":"nyo",
    "ひゃ":"hya","ひゅ":"hyu","ひょ":"hyo","みゃ":"mya","みゅ":"myu","みょ":"myo",
    "りゃ":"rya","りゅ":"ryu","りょ":"ryo","ぎゃ":"gya","ぎゅ":"gyu","ぎょ":"gyo",
    "じゃ":"ja","じゅ":"ju","じょ":"jo","びゃ":"bya","びゅ":"byu","びょ":"byo",
    "あ":"a","い":"i","う":"u","え":"e","お":"o","か":"ka","き":"ki","く":"ku","け":"ke","こ":"ko",
    "さ":"sa","し":"shi","す":"su","せ":"se","そ":"so","た":"ta","ち":"chi","つ":"tsu","て":"te","と":"to",
    "な":"na","に":"ni","ぬ":"nu","ね":"ne","の":"no","は":"ha","ひ":"hi","ふ":"fu","へ":"he","ほ":"ho",
    "ま":"ma","み":"mi","む":"mu","め":"me","も":"mo","や":"ya","ゆ":"yu","よ":"yo",
    "ら":"ra","り":"ri","る":"ru","れ":"re","ろ":"ro","わ":"wa","を":"o","ん":"n",
    "が":"ga","ぎ":"gi","ぐ":"gu","げ":"ge","ご":"go","ざ":"za","じ":"ji","ず":"zu","ぜ":"ze","ぞ":"zo",
    "だ":"da","ぢ":"ji","づ":"zu","で":"de","ど":"do","ば":"ba","び":"bi","ぶ":"bu","べ":"be","ぼ":"bo",
    "ぱ":"pa","ぴ":"pi","ぷ":"pu","ぺ":"pe","ぽ":"po","ー":"","っ":"","ぁ":"a","ぃ":"i","ぅ":"u","ぇ":"e","ぉ":"o",
}
def _kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヴ" else c for c in s)
def _romaji(name):
    s = _kata2hira(name)
    out, i = [], 0
    while i < len(s):
        if s[i] == "っ":  # 促音: 次の子音を重ねる
            nxt = _R2.get(s[i+1:i+3], "") or _R2.get(s[i+1:i+2], "") if i+1 < len(s) else ""
            if nxt and nxt[0] not in "aiueo":
                out.append(nxt[0])
            i += 1; continue
        two = s[i:i+2]
        if two in _R2:
            out.append(_R2[two]); i += 2; continue
        out.append(_R2.get(s[i], "")); i += 1
    return "".join(out)

# 会社/ブランド名は作画でなく原作扱い(作画家ではない)
_BRAND = ["株式会社", "任天堂", "Key", "August", "オーガスト", "Nintendo", "カプコン", "コナミ", "セガ"]
def is_brand(name):
    return any(b.lower() in name.lower() for b in _BRAND)
def sakuga_match(name, sakuga):
    """かな名のローマ字が sakuga key を含むか(漢字主体名は判定不能=False)。"""
    if not sakuga:
        return False
    r = _romaji(name)
    if not r:
        return False
    return sakuga in r or r in sakuga

def split_names(name):
    """combined creator 文字列を個別名に分割(読点/カンマ)。"""
    return [p.strip() for p in re.split(r"[、,]", name) if p.strip()]

_ROLE_SUFFIX = {
    "漫画": "artist", "作画": "artist", "画": "artist", "絵": "artist", "まんが": "artist", "マンガ": "artist",
    "原作": "original", "原案": "original", "著": "original", "作": "original", "原著": "original", "脚本": "original",
    "脚色": "supervisor", "構成": "supervisor", "監修": "supervisor", "編": "supervisor", "編集": "supervisor",
    "協力": "supervisor", "企画": "supervisor", "演出": "supervisor", "案": "supervisor",
}
def strip_role_suffix(name, role):
    """末尾の役割語(脚色/構成 等)を名前から剥がし role を確定。"""
    parts = name.split()
    if len(parts) >= 2 and parts[-1] in _ROLE_SUFFIX:
        return " ".join(parts[:-1]).strip(), _ROLE_SUFFIX[parts[-1]]
    return name, role

def creators_of(isbn):
    """[(name, role)] を返す。combined は分割、末尾役割語を剥がし role 確定。"""
    out = []
    for c in ndl.get(isbn, {}).get("creators", []):
        role = c.get("role")
        for nm in split_names(clean(c.get("name", ""))):
            nm2, role2 = strip_role_suffix(nm, role)
            out.append((nm2, role2))
    return out

def db_meta(isbn):
    return con.execute(
        "SELECT v.release_date, v.cover_url, v.asin, s.title_kana "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id "
        "WHERE v.isbn13=? LIMIT 1", (isbn,)).fetchone()

# base群内: creator が何slugに出るか(共有=原作 判定用)
base_cre_slug = defaultdict(lambda: defaultdict(set))
for r in rows:
    for i in r["isbns"].split(","):
        for nm, _ in creators_of(i):
            base_cre_slug[r["base"]][nm].add(r["slug"])

review = []
written = 0

for r in rows:
    slug, base, sakuga = r["slug"], r["base"], (r["sakuga"] or "").strip()
    isbns = [x for x in r["isbns"].split(",") if x]
    n_slugs_in_base = len({rr["slug"] for rr in rows if rr["base"] == base})

    # creator 集計(当slug内 出現回数 + role)。中黒/空白差の同一人物を統合。
    def _nrm(n):
        return n.replace("・", "").replace("･", "").replace(" ", "").replace("　", "")
    canon = {}  # nrm -> 代表表示名(中黒ありを優先)
    name_role = {}   # display -> set(roles)
    name_cnt = Counter()
    for i in isbns:
        for nm, role in creators_of(i):
            key = _nrm(nm)
            disp = canon.get(key)
            if disp is None or ("・" in nm and "・" not in disp):
                canon[key] = nm; disp = nm
                # 旧表示名の集計を引き継ぎ
                for old in [d for d in list(name_cnt) if _nrm(d) == key and d != nm]:
                    name_cnt[nm] += name_cnt.pop(old)
                    name_role.setdefault(nm, set()).update(name_role.pop(old, set()))
            disp = canon[key]
            name_cnt[disp] += 1
            name_role.setdefault(disp, set()).add(role)

    # 1) role=artist(ブランド名は除外)
    artists = [nm for nm in name_cnt if "artist" in name_role[nm] and not is_brand(nm)]
    # 役割が supervisor(脚色/構成/監修)のみの creator は除外候補
    def is_super_only(nm):
        rs = name_role[nm]
        return rs and rs <= {"supervisor"}
    flag = ""
    if not artists:
        # 2) 共有原作を除いた専有creator
        cand = []
        for nm in name_cnt:
            if is_super_only(nm) or is_brand(nm):
                continue
            shared = len(base_cre_slug[base][nm]) > 1 and n_slugs_in_base > 1
            if not shared:
                cand.append(nm)
        if len(cand) >= 1:
            artists = cand
        else:
            artists = [nm for nm in name_cnt if not is_super_only(nm)]
            flag = "ALL_SHARED"
    # 3) sakuga(かな照合)で一意化: 候補の中で sakuga に合致する creator が1名なら確定
    if sakuga:
        sk = [nm for nm in name_cnt if sakuga_match(nm, sakuga) and not is_super_only(nm)]
        if len(sk) == 1:
            artists = sk
            flag = ""  # sakuga 確定でクリア
    if len({a for a in artists}) > 1:
        flag = (flag + ";" if flag else "") + "MULTI_ARTIST"
    if not name_cnt:
        flag = "NO_CREATOR"

    originals = [nm for nm in name_cnt if nm not in set(artists) and not is_super_only(nm)]
    supervisors = [nm for nm in name_cnt if is_super_only(nm)]

    # グルーピング整合: 選んだ作画が当slugの巻のうち何割に出るか(低=ISBN混在の疑い)
    if artists:
        aset = set(artists)
        with_art = sum(1 for i in isbns
                       if aset & {nm for nm, _ in creators_of(i)})
        cov = with_art / len(isbns) if isbns else 1.0
        if cov < 0.6:
            flag = (flag + ";" if flag else "") + f"GROUPING?({cov:.0%})"

    # title(NDL最頻, clean)
    tc = Counter(clean(ndl.get(i, {}).get("title", "")) for i in isbns if ndl.get(i, {}).get("title"))
    title = tc.most_common(1)[0][0] if tc else slug

    # title_kana(db-v2)
    tkana = ""
    for i in isbns:
        m = db_meta(i)
        if m and m["title_kana"]:
            tkana = m["title_kana"]; break

    # volumes
    vols = []
    for i in isbns:
        ent = ndl.get(i, {})
        m = db_meta(i)
        try:
            voln = int(re.sub(r"[^0-9]", "", str(ent.get("vol") or "")) or 0)
        except ValueError:
            voln = 0
        vols.append({"_voln": voln, "isbn13": i,
                     "release_date": (m["release_date"] if m else None) or (ent.get("year") or None),
                     "cover_url": (m["cover_url"] if m else None),
                     "asin": (m["asin"] if m else None)})
    vns = [v["_voln"] for v in vols]
    if all(vns) and len(set(vns)) == len(vns):
        vols.sort(key=lambda v: v["_voln"])
        for v in vols:
            v["number"] = v["_voln"]
    else:
        vols.sort(key=lambda v: (str(v["release_date"] or "9999"), v["isbn13"]))
        for idx, v in enumerate(vols):
            v["number"] = idx + 1
    for v in vols:
        del v["_voln"]

    years = [str(v["release_date"])[:4] for v in vols if v["release_date"] and re.match(r"\d{4}", str(v["release_date"]))]
    y0 = int(min(years)) if years else None
    y1 = int(max(years)) if years else None

    doc = {
        "slug": slug, "title": title, "title_kana": tkana, "title_romaji": "",
        "year_started": y0, "year_ended": y1, "status": "completed",
        "authors": [{"name": nm, "role": "artist"} for nm in artists],
        "original_authors": originals,
        "supervisors": supervisors or None,
        "publisher": "(unknown)", "magazine": None, "demographic": None,
        "genres": [], "synopsis": None, "anime_adapted": False,
        "alternative_titles": {}, "wikidata_qid": None,
        "editions": [{"type": "standard", "label": "通常版", "imprint": "",
                      "volumes": [{"number": v["number"], "asin": v["asin"], "isbn13": v["isbn13"],
                                   "cover_url": v["cover_url"], "release_date": v["release_date"]}
                                  for v in vols]}],
        "_source": "ndl-option2-recluster",
    }
    if not doc["supervisors"]:
        del doc["supervisors"]
    with open(os.path.join(OUTDIR, slug + ".yml"), "w", encoding="utf-8") as f:
        f.write("# Stage D: NDL option2 recluster (scripts/_slug-apply-recluster.py)\n")
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    written += 1
    review.append((slug, title, "/".join(artists), "/".join(originals),
                   "/".join(supervisors), len(vols), flag))

with open(os.path.join(ROOT, ".cache", "recluster-authors-review.tsv"), "w", encoding="utf-8") as f:
    f.write("slug\ttitle\t作画\t原作\t脚色等\tn_vol\tFLAG\n")
    for r in review:
        f.write("\t".join(str(x) for x in r) + "\n")

print(f"書出: {written} ページ\n")
flagged = [r for r in review if r[6]]
print("=== 要確認 FLAG 付 ===")
for slug, title, art, orig, sup, nv, fl in flagged:
    print(f"  [{fl}] {slug}\n     題={title} 作画={art} 原作={orig or '-'} 脚色={sup or '-'} 巻={nv}")
print(f"\n=== クリーン(FLAG無 {len(review)-len(flagged)}件) 抜粋 ===")
for slug, title, art, orig, sup, nv, fl in [x for x in review if not x[6]][:24]:
    print(f"  {slug}: 題={title} 作画={art} 原作={orig or '-'} 巻={nv}")
print("\n表: .cache/recluster-authors-review.tsv")
