# -*- coding: utf-8 -*-
"""巻リスト改修モックv2: SLAM DUNK 3版(通常/デラックス/愛蔵)を縦に・各コーフロー。
ボタン=楽天/Yahoo/Amazon均等(Kindle無し)+まとめ買いをカッコ良く。A案/C案の2枚。"""
import io, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

FP = r"C:\Windows\Fonts\meiryo.ttc"
def font(sz): return ImageFont.truetype(FP, sz)

EDITIONS = [
    ("通常版", 31, [
        (30, "8507/9784088718507_1_4"), (31, "8392/9784088718392"),
        (1, "6114/9784088716114_1_4"), (2, "6121/9784088716121_1_4"), (3, "6138/9784088716138")]),
    ("デラックス版", 24, [
        (23, "2121/9784088592121"), (24, "2138/9784088592138"),
        (1, "1902/9784088591902"), (2, "1919/9784088591919"), (3, "1926/9784088591926")]),
    ("愛蔵版", 20, [
        (19, "5494/9784087925494"), (20, "5500/9784087925500"),
        (1, "5319/9784087925319"), (2, "5326/9784087925326"), (3, "5333/9784087925333")]),
]
URL = "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{}.jpg?_ex=400x600"


def dl(code):
    req = urllib.request.Request(URL.format(code), headers={"User-Agent": "Mozilla/5.0", "Referer": "https://books.rakuten.co.jp/"})
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")


CACHE = {}
def cover(code):
    if code not in CACHE:
        CACHE[code] = dl(code)
    return CACHE[code]


W = 720
BG = (244, 241, 236); INK = (26, 26, 26); ACCENT = (191, 31, 31)


def rrect(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def store_btn(d, x, cy, w, h, text, fill, fs=19):
    rrect(d, [x, cy - h // 2, x + w, cy + h // 2], h // 2, fill)
    f = font(fs); tw = d.textlength(text, font=f)
    d.text((x + (w - tw) / 2, cy - fs / 2 - 2), text, font=f, fill=(255, 255, 255))


def bulk_btn(img, d, cx, cy, w, h, vols):
    x0, y0 = cx - w // 2, cy - h // 2
    # 影
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x0 + 4, y0 + 7, x0 + w + 4, y0 + h + 7], radius=h // 2, fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    img.alpha_composite(sh)
    # グラデ(深緑→エメラルド)
    grad = Image.new("RGB", (w, h)); gd = ImageDraw.Draw(grad)
    c1, c2 = (20, 90, 60), (46, 190, 130)
    for i in range(w):
        t = i / (w - 1); gd.line([(i, 0), (i, h)], fill=tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
    mask = Image.new("L", (w, h), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=255)
    img.paste(grad, (x0, y0), mask)
    d.text((x0 + 26, cy - 26), "🛒  全巻まとめ買い", font=font(26), fill=(255, 255, 255))
    d.text((x0 + 26, cy + 6), f"全{vols}巻セットをまとめて", font=font(16), fill=(225, 255, 240))
    d.text((x0 + w - 44, cy - 16), "›", font=font(40), fill=(255, 255, 255))


def ratio(im): return im.width / im.height


def draw_edition(img, d, y, label, vols, covs, variant):
    d.text((36, y), label, font=font(26), fill=INK)
    rrect(d, [36 + d.textlength(label, font=font(26)) + 14, y + 2, 36 + d.textlength(label, font=font(26)) + 110, y + 32], 15, (230, 226, 220))
    d.text((36 + d.textlength(label, font=font(26)) + 26, y + 5), f"全{vols}巻", font=font(18), fill=(90, 90, 90))
    d.text((36 + d.textlength(label, font=font(26)) + 122, y + 5), "・ 集英社", font=font(17), fill=(140, 140, 140))
    if variant == "A":
        hs = [185, 185, 185, 185, 185]; br = [0.5, 0.72, 1.0, 0.72, 0.5]; bl = [0, 0, 0, 0, 0]; gap = 12
    else:
        hs = [130, 158, 215, 158, 130]; br = [0.4, 0.62, 1.0, 0.62, 0.4]; bl = [1.6, 0.8, 0, 0.8, 1.6]; gap = 7
    prep = []
    for (n, code), h, b, g in zip(covs, hs, br, bl):
        im = cover(code); c = im.resize((int(h * ratio(im)), h))
        if g: c = c.filter(ImageFilter.GaussianBlur(g))
        if b < 1: c = ImageEnhance.Brightness(c).enhance(b)
        prep.append((n, c))
    gw = sum(c.width for _, c in prep) + gap * 4
    x = (W - gw) // 2; cy = y + 50 + max(hs) // 2
    for n, c in prep:
        yy = cy - c.height // 2; img.paste(c, (x, yy))
        if n == 1:
            d.rectangle([x - 3, yy - 3, x + c.width + 2, yy + c.height + 2], outline=ACCENT, width=4)
        x += c.width + gap
    iy = y + 50 + max(hs) + 14
    d.text((40, iy), "第1巻", font=font(26), fill=INK)
    d.text((132, iy + 6), "・ 1991.02.15", font=font(19), fill=(130, 130, 130))
    by = iy + 52
    bw = (W - 72 - 24) // 3
    store_btn(d, 36, by, bw, 50, "楽天", (191, 0, 0))
    store_btn(d, 36 + bw + 12, by, bw, 50, "Yahoo!", (255, 0, 51))
    store_btn(d, 36 + (bw + 12) * 2, by, bw, 50, "Amazon", (230, 149, 0))
    bulk_btn(img, d, W // 2, by + 78, W - 72, 66, vols)
    return by + 78 + 70


def build(variant):
    img = Image.new("RGBA", (W, 1560), BG + (255,))
    d = ImageDraw.Draw(img)
    d.text((30, 22), "SLAM DUNK", font=font(30), fill=INK)
    d.text((30, 62), "井上雄彦 ・ 3つの版で配信", font=font(18), fill=(130, 130, 130))
    y = 110
    for label, vols, covs in EDITIONS:
        y = draw_edition(img, d, y, label, vols, covs, variant) + 26
        d.line([(30, y - 14), (W - 30, y - 14)], fill=(214, 209, 202), width=2)
    d.rectangle([0, 1560 - 46, W, 1560], fill=(26, 26, 26))
    lab = "案A: 均等＋中央以外を暗く" if variant == "A" else "案C: コーフロー強め(大小＋暗＋外側ぼかし)"
    d.text((28, 1560 - 38), lab + " / 楽天・Yahoo・Amazon均等 + まとめ買い", font=font(18), fill=(255, 255, 255))
    out = f"docs/coverflow-mock2-{variant}.png"
    img.convert("RGB").save(out); print("wrote", out)


for v in ("A", "C"):
    build(v)
