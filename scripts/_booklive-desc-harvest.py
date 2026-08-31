# -*- coding: utf-8 -*-
"""BookLive商品頁の作品紹介文ハーベスト (= エンリッチ材料の新鉱脈。2026-08-27 ユーザ裁定)。

背景: 5冊以上でエンリッチ手つかず3,026作の楽天caption実測=0.6%(30/5,319)で楽天鉱脈は枯れ。
一方BookLive結線済み(tameshiyomi-map)の商品頁は出版社公式の1巻紹介文(120-300字・ネタバレなし)を
持つ(サンプル4/4良品質)= enrich-catch-synopsis の「1巻基点」規律にそのまま合う材料。

処理: 対象slug(.cache/enrich5-targets.json 等)× tameshiyomi-map の title_id →
  https://booklive.jp/product/index/title_id/{tid}/vol_no/001 の JSON-LD description を抽出。
出力: .cache/booklive-desc.jsonl (slug/title_id/desc/at。逐次追記=resumable)
★レート = _booklive 共通ゲート(2026-08-31: 札・直列2.0秒・日次上限)。
  429等の異常はBlocked=台帳に書かず即中断(旧実装は429以外のHTTPエラーをerr行として焼いていた)。

  python scripts/_booklive-desc-harvest.py [--targets .cache/enrich5-targets.json] [--limit N]
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

import _booklive
from _booklive import Blocked, CapReached

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "booklive-desc.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=os.path.join(ROOT, ".cache", "enrich5-targets.json"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    _booklive.assert_not_blocked()
    targets = json.load(io.open(a.targets, encoding="utf-8"))
    tm = json.load(io.open(os.path.join(ROOT, "data", "tameshiyomi-map.json"), encoding="utf-8"))
    done = set()
    if os.path.exists(OUT):
        for ln in io.open(OUT, encoding="utf-8"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            # ★err行のうち404以外(旧実装が403/5xx等を焼いた分)は再取得対象に戻す(2026-08-31)
            if "err" in d and d.get("err") != 404:
                continue
            done.add(d["slug"])
    todo = [t for t in targets if t["slug"] in tm and t["slug"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"対象 {len(todo)} (BookLive結線のみ / 済み{len(done)}skip)", flush=True)
    n_ok = n_empty = n_err = 0
    f = io.open(OUT, "a", encoding="utf-8", newline="\n")
    for i, t in enumerate(todo):
        tid = tm[t["slug"]][0]
        url = f"https://booklive.jp/product/index/title_id/{tid}/vol_no/001"
        try:
            st, html = _booklive.request(url)
        except CapReached as e:
            print(f"★打ち切り: {e}(進捗は逐次保存済み)", flush=True)
            break
        except Blocked as e:
            print(f"★中断: BookLiveから200/404以外の応答 ({e})。台帳には書かない。",
                  file=sys.stderr, flush=True)
            sys.exit(2)
        if st != 200:   # ★404=定まった否定のみ記録(商品頁が無い=紹介文なし確定)
            n_err += 1
            f.write(json.dumps({"slug": t["slug"], "title_id": tid, "desc": "", "err": 404,
                                "at": datetime.date.today().isoformat()}, ensure_ascii=False) + "\n")
            f.flush()
            continue
        desc = ""
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                d = json.loads(m.group(1))
            except Exception:
                continue
            for x in (d if isinstance(d, list) else [d]):
                if isinstance(x, dict) and x.get("description"):
                    desc = str(x["description"])
                    break
            if desc:
                break
        if not desc:
            m = re.search(r'<meta name="description" content="([^"]+)"', html)
            desc = m.group(1) if m else ""
        # BookLive定型尾(「…続きはログイン後」等)は無し=JSON-LDは素の紹介文。全文保存(要約はAI側)
        f.write(json.dumps({"slug": t["slug"], "title_id": tid, "desc": desc,
                            "at": datetime.date.today().isoformat()}, ensure_ascii=False) + "\n")
        f.flush()
        if desc and len(desc) >= 40:
            n_ok += 1
        else:
            n_empty += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(todo)} 良材料{n_ok} 薄/無{n_empty} 404 {n_err}", flush=True)
    print(f"\n完了: 良材料(40字+) {n_ok} / 薄・無し {n_empty} / 404 {n_err} → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
