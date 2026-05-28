"""著名 T4 作品 の en 不在 確認 (= en 抜けの実態調査)"""
import yaml
from pathlib import Path

YAML_PATH = Path('data/seeds/series-supplement-v2.yml')
OUT = Path('.cache/check-famous-en.txt')

TARGETS = [
    '鬼滅の刃', '進撃の巨人', '鋼の錬金術師', '名探偵コナン',
    '銀魂', '呪術廻戦', '約束のネバーランド', '幽☆遊☆白書',
    '不滅のあなたへ', '魔法少女まどか☆マギカ', '弱虫ペダル',
    '七つの大罪', '東京リベンジャーズ', '蟲師', 'るろうに剣心',
    '葬送のフリーレン', '黒子のバスケ', '北斗の拳', '美味しんぼ',
    '寄生獣', 'ハイキュー!!', 'ハンター×ハンター', 'ベルセルク',
    '頭文字D', '美少女戦士セーラームーン', '幽遊白書',
    '銀牙 -流れ星 銀-', 'YAWARA!', 'スラムダンク', '聖闘士星矢',
    'こちら葛飾区亀有公園前派出所', 'バカボンド', '宇宙兄弟',
    '天才バカボン', 'マカロニほうれん荘', 'タッチ', 'はじめの一歩',
    '岸辺露伴は動かない',
]

with YAML_PATH.open('r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

found = {}
for entry in data['series']:
    key = entry.get('key', '')
    parts = key.split('|')
    title_parts = [p[5:] for p in parts if p.startswith('name:')]
    if not title_parts:
        continue
    title = title_parts[-1]
    if title in TARGETS:
        alt = entry.get('alternative_titles') or {}
        en = alt.get('en') if isinstance(alt, dict) else None
        qid = None
        for p in parts:
            if p.startswith('qid:'):
                qid = p[4:]
                break
        found.setdefault(title, []).append({'en': en, 'qid': qid})

lines = ['=== 著名 T4 作品 en 抜け確認 ===\n']
en_missing = 0
en_present = 0
not_found = 0
for t in TARGETS:
    entries = found.get(t)
    if not entries:
        lines.append(f'  ❌ NOT FOUND: {t}\n')
        not_found += 1
        continue
    for e in entries:
        en = e['en']
        qid = e['qid'] or '-'
        mark = '✅' if en else '❌'
        lines.append(f'  {mark} {t:30s} qid={qid:12s} en={en or "(none)"}\n')
        if en:
            en_present += 1
        else:
            en_missing += 1

lines.append('\n=== summary ===\n')
lines.append(f'  en あり: {en_present}\n')
lines.append(f'  en なし: {en_missing}\n')
lines.append(f'  not found: {not_found}\n')

OUT.write_text(''.join(lines), encoding='utf-8')
print(f'wrote {OUT}')
print(f'  en あり: {en_present}, en なし: {en_missing}, not found: {not_found}')
