#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本番待ち全部をテスト環境へ (2026-07-10 script化。「本番待ちテストに出して」の実体)。

前回週次(prod-deploy-marker)以降に変わった manga.v2 頁=「本番待ち」を全部 .preview-data に
投入し、次の週次で公開される内容を事前レビュー可能にする。

  python scripts/_prodwait-to-preview.py --dry-run          # 件数と内訳だけ(何も書かない)
  python scripts/_prodwait-to-preview.py                    # 投入+索引+カレンダー(commitは手動)
  python scripts/_prodwait-to-preview.py --push             # +commit+push(preview自動デプロイ15-20分)
  python scripts/_prodwait-to-preview.py --since 2026-07-07 # cutoff手動指定(下の汚染ガード用)

仕組みと安全弁(2026-07-10の実戦で確立):
  1. cutoff = markerのcode_commitのcommit日時(--sinceで上書き可)
  2. ★mtime汚染ガード: 該当>20,000頁なら「フルpromote(全消し復旧等)でmtimeが汚染」と判断し
     abort → 実変更の始点を調べて --since を指定させる(66k全部previewに入れる事故防止)
  3. preview専用ドラフト(manga.v2に無い頁=確認待ち②③④)は上書きされず温存
  4. masters6本(demographics/genres/magazines/publisher-aliases/publishers/slug-aliases)を差分同期
     (同期漏れ=新出版社キー頁が404の既知の罠)
  5. 索引再構築後、skipを★内部slugで診断(ファイル名≠slugのslug-override頁を誤検出しない)
     +原因分類(genre/publisher/magazine未キー)。genre:other=既知クラス(本番も同様)は報告のみ
  6. previewカレンダー再生成(src=preview自身)
"""
import os, sys, glob, json, shutil, subprocess, datetime, filecmp, argparse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
MASTERS = ["demographics.yml", "genres.yml", "magazines.yml",
           "publisher-aliases.yml", "publishers.yml", "slug-aliases.yml"]
POISON_LIMIT = 20_000


def cutoff_ts(since):
    if since:
        return datetime.datetime.strptime(since, "%Y-%m-%d").timestamp(), f"--since {since}"
    m = json.load(open(MARKER))
    h = m["code_commit"]
    ts = int(subprocess.run(["git", "show", "-s", "--format=%ct", h],
                            capture_output=True, text=True, cwd=ROOT).stdout.strip())
    return ts, f"marker {h[:12]} ({datetime.datetime.fromtimestamp(ts):%Y-%m-%d %H:%M})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    os.chdir(ROOT)
    import yaml

    ts, label = cutoff_ts(a.since)
    files = sorted(p for p in glob.glob("data/manga.v2/*.yml") if os.path.getmtime(p) > ts)
    print(f"本番待ち(cutoff={label}): {len(files)} 頁")
    if len(files) > POISON_LIMIT:
        sys.exit(f"★abort: {len(files)}頁 > {POISON_LIMIT}(フルpromote/全消し復旧でmtime汚染の疑い)。"
                 f"実変更の始点日を調べて --since YYYY-MM-DD を指定して再実行。")
    drafts = [os.path.basename(p) for p in glob.glob(".preview-data/manga/*.yml")
              if not os.path.exists(f"data/manga.v2/{os.path.basename(p)}")]
    print(f"preview専用ドラフト温存: {len(drafts)} 頁 {drafts[:6]}")
    if a.dry_run:
        by_day = {}
        for p in files:
            d = datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
            by_day[d] = by_day.get(d, 0) + 1
        for d in sorted(by_day):
            print(f"  {d}: {by_day[d]}")
        return

    for p in files:
        shutil.copy2(p, os.path.join(".preview-data/manga", os.path.basename(p)))
    synced = []
    for f in MASTERS:
        s, d = f"data/{f}", f".preview-data/{f}"
        if os.path.exists(s) and (not os.path.exists(d) or not filecmp.cmp(s, d, shallow=False)):
            shutil.copy2(s, d); synced.append(f)
    print(f"コピー {len(files)} 頁 / masters同期 {synced or 'なし'}")

    r = subprocess.run([sys.executable, "scripts/_build-list-index.py", ".preview-data/manga", ".preview-data"],
                       capture_output=True, text=True, encoding="utf-8")
    print((r.stdout or "").strip().splitlines()[-1] if r.stdout else r.stderr[:200])

    # skip診断(★内部slugで照合=slug-override頁を誤検出しない)
    idx = json.load(open(".preview-data/manga-list-index.json", encoding="utf-8"))
    rows, fields = idx.get("d") or idx, idx.get("f")
    si = fields.index("slug") if fields and "slug" in fields else 0
    inidx = set(r[si] if isinstance(r, list) else r.get("slug") for r in rows)
    pubs = yaml.safe_load(open(".preview-data/publishers.yml", encoding="utf-8"))
    mags = yaml.safe_load(open(".preview-data/magazines.yml", encoding="utf-8"))
    gens = yaml.safe_load(open(".preview-data/genres.yml", encoding="utf-8"))
    for p in glob.glob(".preview-data/manga/*.yml"):
        d = yaml.safe_load(open(p, encoding="utf-8"))
        slug = d.get("slug") or os.path.splitext(os.path.basename(p))[0]
        if slug in inidx:
            continue
        why = ([f"genre未キー:{g}" for g in (d.get("genres") or []) if g not in gens]
               + ([f"publisher未キー:{d.get('publisher')}"] if d.get("publisher") not in pubs else [])
               + ([f"magazine未キー:{d.get('magazine')}"] if d.get("magazine") and d["magazine"] not in mags else []))
        print(f"  索引skip: {slug} ← {why or '要調査(masters外以外の原因)'}"
              + (" [genre:other=既知クラス・本番も同様]" if "genre未キー:other" in why else ""))

    ym = datetime.date.today().strftime("%Y-%m")
    r = subprocess.run([sys.executable, "scripts/_build-calendar.py", ".preview-data/manga", "public/calendar", ym],
                       capture_output=True, text=True, encoding="utf-8")
    print((r.stdout or "").strip().splitlines()[-1] if r.stdout else r.stderr[:200])

    total = len(glob.glob(".preview-data/manga/*.yml"))
    if a.push:
        subprocess.run(["git", "add", ".preview-data", "public/calendar"], cwd=ROOT)
        subprocess.run(["git", "commit", "-m",
                        f"本番待ち{len(files)}頁をテスト環境へ(ドラフト{len(drafts)}温存・計{total}頁・masters{len(synced)}本同期)"],
                       cwd=ROOT)
        subprocess.run(["git", "push"], cwd=ROOT)
        print(f"→ push済。preview反映15-20分・追いpush禁止。計{total}頁。")
    else:
        print(f"→ 投入完了(計{total}頁)。push する場合: git add .preview-data public/calendar && commit && push")


if __name__ == "__main__":
    main()
