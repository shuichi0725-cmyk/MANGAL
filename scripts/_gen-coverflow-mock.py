# -*- coding: utf-8 -*-
"""巻リスト改修の見た目モック(中央フォーカス・コーフロー)を3パターン生成。実カバー使用。"""
import io, os, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

FONT_PATH = r"C:\Windows\Fonts\meiryo.ttc"
def font(sz, idx=0): return ImageFont.truetype(FONT_PATH, sz, index=idx)

# 中央=1巻、左に31,30(ループ)、右に2,3
COVERS = [
    (30, "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/8507/9784088718507_1_4.jpg?_ex=400x600"),
    (31, "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/8392/9784088718392.jpg?_ex=400x600"),
    (1,  "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/6114/9784088716114_1_4.jpg?_ex=400x600"),
    (2,  "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/6121/9784088716121_1_4.jpg?_ex=400x600"),
    (3,  "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/6138/9784088716138.jpg?_ex=400x600"),
]

def dl(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://books.rakuten.co.jp/"})
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")

imgs = [(n, dl(u)) for n, u in COVERS]

W, H = 720, 1000
BG = (244, 241, 236)
INK = (26, 26, 26)
ACCENT = (191, 31, 31)


def cover_ratio(im):  # height固定で幅算出
    return im.width / im.height


def rrect(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def button(d, cx, cy, w, h, text, fill, fg=(255, 255, 255), fs=20):
    box = [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2]
    rrect(d, box, h // 2, fill)
    f = font(fs)
    tw = d.textlength(text, font=f)
    d.text((cx - tw / 2, cy - fs / 2 - 2), text, font=f, fill=fg)


def build(variant):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # ヘッダ
    d.text((30, 22), "通常版", font=font(26), fill=INK)
    rrect(d, [120, 24, 210, 56], 16, (230, 226, 220))
    d.text((132, 28), "全31巻", font=font(20), fill=(90, 90, 90))
    d.text((228, 28), "出版社: 集英社", font=font(18), fill=(120, 120, 120))

    # コーフロー幾何(中央=index2=1巻)
    if variant == "A":
        heights = [250, 250, 250, 250, 250]; bright = [0.5, 0.72, 1.0, 0.72, 0.5]; blur = [0, 0, 0, 0, 0]; gap = 12
    elif variant == "B":
        heights = [175, 205, 270, 205, 175]; bright = [0.55, 0.75, 1.0, 0.75, 0.55]; blur = [0, 0, 0, 0, 0]; gap = 8
    else:  # C
        heights = [165, 200, 280, 200, 165]; bright = [0.4, 0.62, 1.0, 0.62, 0.4]; blur = [1.6, 0.8, 0, 0.8, 1.6]; gap = 6

    prepared = []
    for (n, im), hgt, br, bl in zip(imgs, heights, bright, blur):
        w = int(hgt * cover_ratio(im))
        c = im.resize((w, hgt))
        if bl:
            c = c.filter(ImageFilter.GaussianBlur(bl))
        if br < 1.0:
            c = ImageEnhance.Brightness(c).enhance(br)
        prepared.append((n, c, n == 1))
    groupw = sum(c.width for _, c, _ in prepared) + gap * 4
    x = (W - groupw) // 2
    cy = 230
    for n, c, focus in prepared:
        y = cy - c.height // 2
        img.paste(c, (x, y))
        if focus:
            d.rectangle([x - 3, y - 3, x + c.width + 2, y + c.height + 2], outline=ACCENT, width=4)
        x += c.width + gap

    # 下: フォーカス巻(1巻)の情報＋カート
    iy = 400
    d.text((40, iy), "第1巻", font=font(30), fill=INK)
    d.text((150, iy + 8), "・ 1991.02.15", font=font(22), fill=(120, 120, 120))
    by = iy + 70
    button(d, 150, by, 200, 56, "楽天で見る", (191, 0, 0))
    button(d, 370, by, 180, 56, "Kindle", (40, 40, 40))
    button(d, 560, by, 170, 56, "Amazon", (230, 149, 0))
    # 全巻まとめ買い
    button(d, W // 2, by + 80, 420, 60, "📚 全巻まとめ買い(全31巻)", (33, 106, 58), fs=22)

    # 操作ヒント
    d.text((40, by + 150), "← スワイプで巻送り(…30 31 [1] 2 3…ループ) ・ タップで選択", font=font(18), fill=(140, 140, 140))
    # 変種ラベル
    label = {"A": "案A: 均等サイズ＋中央以外を暗く(シンプル)",
             "B": "案B: コーフロー(中央大・外は小＋暗)",
             "C": "案C: コーフロー強め(大小＋暗＋外側ぼかし=没入)"}[variant]
    d.rectangle([0, H - 50, W, H], fill=(26, 26, 26))
    d.text((30, H - 42), label, font=font(22), fill=(255, 255, 255))
    out = f"docs/coverflow-mock-{variant}.png"
    img.save(out)
    print("wrote", out)


for v in ("A", "B", "C"):
    build(v)
