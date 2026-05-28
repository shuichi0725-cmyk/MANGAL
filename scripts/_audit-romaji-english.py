"""種a title.romaji の 「英語含有」 実態調査。

仮説: title.romaji は 「Hepburn 純粋」 のはずだが、 実際は
  - 'Dragon Ball' (= 英単語そのまま)
  - 'Shangri-La Frontier' (= 英単語 + Hepburn)
  - 'Death Note' (= 完全英語)
が含まれる。

判定方法:
  - native が カタカナ主体 (= 50% 以上 カナ) なら、 romaji は Hepburn のはず
  - その romaji を 「英語辞書 単語数」 で 検査
  - 「英語単語ヒット率 高い」 = 英語表記、 「単語ヒットなし」 = 純 Hepburn
  - 簡易版: romaji に 「 」 (= スペース) 区切り + 各単語 が 英語 dictionary に存在
"""
import sys, gzip, json, re
sys.stdout.reconfigure(encoding='utf-8')

# 英語頻出語 簡易 dict (= 漫画 title でよく出る 英単語)
ENGLISH_WORDS = {
    'the', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'a', 'an',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those', 'i', 'you', 'we', 'they', 'he', 'she', 'it',
    'my', 'your', 'our', 'their', 'his', 'her', 'its',
    'dragon', 'ball', 'death', 'note', 'one', 'piece', 'naruto', 'bleach',
    'fairy', 'tail', 'attack', 'titan', 'demon', 'slayer', 'hero', 'academia',
    'tokyo', 'ghoul', 'fullmetal', 'alchemist', 'sword', 'art', 'online',
    'jujutsu', 'kaisen', 'chainsaw', 'man', 'spy', 'family',
    'love', 'live', 'star', 'wars', 'space', 'time', 'world', 'life', 'school',
    'high', 'low', 'big', 'small', 'new', 'old', 'first', 'last', 'next',
    'shangri', 'la', 'frontier', 'darkside', 'blues', 'patlabor',
    'food', 'wars', 'tower', 'god', 'solo', 'leveling',
    'eyeshield', 'hunter', 'fist', 'north', 'saint', 'seiya', 'jojo', 'bizarre', 'adventure',
    'bleach', 'gintama', 'inuyasha', 'rurouni', 'kenshin', 'yuyu', 'hakusho',
    'evangelion', 'gundam', 'macross', 'akira', 'ghost', 'shell',
    'rose', 'angel', 'devil', 'king', 'queen', 'prince', 'princess', 'lord', 'lady',
    'black', 'white', 'red', 'blue', 'green', 'yellow', 'silver', 'gold',
    'magic', 'magical', 'witch', 'wizard', 'sorcerer',
    'beyond', 'within', 'after', 'before', 'during',
    'wild', 'mild', 'good', 'bad', 'great', 'super', 'mega', 'ultra',
    'final', 'fantasy', 'mystery', 'horror', 'romance',
    'jojos', 'jojo', 'kimetsu', 'yaiba',  # 紛れ込み防止
    'club', 'cafe', 'bar', 'restaurant',
    'project', 'mission', 'plan', 'mission',
    'and', 'vs', 'versus', 'with', 'without',
    'no', 'yes', 'na',  # 「no」 は Hepburn の助詞 「の」 と被るが多くは英語
    'and', 'but', 'so', 'if', 'when', 'where', 'why', 'how',
    'd', 'p', 'q',  # 単独アルファベット
}

def count_english_words(romaji: str) -> tuple[int, int]:
    """returns (english_word_count, total_word_count)"""
    if not romaji: return (0, 0)
    # subtitle 除去 (= : 以降切る)
    r = romaji.split(':')[0]
    # 単語分割 (= 空白 / 記号で)
    words = re.findall(r"[a-zA-Z']+", r.lower())
    if not words: return (0, 0)
    eng = sum(1 for w in words if w in ENGLISH_WORDS)
    return (eng, len(words))

def is_katakana_heavy(native: str) -> bool:
    """native が カナ 50% 以上 か"""
    if not native: return False
    kata = sum(1 for c in native if 'ァ' <= c <= 'ヿ')
    hira = sum(1 for c in native if 'ぁ' <= c <= 'ゖ')
    kanji = sum(1 for c in native if '一' <= c <= '鿿')
    total = kata + hira + kanji
    if total == 0: return False
    return kata / total >= 0.5

def main():
    print('loading 種a...', flush=True)
    total = 0
    kata_heavy = 0
    has_english_word = 0
    pure_english = 0  # 全単語 英語
    samples_pure_eng = []
    samples_mixed = []
    samples_clean = []
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            total += 1
            t = e.get('title') or {}
            native = t.get('native') or ''
            romaji = t.get('romaji') or ''
            if not is_katakana_heavy(native): continue
            kata_heavy += 1
            eng, all_w = count_english_words(romaji)
            if all_w == 0: continue
            if eng >= 1:
                has_english_word += 1
            if eng == all_w and all_w >= 2:
                pure_english += 1
                if len(samples_pure_eng) < 15:
                    samples_pure_eng.append((native, romaji))
            elif eng >= 1 and eng < all_w:
                if len(samples_mixed) < 15:
                    samples_mixed.append((native, romaji, f'{eng}/{all_w}'))
            else:  # eng == 0
                if len(samples_clean) < 15:
                    samples_clean.append((native, romaji))

    print(f'  全 entries: {total:,}')
    print(f'  カナ主体 (= 50%+ カタカナ) native: {kata_heavy:,}')
    print(f'    その内 romaji に 英単語含む: {has_english_word:,} ({has_english_word*100/kata_heavy:.1f}%)')
    print(f'    その内 romaji 完全英語 (= 2 単語以上 全部英語): {pure_english:,} ({pure_english*100/kata_heavy:.1f}%)')
    print()
    print('=== カナ主体 native × romaji 完全英語 (= 「ローマ字 field に 英語入ってる」) ===')
    for n, r in samples_pure_eng[:15]:
        print(f'  native={n!r}  romaji={r!r}')
    print()
    print('=== カナ主体 native × romaji 部分英語 (= ハイブリッド、 例 「Shangri-La Frontier」) ===')
    for n, r, ratio in samples_mixed[:15]:
        print(f'  native={n!r}  romaji={r!r}  ({ratio})')
    print()
    print('=== カナ主体 native × romaji 純 Hepburn (= 英単語ヒットなし、 多分 Hepburn) ===')
    for n, r in samples_clean[:15]:
        print(f'  native={n!r}  romaji={r!r}')

if __name__ == '__main__':
    main()
