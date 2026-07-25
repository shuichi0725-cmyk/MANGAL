"""取りこぼし作品の楽天ハーベスト = 孤児series(サイトに出ていない作品)の書誌をISBNで回収。

対象 = `docs/production-diagnostics/orphan-verify.tsv`(= `_audit-orphan-new-series.py` →
  検証済みリスト)の ISBN。 種2は題/著者/巻しか持たないので、**頁化に要る情報**
  (正式題・題ヨミ・著者ヨミ・出版社・レーベル・発売日・書影・itemCaption)を楽天から取る。

★2段構え(= live 46,874件×1.3秒=17時間 を避ける):
  1. `--cache` : 既存の巨大キャッシュ(rakuten-isbn.jsonl / -delta.jsonl)を **1パス走査**で回収。
                 ここで大半が埋まる。 数分。
  2. `--live`  : 残りだけ live 取得。 ★1.3秒/req のグローバルレートゲートを通す
                 (= 他の柱と並走しても合算429にならない)。
                 ★**429/瞬断は `_lookup.rakuten_live_retry` が backoff再試行で吸収**し止まらない。
                 連続10件失敗で初めて中断(= 一過性スロットルと本当の遮断を区別)。
                 `--limit N` で小分け実行(resumable = 出力済みISBNは自動skip)。

出力 = `.cache/torikoboshi/harvest.jsonl` (1行=1 ISBN、 追記のみ・冪等)
  {"isbn":..., "src":"cache|live|miss", "item":{楽天itemそのまま} or null}
★read-only: 種2 も 本番 も seed も書かない。 頁化はこの回収結果を材料に別工程で行う。

usage:
  python scripts/_torikoboshi-harvest.py --cache
  python scripts/_torikoboshi-harvest.py --live --limit 500
  python scripts/_torikoboshi-harvest.py --status
"""
import argparse
import csv
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

BACKOFF = [2, 5, 15, 45]    # ★429/瞬断の再試行待ち(秒)。 最後の要素は「待つだけで再試行しない」
FAIL_STREAK = 10            # ★これだけ連続で失敗したら本当の遮断とみなして中断

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "production-diagnostics" / "orphan-verify.tsv"
OUTDIR = ROOT / ".cache" / "torikoboshi"
OUT = OUTDIR / "harvest.jsonl"
CACHES = [ROOT / ".cache" / "rakuten-isbn.jsonl", ROOT / ".cache" / "rakuten-isbn-delta.jsonl"]
# 既定の対象 = 「本当に本番に無い」層のみ(実は掲載済み/同一作品疑いは除く)
DEFAULT_VERDICTS = {"著者は本番に在る(作品は別)", "本番に完全に無い"}


def _lookup():
    """live呼出は _lookup.py に封じ込め(=ここで endpoint/header/レートを再実装しない)。"""
    spec = importlib.util.spec_from_file_location("lookup", ROOT / "scripts" / "_lookup.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def targets(verdicts):
    rows = []
    with SRC.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in verdicts and r.get("isbn"):
                rows.append(r)
    return rows


def done_isbns():
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


def append(recs):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def stage_cache(want):
    """巨大キャッシュを1パスずつ走査(= ISBN毎に開き直さない)。"""
    got = {}
    for p in CACHES:
        if not p.exists() or not want:
            continue
        print(f"  走査 {p.name} ({p.stat().st_size // 1024 // 1024}MB) ...", flush=True)
        n = 0
        with p.open(encoding="utf-8") as f:
            for ln in f:
                n += 1
                if n % 500000 == 0:
                    print(f"    ...{n:,}行 / 回収 {len(got):,}", flush=True)
                if not want:
                    break
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                ib = str(d.get("isbn") or "")
                if ib in want:
                    got[ib] = d.get("item") or {}
                    want.discard(ib)
        print(f"    完了 {n:,}行 / 累計回収 {len(got):,} / 残 {len(want):,}", flush=True)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--verdict", default=None, help="対象verdictをカンマ区切りで上書き")
    a = ap.parse_args()

    verdicts = set(a.verdict.split(",")) if a.verdict else DEFAULT_VERDICTS
    rows = targets(verdicts)
    have = done_isbns()
    todo = [r for r in rows if r["isbn"] not in have]
    hit = sum(1 for ln in OUT.open(encoding="utf-8") if '"item": {' in ln or '"item":{' in ln) if OUT.exists() else 0
    print(f"対象 {len(rows):,} / 取得済 {len(have):,}(実データ {hit:,}) / 残 {len(todo):,}")
    if a.status or not (a.cache or a.live):
        print("  --cache でキャッシュ回収 → --live --limit N で残りを取得")
        return

    if a.cache:
        want = {r["isbn"] for r in todo}
        got = stage_cache(set(want))
        recs = [{"isbn": i, "src": "cache", "item": got[i]} for i in got]
        append(recs)
        print(f"★キャッシュ回収 {len(recs):,} 件を追記 → 残 {len(want) - len(got):,} は --live")
        return

    if a.live:
        L = _lookup()
        env = L._env()
        batch = todo[:a.limit]
        print(f"live取得 {len(batch)} 件 (1.3秒/req = 約{len(batch) * 1.3 / 60:.1f}分) ...", flush=True)
        recs, miss, throttled, streak = [], 0, 0, 0
        stopped = None
        for i, r in enumerate(batch, 1):
            ib = r["isbn"]
            items, err = None, None
            # ★一時スロットル(429)や瞬断で **止まらない**。 共通ヘルパがbackoff再試行する。
            #   (2026-07-25: 即中断実装で73分で停止。3日運転できた既存柱は再試行を持っていた)
            try:
                items = L.rakuten_live_retry(env, isbn=ib, backoff=BACKOFF)
            except Exception as e:
                err = "429" if isinstance(e, L.Throttled) else f"{type(e).__name__}: {str(e)[:50]}"
                throttled += isinstance(e, L.Throttled)
            if err:
                streak += 1
                recs.append({"isbn": ib, "src": "miss", "item": None, "err": err})
                miss += 1
                if streak >= FAIL_STREAK:
                    # ★連続失敗 = 一過性でなく本当の遮断/障害 → ここで初めて中断
                    stopped = f"{FAIL_STREAK}件連続失敗({err})"
                    break
                continue
            streak = 0
            if items:
                recs.append({"isbn": ib, "src": "live", "item": items[0]})
            else:
                recs.append({"isbn": ib, "src": "miss", "item": None})
                miss += 1
            if i % 25 == 0:
                append(recs)
                recs = []
                print(f"  ...{i}/{len(batch)} (ヒット無し{miss} / 429を吸収{throttled})", flush=True)
        append(recs)
        if stopped:
            print(f"★中断: {stopped}。 時間を置いて再実行(取得済はskipされる)")
        else:
            print(f"★live完了: {len(batch)}件 (ヒット無し {miss} / 429を吸収 {throttled})")


if __name__ == "__main__":
    main()
