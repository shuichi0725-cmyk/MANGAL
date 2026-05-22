"""
name: prefix の a-miss 残 14 件 を 直接 fill。
qid: 26 件と同じ protocol で Python 経由 → 直接 JSON 書き出し → apply。
"""
import json
import os

# 抽出した 14 件の exact key + en 案
fills = {
    'name:“HOLY”堀川雅光|name:鉄腕ブレイク':
        {"alternative_titles": {"en": "Tetsuwan Break"}},
    'name:pupps|name:ハズレスキル「逃げる」で俺は極限低レベルのまま最強を目指す|sub:経験値抑制&レベル1でスキルポイントが死ぬほどインフレ、スキルが取り放題になった件':
        {"alternative_titles": {"en": "Hazure Skill 'Nigeru' de Ore wa Kyokugen Tei Level no Mama Saikyou wo Mezasu"}},
    'name:quiet|name:「ジョブが忍者の癖にやかましすぎるだろ……」と冒険者パーティを追放されてきた爆音忍者四人衆と、来月末までに莫大な借金を返さなくちゃいけない子爵令嬢の浮き沈み激しい二ヶ月分の人生':
        {"alternative_titles": {"en": "Job ga Ninja no Kuse ni Yakamashisugiru daro to Bakuon Ninja Yoninshuu to Shishakurei Joou no Jinsei"}},
    'name:quiet|name:最高難度迷宮でパーティに置き去りにされたSランク剣士、本当に迷いまくって誰も知らない最深部へ|sub:俺の勘だとたぶんこっちが出口だと思う':
        {"alternative_titles": {"en": "Saikou Nando Meikyuu de Party ni Okizari ni Sareta S-Rank Kenshi, Hontou ni Mayoimakutte Daremo Shiranai Saishinbu e"}},
    'name:sime|name:龍鎖のオリ|sub:心の中の"こころ" : This is the story of a boy lost the sound mind,and the story he starts':
        {"alternative_titles": {"en": "Ryuusa no Ori"}},
    'name:すかいふぁーむ|name:追放されたお荷物テイマー、世界唯一のネクロマンサーに覚醒する|sub:The tale of the necromancer':
        {"alternative_titles": {"en": "The Tale of the Necromancer"}},
    'name:へいろー|name:大罪ダンジョン教習所の反面教師|sub:外れギフトの〈案内人〉が実は最強の探索者であることを、生徒たちはまだ知らない':
        {"alternative_titles": {"en": "Taizai Dungeon Kyoushuujo no Hanmen Kyoushi"}},
    'name:みょん|name:手に入れた催眠アプリで夢のハーレム生活を送りたい':
        {"alternative_titles": {"en": "Te ni Ireta Saimin App de Yume no Harem Seikatsu wo Okuritai"}},
    'name:中野晴行|name:ブラック・ジャック|sub:ザ・ピース&アース : アンコール出版':
        {"alternative_titles": {"en": "Black Jack: The Peace & Earth"}},
    'name:坂本あかみ|name:カラミざかRe:':
        {"alternative_titles": {"en": "Karamizaka Re:"}},
    'name:大熊猫介|name:脱法テイマーの成り上がり冒険譚|sub:Sランク美少女冒険者が俺の獣魔になっテイマす : THE COMIC':
        {"alternative_titles": {"en": "Dappou Tamer no Nariagari Boukentan"}},
    'name:御守リツヒロ|name:ワールドエンド: デバッガー':
        {"alternative_titles": {"en": "World End: Debugger"}},
    'name:桃井桃子|name:1: 2交際はラブコメに入りますか?':
        {"alternative_titles": {"en": "1:2 Kousai wa Love Comedy ni Hairimasu ka?"}},
    "name:涼子|name:トロイメライ|sub:when it rains,look for rainbows.when it's dark,look for stars":
        {"alternative_titles": {"en": "Träumerei"}},
}

# sub の '&' は YAML 側で実際に何かを確認するため、 まず seed 側 key を 再 verify する必要あり。
# 中野晴行 ブラック・ジャック の sub 文字列 (= '&' or '＆') を 検証して上書き。

import yaml
with open('data/seeds/series-supplement-v2.yml') as f:
    doc = yaml.safe_load(f)
real_keys = {e['key'] for e in doc['series']}

# 実 key と一致しないものを 検出 + 修正試行
import re
KATAKANA = re.compile(r'[゠-ヿ]')
unmatched = [k for k in fills.keys() if k not in real_keys]
if unmatched:
    print(f"⚠️  {len(unmatched)} keys unmatched, attempting auto-fix...")
    for bad_key in unmatched:
        # creator + title で 候補検索
        parts = bad_key.split('|')
        name_parts = [p[5:] for p in parts if p.startswith('name:')]
        if len(name_parts) < 2: continue
        creator, title = name_parts[0], name_parts[-1]
        candidates = [
            e['key'] for e in doc['series']
            if e['key'].startswith('name:') and creator in e['key'] and title in e['key']
            and KATAKANA.search(title) and not (e.get('alternative_titles') or {}).get('en')
        ]
        if len(candidates) == 1:
            real_key = candidates[0]
            fills[real_key] = fills.pop(bad_key)
            print(f"  fixed: {bad_key[:60]!r} → {real_key[:60]!r}")
        else:
            print(f"  ❌ can't auto-fix (candidates={len(candidates)}): {bad_key!r}")

assert len(fills) == 14, f"Expected 14 entries, got {len(fills)}"

out_path = "data/seeds/_fills/amiss-fix-name.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(fills, f, ensure_ascii=False, indent=2)
print(f"Wrote {len(fills)} entries to {out_path}")
