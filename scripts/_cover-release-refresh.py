# -*- coding: utf-8 -*-
"""発売後の書影差し替え追従 (2026-08-25 ユーザ発見: 発売済み30冊中14冊=47%が旧書影)。

型: 楽天は発売前後に画像を更新し、URL末尾の版数が上がる(_1_7.jpg→_1_9.jpg)か
.gif仮書影→実jpgになる。うちは収穫時URLで凍結していた(仮書影検出器は.gif型しか見ない)。

処理: 直近 --days 日以内に発売された巻(ISBN有り)を楽天live再照会し、
現在のURLと異なれば cover-override.jsonl へ追記(ノーマライズ比較・noimage除外)。
★劣化ガード(2026-09-14): live が仮書影(`/{ISBN}.gif` = 著者名と書名を並べただけの画像)で、
  かつ頁に既に書影が在る時は **書かない**。旧実装は「違えば書く」だけで良し悪しを見ず、
  Kobo補完で入れた実書影や実jpgを .gif へ落としていた(885巻の一巡で書込500件中3件)。
  このscriptは週次蒸留が毎回回すので、放置すると毎週潰れ続ける型だった。格上げは従来どおり通る。
→ 対象頁を promote --only-file で再生成(このscriptはリスト出力まで)。
週次蒸留のstep1で --days 45 --ahead-months 1 を回す。

★発売前の巻(2026-10-11 ユーザ裁定 B): 旧実装は「45日前〜今日」に発売された巻しか見ず、
  週次の日より後に出る今月・来月の本は仮書影のまま次の週次まで放置されていた
  (2026-10-08 週次の実測: 10/1〜8発売=322/322が実書影、10/9以降=仮358+無し81がほぼ手つかず)。
  楽天は発売のかなり前に実書影へ差し替える(9/28 のアイドル⑩=差替203冊の75%が発売前・41冊は1か月以上前)。
  --ahead-months N = 今日の翌日〜N か月後の月末に発売予定の巻のうち、**書影が仮(.gif)か無い巻だけ**を足す
  (実書影の巻は発売後に上の窓で追従するので、ここでは引かない=照会数を絞る)。日付が年月だけの予約巻も含む。

usage: python scripts/_cover-release-refresh.py [--days 45] [--ahead-months 0] [--limit 0=無制限] [--plan]
       --plan = 対象の数だけ出して終わる(楽天には問い合わせない)
"""
import argparse
import datetime
import glob
import io
import json
import os
import re
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib
_LK = importlib.import_module("_lookup")

# ★仮書影(= 著者名と書名を並べただけの画像)の判定。skill placeholder-cover-refresh と同一規約:
#   本物 = .../{ISBN}_N_N.jpg  /  仮 = .../{ISBN}.gif (サフィックス無し・拡張子gif)
RE_PLACEHOLDER = re.compile(r"/\d{13}\.gif")


def ahead_end(base: datetime.date, months: int) -> datetime.date:
    """base の月から months か月後の月末。"""
    m = base.month - 1 + months
    y, m = base.year + m // 12, m % 12 + 1
    nxt = datetime.date(y + (m == 12), m % 12 + 1, 1)
    return nxt - datetime.timedelta(days=1)


def in_ahead(d: str, hi: str, ahead_hi: str) -> bool:
    """発売日 d が窓の後(hi より後)〜ahead_hi か。予約巻の「年月だけ」の日付も含める。"""
    if len(d) == 10:
        return hi < d <= ahead_hi
    if len(d) == 7 and d[4] == "-":
        return hi[:7] <= d <= ahead_hi[:7]
    return False


def needs_real_cover(cur: str) -> bool:
    """書影が仮(`/{ISBN}.gif`)か、無い/noimage の巻だけ発売前に引き直す。"""
    return (not cur) or bool(RE_PLACEHOLDER.search(cur)) or "noimage" in cur


