"""
en review で flag された 94 件の en field を 正しい値に修正。

input:
  - .cache/review/all-flags.json (= 8 agents の flag を集約、 90 件)
  - 加えて 私の sampling で agents が漏らした 4 件 (= manual 追加)
output:
  - data/seeds/_fills/en-corrections.json (= apply-fills 形式)
"""
import json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
FLAGS = ROOT / ".cache" / "review" / "all-flags.json"
OUT = ROOT / "data" / "seeds" / "_fills" / "en-corrections.json"

# idx → corrected en の マッピング
# (= agents 90 件 + 私の sampling 漏れ 4 件 = 94 件)
CORRECTIONS = {
    # === SEVERE (= 別作品名混入) → Hepburn ローマ字 or 妥当な意訳 ===
    9925: "Destroy All Humankind. They Can't Be Regenerated.",
    9498: "La Vie en Rose",
    24466: "Shinsengumi Ibun Peace Maker",
    9492: "Bujingai",
    39722: "Ultra Ninpouchou Kira",
    1809: "Infinite Gacha: Reincarnated Trash Hero at Lv9999",
    51148: "Yuukyuu Gensoukyoku Official Comic Fan Book",
    73217: "Air Rise",
    3366: "The Gyaru Who Was Supposed to Confess to Me as a Penalty Game Is Clearly Head Over Heels for Me",
    2899: "Hard Rock",
    15936: "Otoko Sui!",
    5244: "Saikyou Onna Shishou-tachi ga Ikusei Houshin o Megutte Shuraba",
    1340: "Atom Konjaku Monogatari",
    14116: "Cipher Academy",
    9432: "An Old Man from the Countryside Becomes a Sword Saint",
    4064: "Himawari",
    24058: "Makai Gaeri no Rettou Nouryokusha",
    53613: "Zero",
    16831: "Kuryou Kyoushitsu",
    4347: "Shishunki na Adam",
    4816: "Arafou Kenja no Isekai Seikatsu Nikki",
    14209: "Mitarai Kiyoshi: Seiro no Umi",
    55593: "Doraemon: Nobita no Wan Nyan Jikuuden",
    49178: "Cross Roads",
    7426: "A Yuri Story About a Girl Who Insists Girls Can't Be Together but Falls Hard in 100 Days",
    15799: "The Corporate Slave Wants to Be Healed by a Little Ghost Girl",
    5399: "Omou ga Mama ni",
    6749: "Seija Musou",
    14757: "Senmetsu Madou no Saikyou Kenja",
    16333: "Mashranbo",
    190: "No-Rin",
    7: "I'm Standing on a Million Lives",
    202: "Shoushimin Series: Spring-Limited Strawberry Tart Incident",
    466: "The Villager at Lv999",
    292: "Motto, Ikitai...",
    841: "Yancha Goal!",
    49192: "Harulock",
    1936: "Himuro no Tenchi Fate/School Life",
    16092: "Menhera Keiji",
    5438: "Tensei Kyuuketsuki-san wa Ohirune ga Shitai",
    14444: "Sayounara Ryuusei, Konnichiwa Jinsei",
    20567: "Kyokujitsu no Kantai",
    51257: "Atelier Judie",
    18511: "Ruri no Houseki",
    8033: "The A-Rank Party Leaver Aims for the Labyrinth's Deepest Floor with His Former Students",
    59658: "Boku o Tsutsumu Tsuki no Hikari",
    12486: "Ginsou Kikou Odian ORO",
    12007: "Hoshitabi Shounen",
    # === WRONG (= 意味乖離) ===
    45137: "Place Fajisuto Money",
    55632: "Mokkoro-kun",
    686: "I'm Gonna Be an Angel!",
    5431: "Chamo",
    16460: "Mitsuya-sensei no Keikakuteki na Edzuke",
    16013: "Kimun Kamui",
    6564: "Leo-kun is Kind Today Too",
    22836: "Iron Muscle",
    14580: "Taira Miya",
    15801: "Warau Ishi",
    10045: "Koisuru Butsuzou",
    23664: "Megami no Matsuge",
    21161: "Hanamoto Ari",
    19606: "Oda Cinnamon Nobunaga",
    603: "Neon Genesis Evangelion: Girlfriend of Steel 2nd",
    24233: "Kamisama Sacrifice",
    52827: "Alya Sometimes Hides Her Feelings in Russian",
    87: "Robotics;Notes",
    20227: "Jinrui Shikin",
    121: "A-kun (17) no Sensou",
    482: "Akamakura",
    507: "Phantom Burai",
    20725: "Getsuyoubi no Koibito",
    14727: "Tensai Densetsu Dai 2 Shou",
    18953: "Inugami Sukekiyo",
    23729: "Seito no Shuchou, Kyoushi no Honbun",
    22833: "Rurou no Kusari",
    3154: "Genshoku Choujin Paint-Man",
    3063: "Sabaku no Usagi",
    2073: "Touhou Bougetsushou: Tsuki no Inaba to Chijou no Inaba",
    22156: "Fujimaru!",
    21191: "Kagishi",
    22529: "Apollo ni Sayonara",
    12847: "Saihate Drive",
    9875: "Mitsubachi no Kiss",
    849: "Kain",
    4472: "Pittari!!",
    # === TRUNC (= 切詰め) ===
    14675: "The Naughty Little Devil Is Skilled at Undressing and Too Beastly!",
    460: "Arafou Kenja no Isekai Seikatsu Nikki",
    9185: "Gokudou-kun Manyuuki",
    9529: "Chouritsu Soukou Zyklus",
    # === LANG (= 英語以外) ===
    12014: "Aozora no Tamago",
}

# sampling 漏れ 4 件 (= 私の手動 review で 検出、 agents が catch しなかった)
# title から idx を 検索する
SAMPLING_EXTRAS_BY_TITLE = {
    "コミック乱セレクション銅頭鉄額": "Comic Ran Selection: Doutou Tetsugaku",
    "ロマンスは剣の輝き2": "Romance wa Ken no Kagayaki 2",
    "のんポリズム": "Nonpolism",
    "運命の巻戻士": "Unmei no Makimodoshi",
}

def main():
    with SEED3.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    # idx → key の マッピング
    idx_to_key = {}
    title_to_idx = {}
    for i, e in enumerate(doc["series"]):
        idx_to_key[i] = e["key"]
        # title 抽出 (= name parts の last)
        key = e["key"]
        parts = key.split("|")
        name_parts = [p[5:] for p in parts if p.startswith("name:")]
        title = name_parts[-1] if name_parts else ""
        if title in SAMPLING_EXTRAS_BY_TITLE:
            title_to_idx[title] = i

    # sampling extras を CORRECTIONS に merge
    for title, en in SAMPLING_EXTRAS_BY_TITLE.items():
        if title not in title_to_idx:
            print(f"⚠️  sampling extra not found: {title!r}")
            continue
        idx = title_to_idx[title]
        CORRECTIONS[idx] = en

    print(f"Total corrections: {len(CORRECTIONS)}")

    # fills dict 構築
    fills = {}
    missing = []
    for idx, new_en in CORRECTIONS.items():
        if idx not in idx_to_key:
            missing.append(idx)
            continue
        key = idx_to_key[idx]
        fills[key] = {"alternative_titles": {"en": new_en}}

    if missing:
        print(f"⚠️  {len(missing)} idx not found in seed3: {missing[:5]}")

    print(f"Fills written: {len(fills)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(fills, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
