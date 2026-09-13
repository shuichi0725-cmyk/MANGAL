# -*- coding: utf-8 -*-
"""既定OG画像(1200x630)を作る (= 2026-09-14 SEO穴③)

なぜ要るか: OG画像を出しているのは作品頁だけ、しかも書影が在る時だけだった。
  ・作品頁で書影ゼロ = 10,837頁(15.7%)
  ・ジャンル32面/ハブ850面//list//shinkan/著者2万頁/ホーム = 全部なし
SNSやチャットに貼られた時に真っ白になる。1枚の既定画像で全部覆う。

★`output: "export"`(静的書き出し)なので ImageResponse は使わず**静的PNG**にする。
配色は D3テーマ(黒×アシッドライム)= globals.css の :root と揃える。

  python scripts/_gen-og-default.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "og-default.png")

PAPER = (13, 13, 13)        # --color-paper
INK = (242, 242, 236)       # --color-ink
ACCENT = (217, 248, 67)     # --color-accent
SUB = (150, 150, 143)

W, H = 1200, 630


def font(size, bold=True):
    for p in (r"C:\Windows\Fonts\meiryob.ttc" if bold else r"C:\Windows\Fonts\meiryo.ttc",
              r"C:\Windows\Fonts\YuGothB.ttc" if bold else r"C:\Windows\Fonts\YuGothM.ttc",
              r"C:\Windows\Fonts\msgothic.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main():
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    # 左のアクセント帯(サイトのカード意匠と同じ)
    d.rectangle([0, 0, 18, H], fill=ACCENT)
    # 背景に薄い格子(書影の棚を想起させる程度の抑えたもの)
    for x in range(120, W, 96):
        d.line([(x, 0), (x, H)], fill=(26, 26, 24), width=1)

    d.text((90, 176), "MANGAL", font=font(132), fill=INK)
    # ロゴのドット(サイトの MANGAL. と同じ)
    d.text((90 + d.textlength("MANGAL", font=font(132)), 176), ".", font=font(132), fill=ACCENT)

    d.text((96, 344), "日本の漫画データベース", font=font(46), fill=ACCENT)
    d.text((96, 418), "全巻の発売日・ISBN・書影。出版年・著者・出版社・ジャンルから探せる。",
           font=font(28, bold=False), fill=SUB)
    d.text((96, 470), "mangal-db.com", font=font(26), fill=INK)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT, optimize=True)
    print(f"{OUT}  {im.size}  {os.path.getsize(OUT)} bytes")


if __name__ == "__main__":
    main()
