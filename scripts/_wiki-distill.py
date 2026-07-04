#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wiki蒸留エンジン (= トリガー「Wiki蒸留して」。 2026-07-04 釣りキチ/スケバンで実証した方式の汎用化)

対象slug群について ja.wikipedia の書誌情報から巻別ISBN+発売日を取得し、
ゲート通過分のみ edition-canonical を生成する。

型判定:
 ①巻別ISBN型: 『題』出版社〈レーベル〉、全N巻 + *#行に{{ISBN}} → 全自動canonical
 ②構成のみ型: 版リストはあるがISBN無し → worklist(ドカベン式=楽天/NDL充填の半自動へ)
 ③書誌なし型: 節なし → 現状維持

ゲート(慎重・fail-closed):
 - ISBN10→13 checksum再計算 / 宣言巻数と抽出数の一致 / 楽天題baseゲート(1件でも別作題ならabort)
 - 見出しの題が頁題とbase一致するブロックのみ採用(スピンオフ吸い防止)
使い方:
  python scripts/_wiki-distill.py --slugs a,b,c [--write] [--fetch]
  (--fetch=記事を .cache/wiki/ へ取得(1s/req)。無=既存キャッシュのみ)
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def to13(i10):
    d = re.sub(r"[^0-9X]", "", i10.upper())
    if len(d) == 13:
        return d
    core = "978" + d[:9]
    s = sum(int(c) * (1 if k % 2 == 0 else 3) for k, c in enumerate(core))
    return core + str((10 - s % 10) % 10)

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", t).lower()

tm = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))

def fetch(slug, title):
    os.makedirs(os.path.join(ROOT, ".cache", "wiki"), exist_ok=True)
    fp = os.path.join(ROOT, ".cache", "wiki", f"{slug}.txt")
    if os.path.exists(fp):
        return open(fp, encoding="utf-8").read()
    url = "https://ja.wikipedia.org/w/index.php?action=raw&title=" + urllib.parse.quote(title)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except Exception as e:
        return f"__FETCH_ERROR__ {e}"
    open(fp, "w", encoding="utf-8").write(body)
    time.sleep(1.0)
    return body

# 『題』 [出版社]〈レーベル〉、全N巻  (リンク[[..]]許容)
HDR = re.compile(r"『([^』]+)』[^\n]*?〈([^〉]+)〉[^\n]*?全(\d+)巻")

def parse_blocks(txt, page_title):
    pt = norm(page_title)
    blocks = []
    for m in HDR.finditer(txt):
        btitle, label, n = m.group(1), m.group(2), int(m.group(3))
        if norm(btitle) != pt:
            continue  # スピンオフ/別題ブロックは吸わない
        seg = txt[m.end():]
        vols = []
        for line in seg.split("\n"):
            if line.startswith("*#") or line.startswith("##"):
                im = re.search(r"\{\{ISBN2?\|([0-9X\-]+)\}\}", line)
                if not im:
                    continue
                dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", line)
                ds = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else None
                vols.append({"number": len(vols) + 1, "isbn13": to13(im.group(1)), "release_date": ds})
            elif line.startswith("*") or line.startswith("=="):
                break
        blocks.append({"label": re.sub(r"\[\[|\]\]", "", label), "n": n, "vols": vols})
    return blocks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    results = []
    for slug in a.slugs.split(","):
        slug = slug.strip()
        pp = os.path.join(ROOT, "data", "manga.v2", f"{slug}.yml")
        if not os.path.exists(pp):
            results.append((slug, "頁無")); continue
        if os.path.exists(os.path.join(ROOT, "data", "seeds", "edition-canonical", f"{slug}.yml")):
            results.append((slug, "canonical既存=skip")); continue
        page = yaml.safe_load(open(pp, encoding="utf-8"))
        title = page.get("title")
        txt = fetch(slug, title) if a.fetch else (
            open(os.path.join(ROOT, ".cache", "wiki", f"{slug}.txt"), encoding="utf-8").read()
            if os.path.exists(os.path.join(ROOT, ".cache", "wiki", f"{slug}.txt")) else "")
        if not txt or txt.startswith("__FETCH_ERROR__"):
            results.append((slug, f"③記事取得不可 {txt[:40]}")); continue
        blocks = parse_blocks(txt, title)
        full = [b for b in blocks if len(b["vols"]) == b["n"] and b["n"] >= 2]
        if not full:
            kind = "②構成のみ(要ドカベン式)" if blocks else "③書誌なし/形式外"
            results.append((slug, kind)); continue
        b = max(full, key=lambda x: x["n"])  # 主版=最多巻ブロック
        # 楽天題gate
        pt = norm(title)
        bad = []
        checked = 0
        for v in b["vols"]:
            t2 = tm.get(v["isbn13"])
            if t2 is None:
                continue
            checked += 1
            base = norm(re.sub(r"[（(]\s*\d+\s*[)）]\s*$|第?\s*\d+\s*巻?\s*$", "", t2))
            if not (base.startswith(pt) or pt.startswith(base)):
                bad.append((v["number"], t2[:20]))
        if bad:
            results.append((slug, f"★楽天題不一致abort {bad[:3]}")); continue
        std = next((e for e in page.get("editions", []) if e.get("type") == "standard"), {})
        seed = {"slug": slug, "canonical_label": b["label"],
                "source": f"Wiki蒸留 2026(巻別ISBN+日付・全{b['n']}巻・checksum再計算・楽天gate{checked}/{b['n']})",
                "publisher": std.get("publisher"), "volumes": b["vols"]}
        if a.write:
            yaml.dump(seed, open(os.path.join(ROOT, "data", "seeds", "edition-canonical", f"{slug}.yml"),
                                 "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
        results.append((slug, f"①canonical{'書出' if a.write else '可'} 全{b['n']}巻 楽天{checked}確認"))
    for r in results:
        print(f"  {r[0]}: {r[1]}")
    ok = [r[0] for r in results if r[1].startswith("①")]
    json.dump(ok, open(os.path.join(ROOT, ".cache", "wiki-distill-ok.json"), "w"))
    print(f"①型 {len(ok)} / 全{len(results)}")

if __name__ == "__main__":
    main()
