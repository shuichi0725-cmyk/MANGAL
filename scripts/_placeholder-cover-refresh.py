#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仮の書影(文字だけの .gif)を、楽天に実物が出たら差し替える。

★なぜ要るか (= 2026-08-02 ユーザ発見)
  楽天は発売前・発売直後の本に「著者名と書名を並べただけの画像」を返す。実物が用意されると
  **URL自体が別物に変わる**ため、こちらが引き直さない限り永久に仮のまま出続ける。
  実例: HUNTER×HUNTER 39 は本番が .gif のままだったが、live で引くと _1_9.jpg が返った。

★判定は URL の形だけで確実にできる(実測で裏取り済み)
    本物 = .../{ISBN}_1_9.jpg   ← サフィックス _N_N 付き
    仮   = .../{ISBN}.gif       ← サフィックス無し・拡張子 gif
  初回実測: 本番 10,063巻が .gif。うち2025年以降が約1,750巻(=実物が出ている見込みが高い)。
  2019年以前の約8,300巻は live で引いても .gif のまま(絶版で画像が用意されない)=既定では触らない。

★アイドル運転の3条件を満たす(idle-run の柱⑩)
  逐次保存 = 1件ごとに queue/結果を書く / 自然停止 = queue が尽きたら終わる /
  冪等再開 = 済み集合で続きから。429 は即中断(次の手すきで再開)。

使い方:
  python scripts/_placeholder-cover-refresh.py --build-queue      # 本番索引から対象を作る(月1)
  python scripts/_placeholder-cover-refresh.py --limit 200        # 1バッチ(~4.5分)。再起動で続き
  python scripts/_placeholder-cover-refresh.py --stats            # 現在地
  python scripts/_placeholder-cover-refresh.py --build-queue --since-year 2000   # 旧作も対象にする

★このscriptは seed に書くだけ(cover-override.jsonl)。頁への反映は上位モデルの「反映して」。
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _lookup as _LK  # ★共通楽天ヘルパ(429厳密判定+backoff吸収。偽429恒久対策 2026-08-03)
SRC = os.path.join(ROOT, "data", "manga.v2")
QUEUE = os.path.join(ROOT, ".cache", "placeholder-cover", "queue.jsonl")
DONE = os.path.join(ROOT, ".cache", "placeholder-cover", "done.json")
OUT = os.path.join(ROOT, "data", "seeds", "cover-override.jsonl")
EP = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"
RATE = 1.3

RE_PLACEHOLDER = re.compile(r"/(\d{13})\.gif")
RECENT_FLOOR = (date.today() - timedelta(days=180)).isoformat()  # ★新刊窓(レーベルロゴ型)の下限
RE_REAL = re.compile(r"_\d+_\d+\.(jpg|jpeg|png)")


def load_env() -> dict:
    env = {}
    p = os.path.join(ROOT, ".env.local")
    if not os.path.exists(p):
        return env
    for ln in io.open(p, encoding="utf-8"):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def rakuten_by_isbn(env: dict, isbn: str) -> dict:
    """楽天live 1件。★偽429恒久対策(2026-08-03 アイドル柱⑩停止の根因):
    旧実装+呼び側の `"429" in str(e)` 文字列マッチが、JSONDecodeError の位置表示
    (「line 1 column 429」等)まで実429と誤検知して柱ごと停止していた。
    以後は共通ヘルパ `_lookup.rakuten_live_retry`(HTTPError.code==429 の厳密判定 +
    backoff(2,5,15,45s)吸収・rate_gate/Referer/Origin内蔵)に統一。
    連続429(実スロットル)は Throttled が伝播(呼び側で中断)。"""
    return {"Items": _LK.rakuten_live_retry(env, isbn=isbn)}


