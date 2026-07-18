#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AniList 差分再フェッチ (= 2026-07-18 新設。アイドル運転柱=種aの鮮度維持)

背景: 全件ダンプ(anilist-manga-dump-v3.jsonl.gz)は 2026-05-31 取得の一回きり。
月次フルダンプが正規ルートだが回らない期間の鮮度劣化(新作gap/status/popularity)を、
「前回カーソル以降に更新された作品だけ」の軽量フェッチで埋める。

仕組み:
  sort: UPDATED_AT_DESC で新しい方から頁繰り → updatedAt がカーソル(前回同期時刻)を
  下回った頁で自然停止。取得行は dump-v3 と同スキーマ(+updatedAt) で delta jsonl に追記。
  カーソルは「走行開始時刻」へ、★完走した時だけ前進(中断時は次回同じ範囲を再取得=冪等)。

制約(既知):
  AniList は 1 filter 組合せ 5,000 件(page100)cap。差分が 5,000 を超えた場合は
  「カバーできた最古 updatedAt」までカーソルを進め、残りは次回フルダンプ回収と明示log。

CLI:
  python scripts/_anilist-delta.py               # 差分収集(アイドル運転用。自然停止)
  python scripts/_anilist-delta.py --since 2026-05-31   # カーソル手動指定(初回/やり直し)
  python scripts/_anilist-delta.py --merge       # delta を dump-v3 へ畳む(★蒸留/enrich再生成の直前に。アイドルでは実行しない)
出力:
  .cache/anilist-delta.jsonl        (追記。id重複あり=読む側でlast-wins)
  .cache/anilist-delta-cursor.json  ({"since": unix, "at": iso})
