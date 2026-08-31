#!/usr/bin/env python3
"""電子カラー版柱③: カラー版のBookLive title_id を収集し試し読み結線する。

- 対象: data/seeds/color-editions.yml の各entry(= slug確定済みカラー版)。
- 検索: TinyFish無料Search `site:booklive.jp <カラー版display題>`。
  ★採用は「結果題がカラー版display題と完全一致(norm)」かつ HEAD200 のみ(_tameshiyomi-harvest と同基準)。
  曖昧は保留(.cache/color-tame-holds.tsv)= AIが後で裁定。
- 出力: data/seeds/color-tameshiyomi.jsonl(純粋追記・resumable)。
  _color-editions-build.py 再実行で public/data/color-editions.json の `b` に結線される。
- レート: TinyFish無料枠のみ・1回の実行 --limit 100 まで。失敗中断=そのまま再実行で再開。
  ★BookLive宛(HEAD)は _booklive 共通ゲート(2026-08-31: 札・直列2.0秒・日次上限。Blocked=保留に書かず即中断)。

使い方: python scripts/_color-tameshiyomi.py [--limit 30]
"""
import sys, io, os, re, json, time, argparse, unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import yaml  # noqa: E402
import _booklive  # noqa: E402
from _booklive import Blocked, CapReached  # noqa: E402

SEED = ROOT / "data" / "seeds" / "color-tameshiyomi.jsonl"
HOLDS = ROOT / ".cache" / "color-tame-holds.tsv"


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[ァ-ヶ]", lambda m: chr(ord(m.group(0)) - 0x60), s)
    return re.sub(r"[\s　・!！?？:：〜~ー\-。、．.「」『』()（）☆★♥×]", "", s)


def check_cid(cid):
    """→ True=あり / False=無い(404だけ)。★404以外の異常はBlocked=呼び手が中断
    (2026-08-31是正: 旧は全例外→Falseで、規制中の応答を「HEAD失敗」保留に焼いていた)。"""
    return _booklive.head200(f"https://booklive.jp/bviewer/s/?cid={cid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    _booklive.assert_not_blocked()   # ★入口でも見る=TinyFish検索を始める前に落とす
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
    blocked = False
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
        try:
            hit = len(strong) == 1 and check_cid(f"{strong[0]}_001")
        except CapReached as ex:
            print(f"★打ち切り: {ex}(進捗は逐次保存済み・続きは次回)")
            break
        except Blocked as ex:
            print(f"★中断: BookLiveから200/404以外の応答 ({ex})。保留には書かない。", file=sys.stderr)
            blocked = True
            break
        if hit:
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
        time.sleep(1.0)   # TinyFish側のペーシング(BookLive側は_booklive gateが担う)
    print(f"収集 {n_ok} / 保留 {n_hold} → 反映は _color-editions-build.py 再実行")
    if blocked:
        sys.exit(2)


if __name__ == "__main__":
    main()
