"""第3弾(2026-11-07 ユーザ「順番はまかせる」)= 根拠台帳に出てくるのに雑誌マスタに無い誌を、 その誌の Wikipedia 記事で確かめて足す。

  python scripts/magazine-verify/mag_master_3.py plan    # 計画表 docs/production-diagnostics/magazine-master-plan-2026-11-07.tsv(読むだけ)
  python scripts/magazine-verify/mag_master_3.py apply   # 計画の NEW を data/magazines.yml へ、 ALIAS を data/seeds/magazine-evidence/aliases.yml へ

誌名ごとに: ① 手元の本文ダンプ(scripts/_wiki_local.py)の記事名(転送も辿る)で記事を引く ② 雑誌の記事か確かめる(Infobox 雑誌 / 分類「…漫画雑誌」「ウェブコミック…」)
③ 出版社 = Infobox の出版社 → publishers.yml のキー ④ 読者層 = 分類/ジャンル(少年/少女/青年/女性/児童)、 無ければ頁の多数
⑤ 既存の誌の記事に着いたら別名(ALIAS)。 キー = Wikidata の英語名(QLever)、 無ければヘボン式。
★守り: 増刊が親誌の記事へ転送されている(「週刊少年ジャンプ増刊」→「週刊少年ジャンプ」)= 親誌に寄せない(ユーザ裁定「増刊は別の誌」)。
         雑誌でない記事(Twitter・note・出版社・作品)は足さない。 記事が無い名は足さない(HOLD)。
"""
import bz2, csv, datetime, html, importlib.util, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLAN = os.path.join(ROOT, "docs", "production-diagnostics", "magazine-master-plan-2026-11-07.tsv")
PLAN_JSON = os.path.join(ROOT, ".cache", "magazine-lists", "magazine-master-plan-3.json")
ALIASES = os.path.join(ROOT, "data", "seeds", "magazine-evidence", "aliases.yml")
UA = "MANGAL-research/1.0 (manga catalogue; magazine master)"

spec = importlib.util.spec_from_file_location("ml", os.path.join(ROOT, "scripts", "_magazine-ledger.py"))
ML = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ML)
import yaml
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _wiki_local as WL                                     # ★Wikipedia は手元のダンプ(C:)から

MAG = ML.MAG
PUB = yaml.safe_load(open(os.path.join(ROOT, "data", "publishers.yml"), encoding="utf-8"))
PUB_ALIAS = yaml.safe_load(open(os.path.join(ROOT, "data", "publisher-aliases.yml"), encoding="utf-8")) or {}


