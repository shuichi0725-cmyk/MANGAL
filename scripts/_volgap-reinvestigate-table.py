# -*- coding: utf-8 -*-
"""【巻抜け残りの見直し表 2026-11-01】巻抜け残り314頁の見直し(2026-11-01)= 頁ごとに「直せる型 / 判断が要る / 直せない」を付けて表にする。
直せる型は人が確かめた一覧(下の FIX)。残りは各照合器の結果(楽天ローカル・楽天live・NDL・MADB兄弟)から機械で分ける。"""
import csv, os, sys
from collections import defaultdict, Counter
import yaml

sys.stdout.reconfigure(encoding="utf-8")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = "docs/production-diagnostics/"

FIX = {
    "取込もれ(楽天・NDLでISBN確認済み・足せば閉じる)": """shinsengumi fukushuu-no-kyoujuu hard-ando-ruuzu elysion teiaazu-tou-tiara koyoi-omae-to nippon-jinbutsushi kemono-otoko-to-yuutousei-joshi shitsuji-emu romeo houga-purezen-joshikousei-houkichi-eiko-san netchuu-kobo-chan pittosporum blue-flight hereteku-no-ana sanjigen-okotowarinawatashinokeiyakukekkon seijo-yuusha-party-kara-kaikosareta-node-guild-o-tsukuttara-attohoomu-na-saikyou-guild-ni inoz dragon-circus mirrorman-2d omatsuri-piisu-denkiten heterogenia-ringisuteiko inukai-kun-no-shippo murabito-tensei senki-to-yobareta-otoko-ouke-ni-ansatsu-saretara-musume-o-hiroi-isshokenmei-ni-slow-life-o-hajimeru""",
    "別の本が紛れ込んでいる(除けば閉じる)": "tinker-bell",
    "1巻が副題付きの別登録(種2に在るのにどこにも出ていない)": """16-nen-kimi-o-omou-to-konnani-ookiku chuchu-hunter dorabeesu-doraemon-super-baseball-gaiden dotou-no-saikyou-suit-suima-kun hayato-kun-to-saho-chan-wa-honjitsu-mo-ichaama hitokui-origin hodogaya-saichuusokuha-seven katakoi-kekkon kiken-na-chouai kikou-kiden-hiwou-senki kiraware-reijou-wa-gin-no-ouji-ni-amayakasareru linkman love-taishitsu minami-kun-wa-sono-koe-ni-jirasaretai moto-yakuza-wa-shinshi-de-moujuu moto-yan-ooeru-wa-kojirase-elite-no-iinari-omocha nanimo-kikazu-ni-dakasetekure ookisugite-kare-no-are-ga-sakitcho-shika-hairimasen sora-made-itchau yuru-days shin-nippon-jinbutsushi""",
    "1つの刊行が版タブ2つに割れている(まとめれば閉じる)": """1-2-no-1-rou heba-hello-chan maboroshi-no-futsuu-shoujo plamo-kyoushirou pokkapoka shippo-ga-tomodachi toki-no-gyouja tsuma-to-boku-no-shoukibo-na-ikuji tsuihousareta-cheat-fuyo-majutsushi-wa-kimama-na-sekando-life-o-ouka-suru sekai-saikyou-no-majo-hajimemashita""",
    "同じ作品が2頁に分かれている(統合すれば閉じる)": """chotto-morimashita hannintachi-no-file-kindaichi-shounen-no-file-gaiden l-gion mahoujin-guruguru-gaiden-mai-yuuden-kitakita ore-to-mou-ichido-hatsukoi piisu-maker-kurogane premier rinjin-o-maiseyo baka-to-test-to-shoukanjuu-supinauto-sore-ga-bokura-no-nichijou cafe captain-harlock-jigen-koukai gakkou-kachinukisen-jikken-taiketsu-2016 gororo-mamonogatari haishin-chuu-megami-channel hoshi-no-kirby-manpukupupupufantajii marii-to-ellie-no-atelier-zaaruburugu-no-renkinjutsushi-sekando-season non-sutoppu-kyouhei shintouki f1-sokuhou-guranpuri-tengoku nono-chan-zenshuu shin-mimibukuro-kaidan-hyakumonogatari""",
    "版元の移籍で前半が別版元(足せば閉じる)": "pachisuro-de-atta-zenbu-umai-hanashi-zetto",
    "頁そのものが掲載対象外(設定本・ポーズ資料)": "tv-animation-major-characters-handbook-heroes pose-file",
}
PART = {
    "一部だけ埋まる": """zebra gunnm-last-order kaettekita-kita-dora-neko doughnuts-books ura-aka-otoko-wa-dakaretai-seme-sama-no-1-ni-xx-saretai etchi-ni-kisu-shite""",
    "判断が要る: アンソロジー(埋まる巻はあるが、そもそも載せるか)": """neko-punch houkago-pedal star-ocean-second-story star-ocean-sekando-story b-boy horror-occult-kyousaku-daizenshuu hontoni-atta-kowai-hanashi mezase-mangaka-tezuka-akatsuka-show-jushou-sakuhinshuu kuusou-kagaku-dai-bouken-katsugeki-kyousaku-dai-zenshuu lemon-kids doragonkuesuto-4-koma-manga-gekijou zeruda-no-densetsu-4-koma-manga-gekijou comic-cue guruguru-shoukougun fate-kishi hontoni-atta-noroi-no-video-comic yuri-shoujo kyuukoku-no-seijo-desu-kokugai-tsuihousareta-sarechaimashita chou-ten-chan collar-me""",
    "判断が要る: 巻ごとに作画者違い・日付の矛盾・番号の付け直し・版の入り組み": """kandouou-rendetsu suteki-na-kekkon kizudarake-no-tenshitachi ramen-daisuki-koizumi-san-narumi-2014 gakken-manga-sekai-no-rekishi kirikiritei-no-buraun-sensei cleopatra-d-c 81-bunch-no-inu gaddesu-megami-no-ketsumyaku kaina-surugajou-gozen-jiai bikkuriman-omoshiro-land bikkuriman-omoshirorando hana-ichimonme nanda-kanda-de-onna-no-hashori-michi love-neko""",
}
lab = {}
for k, v in list(FIX.items()) + list(PART.items()):
    for s in v.split():
        assert s not in lab, s
        lab[s] = k

