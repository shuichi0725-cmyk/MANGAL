"""連載誌の是正を seed に書く(本番頁はまだ触らない = 後で _reflect-targeted --only)。
- data/magazines.yml に新しい雑誌キーを足す(末尾追記・既存不変)
- data/seeds/magazine-corrections.yml に slug→magazine を足す(既存キーは触らない)
- data/seeds/magazine-fix-changelog.jsonl に1頁1行
- .cache/magazine-lists/stems.txt = 再生成する manga.v2 ファイル名(SRC stem)
"""
import csv, datetime, json, os, re, sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / ".cache" / "magazine-lists"
TODAY = "2026-11-04"
ART = {  # 記事key → (記事名, revid)
    "jump-plus": ("少年ジャンプ+", 111584975), "wsj-list": ("週刊少年ジャンプ連載作品の一覧", 111238049),
    "jump-sq": ("ジャンプスクエア", 111299297), "monthly-jump": ("月刊少年ジャンプ", 110944411),
    "v-jump": ("Vジャンプ", 111361831), "saikyo-jump": ("最強ジャンプ", 111298546), "wyj": ("週刊ヤングジャンプ", 111621594),
    "ultra-jump": ("ウルトラジャンプ", 111436922), "wsj-zokan": ("週刊少年ジャンプの増刊号", 109514454),
    "fresh-jump": ("フレッシュジャンプ", 110191752), "champion-list": ("週刊少年チャンピオン連載作品の一覧", 111563117),
    "wsm-list": ("週刊少年マガジン連載作品の一覧", 111539313), "wss-list": ("週刊少年サンデー連載作品の一覧", 111629295),
}
NEW_MAGS = {  # 新設する雑誌キー(★追記のみ)
    "shonen-jump-plus": ("少年ジャンプ+", "shounen"), "jump-sq": ("ジャンプSQ", "shounen"),
    "monthly-shonen-jump": ("月刊少年ジャンプ", "shounen"), "saikyo-jump": ("最強ジャンプ", "kodomo"),
    "v-jump": ("Vジャンプ", "shounen"), "fresh-jump": ("フレッシュジャンプ", "shounen"),
    "tonari-no-young-jump": ("となりのヤングジャンプ", "seinen"),
}
AUTO_EXCLUDE = {"captain-2", "kishibe-rohan-wa-ugokanai", "isshokenmei-ni-kurashite-ii-desuka"}
# 人が見た組の裁定(slug → (雑誌, 根拠に使う記事, 補足))。 None = 触らない
J = "shonen-jump-plus"
MANUAL = {}
for s in """accel-star black-clover-gaiden-quartet-knights boku-no-hero-academia-smash bokutachi-hoikuka-koukou-1-nensei bubble-2022
cheer-otoko-goo-breakers exp-0 fuchuu-sanokuen-jiken-o-keikaku-jikkou-shita-noha-watashi-desu fuji-no-yamai-wa-fushi-no-yamai gaming-ojou-sama
godzilla-kaijuu-wakusei hachuurui-chan-wa-natsukanai haikyuubu hetalia-world-stars high-risk-mission-therapy hinmin-choujin-kanenashi-kun
honnori-donpatchi jikan-no-shihaisha jingi-naki-yoshida-ke jumyou-o-kaitotte-moratta-ichinen-ni-tsuki-ichimanen-de juuni-taisen
kami-sama-ki-sama-o-koroshitai kao-ga-konoyo-ni-muite-nai karada-sagashi karada-sagashi-i keppare-matsubara-san koisuru-wan-piisu
kuchi-nikansuru-ankeeto kuroko-no-basket-replace-plus let-haikyuu machikoromatchi-plus magical-patissier-kosaki-chan mainchi-yuzuman
naruto-konoha-shinden naruto-sasuke-rendetsu nekota-hiyori oishii-coffee-no-irekata omukae-ni-agarimashita ore-o-suki-nano-wa-omae-dake-kayo
oyakusoku-no-neverland psycho-against psycho-pass-3 red-list-2 rocking-you romantic-killer seiyuu-mashimashi-club shijinsou-no-satsujin
shokugeki-no-sooma-retowaaru shouwa-otome-otogibanashi spider-man-octopus-girl ssss-gridman summer-time-renda-2026-mizen-jiko-bukken
taishou-otome-otogibanashi-pessimist-no-shokutaku tenjin touken-ranbu-hanamaru wan-piisu-kobii-ni-no-kohiyama
cherry-teacher-sakura-naoki eru-doraibu hottarakashi-meshi kaijuu-hachigou-side-b karada-sagashi-za-last-night rough-diamond-2014
yomikirishuu-koi yomikirishuu-sei hidarikiki-no-eren rettougan-no-tensei-majutsushi koibito-ijou-yuujin-miman""".split():
    MANUAL[s] = (J, "jump-plus", "")
MANUAL["gunjou-ni-siren"] = (J, "jump-plus", "初出は月刊YOU(雑誌マスタ未登録)→J+へ移籍。旧値マーガレットは誤り")
for s in "kakuriyo-monogatari boku-no-mary isshokenmei-hajime-hajime-kun kajitetsu-ouji the-samurai uratarou yayoi-no-oozora heesei-policemen kurogane-no-valhallian ribidoozu".split():
    MANUAL[s] = ("weekly-young-jump", "wyj", "")
