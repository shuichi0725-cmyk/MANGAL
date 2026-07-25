"""取りこぼし第2パス = 楽天で埋まらなかった作品を NDL(ISBN直引き)で補う。

第1パス(`_torikoboshi-harvest.py`)は楽天で 44,533件中 42,558件を回収したが、
  - 楽天ヒット無し 1,946件(= 古い絶版本835件/極小出版/外国ISBN111件。 ★NDLでは実在を確認済)
  - ヒットしたが 題ヨミ/著者ヨミ 等が欠ける分
が残る。 NDLは **`dc:title` の `dcndl:transcription` = 題ヨミ(分かち書き)** を持ち、
これは [[furigana_ndl_audit]] の通り ground truth。 slug生成と索引ガードの土台になる。

★NDL不在 ≠ 不存在(BL/小出版は収録が弱い)。 埋まらないものは**埋めない**(=登録保留)。

出力 = `.cache/torikoboshi/ndl.jsonl` (1行=1 ISBN、 追記のみ・冪等)
  {"isbn":..., "hit":bool, "rec":{title,title_kana,series,series_kana,date,pub,creators,vol}}
★read-only: 種2 も 本番 も seed も書かない。

usage:
  python scripts/_torikoboshi-ndl.py --status
  python scripts/_torikoboshi-ndl.py --run --limit 300     # 1.3秒/req ≒ 7分/300件
  python scripts/_torikoboshi-ndl.py --run --limit 300 --mode nokana   # 楽天ヒット有だがヨミ欠け
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
HARVEST = ROOT / ".cache" / "torikoboshi" / "harvest.jsonl"
OUT = ROOT / ".cache" / "torikoboshi" / "ndl.jsonl"
BACKOFF = (3, 10, 30, 90)      # ★NDLの回復は楽天より遅い(時間単位)ので待ちを長く
FAIL_STREAK = 8                # 連続失敗 = 本当の遮断とみなして中断


def _lookup():
    """live呼出は _lookup.py に封じ込め(= endpoint/レート/ヨミ抽出を再実装しない)。"""
    spec = importlib.util.spec_from_file_location("lookup", ROOT / "scripts" / "_lookup.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def targets(mode):
    """mode=miss(既定): 楽天ヒット無し / nokana: ヒット有だが題ヨミ欠け / all: 両方。"""
    seen, out = set(), []
    with HARVEST.open(encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            ib = d["isbn"]
            if ib in seen:
                continue
            seen.add(ib)
            it = d.get("item") or {}
            if not it:
                if mode in ("miss", "all"):
                    out.append(ib)
            elif not (it.get("titleKana") or "").strip():
                if mode in ("nokana", "all"):
                    out.append(ib)
    return out


def done():
    if not OUT.exists():
        return set()
    s = set()
    with OUT.open(encoding="utf-8") as f:
        for ln in f:
            try:
                s.add(json.loads(ln)["isbn"])
            except Exception:
                continue
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--mode", default="miss", choices=["miss", "nokana", "all"])
    a = ap.parse_args()

    tg = targets(a.mode)
    have = done()
    todo = [i for i in tg if i not in have]
    hit = 0
    if OUT.exists():
        hit = sum(1 for ln in OUT.open(encoding="utf-8") if '"hit": true' in ln)
    print(f"mode={a.mode} 対象 {len(tg):,} / 取得済 {len(have):,}(NDL実在 {hit:,}) / 残 {len(todo):,}")
    if not a.run:
        print("  --run --limit N で実行(1.3秒/req)")
        return

    L = _lookup()
    batch = todo[:a.limit]
    print(f"NDL照会 {len(batch)} 件 (約{len(batch) * 1.3 / 60:.1f}分) ...", flush=True)
    buf, nhit, streak, stopped = [], 0, 0, None
    for i, ib in enumerate(batch, 1):
        try:
            recs = L.ndl_live_retry(f'isbn="{ib}"', maximum=3, backoff=BACKOFF)
        except Exception as e:
            streak += 1
            print(f"  ✗ {ib}: {type(e).__name__}", flush=True)
            if streak >= FAIL_STREAK:
                stopped = f"{FAIL_STREAK}件連続失敗"
                break
            continue
        streak = 0
        r = recs[0] if recs else None
        if r:
            nhit += 1
            buf.append({"isbn": ib, "hit": True, "rec": {
                "title": r.get("title"), "title_kana": r.get("title_kana"),
                "series": r.get("series"), "series_kana": r.get("series_kana"),
                "date": r.get("date"), "pub": r.get("pub"),
                "creators": r.get("creators"), "vol": r.get("vol")}})
        else:
            buf.append({"isbn": ib, "hit": False, "rec": None})
        if i % 25 == 0:
            _append(buf); buf = []
            print(f"  ...{i}/{len(batch)} (NDL実在 {nhit})", flush=True)
    _append(buf)
    print(f"★{'中断: ' + stopped if stopped else '完了'} / NDL実在 {nhit}/{len(batch)}")


def _append(recs):
    if not recs:
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