"""
import gzip
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
UA = "MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)"
ENDPOINT = "https://graphql.anilist.co"
DUMP = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
DELTA = ROOT / ".cache" / "anilist-delta.jsonl"
CURSOR = ROOT / ".cache" / "anilist-delta-cursor.json"
KEEP_FORMATS = {"MANGA", "ONE_SHOT"}  # dump-v3 と同スコープ(NOVEL 除外)

# ★dump-v3 の QUERY と同 field + updatedAt(カーソル判定用)
QUERY = """
query ($page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { total currentPage hasNextPage }
    media(type: MANGA, countryOfOrigin: \"JP\", sort: UPDATED_AT_DESC) {
      id
      idMal
      updatedAt
      title { romaji english native }
      synonyms
      type
      format
      status
      source(version: 3)
      countryOfOrigin
      isAdult
      isLicensed
      volumes
      chapters
      startDate { year month day }
      endDate { year month day }
      description(asHtml: false)
      averageScore
      meanScore
      popularity
      favourites
      genres
      tags { name rank category isGeneralSpoiler isMediaSpoiler isAdult }
      relations {
        edges {
          relationType
          node {
            id type format
            title { romaji english native }
          }
        }
      }
      staff(perPage: 10) {
        edges {
          role
          node { id name { full native } }
        }
      }
    }
  }
}
"""


def fetch_page(page, max_retry=5):
    data = json.dumps({"query": QUERY, "variables": {"page": page}}).encode()
    for retry in range(max_retry):
        try:
            req = urllib.request.Request(ENDPOINT, data=data,
                                         headers={"User-Agent": UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["data"]["Page"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                wait = 10 * (2 ** retry)
                print(f"  HTTP {e.code} → {wait}s待機", flush=True)
                time.sleep(wait)
                continue
            if e.code == 400:
                return None  # page cap
            raise
        except Exception as e:
            time.sleep(5 * (retry + 1))
    raise RuntimeError(f"page {page}: {max_retry}回失敗")


def cmd_collect(since_arg):
    if since_arg:
        since = int(time.mktime(time.strptime(since_arg, "%Y-%m-%d")))
    elif CURSOR.exists():
        since = json.loads(CURSOR.read_text())["since"]
    elif DUMP.exists():
        since = int(DUMP.stat().st_mtime)  # 初回=全件ダンプ取得時刻から
    else:
        print("カーソルも dump-v3 も無い → --since YYYY-MM-DD を指定"); sys.exit(1)
    run_start = int(time.time())
    print(f"anilist-delta: since={time.strftime('%Y-%m-%d %H:%M', time.localtime(since))} から回収 (2.5s/req)")
    n_new = n_skip_fmt = 0
    min_seen = None
    page = 1
    capped = False
    with io.open(DELTA, "a", encoding="utf-8") as f:
        while True:
            p = fetch_page(page)
            if p is None:
                capped = True
                print("★page cap(400) 到達"); break
            media = p.get("media") or []
            reached_boundary = False
            for m in media:
                ua = m.get("updatedAt") or 0
                min_seen = ua if min_seen is None else min(min_seen, ua)
                if ua < since:
                    reached_boundary = True
                    continue
                if m.get("format") not in KEEP_FORMATS:
                    n_skip_fmt += 1
                    continue
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
                n_new += 1
            f.flush()
            if reached_boundary or not (p.get("pageInfo") or {}).get("hasNextPage"):
                break
            if page >= 100:
                capped = True
                print("★5,000件cap到達(page=100)"); break
            page += 1
            if page % 20 == 0:
                print(f"  ...page {page} (回収{n_new})", flush=True)
            time.sleep(2.5)
    # ★カーソル前進: 完走=走行開始時刻 / cap=カバー済み最古updatedAt(それ以前の残りは次回フルダンプで回収)
    new_since = min_seen if (capped and min_seen and min_seen > since) else run_start
    CURSOR.write_text(json.dumps({"since": new_since, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    tail = "(cap到達: 取り残しは次回月次フルダンプで回収)" if capped else ""
    print(f"完了: 回収{n_new} / 対象外format skip {n_skip_fmt} / 頁{page} → {DELTA.name} {tail}")
    print(f"  カーソル→{time.strftime('%Y-%m-%d %H:%M', time.localtime(new_since))}")


def cmd_merge():
    """delta を dump-v3 に畳む(last-wins)。★enrichマップ/match再生成の直前に明示実行。"""
    if not DELTA.exists():
        print("delta なし = merge不要"); return
    delta = {}
    for l in io.open(DELTA, encoding="utf-8"):
        try:
            m = json.loads(l)
            delta[m["id"]] = m  # 後勝ち=最新
        except Exception:
            pass
    print(f"delta: {len(delta):,}作品(重複畳み後)")
    bak = DUMP.with_suffix(f".bak-{time.strftime('%Y%m%d-%H%M%S')}.gz")
    os.replace(DUMP, bak)
    n_upd = n_keep = 0
    with gzip.open(bak, "rt", encoding="utf-8") as src, gzip.open(DUMP, "wt", encoding="utf-8") as out:
        for l in src:
            try:
                mid = json.loads(l)["id"]
            except Exception:
                out.write(l); continue
            if mid in delta:
                out.write(json.dumps(delta.pop(mid), ensure_ascii=False) + "\n"); n_upd += 1
            else:
                out.write(l); n_keep += 1
        for m in delta.values():  # 新規作品
            out.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"merge完了: 更新{n_upd:,} / 据置{n_keep:,} / 新規{len(delta):,} (backup={bak.name})")
    print("  ★次: enrichマップ再生成(_build-anilist-enrich-map.py)→promoteで本番反映。deltaは残す(次mergeはbakでなく新dump基準)")
    os.replace(DELTA, DELTA.with_suffix(".merged-" + time.strftime("%Y%m%d") + ".jsonl"))


if __name__ == "__main__":
    if "--merge" in sys.argv:
        cmd_merge()
    else:
        since = None
        if "--since" in sys.argv:
            since = sys.argv[sys.argv.index("--since") + 1]
        cmd_collect(since)