MANUAL["one-punch-man"] = ("tonari-no-young-jump", "wyj", "となりのヤングジャンプ(週刊ヤングジャンプのWeb版)で2012年6月14日〜連載")
for s in "jojo-no-kimyou-na-bouken-crazy-diamond-no-akuryouteki-shitsuren the-jojolands it maou-sama-chotto-sore-totte mononogatari tenjou-tenge".split():
    MANUAL[s] = ("ultra-jump", "ultra-jump", "")
for s in "shinigami-kun tekkenji-kousuke".split():
    MANUAL[s] = ("fresh-jump", "fresh-jump", "初出=フレッシュジャンプ(のち月刊少年ジャンプへ)")
for s in """7thgarden fantasma hanna-sensei-shigoto-o-shite-kudasai kanshikan-tsunemori-akane katsugeki-touken-ranbu kekkai-sensen-back-2-back kuoridia-code
rurouni-kenshin-meiji-kenkaku-roman-tan-hokkaido-hen salaryman-futsumashi-okumura-yukio-no-aishuu sensou-kyoushitsu serapuchi black-torch demon-tune
kawaisugi-crisis kojirase-hyakki-domainaa phantom-busters taishou-otome-otogibanashi untrace yuugai-shitei-doukyuusei""".split():
    MANUAL[s] = ("jump-sq", "jump-sq", "")
for s in "claymore gyagu-manga-hiyori mahoutsukai-kurohime rosario-to-vampire tegami-bachi".split():
    MANUAL[s] = ("monthly-shonen-jump", "jump-sq", "ジャンプSQの表の注記「←『MJ』…より継続」= 初出は月刊少年ジャンプ")
for s in "captain kekkoukamen mist-story".split():
    MANUAL[s] = ("monthly-shonen-jump", "monthly-jump", "")
for s in """chin-piece digimon-dreamers fischer-s-one-piece-7-tsunagi-no-daihihou kimetsu-gakuen korosensee-quest kuri-hiroi sakamoto-holidays
fire-emblem-engage fuwari-donpatchi kaijuu-hachigou-relax wan-piisu-gakuen""".split():
    MANUAL[s] = ("saikyo-jump", "saikyo-jump", "")
for s in "slime-morimori dragon-quest-dai-no-daibouken-yuusha-aban-to-gokuen-no-maou chokin-suit-kyasshuman monhan-manga-pokapoka-airuumura".split():
    MANUAL[s] = ("v-jump", "v-jump", "")
MANUAL["dr-eggs"] = ("grand-jump", "jump-plus", "J+の表の注記「『GJ』作品の特別編」= グランドジャンプ連載")
MANUAL["uramiya-honpo-diablo"] = ("grand-jump", "jump-plus", "J+の表の注記「『GJ』作品の特別読切」= グランドジャンプ連載")
MANUAL["otome-no-teikoku"] = ("grand-jump", "jump-plus", "J+の表の注記「←『GJ公式サイト』」= グランドジャンプ(Web)で開始しJ+へ移籍")
MANUAL["sengoku-koshien"] = ("weekly-shonen-sunday", "wss-list", "")
MANUAL["dreams"] = ("weekly-shonen-magazine", "wsm-list", "初出=週刊少年マガジン(のちマガジンSPECIALへ移籍)")
MANUAL["nesshou-hanazawa-koukou"] = ("champion", "champion-list", "頁の出版社は再刊の徳間書店")
MANUAL["kagemusha-tokugawa-ieyasu"] = ("weekly-shonen-jump", "wsj-list", "頁の出版社は再刊の新潮社")
ART_OF = {"shonen-jump-plus": "jump-plus", "weekly-shonen-jump": "wsj-list", "jump-sq": "jump-sq", "monthly-shonen-jump": "monthly-jump",
          "v-jump": "v-jump", "saikyo-jump": "saikyo-jump", "fresh-jump": "fresh-jump", "weekly-shonen-magazine": "wsm-list",
          "weekly-shonen-sunday": "wss-list", "champion": "champion-list"}


def stem_of(slug, rev):
    if (ROOT / "data" / "manga.v2" / f"{slug}.yml").exists():
        return slug
    for k in rev.get(slug, []):
        if (ROOT / "data" / "manga.v2" / f"{k}.yml").exists():
            return k
    return None


