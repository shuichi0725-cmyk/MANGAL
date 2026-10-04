#!/usr/bin/env python3
"""MADB 巻書誌(生 metadata101.json)の役割付きクレジット → data/seeds/madb-role-credits.json.gz。

2026-10-04 ユーザ裁定(ゴブリンスレイヤー本編/外伝の原作者抜け): 頁の著者は種2のシリーズ台帳
(cm104 は 2024-11 凍結)だけから作られ、巻ごとの書誌の「[原作]蝸牛くも」が使われていなかった。
clean 版(metadata101-clean.json)は役割の接頭辞を落とすので、**生**から役割付きで抜く。

出力 = {isbn13: {"o": [原作の名前...], "a": [作画系の名前...]} | 0}。
  0 = クレジットは在るが役割タグ(原作/作画系)が無い巻(=「過半数の巻」の分母に入れるため。 [著]だけの巻など)。
  o = [原作] のみ(原案・キャラクター原案は原作者ではないので入れない)。
  a = [作画][漫画][画][まんが][劇画](作画者の役割是正に使う)。
promote(_promote-bulk-v2.py)が読む。 月次で MADB を取り込んだら再生成する(純粋な派生物)。
使い方: python scripts/_gen-madb-role-credits.py [metadata101.json]
"""
import gzip, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, ".cache", "madb", "metadata101.json")
OUT = os.path.join(ROOT, "data", "seeds", "madb-role-credits.json.gz")

ORIG_TAGS = {"原作"}
ART_TAGS = {"作画", "漫画", "画", "まんが", "劇画"}


def to13(i):
    i = re.sub(r"[^0-9Xx]", "", str(i))
    if len(i) == 13:
        return i
    if len(i) == 10:
        b = "978" + i[:9]
        s = sum((1 if k % 2 == 0 else 3) * int(c) for k, c in enumerate(b))
        return b + str((10 - s % 10) % 10)
    return None


def split_names(s):
    # 区切り(, 、 ，)で割る。 ★「」『』の中の読点では割らない(「君が踊る、夏」製作委員会 が2つに割れた)
    parts, buf, depth = [], "", 0
    for ch in s:
        if ch in "「『":
            depth += 1
        elif ch in "」』":
            depth = max(0, depth - 1)
        if ch in ",、，" and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    out = []
    for n in (x.strip(" 　") for x in parts):
        if not n:
            continue
        # 「おばけ屋 LAIDBACKERS製作委員会」= 2名が空白で連結されている型だけ割る
        #   (★空白で一律に割らない: Ark Performance / Sound Horizon 等は1つの名前)
        m = re.match(r"^(\S*[^\x00-\x7F]\S*)[ 　]+(\S+委員会)$", n)
        out += [m.group(1), m.group(2)] if m else [n]
    return out


def main():
    g = json.load(open(SRC, encoding="utf-8"))
    rows = g.get("@graph", g) if isinstance(g, dict) else g
    out = {}
    for r in rows:
        cr = r.get("schema:creator")
        if not cr:
            continue
        cr = [x for x in (cr if isinstance(cr, list) else [cr]) if isinstance(x, str)]
        o, a = [], []
        for x in cr:
            m = re.match(r"^\[([^\]]+)\]\s*(.*)$", x.strip())
            if not m:
                continue
            tag, body = m.group(1).strip(), m.group(2)
            if tag in ORIG_TAGS:
                o += split_names(body)
            elif tag in ART_TAGS:
                a += split_names(body)
        ent = {}
        if o:
            ent["o"] = list(dict.fromkeys(o))
        if a:
            ent["a"] = list(dict.fromkeys(a))
        isb = r.get("schema:isbn")
        for x in (isb if isinstance(isb, list) else [isb]):
            k = to13(x) if x else None
            if k:
                out[k] = ent or 0
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    no = sum(1 for v in out.values() if v and "o" in v)
    na = sum(1 for v in out.values() if v and "a" in v)
    print(f"madb-role-credits: {len(out)} ISBN (原作 {no} / 作画系 {na}) → {OUT} ({os.path.getsize(OUT)/1e6:.1f}MB)")


if __name__ == "__main__":
    main()
