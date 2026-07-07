#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ R4 = SPLIT38群の手動裁定表を seed に展開 (2026-07-07 全証拠精査済)。

DEDUP = union が lossless(隠れ本なし) かつ 同一作/題系譜家族 → canonical指定でpage-dedup。
SPLIT = 隠れ本あり(number-dedupで不可視の実本) or 別作品 → merge-exceptions block(頁sid全ペア対称)
        + クラスタ内の非頁home sid(サブ断片)は題が合わない頁sidに対してもblock。
DEFER = 妖精国Ballad(arc構造の外部確認要)。
出力: seed追記 + reflectコマンド引数(.cache/r4-reflect-args.txt)。
"""
import os, re, sys, json, sqlite3, datetime, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
TM = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))
TODAY = "2026-07-07"

# ==== 手動裁定表 ====
DEDUP = {  # canonical: [drops]
 "dragon-quest-daino-daibouken": ["dragon-quest", "dragon-quest-dai-no-daibouken"],  # ダイの大冒険 旧/新装彩録/文庫=同一作
 "xxxholic": ["clamp-premium-collection-holic"],  # CPC=新装レーベル
 "eikou-no-naporeon": ["eroika"],  # 栄光のナポレオン-エロイカ=同一作(単行本題/文庫題)
 "kantai-collection-kancolle-comic-arakaruto-maizuru-chinjufu-hen": ["kantai-collection-kancolle-comic-arakaruto"],  # 全冊舞鶴鎮守府編
 "joshi-joshikousei-girls-hai": ["joshikousei"],  # 新装+続=同一作
 "hanitarou-desu": ["10-ko-iri-hani-tarou-desu","3-banme-no-hani-tarou-desu","7-banme-no-hani-tarou-desu","boyoyon-hani-tarou-desu","curry-aji-hani-tarou-desu","irasshaimase-hani-tarou-desu","jinrui-metsubou-made-hani-tarou-desu","koryamata-hani-tarou-desu","maa-iijan-hani-tarou-desu","nannokotcha-hani-tarou-desu","upupu-hani-tarou-desu","yappari-hani-tarou-desu"],  # 巻題ギミック1シリーズ全14巻・union lossless
 "masurao": ["hihon-gikeiki"],  # ますらお-秘本義経記-=同一作
 "magic-knight-rayearth": ["clamp-premium-collection-magic-knight-rayearth"],
 "magic-naito-rayearth-2": ["clamp-premium-collection-magic-knight-rayearth-2"],
 "wakusei-nendaiki": ["ao-wakusei-nendaiki","kan-wakusei-nendaiki","sui-wakusei-nendaiki","wakusei-nendaiki-gekkan-sachisachi","wakusei-nendaiki-ruunyan","zoku-sui-wakusei-nendaiki"],  # 水惑星年代記家族・union lossless
 "pangaea-ezel-2010": ["pangaea-ezel"],
 "sarutobi-etsu-chan": ["okashina-okashina-okashina-ano-ko-sarutobi-etsu-chan","okashina-okashina-okashina-anoko-sarutobi-etsu-chan"],  # 改題同作
 "adventure-2030-gakuen": ["adventure2030-gakuen"],
 "oji-san-to-marshmallow": ["googoo-oji-san-to-marshmallow","motto-oji-san-to-marshmallow","souda-oji-san-to-marshmallow","yondara-oji-san-to-marshmallow"],  # 巻題ギミック全5巻
 "toaru-hi-no-kuru": ["totoaruhi-no-kuru","aru-nichi-toaru-nichi-totoaru-nichi-no-kuru"],  # クル続篇家族・lossless
 "dai-mahou-touge": ["chou-dai-mahou-touge","chou-chou-dai-mahou-touge","chou-chou-chou-daimahoutouge"],  # 続篇家族・lossless
 "neko-banashi-pandania-2020": ["mikke-neko-banashi","nyanto-neko-banashi","yotsu-neko-banashi"],  # ねこむかしばなし家族・lossless
 "mayonaka-no-jewel": ["motto-mayonaka-no-jewel","motto-motto-mayonaka-no-jewel"],
 "neko-monster": ["neko-monster-fumifumi","neko-monster-nyaao"],
 "shinpika-mizuki-shigeru-den": ["watashi-ha-gegege"],  # 改題再刊同一作
}
SPLIT = [  # 各クラスタの頁stem群(全ペアblock)
 ["kowai-hon","umezu-kazuo-kowai-hon","zoku-kowai-hon"],  # ソノラマ系/角川2020全11/2025全10=各完備の別シリーズ(隠れ12冊surfacing)
 ["hakushaku-cain","akai-hitsuji-no-kokuin","kafuka","wasure-rareta-juliet"],  # 文庫統合版/単行本各題/別作カフカ
 ["bunbuku-tanuki-no-teii-party","bunbuku-teii-potto-plus"],  # ティーポット+隠れ5冊
 ["dream","youseiou"],  # ドリーム=別作(全集巻・隠れ1)
 ["juran","saishuu-sensou","saishuu-sensou-densetsu"],  # 十蘭=別作/最終戦争=単巻(隠れ2)
 ["idol-sousei-densetsu-princess","princess"],  # 学研5巻と角川5巻=別刊行(相互隠れ)
 ["kimi-no-tonari","yami-toshi-densetsu"],  # キミノトナリ=実在3巻(隠れ3)
 ["anata-no-omocha","mottox3-anata-no-omocha","motto-2-kai-anata-no-omocha","motto-3-kai-anata-no-omocha"],  # 続篇+新装版隠れ
 ["besuteia","ryuugetsushou"],  # ベスティア1-3隠れ
 ["neko-youkai","neko-youkai-gorogoro","neko-youkai-mugyutsu"],  # 各隠れ1
 ["steins-gate","steins-gate-2011"],  # 4コマしゅたいんず・げーと!=別作
 ["gudaguda-ace","koha-ace","koha-ace-collection","koha-ace-ekkusupii","koha-ace-iiekkusu"],  # 各単巻続篇(隠れ有)
 ["lady-q","tensai-choukoushi-houjou-mika"],
 ["boku-to-ohiru-o","inasaku"],
 ["fushigi-toshokan","slope-mansion-ni-okaeri"],
 ["garakutamachi-ki-tan","kamen-shounen"],
 ["keetai-ga-ochiteita","seven-piisu"],
]
# DEFER: alfheim-no-kishi-ballad / arufuheimunokishibaraddotsuguminomori (arc構造は外部確認要)

RE_SKEY = re.compile(r"^_skey:\s*(.+?)\s*$", re.M)
RE_SLUG = re.compile(r"^slug:\s*(.+?)\s*$", re.M)
RE_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")
PUNCT = re.compile(r"[\s　・=\-〜~×!！?？。、.,:：;；'’\"「」『』()（）\[\]〔〕【】&＆♥❤☆★…]+")
def norm(t):
    return PUNCT.sub("", unicodedata.normalize("NFKC", str(t or ""))).lower()

def sid_of(stem):
    sp = os.path.join(ROOT, "data", "manga", stem + ".yml")
    s = open(sp, encoding="utf-8").read()
    skey = RE_SKEY.search(s).group(1).strip("'\"")
    r = con.execute("SELECT id FROM series WHERE series_key=?", (skey,)).fetchone()
    assert r, f"sid未解決: {stem}"
    return r[0]

def page_info(stem):
    t = open(os.path.join(ROOT, "data", "manga.v2", stem + ".yml"), encoding="utf-8").read()
    return ((RE_SLUG.search(t).group(1) if RE_SLUG.search(t) else stem),
            (RE_TITLE.search(t).group(1) if RE_TITLE.search(t) else stem).strip("'\""),
            set(RE_ISBN.findall(t)))

# ---- DEDUP → auto.json (apply スクリプト再利用形式) ----
auto = []
for canon, drops in DEDUP.items():
    cslug, ctitle, cisbns = page_info(canon)
    auto.append({"canonical": canon, "canonical_slug": cslug, "title": ctitle, "author_differ": False,
                 "drops": [{"stem": d, "slug": page_info(d)[0], "title": page_info(d)[1]} for d in drops],
                 "isbns": len(cisbns)})
json.dump(auto, open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---- SPLIT → merge-exceptions blocks ----
lines = []
affected = set()
for group in SPLIT:
    sids = {}
    titles = {}
    isbns_union = set()
    for st in group:
        sids[st] = sid_of(st)
        slug, title, isbns = page_info(st)
        titles[st] = title
        isbns_union |= isbns
        affected.add(st)
    sts = sorted(group)
    for i in range(len(sts)):
        for j in range(i + 1, len(sts)):
            a, b = sids[sts[i]], sids[sts[j]]
            lines.append(f"  - [{min(a,b)}, {max(a,b)}]  # {titles[sts[i]][:14]} × {titles[sts[j]][:14]} (ISBNダブリR4分割 {TODAY})")
    # 非頁home sid: 題が合わない頁に対してblock
    page_sids = set(sids.values())
    for isbn in isbns_union:
        for hsid, htitle in con.execute("""SELECT s.id, s.title FROM series s
            JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
            WHERE v.isbn13=?""", (isbn,)).fetchall():
            if hsid in page_sids:
                continue
            hn = norm(htitle)
            for st in group:
                pn = norm(titles[st])
                if not (hn in pn or pn in hn):
                    a, b = min(hsid, sids[st]), max(hsid, sids[st])
                    ln = f"  - [{a}, {b}]  # サブ断片{htitle[:12]} × {titles[st][:12]} (R4 {TODAY})"
                    if ln not in lines:
                        lines.append(ln)

with open(os.path.join(ROOT, "data", "seeds", "merge-exceptions.yml"), "a", encoding="utf-8") as f:
    f.write("\n".join(dict.fromkeys(lines)) + "\n")

only = sorted(set(DEDUP.keys()) | affected)
drops = sorted({d for v in DEDUP.values() for d in v})
open(os.path.join(ROOT, ".cache", "r4-reflect-args.txt"), "w").write(",".join(only) + "\n" + ",".join(drops))
print(f"dedup {len(DEDUP)}群/drop {len(drops)}頁 | split {len(SPLIT)}群/block行 {len(set(lines))} | reflect対象 {len(only)}+drop{len(drops)}")