def nf(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def pub_key(name):
    n = ML.nrm(name)
    if not n:
        return ""
    for k, v in PUB.items():
        if ML.nrm(v["name"]) == n or any(ML.nrm(a) == n for a in (v.get("aliases") or [])):
            return k
    for a, k in PUB_ALIAS.items():
        if ML.nrm(a) == n:
            return k
    return ""


# ---------------------------------------------------------------- 1. マスタに無い誌名(強い根拠に出る名)と頁
def missing_names():
    pages = ML.load_pages()
    names = defaultdict(set)
    for key, _col, strong in ML.SOURCES:
        if not strong:
            continue
        recs, _ = ML.read_source(key)
        for slug, (_at, hs) in recs.items():
            if slug not in pages:
                continue
            hs = ML.clean_hits(hs)
            use = [h for h in hs if h.get("main")] if key == "madb-mokuji" else [h for h in hs if not h.get("sub")]
            for h in use:
                if h["mag"].startswith("?"):
                    names[h["mag"][1:]].add(slug)
    return pages, names


# ---------------------------------------------------------------- 2. ダンプの記事を引く
def title_forms(raw):
    r = nf(raw).strip("「」『』【】 ")
    out = [r, r + " (雑誌)", r + " (漫画雑誌)", r.replace("!", "！"), r.replace("！", "!")]
    if r[:1].isascii():
        out += [r[:1].upper() + r[1:]]
    return list(dict.fromkeys(x for x in out if x))


# ---------------------------------------------------------------- 3. 記事を読む
CAT = re.compile(r"\[\[\s*Category\s*:\s*([^\]|]+)")
DEMO_CAT = [("少年漫画雑誌", "shounen"), ("少女漫画雑誌", "shoujo"), ("青年漫画雑誌", "seinen"), ("女性漫画雑誌", "josei"),
            ("レディースコミック", "josei"), ("児童漫画雑誌", "kodomo"), ("幼年", "kodomo"), ("児童雑誌", "kodomo"), ("学年誌", "kodomo")]
DEMO_WORD = [("少年漫画", "shounen"), ("少女漫画", "shoujo"), ("青年漫画", "seinen"), ("女性漫画", "josei"), ("児童", "kodomo"), ("幼児", "kodomo")]
IS_MAG_CAT = re.compile(r"漫画雑誌|ウェブコミック|漫画アプリ|雑誌$")   # ★電子書籍ストア(コミックシーモア等)は誌でない


def infobox(wt, name):
    m = re.search(r"\{\{\s*(?:Infobox|基礎情報)\s+" + name, wt)
    if not m:
        return None
    i, depth, j = m.start(), 0, m.start()
    while j < len(wt):
        if wt.startswith("{{", j):
            depth += 1; j += 2; continue
        if wt.startswith("}}", j):
            depth -= 1; j += 2
            if depth == 0:
                break
            continue
        j += 1
    body = wt[m.end():j - 2]
    d, key = {}, None
    for line in body.split("\n"):
        mm = re.match(r"\s*\|\s*([^=|]+?)\s*=\s*(.*)$", line)
        if mm:
            key = mm.group(1).strip()
            d[key] = mm.group(2).strip()
        elif key:
            d[key] += " " + line.strip()
    return d


def plain(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", "", s or "", flags=re.S)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return re.sub(r"<[^>]+>", " ", s).strip()


def read_mag_article(wt):
    cats = [c.strip() for c in CAT.findall(wt)]
    ib = infobox(wt, "雑誌") or infobox(wt, "Magazine") or {}
    if ML.DISAMBIG.search(wt):
        return {"kind": "曖昧さ回避"}
    is_mag = bool(ib) or any(IS_MAG_CAT.search(c) for c in cats)
    if not is_mag:
        return {"kind": "雑誌の記事でない", "cats": cats[:6]}
    # 出版社の候補を順に集め、 publishers.yml に引ける最初の社を採る。
    #   ① 雑誌の Infobox「出版社」(移り変わり A→B は最後 = 今の社)② Web の誌の Infobox Website「運営者」等
    #   ③ 冒頭文「『誌名』は、(かつて)[[社]]が/から発行…」の先頭200字のリンク
    cand = []
    ibw = infobox(wt, "Website") or {}
    for raw in (ib.get("出版社", ""), ib.get("発行所", ""), ibw.get("運営者", ""), ibw.get("運営", ""), ibw.get("開発元", "")):
        links = re.findall(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]", raw)
        names = [a for a, _ in links] + [b for _, b in links if b]
        if "→" in raw:
            names = names[::-1]
        cand += names + [x for x in re.split(r"→|、|,|<br\s*/?>", plain(raw)) if x.strip()]
    m_lead = re.search(r"[』」]\s*(?:（[^）]*）)?\s*は、(.{0,200})", wt)
    if m_lead:
        cand += [a for a, _ in re.findall(r"\[\[([^\]|#]+)(?:\|([^\]]*))?\]\]", m_lead.group(1))]
    cand = [re.sub(r"\s*\([^)]*\)$", "", c).strip() for c in cand if c.strip()]
    pubname = next((c for c in cand if pub_key(c)), cand[0] if cand else "")
    demo, how = "", ""
    for c in cats:
        for w, d in DEMO_CAT:
            if w in c:
                demo, how = d, "分類:" + c
                break
        if demo:
            break
    if not demo:
        g = plain(ib.get("ジャンル", "") + " " + ib.get("読者対象", ""))
        for w, d in DEMO_WORD:
            if w in g:
                demo, how = d, "ジャンル:" + g[:30]
                break
    return {"kind": "雑誌", "pub_name": pubname, "pub": pub_key(pubname), "demo": demo, "demo_how": how,
            "freq": plain(ib.get("刊行頻度", ""))[:20], "en_title": plain(ib.get("英文誌名", "")), "cats": cats[:6]}


# ---------------------------------------------------------------- 4. キー(Wikidata の英語名)
def qlever_en(titles):
    out = {}
    tl = sorted(titles)
    for i in range(0, len(tl), 150):
        b = tl[i:i + 150]
        vals = " ".join("<https://ja.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"), safe="()") + ">" for t in b)
        q = f"""PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?article ?en WHERE {{ VALUES ?article {{ {vals} }}
  ?article schema:about ?item . ?item rdfs:label ?en . FILTER(LANG(?en) = "en") }}"""
        data = urllib.parse.urlencode({"query": q}).encode()
        req = urllib.request.Request("https://qlever.dev/api/wikidata", data=data, headers={
            "User-Agent": UA, "Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    rows = json.loads(r.read().decode("utf-8"))["results"]["bindings"]
                break
            except Exception as e:
                print(f"  qlever retry {attempt + 1} ({str(e)[:60]})", flush=True)
                time.sleep(2 ** attempt + 1)
        else:
            print("  ★QLever 失敗 = 英語名なしで続ける(キーはヘボン式)", flush=True)
            rows = []
        for r in rows:
            t = urllib.parse.unquote(r["article"]["value"].rsplit("/wiki/", 1)[-1]).replace("_", " ")
            out[t] = r["en"]["value"]
        time.sleep(1)
    return out


def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\((?:magazine|manga magazine|japanese magazine)\)", "", s)
    s = s.replace("+", " plus ").replace("&", " and ").replace("!", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def hepburn(s):
    import pykakasi
    kk = pykakasi.kakasi()
    parts = []
    for x in kk.convert(nf(s)):
        w = x["hepburn"] if re.search(r"[぀-ヿ一-鿿]", x["orig"]) else x["orig"]
        parts.append(w)
    return slugify(" ".join(parts))


# ---------------------------------------------------------------- plan / apply
# ---- 人が決めたこと(2026-11-07 計画表を1件ずつ読んで)
# 誌名 → キー(英語名が誤っている・無い・カナのヘボン式で読みにくい時)
KEY_OVERRIDE = {
    "ジャンプ改": "jump-kai", "近代麻雀": "kindai-mahjong", "コミックハイ!": "comic-high", "少年エースplus": "shonen-ace-plus",
    "月刊電撃コミックガオ!": "dengeki-comic-gao", "ビッグコミック増刊号": "big-comic-zokan", "月刊少年ギャグ王": "monthly-shonen-gag-oh",
    "ビッグゴールド": "big-gold", "ジーンLINE": "gene-line", "月刊ステンシル": "monthly-stencil", "月刊コミックコンプ": "comic-comp",
    "ガンガン戦-IXA-": "gangan-ixa", "ヒーロークロスライン": "hero-cross-line", "ガンガンpixiv": "gangan-pixiv",
    "Champion タップ!": "champion-tap", "まんがぱれっとLite": "manga-palette-lite", "本当にあった笑える話": "honto-ni-atta-waraeru-hanashi",
    "漫画ゴラクネクスター": "manga-goraku-nexter", "ほんとうに怖い童話": "honto-ni-kowai-douwa", "月刊少年ブラッド": "monthly-shonen-blood",
    "まんがタウンオリジナル": "manga-town-original", "エース桃組": "ace-momogumi", "ゴラクうぇぶ!": "goraku-web",
    "コミック乱ツインズ 戦国武将列伝": "comic-ran-twins-sengoku-busho-retsuden", "ポップコーン": "popcorn",
    "ポケモンワンダーランド": "pokemon-wonderland", "季刊エス": "kikan-s", "電撃コミック ジャパン": "dengeki-comic-japan",
    "月刊少年コミック": "monthly-shonen-comic", "コミックブレイドZEBEL": "comic-blade-zebel", "エース特濃": "ace-tokunou",
    "コミック・ノストラダムス": "comic-nostradamus", "アクションピザッツSP": "action-pizazz-sp", "ファミ通ブロス": "famitsu-bros",
    "ヤング・キャプテン": "young-captain", "週刊少年アクション": "weekly-shonen-action", "コンプH's": "comp-hs", "模型情報": "mokei-joho",
    "コミックエッセイ劇場": "comic-essay-gekijo", "朝日ジャーナル": "asahi-journal", "ル・ノエル": "le-noel", "COMICジャンク": "comic-junk",
    "漫画実話ナックルズ": "manga-jitsuwa-knuckles", "読売ウイークリー": "yomiuri-weekly", "ヤングキング別冊キングダム": "young-king-bessatsu-kingdom",
    "花とゆめ 文系少女": "hana-to-yume-bunkei-shojo", "わしズム": "washizumu", "ねこぱんち": "neko-panch", "月刊ニュータイプ": "newtype",
    "週刊宝石": "shukan-hoseki", "MAGCOMI": "magcomi", "RPGマガジン": "rpg-magazine", "ゴーゴーバンチ": "go-go-bunch",
    "Comicキャンドール": "comic-candoll", "月刊ヤングキングアワーズGH": "young-king-ours-gh", "週刊アスキー": "weekly-ascii", "少年王": "shonen-ou",
}
# 誌名 → 既存の誌(記事の転送先が別の記事でも、 改名・表記ゆれで同じ誌と確かめたもの)
ALIAS_OVERRIDE = {"ドラゴンエイジピュア": "dragon-age-pure", "オフィスユー": "office-you", "マガポケ": "manga-pocket",
                  "週刊少年サンデー増刊号": "weekly-shonen-sunday-zokan", "増刊少年サンデー": "weekly-shonen-sunday-zokan"}
# 寄せない(転送先 = 親誌や姉妹誌の記事の1節。 別の誌・増刊・Web版・アプリ・別の学年誌)
ALIAS_HOLD = {
    "水曜日のシリウス", "ヤンマガWeb", "ヤンマガweb", "eヤングマガジン", "月刊コミックガーデン", "エイジプレミアム", "少年マガジンR", "漫画ゴラクスペシャル",
    "別冊ヤングマガジン", "グランドジャンプむちゃ", "グランドジャンプめちゃ", "マガジンドラゴン", "ヤンチャンWeb", "ヤンチャンweb",
    "ドラドラドラゴンエイジ", "ドラドラふらっと♭", "アライブ+", "角川ニコニコエース", "週刊コロコロコミック", "なかぞう", "COMIC BRIDGE",
    "電撃コミック レグルス", "ビーボーイP!", "BE・BOY GOLD", "月マガ基地", "週プレNEWS", "ジャンプSQ.CROWN", "新雑誌研究所", "コミックGENKi",
    "comicブースト", "コミックタタン", "SFアニメディア", "コミックアルナ", "コミックアルファ", "YSスペシャル", "ソク読みサンデー",
    "ガンダムユニコーンエース", "たのしい三年生", "たのしい四年生", "スペリオール・ダルパナ", "&Sofa", "ヤンジャン！", "ベアーズクラブ",
    "サクラミステリー", "EYE-COM", "ゆりひめ@ピクシブ", "漫画アクションファミリー増刊 クレヨンしんちゃん特集号", "姉フレンド", "さくらハーツ",
    "マガジンZKC", "別冊コーラス",
}
HOLD_ARTICLES = {"小学館の学年別学習雑誌": "学年誌の総称の記事 = 1つの誌でない(各学年誌は既存)",
                 "魔法少女まどか☆マギカの漫画作品": "作品の記事 = 誌でない"}
# 読者層(一般誌・アニメ誌で、 頁の多数が当てにならないもの)
DEMO_OVERRIDE = {"週刊プレイボーイ": "seinen", "S-Fマガジン": "seinen", "女性自身": "josei", "読売ウイークリー": "seinen",
                 "DOS/V POWER REPORT": "seinen", "POPEYE": "seinen", "月刊ニュータイプ": "seinen", "少女クラブ": "shoujo",
                 "アクションピザッツDX": "seinen", "アクションピザッツSP": "seinen"}


def plan():
    pages, names = missing_names()
    print(f"マスタに無い誌名 {len(names):,}(頁 延べ {sum(len(v) for v in names.values()):,})", flush=True)
    forms = {n: title_forms(n) for n in names}
    want = {t for fs in forms.values() for t in fs}
    got = {t: g for t in want if (g := WL.get(t))}          # 手元の Wikipedia ダンプ(転送を辿る)
    texts = {fin: wt for fin, wt in got.values()}
    print(f"  記事名の候補 {len(want):,} → 在る記事 {len(texts):,}(ダンプ {WL.dump_date()})", flush=True)
    res = {}
    for n, fs in forms.items():
        hit = None
        for t in fs:
            if t in got:
                hit = (t, got[t][0])
                break
        r = {"name": n, "pages": len(names[n]), "slugs": sorted(names[n])[:5]}
        if not hit:
            r.update(decision="HOLD", why="記事なし")
        else:
            t, fin = hit
            info = read_mag_article(texts[fin])
            r.update(article=fin, redirected=(t != fin), **{k: v for k, v in info.items() if k != "kind"})
            base = re.sub(r"\s*\([^)]*\)$", "", fin)    # 「ハルタ (漫画誌)」「イブニング (雑誌)」
            kparent = ML.resolve(base)
            if info["kind"] != "雑誌":
                r.update(decision="HOLD", why=info["kind"])
            elif re.search(r"の増刊号?$|一覧$", base):
                r.update(decision="HOLD", why=f"一覧の記事({fin}) = 1つの誌でない")
            elif t != fin and ML.nrm(base) != ML.nrm(n) and ML.nrm(base) in ML.nrm(n):
                r.update(decision="HOLD", why=f"増刊・号の名が親誌の記事({fin})へ転送 = 親誌に寄せない")
            elif not kparent.startswith("?"):
                r.update(decision="ALIAS", key=kparent, why=f"既存の誌の記事({fin})")
            else:
                r.update(decision="NEW", master_name=base)
        if n in ALIAS_OVERRIDE:
            r.update(decision="ALIAS", key=ALIAS_OVERRIDE[n], why="人が確かめた別名(改名・表記ゆれ)")
        elif n in ALIAS_HOLD:
            r.update(decision="HOLD", why="親誌・姉妹誌の記事の1節 = 別の誌・増刊・Web版(人が確かめて寄せない)")
        elif r.get("article") in HOLD_ARTICLES and r["decision"] != "HOLD":
            r.update(decision="HOLD", why=HOLD_ARTICLES[r["article"]])
        res[n] = r
    # 同じ記事に着く名はまとめる(先に頁の多い名)
    new_by_art = defaultdict(list)
    for n, r in sorted(res.items(), key=lambda x: -x[1]["pages"]):
        if r["decision"] == "NEW":
            new_by_art[r["article"]].append(n)
    en = qlever_en(set(new_by_art))
    used = set(MAG)
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {k: i for i, k in enumerate(li["f"])}
    demo_of = {r[F["slug"]]: r[F["demographic"]] or "" for r in li["d"]}
    for art, ns in new_by_art.items():
        head = res[ns[0]]
        key, how = (KEY_OVERRIDE[head["master_name"]], "手で決めた") if head["master_name"] in KEY_OVERRIDE else ("", "")
        if not key and head.get("en_title") and re.search(r"[A-Za-z]{3}", head["en_title"]):
            key, how = slugify(head["en_title"]), "英文誌名"
        if not key and art in en:
            key, how = slugify(en[art]), "Wikidata英語名"
        how = how or "ヘボン式"
        if not key or key in used:
            key2 = hepburn(head["master_name"])
            key = key2 if key2 and key2 not in used else (key or key2) + "-" + str(len(used))
        used.add(key)
        if not head.get("demo"):
            cnt = Counter(demo_of.get(s, "") for n in ns for s in names[n] if demo_of.get(s))
            if cnt:
                head["demo"], head["demo_how"] = cnt.most_common(1)[0][0], f"頁の多数 {dict(cnt.most_common(3))}"
        if head["master_name"] in DEMO_OVERRIDE:
            head["demo"], head["demo_how"] = DEMO_OVERRIDE[head["master_name"]], "人が決めた(一般誌・アニメ誌)"
        for i, n in enumerate(ns):
            r = res[n]
            r["key"] = key
            r["key_how"] = how
            r["en"] = en.get(art, "")
            if i:
                r.update(decision="ALIAS", why=f"同じ記事({art})の別表記 → {key}")
            else:
                r["demo"], r["demo_how"] = head.get("demo", ""), head.get("demo_how", "")
    for r in res.values():
        if r["decision"] == "NEW" and r.get("demo") not in ("shounen", "shoujo", "seinen", "josei", "kodomo"):
            r.update(decision="HOLD", why="読者層が決まらない")
        elif r["decision"] == "NEW" and not r.get("pub"):
            r.update(decision="HOLD", why=f"出版社が決まらない({r.get('pub_name', '')}) = 電子書籍ストア・小説サイト・社がマスタに無い")
    for r in res.values():                             # 足さない誌に寄せる予定だった別表記も足さない
        if r["decision"] == "ALIAS" and r.get("key") and r["key"] not in MAG and not any(
                x["decision"] == "NEW" and x.get("key") == r["key"] for x in res.values()):
            r.update(decision="HOLD", why=f"寄せ先({r['key']})を足さない")
    json.dump(res, open(PLAN_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    cols = ["decision", "name", "pages", "key", "master_name", "article", "pub_name", "pub", "demo", "demo_how", "en", "key_how", "why", "slugs"]
    with open(PLAN, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 雑誌マスタ第3弾の計画(2026-11-07)。 NEW=足す / ALIAS=既存誌(または同じ記事の誌)の別名 / HOLD=足さない。 正本は mag_master_3.py が作る\n")
        f.write("\t".join(cols) + "\n")
        for r in sorted(res.values(), key=lambda x: (x["decision"], -x["pages"])):
            f.write("\t".join(str(r.get(c, "") if c != "slugs" else " ".join(r.get("slugs", []))).replace("\t", " ").replace("\n", " ")
                              for c in cols) + "\n")
    c = Counter(r["decision"] for r in res.values())
    pc = Counter()
    for r in res.values():
        pc[r["decision"]] += r["pages"]
    print("計画:", {k: f"{v}誌/{pc[k]}頁" for k, v in c.items()})
    print("HOLD の理由:", Counter(r["why"].split("(")[0] for r in res.values() if r["decision"] == "HOLD").most_common(8))
    print("→", os.path.relpath(PLAN, ROOT))


def qy(s):
    return "'" + str(s).replace("'", "''") + "'"


def apply():
    res = json.load(open(PLAN_JSON, encoding="utf-8"))
    new = [r for r in res.values() if r["decision"] == "NEW"]
    alias = {r["name"]: r["key"] for r in res.values() if r["decision"] == "ALIAS"}
    mp = os.path.join(ROOT, "data", "magazines.yml")
    cur = yaml.safe_load(open(mp, encoding="utf-8"))
    add = [r for r in new if r["key"] not in cur]
    with open(mp, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"# ---- 第3弾 2026-11-07: 根拠台帳に出る誌を ja.wikipedia の誌の記事で確認して追加(scripts/magazine-verify/mag_master_3.py)\n")
        for r in sorted(add, key=lambda x: x["key"]):
            f.write(f"{r['key']}:\n  name: {qy(r['master_name'])}\n  publisher: {qy(r.get('pub') or '')}\n  demographic: {r['demo']}\n")
    old = yaml.safe_load(open(ALIASES, encoding="utf-8")) if os.path.exists(ALIASES) else {}
    old = old or {}
    old.update(alias)
    with open(ALIASES, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 誌名の別名 → 雑誌マスタのキー。 _magazine-ledger.py の resolve が読む。 書き方1つにつきキー1つ(2誌に当たる名は書かない)\n")
        for k in sorted(old):
            f.write(f"{qy(k)}: {old[k]}\n")
    print(f"雑誌マスタに {len(add)} 誌 / 別名 {len(alias)} 件")


if __name__ == "__main__":
    {"plan": plan, "apply": apply}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