def build_queue(since_year: int) -> int:
    """本番索引の全頁から「仮の書影」の巻を集める。冪等(毎回作り直し)。"""
    rows = []
    files = sorted(glob.glob(os.path.join(SRC, "*.yml")))
    print(f"走査 {len(files)} 頁", flush=True)
    import yaml
    for n, p in enumerate(files, 1):
        if n % 20000 == 0:
            print(f"  … {n}", flush=True)
        try:
            d = yaml.safe_load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        slug = d.get("slug") or os.path.basename(p)[:-4]
        for e in (d.get("editions") or []):
            for v in (e.get("volumes") or []):
                cu = str(v.get("cover_url") or "")
                m = RE_PLACEHOLDER.search(cu)
                rd = str(v.get("release_date") or "")
                y = int(rd[:4]) if rd[:4].isdigit() else 0
                if m:
                    if y < since_year:
                        continue  # 旧作は live でも .gif のまま=既定で除外
                    rows.append({"isbn": m.group(1), "slug": slug,
                                 "number": v.get("number"), "release_date": rd, "cur": cu})
                elif rd and rd >= RECENT_FLOOR and v.get("isbn13"):
                    # ★新刊窓(2026-08-04 LV999の村人21型): URL形式は正常(_1_6.jpg)でも中身が
                    #   レーベルロゴ等のことがある。発売前後(直近180日〜未来)の巻は live を
                    #   引き直し、★書影URLが変わっていたら差し替える(変わらなければ何もしない)。
                    rows.append({"isbn": str(v["isbn13"]), "slug": slug,
                                 "number": v.get("number"), "release_date": rd, "cur": cu})
    # ★周回設計(2026-08-03 ユーザ指摘「枯れても、いつ実物に差し替わるか不定=一回やったらおしまいではない」):
    #   旧実装は done.json が build-queue 後も残り、「まだ仮のまま(still_placeholder)」の巻が
    #   次周回で二度と再照会されなかった(=後から実物が出る層が恒久に取り残される穴)。
    #   以後: 「済み」の表現は seed(cover-override.jsonl)在籍のみ = queueから除外し(reflect前の二重照会防止)、
    #   done.json は build-queue 時に rotate(リセット)して still/no_item/error を毎周回すべて引き直す。
    # ★同一ISBNの重複行を除去(複数edition/バージョンで同ISBNが並ぶ型)
    _seen_q = set()
    rows = [r for r in rows if not (r["isbn"] in _seen_q or _seen_q.add(r["isbn"]))]
    seeded = set()
    if os.path.exists(OUT):
        for ln in io.open(OUT, encoding="utf-8"):
            try:
                seeded.add(json.loads(ln)["isbn13"])
            except Exception:
                pass
    before = len(rows)
    rows = [r for r in rows if r["isbn"] not in seeded]
    if os.path.exists(DONE):
        os.replace(DONE, DONE + ".prev")  # 前周回の照会結果は .prev に退避(done はリセット)
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    with io.open(QUEUE, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    yr = collections.Counter(r["release_date"][:4] for r in rows if r["release_date"])
    print(f"\nqueue {len(rows)}件 (seed差し替え済 {before - len(rows)}件を除外 / done.jsonはrotate) → {os.path.relpath(QUEUE, ROOT)}")
    print("  発売年:", dict(sorted(yr.items(), reverse=True)[:8]))
    return len(rows)


def load_done() -> dict:
    if os.path.exists(DONE):
        try:
            return json.load(io.open(DONE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-queue", action="store_true")
    ap.add_argument("--since-year", type=int, default=2025,
                    help="この年以降の巻だけ対象(既定2025。旧作は live でも .gif のまま)")
    ap.add_argument("--limit", type=int, default=200, help="1バッチの照会件数")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()

    if a.build_queue:
        build_queue(a.since_year)
        return 0

    if not os.path.exists(QUEUE):
        print("★queue が無い → 先に --build-queue")
        return 2
    q = [json.loads(l) for l in io.open(QUEUE, encoding="utf-8") if l.strip()]
    done = load_done()
    todo = [r for r in q if r["isbn"] not in done]

    if a.stats:
        got = sum(1 for v in done.values() if v == "replaced")
        still = sum(1 for v in done.values() if v == "still_placeholder")
        print(f"queue {len(q)} / 照会済 {len(done)} / 残 {len(todo)}")
        print(f"  実物に差し替えた: {got} / まだ仮のまま: {still}")
        print(f"  seed: {OUT} ({sum(1 for _ in io.open(OUT, encoding='utf-8')) if os.path.exists(OUT) else 0} 行)")
        return 0

    if not todo:
        print("★queue 消化済み(自然停止)。--build-queue で作り直せば次の周回へ")
        return 0

    env = load_env()
    if not env.get("RAKUTEN_APP_ID"):
        print("★abort: .env.local に RAKUTEN_APP_ID が無い")
        return 2

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n_rep = n_still = n_none = 0
    batch = todo[:a.limit]
    print(f"照会 {len(batch)}件 (残 {len(todo)})", flush=True)
    fout = io.open(OUT, "a", encoding="utf-8", newline="\n")
    for i, r in enumerate(batch, 1):
        isbn = r["isbn"]
        try:
            d = rakuten_by_isbn(env, isbn)
        except _LK.Throttled:
            print("★楽天429が連続(実スロットル)→中断(次の手すきで再開)")
            break
        except Exception:
            done[isbn] = "error"  # 瞬断/JSON崩れ=1件skip(偽429で柱を止めない)
            continue
        its = d.get("Items") or []
        img = str((its[0].get("largeImageUrl") or its[0].get("mediumImageUrl") or "")) if its else ""
        _norm = lambda u: re.sub(r"\?_ex=\d+x\d+$", "", u or "")  # noqa: E731
        cur = str(r.get("cur") or "")
        if img and RE_REAL.search(img) and _norm(img) != _norm(cur):
            was_gif = RE_PLACEHOLDER.search(cur) is not None
            fout.write(json.dumps({"isbn13": isbn, "cover_url": img, "slug": r["slug"],
                                   "number": r["number"],
                                   "reason": "placeholder_gif→real" if was_gif else "cover_url変化(レーベルロゴ型)",
                                   "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
            fout.flush()                      # ★逐次保存(停止しても残る)
            done[isbn] = "replaced"
            n_rep += 1
        elif img:
            done[isbn] = "still_placeholder"  # gif据置き or URL不変(新刊窓)
            n_still += 1
        else:
            done[isbn] = "no_item"
            n_none += 1
        if i % 20 == 0:
            json.dump(done, io.open(DONE, "w", encoding="utf-8"))
            print(f"  …{i}/{len(batch)} 実物{n_rep} 仮のまま{n_still}", flush=True)
    fout.close()
    json.dump(done, io.open(DONE, "w", encoding="utf-8"))
    print(f"\n実物に差し替え {n_rep} / まだ仮 {n_still} / 該当なし {n_none}")
    print(f"  seed 追記 → {os.path.relpath(OUT, ROOT)}")
    print(f"  残 {len([r for r in q if r['isbn'] not in done])}件 → 同じコマンドで続き")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
