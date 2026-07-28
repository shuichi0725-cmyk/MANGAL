"""★「連載中なのに最終巻が古い」作品に **続刊が実在するか** を外部で確認する(read-only)。

背景(2026-07-28 ユーザ依頼): status=ongoing の 11,089作のうち **3,367作は最終巻が2023年以前**。
実際には完結/打ち切り/休止か、あるいは **当方が続刊を取りこぼしている**かのどちらか。
前者なら status 是正、後者なら巻補完 = どちらに転ぶかを外部ソースで先に判定する。

判定方針(保守的・自動適用はしない):
  - 楽天/NDL を **題で検索**し、①巻番号が当方の最大巻より大きい ②または発売年が当方の最終年より新しい
    もののうち、★**著者が一致するもの**だけを候補にする(同名別作・スピンオフの混入を避ける)。
  - 見つかった候補は **証拠(題/著者/ISBN/発売日)ごと**出す。 採否は人/AIが後で裁定する。
  - 何も見つからない = 「続刊なし」の消極的証拠。 **それだけで完結とは断定しない**(市場から消えただけの
    古書・電子のみ移行もあるため)。 status是正は別工程([[completion-judge]] skill)。

resumable: 1作ごとに jsonl へ即時追記。 中断しても既済はskip。
rate: _lookup.py の gate(1.3秒/host)に従う。 楽天とNDLは **別ホストなので2プロセス並走可**。

usage:
  python scripts/_check-ongoing-continuation.py --source rakuten
  python scripts/_check-ongoing-continuation.py --source ndl
出力: .cache/ongoing-cont-<source>.jsonl
"""
import argparse
import importlib.util
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "ongoing-stale.json"

_L = importlib.util.spec_from_file_location("l", str(ROOT / "scripts" / "_lookup.py"))
L = importlib.util.module_from_spec(_L)
_L.loader.exec_module(L)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s　・･,，、。\.\-─―ー]+", "", s)


VOLPAT = re.compile(r"[（(]\s*(\d{1,3})\s*[）)]|第\s*(\d{1,3})\s*巻|\s(\d{1,3})\s*$|\.\s*(\d{1,3})$")
# ★ノイズ商品(続刊ではない)。 セット/合本は既刊の詰め合わせ、分冊版は電子の章売りで巻数体系が別。
#   これを弾かないと「1-3巻セット(2024年発売)」が年だけ新しく続刊に見える(2026-07-28 実測)。
NOISE = re.compile(r"セット|ｾｯﾄ|全巻|合本|まとめ買い|分冊版|話売り|\bbox\b|BOX|コミックセット", re.I)


def volnum(t: str):
    m = VOLPAT.search(unicodedata.normalize("NFKC", str(t or "")))
    if not m:
        return None
    for g in m.groups():
        if g:
            return int(g)
    return None


def author_ok(ours: list, theirs: str) -> bool:
    """★著者一致ゲート。 姓(先頭2字)がどちらかに含まれれば可とする緩い判定。
    NDLは「サイトウ, タカヲ」形式、楽天は「さいとう・たかを」等で表記が揃わないため厳密一致は使えない。"""
    t = norm(theirs)
    if not t:
        return False
    for a in ours:
        n = norm(a)
        if not n:
            continue
        if n in t or t in n:
            return True
        if len(n) >= 2 and n[:2] in t:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["rakuten", "ndl"], required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    out = ROOT / ".cache" / f"ongoing-cont-{a.source}.jsonl"

    rows = json.load(SRC.open(encoding="utf-8"))
    done = set()
    if out.exists():
        for ln in out.open(encoding="utf-8"):
            try:
                done.add(json.loads(ln)["slug"])
            except Exception:
                pass
    todo = [r for r in rows if r["slug"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"[{a.source}] 対象 {len(rows):,} / 既済 {len(done):,} / 今回 {len(todo):,} "
          f"(推定 {len(todo) * 1.3 / 60:.0f}分)", flush=True)

    env = L._env() if a.source == "rakuten" else None
    nfound = 0
    with out.open("a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            mv = r.get("max_vol") or 0
            my = int(r["max_year"])
            cands = []
            try:
                if a.source == "rakuten":
                    items = L.rakuten_live_retry(env, title=r["title"], hits=30) or []
                    for it in items:
                        t, au = str(it.get("title") or ""), str(it.get("author") or "")
                        if not author_ok(r["authors"], au):
                            continue
                        # 題の同一性(当方題が相手題に含まれる)を要求 = 別作品を弾く
                        if norm(r["title"]) not in norm(t):
                            continue
                        if NOISE.search(t):
                            continue
                        v = volnum(t)
                        y = str(it.get("salesDate") or "")[:4]
                        # ★strong = 巻番号が当方最大より大きい / weak = 巻番号不明だが発売年が新しい
                        kind = "strong" if (v is not None and v > mv) else (
                            "weak" if (y.isdigit() and int(y) > my) else None)
                        if kind:
                            cands.append({"kind": kind, "vol": v, "isbn": it.get("isbn"),
                                          "date": it.get("salesDate"), "title": t[:60], "author": au[:40]})
                else:
                    recs = L.ndl_live_retry(f"title={r['title']}", maximum=40) or []
                    for x in recs:
                        t = str(x.get("title") or "")
                        au = " ".join(x.get("creators") or [])
                        if not author_ok(r["authors"], au):
                            continue
                        if norm(r["title"]) not in norm(t):
                            continue
                        if NOISE.search(t):
                            continue
                        v = volnum(t) or (int(str(x.get("vol"))) if str(x.get("vol") or "").isdigit() else None)
                        y = str(x.get("date") or "")[:4]
                        kind = "strong" if (v is not None and v > mv) else (
                            "weak" if (y.isdigit() and int(y) > my) else None)
                        if kind:
                            cands.append({"kind": kind, "vol": v, "isbn": x.get("isbn"),
                                          "date": x.get("date"), "title": t[:60], "author": au[:40]})
            except Exception as e:
                cands = None
                print(f"    ✗ {r['slug']} {str(e)[:60]}", flush=True)
            rec = {"slug": r["slug"], "title": r["title"], "max_vol": mv, "max_year": r["max_year"],
                   "found": cands if cands else [], "error": cands is None}
            if rec["found"]:
                nfound += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 100 == 0:
                print(f"  [{a.source}] {i:,}/{len(todo):,} 続刊あり {nfound:,}", flush=True)
    print(f"\n[{a.source}] 完了 {len(todo):,}作 / ★続刊候補あり {nfound:,}作 → {out}")


if __name__ == "__main__":
    main()
