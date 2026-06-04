#!/usr/bin/env python3
"""画集フリガナ確定版を組み立て (= clean18[NDL] + flagged手当て19)。 ★生成のみ。

flagged は ①既存OK姉妹entry転写 ②固有名読み構築 ③カタカナ化 で手当て。
Le grand livre de sailor moon(仏語題)のみ保留=出力しない。
出力: .cache/artbook-furigana-final.yml (= furigana-corrections.yml へ純粋追加する確定候補)
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FILLS = ROOT / ".cache" / "artbook-furigana-fills.yml"
OUT = ROOT / ".cache" / "artbook-furigana-final.yml"

# flagged 手当て: key -> (title_kana, derivation)
MANUAL = {
    # ①既存OK姉妹entry転写 (= 同名/同型の確定kanaを踏襲)
    "name:セム|name:セム画集|sub:彼の生きたフランス、時代と文化": ("セムガシュウ", "sibling:セム画集"),
    "name:ジャック・クレピノー|name:セム画集": ("セムガシュウ", "sibling:セム画集"),
    "name:グザヴィエ・シロン|name:セム画集": ("セムガシュウ", "sibling:セム画集"),
    "name:峯島正行|name:当世おんな風俗画集": ("トウセイオンナフウゾクガシュウ", "sibling:当世おんな風俗画集"),
    "name:Koi|name:Café du lapin 「ご注文はうさぎですか?」画集": ("CafeduLapinゴチュウモンワウサギデスカガシュウ", "sibling:Caf?duLapin"),
    "name:フジテレビ|name:月面兎兵器ミーナ okama ARTWORKS": ("ゲツメントヘイキミーナokamaartworks", "sibling:okama版"),
    "qid:Q11638680|name:[近藤るるる画集L・Rプレミアムbox]|sub:初回限定版": ("コンドウルルルガシュウLRプレミアムbox", "sibling:近藤画集L・Rbox"),
    # ②固有名読み構築 (= 公式/通用読み)
    "qid:Q11671469|name:高橋真琴画集 あこがれ": ("タカハシマコトガシュウアコガレ", "build:高橋真琴=たかはしまこと"),
    "name:Clamp|name:「魔法騎士レイアース2」原画集": ("マジックナイトレイアースニゲンガシュウ", "build:魔法騎士=マジックナイト/2=ニ"),
    "name:森晴路|name:手塚治虫カラーマンガ原画コレクション 単行本未収録画集成": ("テズカオサムカラーマンガゲンガコレクションタンコウボンミシュウロクガシュウセイ", "build:手塚治虫=テズカオサム(DB踏襲)"),
    "qid:Q3776935|name:里中満智子オリジナルイラスト集恋人たち": ("サトナカマチコオリジナルイラストシュウコイビトタチ", "build:里中満智子=さとなかまちこ"),
    "qid:Q5366793|name:超人ロック 自選複製原画集": ("チョウジンロックジセンフクセイゲンガシュウ", "build:超人ロック=チョウジンロック(sibling確認)"),
    "qid:Q5366793|name:超人ロック　自選複製原画集": ("チョウジンロックジセンフクセイゲンガシュウ", "build:超人ロック(全角空白variant)"),
    "qid:Q11638680|name:近藤るるる画集L": ("コンドウルルルガシュウL", "build:NDL(L=巻記号)"),
    "qid:Q11638680|name:近藤るるる画集R": ("コンドウルルルガシュウR", "build:NDL(R=巻記号)"),
    # ③カタカナ化 (= 外国語題の発音)
    "qid:Q11280638|name:Soul flower": ("ソウルフラワー", "katakana"),
    "qid:Q11626418|name:Y's art works": ("ワイズアートワークス", "katakana"),
    "qid:Q966701|name:G/B": ("ジービー", "katakana:G/B"),
    "name:カズアキ|name:Kazuaki Artworks": ("カズアキアートワークス", "katakana"),
}
# 保留 (= 出力しない): name:Takeuti|name:Le grand livre de sailor moon (仏語題・読み不確定)
HOLD = {"name:Takeuti|name:Le grand livre de sailor moon"}


def main():
    clean = yaml.safe_load(FILLS.read_text(encoding="utf-8"))["corrections"]
    entries = list(clean)  # 18 NDL clean (segmented付き)
    for key, (kana, deriv) in MANUAL.items():
        entries.append({
            "key": key,
            "title_kana": re.sub(r"[\s　]+", "", kana),
            "source": "ndl" if deriv.startswith("build:NDL") else "manual",
            "note": f"artbook-furigana-fill / {deriv}",
        })
    OUT.write_text(yaml.dump({"corrections": entries}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"確定候補: {len(entries)} 件 (clean18 + manual{len(MANUAL)})")
    print(f"保留: {len(HOLD)} 件 (Le grand livre de sailor moon)")
    print(f"  → {OUT}")


if __name__ == "__main__":
    main()
