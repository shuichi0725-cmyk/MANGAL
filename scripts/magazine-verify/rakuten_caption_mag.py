"""候補頁の各巻 ISBN → 楽天 itemCaption から「〜で連載」の雑誌名を抜く(手元キャッシュのみ・読むだけ)。
出力 .cache/magazine-lists/rakuten-caption-mags.json = {slug: [[isbn, 発売日, 誌名, 前後の文]...]}"""
import json, sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); L = os.path.join(ROOT, ".cache/magazine-lists")
rows = json.load(open(f"{L}/madb-decision.json", encoding="utf-8"))
cand = {r[2] for r in rows if r[0] in ("未解決表", "その他") and r[1] in ("食い違い", "空欄→埋められる", "マスタに無い誌")}
pidx = json.load(open(os.path.join(ROOT, ".cache/isbn-page-index.json"), encoding="utf-8"))
want = {}
for isbn, slugs in pidx.items():
    for s in slugs:
        if s in cand: want.setdefault(isbn, []).append(s)
print("候補頁", len(cand), "その巻ISBN", len(want), flush=True)
KW = r"(?:誌上?)?\s*(?:で|にて|に|の|より|から)?\s*(?:大?人気|好評|話題|絶賛|超人気|大好評|人気)?\s*(?:連載|掲載|発|新連載|連載中|掲載中)"
Q = re.compile(r"[「『【]([^」』】\n]{2,30})[」』】]" + KW)
NQ = re.compile(r"((?:週刊|月刊|隔週刊|別冊|増刊)?[^\s「」『』、。！!？?\n]{1,12}(?:ジャンプ|マガジン|サンデー|チャンピオン|ガンガン|エース|コミック|ゆめ|LaLa|ララ|マーガレット|フレンド|りぼん|なかよし|ちゃお|Sho-Comi|モーニング|アフタヌーン|ビッグコミック[^\s、。]{0,8}|スピリッツ|ヤングジャンプ|バンチ|ライバル|シリウス|アライブ|ブレイド|コロコロ|ボンボン|ゴラク|アクション|ヒバナ|ゲッサン|クラブサンデー|ウェブコミック|ONLINE|オンライン))" + KW)
out = {}; n = hit = 0
with open(os.path.join(ROOT, ".cache/rakuten-isbn-delta.jsonl"), encoding="utf-8") as f:
    for line in f:
        isbn = line[10:23]
        if isbn not in want: continue
        n += 1
        try: it = json.loads(line)["item"]
        except Exception: continue
        cap = (it.get("itemCaption") or "") + "\n" + (it.get("contents") or "")
        ms = [(m.group(1), cap[max(0, m.start() - 10):m.end() + 6].replace("\n", " ")) for m in Q.finditer(cap)]
        ms += [(m.group(1), cap[max(0, m.start() - 10):m.end() + 6].replace("\n", " ")) for m in NQ.finditer(cap)]
        if not ms: continue
        hit += 1
        for s in want[isbn]:
            for name, ctx in ms:
                out.setdefault(s, []).append([isbn, it.get("salesDate", ""), name.strip(), ctx])
json.dump(out, open(f"{L}/rakuten-caption-mags.json", "w", encoding="utf-8"), ensure_ascii=False)
print("楽天に在った巻", n, "/ 雑誌名が書かれた巻", hit, "/ 頁", len(out))
