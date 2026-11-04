"""裁定表(wiki-judge2.json)→ 段階分けの最終表 + 誌ごとの集計(読むだけ・本番は触らない)。
出力: docs/production-diagnostics/magazine-verify-2026-11-04.tsv / .cache/magazine-lists/verify-summary.json"""
import json, sys, os, re
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from wiki_mag_lib import ROOT, MAG
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache/magazine-lists")
res = json.load(open(f"{L}/wiki-judge2.json", encoding="utf-8"))

# 人が読んで決めた分(2026-11-04)。 値 = (提案, 理由)。 提案が "" = 空のまま / "?誌名" = マスタに無い誌
MANUAL = {
    "yorugata-aijin-senmonten": ("?別冊花とゆめ", "Wiki・MADBとも別冊花とゆめ(Wikiの年は旧版の分)"),
    "umi-no-ouji-2009": ("weekly-shonen-sunday", "Wiki・MADBとも週刊少年サンデー(頁は2009年の復刊)"),
    "gegege-no-kitarou": ("weekly-shonen-magazine", "Wiki・MADBとも週刊少年マガジン"),
    "kokurikozaka-kara": ("nakayoshi", "Wiki・MADBとも なかよし(頁は2011年の文庫)"),
    "chimua-port": ("?ザ花とゆめ", "Wiki・MADBとも ザ花とゆめ"),
    "mahoutsukai-no-pan": ("?office YOU", "Wiki・MADBとも office YOU(MADBの初出欄は題を先に書いている)"),
    "gokko": ("super-jump", "Wiki=スーパージャンプ→グランドジャンプPREMIUM。 初出誌=スーパージャンプ(MADBにSJの目次が無い)"),
    "kamen-no-ninja-akakage": ("champion", "この頁=秋田書店1987年版=新・仮面の忍者赤影。 Wiki本文「1987年より週刊少年チャンピオンで連載」"),
    "real-account": ("bessatsu-shonen-magazine", "Wiki=別冊少年マガジン→週刊少年マガジン→別冊。 初出誌=別冊少年マガジン(MADBに別マガの目次が無い)"),
    "kamen-rider-2011": ("?テレビランド", "この版(2011)の初出=テレビランド1978-79(MADB)。 Wikiは石ノ森版(ぼくらマガジン)の記事"),
    "daisuki-ga-mushi-ha-tadashi-kun-no": ("champion", "Web発(作者HP)→週刊少年チャンピオンで連載。 単行本は少年チャンピオン・コミックス"),
    "senyuu": ("jump-sq", "Web発(ニコニコ)→ジャンプSQ.で連載。 単行本の初出=ジャンプSQ.(MADB)"),
    "hori-san-to-miyamura-kun": ("gangan-online", "Web発(読解アヘン)。 単行本の初出欄=ガンガンONLINE(MADB)"),
    "bear-bear": ("?LaLa DX", "Wiki=LaLaDX。 MADBの初出はLaLa増刊(黒ララ・白ララ)→LaLaDX"),
    "tenkuu-shinpan": ("?マンガボックス", "Wiki=マンガボックス(MADBの週刊少年マガジン10回は出張掲載)"),
    "nina-to-usagi-to-mahou-no-sensha": ("?スーパーダッシュ&ゴー!", "Wiki本文=漫画版はスーパーダッシュ&ゴー!(2011-2013)"),
    "sayonara-trigger": ("?マガジンSPECIAL", "Wiki=マガジンSPECIAL。 MADB目次=週刊少年マガジン本誌の号に21回(本誌にも載った)。 初出誌=マガジンSPECIAL"),
    "jungle-kurobee": ("", "よいこ・幼稚園・学年誌・新聞など複数=1誌に決められない"),
    "hinotori": ("", "編ごとに誌が違う(漫画少年・少女クラブ・COM・マンガ少年…)=1誌に決められない"),
    "kaitou-pokemon-7": ("", "小学二年生・小学三年生の両方=1誌に決められない"),
    "youkai-watch": ("?月刊コロコロコミック", "小西紀行版=月刊コロコロコミック(Wiki)。 MADBの「ちゃお52回」は別の漫画版を拾っている"),
}
# 方針で決まる分(移籍の初出誌・増刊の扱い): 既定=初出誌(2026-11-04 の連載誌是正と同じ)。 マスタに無い誌は '?'
POLICY = {
    "yuuyake-banchiyou": ("?冒険王", "Wiki=冒険王→週刊少年チャンピオン。 初出誌=冒険王"),
    "mobile-suit-gundam-msv-senki-jonii-raiden": ("?ガンダムマガジン", "Wiki=ガンダムマガジン→コミックボンボン。 初出誌=ガンダムマガジン"),
    "sweet-poolside": ("?週刊ヤングマガジン", "Wiki=週刊ヤングマガジン→別冊少年マガジン。 初出誌=YM(2004読切)・本連載=別マガ(2011)"),
    "wagatsuma-san-wa-ore-no-yome": ("?マガジンSPECIAL", "Wiki=マガジンSPECIAL→週刊少年マガジン。 初出誌=マガジンSPECIAL"),
    "tableau-gate": ("?月刊ASUKAファンタジーDX", "Wiki=ASUKAファンタジーDX→少女帝国→プリンセスGOLD→プリンセス。 初出誌=ASUKAファンタジーDX"),
    "boku-no-karada-wa-tsuu-out": ("?ビジネスジャンプ", "Wiki=ビジネスジャンプ→グランドジャンプ。 初出誌=ビジネスジャンプ"),
    "shinigami-no-ballad": ("lala", "Wiki=LaLa、LaLa DX / MADB初出=ララDX、ララ = 順序が割れる"),
    "papa-to-atashi-no-baasasu-na-nichijou": ("?なかよしラブリー", "Wiki=なかよしラブリー(なかよし増刊)/ MADB=なかよし"),
    "meitantei-yumemizu-kiyoshirou-jiken-note": ("?なかよしラブリー", "Wiki=なかよしラブリー / MADB初出=なかよしラブリー"),
    "celeb-na-slave": ("?なかよしラブリー", "Wiki=なかよしラブリー / MADB初出=なかよし、なかよしラブリー"),
    "hitori-ja-naikoto": ("?なかよしラブリー", "Wiki=なかよしラブリー / MADB=なかよし200803～06"),
    "teiichi-no-kuni": ("?ジャンプSQ.19", "Wiki=ジャンプSQ.19→ジャンプスクエア / MADB初出(1巻)=ジャンプSQ.19・目次=SQ51回。 初出誌=SQ.19(増刊を別の誌にしないならジャンプSQ)"),
    "naisho-no-tsubomi-mebae": ("?小学三年生", "Wiki・MADBとも 小学三年生→小学四年生(学年誌)。 今の「ちゃお」は誤り"),
    "kamui-gaiden": ("weekly-shonen-sunday", "第1部=週刊少年サンデー(1965)・第2部=ビッグコミック(1982)。 この頁は両部の20巻。 初出誌=週刊少年サンデー(MADBは第2部の目次だけ当たった)"),
}

