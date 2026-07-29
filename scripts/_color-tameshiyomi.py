#!/usr/bin/env python3
"""電子カラー版柱③: カラー版のBookLive title_id を収集し試し読み結線する。

- 対象: data/seeds/color-editions.yml の各entry(= slug確定済みカラー版)。
- 検索: TinyFish無料Search `site:booklive.jp <カラー版display題>`。
  ★採用は「結果題がカラー版display題と完全一致(norm)」かつ HEAD200 のみ(_tameshiyomi-harvest と同基準)。
  曖昧は保留(.cache/color-tame-holds.tsv)= AIが後で裁定。
- 出力: data/seeds/color-tameshiyomi.jsonl(純粋追記・resumable)。
  _color-editions-build.py 再実行で public/data/color-editions.json の `b` に結線される。
- レート: TinyFish無料枠のみ・1回の実行 --limit 100 まで。失敗中断=そのまま再実行で再開。

使い方: python scripts/_color-tameshiyomi.py [--limit 30]
"""
import sys, io, os, re, json, time, argparse, unicodedata, urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import yaml  # noqa: E402

SEED = ROOT / "data" / "seeds" / "color-tameshiyomi.jsonl"
HOLDS = ROOT / ".cache" / "color-tame-holds.tsv"


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[ァ-ヶ]", lambda m: chr(ord(m.group(0)) - 0x60), s)
    return re.sub(r"[\s　・!！?？:：〜~ー\-。、．.「」『』()（）☆★♥×]", "", s)


def head_ok(cid):
    try:
        req = urllib.request.Request(f"https://booklive.jp/bviewer/s/?cid={cid}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=20).status == 200
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    from _tinyfish import search

    entries = (yaml.safe_load(SEED.parent.joinpath("color-editions.yml").open(encoding="utf-8")) or {}).get("entries") or []
    done, holds = set(), set()
    if SEED.exists():
        for l in SEED.open(encoding="utf-8"):
            try:
                done.add(json.loads(l)["slug"])
            except Exception:
                pass
    if HOLDS.exists():
        for l in HOLDS.open(encoding="utf-8"):
            holds.add(l.split("\t")[0])
    todo = [e for e in entries if e["slug"] not in done and e["slug"] not in holds]
    todo.sort(key=lambda e: -int(e.get("volumes") or 0))  # 巻数多い=有名どころから
    todo = todo[: a.limit]
    print(f"対象 {len(todo)} 作 (収集済{len(done)}/保留{len(holds)})", flush=True)
    seed = SEED.open("a", encoding="utf-8", newline="\n")
    os.makedirs(HOLDS.parent, exist_ok=True)
    hf = HOLDS.open("a", encoding="utf-8", newline="\n")
    n_ok = n_hold = 0
    for e in todo:
        slug, disp = e["slug"], e["display"]
        try:
            res = search(f"site:booklive.jp {disp}")
        except Exception as ex:
            print(f"★検索失敗で中断(再実行で再開可): {ex}")
            break
        dn = norm(disp)
        cand = {}
        for h in (res.get("results") or []):
            m = re.search(r"title_id/(\d+)", h.get("url", ""))
            if not m:
                continue
            ht = norm(re.sub(r"[|｜].*$", "", h.get("title", "")))
            ht = re.sub(r"(【[^】]*】|\d+巻?$|第\d+巻)", "", ht)
            exact = (ht == dn) or ht.startswith(dn + "1") or (dn == re.sub(r"\d+$", "", ht))
            cand.setdefault(m.group(1), {"exact": False, "ev": h.get("title", "")[:80]})
            if exact:
                cand[m.group(1)]["exact"] = True
        strong = [tid for tid, c in cand.items() if c["exact"]]
        if len(strong) == 1 and head_ok(f"{strong[0]}_001"):
            rec = {"slug": slug, "display": disp, "title_id": strong[0], "cid1": f"{strong[0]}_001",
                   "verified": "head200", "evidence": cand[strong[0]]["ev"], "at": time.strftime("%Y-%m-%d")}
            seed.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seed.flush()
            n_ok += 1
            print(f"  OK {slug} → {strong[0]}", flush=True)
        else:
            reason = "候補0" if not cand else ("完全一致なし" if not strong else ("複数候補" if len(strong) > 1 else "HEAD失敗"))
            hf.write(f"{slug}\t{disp}\t{reason}\t{json.dumps(cand, ensure_ascii=False).replace(chr(9),' ').replace(chr(10),' ')}\n")
            hf.flush()
            n_hold += 1
        time.sleep(1.0)
    print(f"収集 {n_ok} / 保留 {n_hold} → 反映は _color-editions-build.py 再実行")


if __name__ == "__main__":
    main()
