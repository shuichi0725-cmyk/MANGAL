# -*- coding: utf-8 -*-
"""保留頁の自動再訪 (2026-08-24 ユーザGO③)。

demographic/caption 未供給で索引保留になった予約由来頁(発売直後は楽天が空=正常)を、
後日の日次で自動再照会して埋める。捏造はしない=楽天が返した時だけ埋まる。

対象 = data/seeds/preorder-pages/*.yml のうち demographic 空 or rakuten_caption 空。
照会 = 楽天 live by ISBN(rakuten_live_retry・1.3s)。booksGenreId→demographic 写像は分類器と同じ。
更新 = preorder-pages(恒久保管庫) を直接更新 → 変更slugを表示(呼び手が reflect --only する)。

usage: python scripts/_preorder-refresh-held.py [--limit 30]
       python scripts/_preorder-refresh-held.py --recheck-demo <slug,...>   # 既に付いた demographic を引き直す

★2026-09-24 是正(写像バグ): 旧 DEMO_MAP は booksGenreId の**先頭6桁**で引いていたが、楽天の `001001` は
  「漫画(コミック)」全体。少年/少女/青年/レディースは**9桁**(001001001/002/003/004 = harvest の SUBGENRES と同じ)。
  そのため再訪で demographic が付いた頁は**中身に関係なく全部 shounen** になっていた
  (8/26〜9/19 に29頁。秋田 A.L.C.DX / ラブパルフェ(TL) まで shounen)。9桁で引き、複数の対象が割れたら付けない(fail-closed)。
  引き直しは --recheck-demo(写像が決まらなければ null に戻す=誤値より空。promote は null なら表示しない)。
"""
import argparse
import datetime
import glob
import io
import json
import os
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, ".cache", "preorders", "refresh-held-state.json")  # slug → 最後に楽天照会した日
TODAY = datetime.date.today().isoformat()
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib
_LK = importlib.import_module("_lookup")

# harvest(_rakuten-preorder-harvest.py SUBGENRES)と同じ写像。★001001 は漫画全体=9桁で引く(2026-09-24 是正)
DEMO_MAP9 = {"001001001": "shounen", "001001002": "shoujo", "001001003": "seinen",
             "001001004": "josei"}
DEMO_MAP6 = {"001021": "josei"}  # BL(skill daily-distill Layer1 の規定)


def demo_from_gid(gid: str):
    """booksGenreId("/"区切り複数あり)→demographic。対象が1種に決まる時だけ返す(割れ/該当なし=None)。"""
    found = set()
    for g in gid.split("/"):
        d = DEMO_MAP9.get(g[:9]) or DEMO_MAP6.get(g[:6])
        if d:
            found.add(d)
    return found.pop() if len(found) == 1 else None


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
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--recheck-demo", default="", help="slug,... = 既存 demographic を楽天 booksGenreId から引き直す")
    a = ap.parse_args()
    env = load_env()
    touched = []
    n_seen = 0
    recheck = {s.strip() for s in a.recheck_demo.split(",") if s.strip()}
    # ★2026-09-24: 旧実装は「ファイル名順の先頭 --limit 件」を毎日取っていた。楽天に caption がまだ無い頁
    #   (2,239頁中1,924頁)が先頭枠を塞ぎ続け、a〜b で始まる頁しか再訪されていなかった。
    #   → 最後に照会した日を STATE に持ち、古い順(未照会が先頭)に回す。状態は .cache(順番の記録にすぎない)。
    try:
        state = json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        state = {}
    cands = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "seeds", "preorder-pages", "*.yml"))):
        if recheck and os.path.basename(f)[:-4] not in recheck:
            continue
        y = yaml.safe_load(io.open(f, encoding="utf-8")) or {}
        pd0 = y.get("_preorder_draft") if isinstance(y.get("_preorder_draft"), dict) else {}
        # ★ジャンルID記録済み(=楽天が「その他」等で写像が決まらなかった頁)は demographic の再照会をしない。
        #   しないと決まらない頁が sorted 順の先頭 --limit 枠を毎日占有し、後ろの頁が永久に再訪されない。
        need_demo = bool(recheck) or (not y.get("demographic") and not pd0.get("rakuten_genre_id"))
        need_cap = not recheck and not (y.get("rakuten_caption") or y.get("synopsis"))
        if not (need_demo or need_cap):
            continue
        isbn = None
        for ed in y.get("editions") or []:
            for v in ed.get("volumes") or []:
                if v.get("isbn13"):
                    isbn = str(v["isbn13"])
                    break
            if isbn:
                break
        if not isbn:
            continue
        stem = os.path.basename(f)[:-4]
        cands.append((state.get(stem, ""), f, stem, y, need_demo, need_cap, isbn))
    cands.sort(key=lambda c: c[0])  # stable = 同じ照会日の中はファイル名順
    print(f"再訪候補 {len(cands)} (未照会 {sum(1 for c in cands if not c[0])})", flush=True)
    for _last, f, stem, y, need_demo, need_cap, isbn in cands[:a.limit]:
        n_seen += 1
        try:
            items = _LK.rakuten_live_retry(env, isbn=isbn)
        except Exception as e:
            print("  ERR", y.get("slug"), type(e).__name__, flush=True)
            continue
        state[stem] = TODAY
        it = (items or [{}])[0]
        it = it.get("Item") or it
        changed = []
        gid_new = False  # ジャンルIDの初記録だけ(=表示は変わらない)なら書くが reflect 対象にはしない
        gid = str(it.get("booksGenreId") or "")
        if need_demo and (gid or not recheck):
            d = demo_from_gid(gid)
            old = y.get("demographic")
            if (d or recheck) and d != old:
                y["demographic"] = d
                changed.append(f"demographic={old}->{d}(gid={gid})")
            if gid:  # 根拠を残す(空 dict は falsy なので `or {}` で書くと捨てられる)
                if not isinstance(y.get("_preorder_draft"), dict):
                    y["_preorder_draft"] = {}
                gid_new = y["_preorder_draft"].get("rakuten_genre_id") != gid
                y["_preorder_draft"]["rakuten_genre_id"] = gid
        elif need_demo and recheck:
            print(f"  ? {y.get('slug')}: 楽天が booksGenreId を返さない=据え置き", flush=True)
        cap = (it.get("itemCaption") or "").strip()
        if need_cap and len(cap) > 20:
            y["rakuten_caption"] = cap
            changed.append("caption")
        if changed or gid_new:
            io.open(f, "w", encoding="utf-8", newline="\n").write(
                yaml.safe_dump(y, allow_unicode=True, sort_keys=False))
        if changed:
            touched.append(os.path.basename(f)[:-4])
            print(f"  更新 {y.get('slug')}: {'+'.join(changed)}", flush=True)
        time.sleep(1.3)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, io.open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"再訪 {n_seen} / 更新 {len(touched)}")
    if touched:
        print("→ 反映: python scripts/_reflect-targeted.py --only " + ",".join(touched) + " --commit-only")


if __name__ == "__main__":
    main()