rows = []
for x in res:
    v = x["verdict"]; w = x["wiki"] or {}
    prop = x["madb_id"]; why = ""
    if x["slug"] in MANUAL:
        prop, why = MANUAL[x["slug"]]; tier = "D 人が読んで決めた"
    elif x["slug"] in POLICY:
        prop, why = POLICY[x["slug"]]; tier = "D' 方針で決まる(初出誌・増刊)"
    elif v.startswith("今のまま"):
        tier = "E 今の値で正しい"; prop = x["cur"]
    elif v.startswith(("直す(", "埋める(")):
        tier = "A 根拠2つが一致"
    elif v.startswith("MADBのみ(強)"):
        tier = "B MADBのみ(強)"
    elif v.startswith("MADBのみ(弱)"):
        tier = "C MADBのみ(弱)"
    elif v.startswith("未取得"):
        tier = "Z Wiki未取得"
    else:
        tier = "D 要確認(未裁定)"
    inm = (prop in MAG) if prop else None
    me = x["madb_ev"]
    mev = "; ".join(f"{k}:{json.dumps(v2, ensure_ascii=False)}" for k, v2 in me.items())[:220]
    wev = f'「{w.get("article", "")}」{w.get("raw", "")}'[:160] if w else ""
    rev = " / ".join(f"{c[2]}:{c[3]}" for c in x["rakuten"])[:120]
    rows.append({"tier": tier, "in_master": inm, "grp": x["grp"], "slug": x["slug"], "title": x["title"], "cur": x["cur"],
                 "prop": prop, "verdict": v, "why": why, "madb_name": x["madb"], "wiki": wev, "madb": mev, "rakuten": rev})

