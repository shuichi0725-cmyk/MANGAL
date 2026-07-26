"""★特装版是正 seed の (特装版ISBN → 通常版ISBN) 対応が **別作品を指していないか**を検査。

背景(2026-07-26 僕のヒーローアカデミアで発覚):
  `special-edition-fix-redo2.yml` の
    special_isbn 9784089082911 (=「僕のヒーローアカデミア(14)特装版」堀越耕平)
    → normal_isbn 9784088828596 (=「ヴィジランテ 14 -僕のヒーローアカデミアILLEGALS-」別天荒人)
  という **別作品への対応**が入っており、本編頁の14巻がスピンオフの書影/リンクに化けていた。
  promote は special_isbn を normal_isbn で**置換**するので、対応先を間違えると
  ★volume-exclude より後段で走るため除外でも止められない(= seedを直すしかない)。

判定: 楽天キャッシュ(.cache/rakuten-isbn.jsonl)で両ISBNの題を引き、
  「特装/限定/同梱/BOX/セット」等の版表記と巻数・記号を落として比べる。
  一致しなければ ★別作品の疑い として出す(read-only)。

出力: docs/production-diagnostics/special-fix-pair-mismatch.tsv
usage: python scripts/_audit-special-fix-pairs.py
"""
import argparse
import glob
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "rakuten-isbn.jsonl"
# ★--live で引いた題の置き場(再開用)。 中断しても既に引いたISBNは再照会しない。
LIVE = ROOT / ".cache" / "special-fix-titles.jsonl"
OUT = ROOT / "docs" / "production-diagnostics" / "special-fix-pair-mismatch.tsv"

# 版表記・巻数・記号は同一性判定から外す(特装版と通常版は題が少し違って当然)
NOISE = re.compile(
    r"(特装版|限定版|初回限定|通常版|同梱版?|アニメdvd|dvd付き?|dvd|ova|cd付き?|小冊子付?|"
    r"ドラマcd|フィギュア付?|セット|box|愛蔵版|完全版|新装版|コミック|漫画|"
    r"[0-9]+|[（(][^）)]*[）)]|【[^】]*】|[･・、。!！?？:：;；~〜ー\-\s.,＆&＋+/／]+)")


def norm(s: str) -> str:
    return NOISE.sub("", unicodedata.normalize("NFKC", str(s or "")).lower())


def load_live() -> dict:
    d = {}
    if LIVE.exists():
        for ln in LIVE.open(encoding="utf-8"):
            try:
                o = json.loads(ln)
            except Exception:
                continue
            d[o["isbn"]] = o.get("title") or ""
    return d


def fetch_live(missing: list) -> dict:
    """★楽天へライブ照会(1.3秒/req は _lookup.py の rate gate が担保)。
    引けなかったISBNも空文字で記録する = 再実行で無限に叩き直さないため。"""
    spec = importlib.util.spec_from_file_location("l", str(ROOT / "scripts" / "_lookup.py"))
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    env = L._env()
    got = {}
    with LIVE.open("a", encoding="utf-8") as f:
        for i, ib in enumerate(missing, 1):
            try:
                it = (L.rakuten_live_retry(env, isbn=ib) or [{}])[0]
            except Exception as e:
                print(f"    ✗ {ib} {e}", flush=True)
                it = {}
            t = ((it.get("title") or "") + " " + (it.get("author") or "")).strip()
            got[ib] = t
            f.write(json.dumps({"isbn": ib, "title": t}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0:
                print(f"    ...{i:,}/{len(missing):,} 照会済", flush=True)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="ローカルキャッシュに無いISBNを楽天へライブ照会(再開可)")
    a = ap.parse_args()
    print("[1/3] seed を読む ...", flush=True)
    pairs = []
    for p in sorted(glob.glob(str(ROOT / "data" / "seeds" / "special-edition-fix*.yml"))):
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        for c in (d.get("corrections") or []):
            s, n = str(c.get("special_isbn") or ""), str(c.get("normal_isbn") or "")
            if s and n:
                pairs.append((Path(p).name, s, n))
    want = {x for _, s, n in pairs for x in (s, n)}
    print(f"  対応 {len(pairs):,} 組 / 照会ISBN {len(want):,}", flush=True)

    print("[2/3] 楽天キャッシュから題を引く ...", flush=True)
    title = {}
    with CACHE.open(encoding="utf-8") as f:
        for ln in f:
            try:
                o = json.loads(ln)
            except Exception:
                continue
            # ★キャッシュは {"isbn":..., "item":{楽天itemそのまま}} の形(2026-07-26 実測)。
            #   トップレベルに title は無いので item から取る。
            i = str(o.get("isbn") or "")
            if i in want and i not in title:
                it = o.get("item") or {}
                title[i] = (it.get("title") or "") + " " + (it.get("author") or "")
    title.update({k: v for k, v in load_live().items() if k in want and v})
    print(f"  引けた {len(title):,}/{len(want):,}", flush=True)

    if a.live:
        done = set(load_live())
        missing = [i for i in sorted(want) if i not in title and i not in done]
        print(f"[2b] ★ライブ照会 {len(missing):,} 件 (推定 {len(missing) * 1.3 / 60:.0f} 分) ...", flush=True)
        title.update({k: v for k, v in fetch_live(missing).items() if v})
        print(f"  → 題が揃ったISBN {len(title):,}/{len(want):,}", flush=True)

    print("[3/3] 突合 ...", flush=True)
    rows = []
    for src, s, n in pairs:
        ts, tn = title.get(s), title.get(n)
        if not ts or not tn:
            continue                      # キャッシュに無い = 判定不能(黙って落とす)
        a, b = norm(ts), norm(tn)
        if a == b or (a and b and (a in b or b in a)):
            continue
        rows.append((src, s, ts, n, tn))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("seed\tspecial_isbn\tspecial_title\tnormal_isbn\tnormal_title\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"\n=== 特装版→通常版 が別作品の疑い ===")
    print(f"  ★{len(rows):,} 組 (判定できた {sum(1 for _, s, n in pairs if title.get(s) and title.get(n)):,} 組中)"
          f" → {OUT}")
    for r in rows[:25]:
        print(f"   {r[1]}「{r[2][:26]}」 → {r[3]}「{r[4][:26]}」")


if __name__ == "__main__":
    main()