rem = [l.split("\t") for l in open(P + "vol_gap_virtual_remain.tsv", encoding="utf-8").read().splitlines()[1:]]
tiers = defaultdict(set)
for f, col in (("volgap-local-fill-v2.tsv", 0), ("volgap-lead-live-fill.tsv", 0), ("volgap-ndl-fill.tsv", 0)):
    for r in csv.reader(open(P + f, encoding="utf-8"), delimiter="\t"):
        if r and r[0] != "tier":
            tiers[r[1]].add(r[0])
tg = defaultdict(list)
for r in csv.DictReader(open(P + "volgap-fill-targets.tsv", encoding="utf-8"), delimiter="\t"):
    tg[r["stem"]].append(r)

rows = []
for stem, title, gaps in rem:
    d = yaml.safe_load(open(f"data/manga.v2/{stem}.yml", encoding="utf-8"))
    ds = sorted(str(v.get("release_date") or "")[:4] for e in d.get("editions") or [] for v in e.get("volumes") or [] if v.get("release_date"))
    first = ds[0] if ds else ""
    au = " ".join(a.get("name") or "" for a in d.get("authors") or [])
    if stem in lab:
        cat = lab[stem]
    else:
        t = tiers.get(stem, set())
        if any(w in (title + au) for w in ("アンソロジー", "競作", "傑作選", "編集部", "企画")) or len(d.get("authors") or []) >= 5:
            cat = "直せない: アンソロジー・寄せ集め"
        elif t & {"REJECT_EDITION", "EXISTS"}:
            cat = "直せない: 見つかるのは別の版・別の作品の本だけ"
        else:
            cat = "直せない: どの情報源にも欠けた巻が無い"
    rows.append({"category": cat, "stem": stem, "title": title, "first_year": first, "gaps": gaps})

order = list(FIX) + list(PART) + ["直せない: 見つかるのは別の版・別の作品の本だけ", "直せない: アンソロジー・寄せ集め", "直せない: どの情報源にも欠けた巻が無い"]
rows.sort(key=lambda r: (order.index(r["category"]), r["stem"]))
with open(P + "volgap-reinvestigate-2026-11-01.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
    w.writeheader()
    w.writerows(rows)
c = Counter(r["category"] for r in rows)
for k in order:
    print(f"{c.get(k, 0):4d}  {k}")
print(f"計 {len(rows)}")
nf = [r for r in rows if r["category"] == "直せない: どの情報源にも欠けた巻が無い"]
dec = Counter((r["first_year"][:3] + "0年代") if r["first_year"] else "不明" for r in nf)
print("どの情報源にも無い頁の、最初の巻の年代:", dict(sorted(dec.items())))