order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 5, "Z": 6}
rows.sort(key=lambda r: (order.get(r["tier"][0], 4), not r["in_master"], r["prop"] or "", r["slug"]))
out = os.path.join(ROOT, "docs/production-diagnostics/magazine-verify-2026-11-04.tsv")
with open(out, "w", encoding="utf-8") as f:
    f.write("# 連載誌の検証(MADB × Wikipedia作品記事 × 楽天の商品説明)。 読むだけの診断(本番は未変更)。 2026-11-04\n")
    f.write("# 段階: A=根拠2つが一致 / B=MADBのみ(強: 1巻の初出欄 or 目次10回以上・8割以上) / C=MADBのみ(弱) / D=人が読んで決めた / D'=方針で決まる(移籍は初出誌) / E=今の値で正しい / Z=Wiki未取得\n")
    f.write("# 提案が「?誌名」= 雑誌マスタに無い誌(足すかどうかは裁定待ち)。 提案が空 = 空のまま\n")
    f.write("段階\tマスタに有る\t区分\tslug\ttitle\t今の連載誌\t提案\t判定\t理由\tMADB誌名\tWikipedia\tMADB\t楽天\n")
    for r in rows:
        f.write("\t".join(str(r[k] if r[k] is not None else "").replace("\t", " ").replace("\n", " ")
                          for k in ("tier", "in_master", "grp", "slug", "title", "cur", "prop", "verdict", "why", "madb_name", "wiki", "madb", "rakuten")) + "\n")
c = Counter((r["tier"], "マスタ有" if r["in_master"] else ("空のまま" if r["prop"] == "" else "マスタ無")) for r in rows)
print("頁", len(rows))
for t in sorted({r["tier"] for r in rows}, key=lambda t: order.get(t[0], 4)):
    print(f"  {t}: " + " / ".join(f"{k[1]} {n}" for k, n in sorted(c.items()) if k[0] == t))
# 直す/埋める の内訳(マスタに有る誌)
ch = Counter((r["tier"][0], "埋める" if not r["cur"] else "直す") for r in rows if r["in_master"] and r["tier"][0] in "ABCD" and r["prop"] != r["cur"])
print("マスタに有る誌で変わる頁:", dict(ch))
mag = defaultdict(Counter)
for r in rows:
    if r["prop"] and r["prop"].startswith("?") and r["tier"][0] in "ABD":
        mag[r["prop"][1:]][r["tier"][0]] += 1
top = sorted(mag.items(), key=lambda kv: -sum(kv[1].values()))
print("マスタに無い誌(A+B+D):", len(top), "誌 /", sum(sum(v.values()) for _, v in top), "頁")
for k, v in top[:40]:
    print(f"   {k}: 計{sum(v.values())} (A{v['A']} B{v['B']} D{v['D']})")
json.dump({"rows": rows, "mags": {k: dict(v) for k, v in top}}, open(f"{L}/verify-summary.json", "w", encoding="utf-8"), ensure_ascii=False)
print("→", out)