def load_env():
    env = {}
    for name in (".env.local", ".env"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            for ln in io.open(p, encoding="utf-8"):
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--from", dest="lo", default=None, help="期間指定 YYYY-MM-DD(--daysより優先。未来も可=予約書影も動く)")
    ap.add_argument("--to", dest="hi", default=None)
    ap.add_argument("--ahead-months", type=int, default=0,
                    help="発売前の巻も見る: 窓の翌日〜Nか月後の月末(0=見ない)。書影が仮/無しの巻だけ")
    ap.add_argument("--plan", action="store_true", help="対象数だけ出して終わる(楽天に問い合わせない)")
    a = ap.parse_args()
    today = datetime.date.today()
    lo = a.lo or (today - datetime.timedelta(days=a.days)).isoformat()
    hi = a.hi or today.isoformat()
    ahead_hi = ahead_end(datetime.date.fromisoformat(hi), a.ahead_months).isoformat() if a.ahead_months > 0 else None
    years = {lo[:4], hi[:4]} | ({ahead_hi[:4]} if ahead_hi else set())

    # 直近発売巻の収集(発売日がlo..hi・ISBN有り) + 発売前で書影が仮/無しの巻(hi<日付<=ahead_hi)
    targets = []  # (slug, isbn, cur_cover)
    n_ahead = 0
    seen = set()
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        t = io.open(f, encoding="utf-8").read()
        if not any(yr in t for yr in years):
            continue
        try:
            y = yaml.safe_load(t)
        except Exception:
            continue
        stem = os.path.basename(f)[:-4]
        for ed in y.get("editions") or []:
            for v in ed.get("volumes") or []:
                if not v.get("isbn13"):
                    continue
                isbn = str(v["isbn13"])
                cur = str(v.get("cover_url") or "")
                d = str(v.get("release_date") or "")[:10]
                if len(d) == 10 and lo <= d <= hi:
                    pass
                elif ahead_hi and in_ahead(d, hi, ahead_hi) and needs_real_cover(cur):
                    n_ahead += 1
                else:
                    continue
                if (stem, isbn) in seen:
                    continue
                seen.add((stem, isbn))
                targets.append((stem, isbn, cur))
    print(f"対象巻(発売{lo}〜{hi}): {len(targets) - n_ahead}"
          + (f" + 発売前(〜{ahead_hi}・書影が仮/無し): {n_ahead}" if ahead_hi else ""), flush=True)
    if a.plan:
        print(f"(--plan: 楽天照会 約{len(targets) * 1.3 / 60:.0f}分の見込み・ここで終了)")
        return
    if a.limit:
        targets = targets[: a.limit]

    env = load_env()
    out = io.open(os.path.join(ROOT, "data", "seeds", "cover-override.jsonl"), "a", encoding="utf-8", newline="\n")
    touched = set()
    n_upd = n_same = n_none = n_err = n_down = 0
    for i, (stem, isbn, cur) in enumerate(targets):
        try:
            items = _LK.rakuten_live_retry(env, isbn=isbn)
        except Exception:
            n_err += 1
            continue
        live = ""
        for it in items or []:
            d = it.get("Item") or it
            live = d.get("largeImageUrl") or d.get("mediumImageUrl") or ""
            if live:
                break
        if not live or "noimage" in live:
            n_none += 1
        elif live.split("?")[0] == cur.split("?")[0]:
            n_same += 1
        elif RE_PLACEHOLDER.search(live) and cur:
            # ★劣化ガード(2026-09-14 実測で新設): live が仮書影(= 著者名と書名を並べただけの
            #   `/{ISBN}.gif`)の時は、頁に既に何か書影が在るなら **絶対に書かない**。
            #   旧実装は「頁と違えば書く」だけで良し悪しを見ず、楽天が紙の仮書影を返すISBNで
            #   ①Kobo電子で補完した実書影(jukebox 3巻/吸血バーへようこそ 4巻)
            #   ②実jpg
            #   を .gif へ落としていた(9月発売885巻の一巡で書込500件中3件)。週次蒸留 step1 が
            #   --days 45 で毎回回すため、放置すると Kobo補完/巻抜けfill の書影が毎週潰される。
            #   ★逆方向(仮.gif → 実jpg)と版数上げ(_1_2 → _1_3)は従来どおり通る=格上げは止めない。
            #   ★頁が空(cur無し)の時だけは仮書影でも書く(文字だけでも無いよりは出る)。
            #   ★Kobo由来を一律保護にはしない: 紙の実物が出たらそちらが正しいため
            #   ([[kobo_cover_wrong_for_old_print]] = Kobo電子は注意書き付きの代替)。
            n_down += 1
        else:
            url = live.replace("?_ex=120x120", "?_ex=300x300").replace("?_ex=200x200", "?_ex=300x300")
            out.write(json.dumps({"isbn13": isbn, "cover_url": url, "slug": stem,
                                  "reason": f"発売後差し替え追従(旧:{cur.split('/')[-1][:28]})",
                                  "at": today.isoformat()}, ensure_ascii=False) + "\n")
            out.flush()
            touched.add(stem)
            n_upd += 1
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(targets)} 更新{n_upd}", flush=True)
        time.sleep(1.3)
    io.open(os.path.join(ROOT, ".cache", "cover-refresh-touched.txt"), "w", encoding="utf-8", newline="\n").write(
        "\n".join(sorted(touched)))
    print(f"更新{n_upd} / 同一{n_same} / 楽天無し{n_none} / err{n_err} / ★劣化ガードで不採用{n_down} → 対象頁 {len(touched)}")
    if touched:
        print("→ 再生成: python scripts/_promote-bulk-v2.py --only-file .cache/cover-refresh-touched.txt")


if __name__ == "__main__":
    main()