def main(write: bool):
    auto = list(csv.DictReader(open(D / "decide-auto.tsv", encoding="utf-8"), delimiter="\t"))
    review = {r["slug"]: r for r in csv.DictReader(open(D / "decide-review.tsv", encoding="utf-8"), delimiter="\t")}
    plan = {}
    for r in auto:
        if r["slug"] in AUTO_EXCLUDE:
            continue
        art = ART_OF[r["to"]]
        ev = r["ev"].partition(": ")[2]
        plan[r["slug"]] = {"old": r["cur"], "new": r["to"], "art": art, "line": ev, "note": "", "title": r["title"]}
    for s, (mag, art, note) in MANUAL.items():
        if s not in review:
            sys.exit(f"MANUAL の slug が review に無い: {s}")
        r = review[s]
        ev = next((part.partition(": ")[2] for part in r["ev"].split(" ‖ ") if part.startswith(art + ":")), r["ev"])
        plan[s] = {"old": r["cur"], "new": mag, "art": art, "line": ev, "note": note, "title": r["title"]}
    existing = yaml.safe_load(open(ROOT / "data" / "seeds" / "magazine-corrections.yml", encoding="utf-8"))["corrections"]
    clash = sorted(set(plan) & set(existing))
    for s in clash:
        plan.pop(s)
    ov = yaml.safe_load(open(ROOT / "data" / "seeds" / "slug-overrides.yml", encoding="utf-8"))["overrides"]
    rev = {}
    for k, v in ov.items():
        if isinstance(v, dict) and v.get("slug"):
            rev.setdefault(v["slug"], []).append(k)
    stems, missing = [], []
    for s in plan:
        st = stem_of(s, rev)
        (stems.append(st) if st else missing.append(s))
    from collections import Counter
    print("計", len(plan), "頁 / 既存seedと重複で除外", clash, "/ stem不明", missing)
    print(Counter((p["old"], p["new"]) for p in plan.values()).most_common())
    if not write:
        return
    # 1) 雑誌マスタ(末尾追記)
    mags_txt = (ROOT / "data" / "magazines.yml").read_text(encoding="utf-8")
    mags = yaml.safe_load(mags_txt)
    add = [k for k in NEW_MAGS if k not in mags]
    if add:
        block = "\n# ★2026-11-04 連載誌の是正(忘却バッテリー=少年ジャンプ+ のユーザ報告から)で追加。 Web/ジャンプ系列誌が無く、\n" \
                "#   種3のAI埋めが集英社の少年漫画をまとめて週刊少年ジャンプにしていた。 根拠= ja.wikipedia 各誌の掲載作品一覧。\n"
        for k in add:
            name, demo = NEW_MAGS[k]
            block += f"{k}:\n  name: {name}\n  publisher: shueisha\n  demographic: {demo}\n"
        if not mags_txt.endswith("\n"):
            mags_txt += "\n"
        (ROOT / "data" / "magazines.yml").write_text(mags_txt + block, encoding="utf-8")
    # 2) magazine-corrections.yml(末尾追記・yaml.dump で引用符も正しく)
    entries = {}
    for s, p in sorted(plan.items()):
        name, revid = ART[p["art"]]
        ev = re.sub(r"\s+", " ", p["line"]).strip()[:140]
        evidence = f"ja.wikipedia「{name}」(revid {revid}) の掲載作品一覧に題+著者で一致: {ev}"
        if p["note"]:
            evidence += f"。{p['note']}"
        evidence += f"。旧値 {p['old']}(種3のAI埋め)"
        entries[s] = {"magazine": p["new"], "source": "wiki-verified", "evidence": evidence, "added_at": TODAY}
    dumped = yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=10000)
    dumped = "\n".join(("  " + ln) if ln else ln for ln in dumped.splitlines())
    corr_p = ROOT / "data" / "seeds" / "magazine-corrections.yml"
    txt = corr_p.read_text(encoding="utf-8")
    if not txt.endswith("\n"):
        txt += "\n"
    corr_p.write_text(txt + "  # ★2026-11-04 連載誌の一括是正(ユーザ「連載はジャンププラスなはず。類似も探して修正して」)。\n"
                      "  #   ja.wikipedia 13誌の掲載作品一覧 × 本番の題+著者+開始年+出版社で突合。 自動=一覧1誌だけ/年と出版社が一致/移籍注記なし、\n"
                      "  #   残りは注記(←『MJ』等)を読んで1件ずつ裁定。 道具= .cache/magazine-lists/(mag_audit2/mag_decide)。\n"
                      + dumped + "\n", encoding="utf-8")
    yaml.safe_load(corr_p.read_text(encoding="utf-8"))  # 壊していないか
    # 3) changelog
    at = datetime.datetime.now().isoformat(timespec="seconds")
    with open(ROOT / "data" / "seeds" / "magazine-fix-changelog.jsonl", "a", encoding="utf-8") as f:
        for s, p in sorted(plan.items()):
            f.write(json.dumps({"op": "magazine-correct", "slug": s, "title": p["title"], "before": None if p["old"] == "(空)" else p["old"],
                                "after": p["new"], "evidence": entries[s]["evidence"], "at": at,
                                "via": "magazine-corrections.yml → _reflect-targeted --only",
                                "reversible": "magazine-corrections.yml の当該キーを消して再反映"}, ensure_ascii=False) + "\n")
    (D / "stems.txt").write_text("\n".join(sorted(set(stems))) + "\n", encoding="utf-8")
    print("書いた: magazines.yml +", add, "/ corrections +", len(entries), "/ stems", len(set(stems)))


if __name__ == "__main__":
    main("--write" in sys.argv)
