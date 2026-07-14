# -*- coding: utf-8 -*-
"""slug生成lib(2026-07-06): janome分かち+カタカナ貪欲辞書変換(katakana-english.yml)+ヘボン。
生成器/再slugの共通実装。誤爆ガード=語中マッチ禁止。"""
# -*- coding: utf-8 -*-
"""slug再生成v3: カタカナ連続部を辞書の最長一致で貪欲変換(janome分割に依存しない)。
残ドラフト全件で new!=old を検出→後退ガード→rename+三点同期。"""
import glob, json, os, re, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
from janome.tokenizer import Tokenizer
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = Tokenizer()
DIC = (yaml.safe_load(open(f"{ROOT}/data/seeds/katakana-english.yml", encoding="utf-8")) or {}).get("mappings", {})
KEYS = sorted(DIC.keys(), key=len, reverse=True)  # 最長一致

TBL = {'キャ':'kya','キュ':'kyu','キョ':'kyo','シャ':'sha','シュ':'shu','ショ':'sho','チャ':'cha','チュ':'chu','チョ':'cho','ニャ':'nya','ニュ':'nyu','ニョ':'nyo','ヒャ':'hya','ヒュ':'hyu','ヒョ':'hyo','ミャ':'mya','ミュ':'myu','ミョ':'myo','リャ':'rya','リュ':'ryu','リョ':'ryo','ギャ':'gya','ギュ':'gyu','ギョ':'gyo','ジャ':'ja','ジュ':'ju','ジョ':'jo','ビャ':'bya','ビュ':'byu','ビョ':'byo','ピャ':'pya','ピュ':'pyu','ピョ':'pyo','ウィ':'wi','ウェ':'we','ウォ':'wo','ヴァ':'va','ヴィ':'vi','ヴェ':'ve','ヴォ':'vo','ヴ':'vu','ファ':'fa','フィ':'fi','フェ':'fe','フォ':'fo','ティ':'ti','ディ':'di','デュ':'dyu','チェ':'che','シェ':'she','ジェ':'je','ツァ':'tsa','ツェ':'tse','ツォ':'tso','トゥ':'tu','ドゥ':'du',
'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho','マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo','ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo','ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do','バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po','ァ':'a','ィ':'i','ゥ':'u','ェ':'e','ォ':'o','ッ':'','ー':''}

def kana2romaji(k):
    k = unicodedata.normalize('NFKC', str(k))
    k = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ん' else c for c in k)
    out = ''; i = 0; sokuon = False
    while i < len(k):
        c = k[i]
        if c == 'ッ':
            sokuon = True; i += 1; continue
        if c == 'ー':
            if out and out[-1] in 'aiueo': out += out[-1]
            i += 1; continue
        two = k[i:i+2]
        if two in TBL and len(two) == 2 and two != 'ッ':
            r = TBL[two]; i += 2
        elif c in TBL:
            r = TBL[c]; i += 1
        else:
            i += 1; continue
        if sokuon and r:
            r = (r[0] if r[0] not in 'aiueon' else 't') + r; sokuon = False
        out += r
    return out

FALLBACK = []  # ★直近make_slug呼出で辞書に掛からずカナ転写した断片(=自動で決められない語。呼出側が保留簿へ)


def kata_run_convert(run):
    """カタカナ連続文字列を辞書最長一致で貪欲分割→英語断片列。未マッチはまとめてカナ転写。"""
    parts = []; i = 0; buf = ''
    while i < len(run):
        hit = None
        if not buf:  # ★語中マッチ禁止(ブ「ラット」/アクアプ「エラー」誤爆防止): 未変換が溜まったらrun末尾まで貫く
            for k in KEYS:
                if run.startswith(k, i):
                    hit = k; break
        if hit:
            if buf:
                parts.append(kana2romaji(buf))
                if len(buf) >= 2: FALLBACK.append(buf)
                buf = ''
            parts.append(DIC[hit]); i += len(hit)
        else:
            buf += run[i]; i += 1
    if buf:
        parts.append(kana2romaji(buf))
        if len(buf) >= 2: FALLBACK.append(buf)
    return [p for p in parts if p]

def make_slug(title):
    del FALLBACK[:]
    t = unicodedata.normalize('NFKC', str(title))
    t = re.sub(r'[〔\[【（(].*?[〕\]】）)]', ' ', t)
    t = re.sub(r'[・×↔→]', ' ', t)
    parts = []
    for tk in T.tokenize(t):
        surf = tk.surface.strip()
        if not surf or re.fullmatch(r'[\s、。，．,.…‥!！?？〜~☆★♡♥◆■○●「」『』"\'"“”:：;；/／|＆&＋+*＊%％#＃-]+', surf):
            continue
        pos = tk.part_of_speech.split(',')
        reading = tk.reading if tk.reading != '*' else surf
        if re.fullmatch(r'[A-Za-z0-9@\'.\-]+', surf):
            parts.append(('lat', surf.lower(), pos)); continue
        # ★カタカナ連(長音含む)は貪欲辞書変換
        if re.fullmatch(r'[ァ-ヶー]+', surf):
            for frag in kata_run_convert(surf):
                parts.append(('lat' if not re.search(r'[^a-z0-9-]', frag) else 'ja', frag, pos))
            continue
        # ★助詞は/へ/をは読み替え、それ以外は読みを保持(ローマ字化は連結後=モーラ割れ/過分割の根治 2026-07-07)
        if pos[0] == '助詞' and surf in ('は', 'へ', 'を'):
            parts.append(('ja', {'は': 'wa', 'へ': 'e', 'を': 'o'}[surf], pos, True))  # 変換済フラグ
        else:
            parts.append(('ja', reading, pos, False))  # 読み(未変換)を保持
    # 読みレベルで結合してからローマ字化(にゃ→ニャのモーラ割れ・ほどいて過分割を根治)
    SMALL = 'ァィゥェォャュョヮッぁぃぅぇぉゃゅょゎっ'
    merged = []  # [kind, value, converted]
    for item in parts:
        if len(item) == 4:
            kind, val, pos, conv = item
        else:
            kind, val, pos = item; conv = True  # lat/katakana断片は変換済
        # 小書き先頭 or 動詞+活用/助動詞/非自立/接尾 は前のjaへ読み連結
        small_lead = (kind == 'ja' and not conv and val and unicodedata.normalize('NFKC', val)[0] in SMALL)
        attach = (kind == 'ja' and not conv and merged and merged[-1][0] == 'ja' and not merged[-1][2]
                  and ((pos[0] in ('助動詞',)) or (len(pos) > 1 and pos[1] in ('非自立', '接尾'))
                       or (pos[0] == '助詞' and merged[-1][3][0] == '動詞')  # 動詞+て/で
                       or small_lead))
        if attach:
            merged[-1][1] += val
        else:
            merged.append([kind, val, conv, pos])
    slug = '-'.join(m[1] if m[2] else kana2romaji(m[1]) for m in merged)
    slug = re.sub(r'[^a-z0-9-]', '', slug.lower())
    return re.sub(r'-{2,}', '-', slug).strip('-')[:80]

