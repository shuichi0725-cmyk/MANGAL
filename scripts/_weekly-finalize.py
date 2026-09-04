#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週次蒸留 finalize (2026-07-10 弱モデル耐性): R2同期後の締めを1本化+ゲート連鎖。

  python scripts/_weekly-finalize.py            # 完了判定→疎通→marker→manifest
  python scripts/_weekly-finalize.py --no-post  # 疎通のcontact POSTをskip

ゲート連鎖(前段greenでないと次に進まない=「できたつもり」防止):
  1. ビルド完了判定: weekly-build.log に「✓ Exporting」+ out/manga ファイル数 ≥ 120,000(≈頁数×2)
  2. sitemap: out/sitemap.xml 存在(手順3.5忘れ検出=WARN)
  3. 疎通確認: _prod-smoke.py 全PASS(FAILなら marker を書かずabort)
  4. marker更新: .cache/prod-deploy-marker.json(diff-deployの基準点)
  5. pages-manifest初期化: _init-pages-manifest.py
markerは1-3が全部通った時だけ書く。途中失敗=markerは前回のまま(diff-deployが安全側に倒れる)。
"""
import json, os, sys, subprocess

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, ".cache", "weekly-build.log")
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
MIN_PAGES = 120_000


def die(msg):
    print(f"★abort: {msg}(markerは書かない=diff-deployは前回基準のまま安全側)")
    sys.exit(1)


def main():
    os.chdir(ROOT)
    # ★--data-week (2026-08-27 ハイブリッド週次): フルビルド無し週(diff-deployルート)の締め。
    #   out/は先週のまま=ビルド系検査(1/1.5/2)とmarker/manifest(diff-deployが更新済)はskipし、
    #   ③疎通 → ③.5 prune実証+台帳消し込み → ⑥snapshot だけを回す。
    data_week = "--data-week" in sys.argv
    if data_week:
        print("(--data-week: ビルド検査/marker/pages-manifestはskip=diff-deployが担当済)")
    # 1. ビルド完了判定 (★data_week=skip: フルビルド無し週はout/が先週のまま=検査対象外)
    if not data_week:
        if not os.path.exists(LOG):
            die(f"{os.path.relpath(LOG, ROOT)} が無い(ビルドを回していない?)")
        # ★PowerShell の Out-File は既定で **UTF-16LE(BOM付き)** を書く(PS 5.1)。
        #   utf-8固定で読むと本文が「?」だらけになり「✓ Exporting」が見つからず、
        #   ★**ビルドは成功しているのに finalize が abort する**(2026-07-27 実害)。
        #   BOM を見て復号を切り替える(utf-16 → utf-8-sig → utf-8 の順)。
        _raw = open(LOG, "rb").read()
        for _enc in ("utf-16", "utf-8-sig", "utf-8"):
            if _enc == "utf-16" and not _raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                continue
            try:
                log = _raw.decode(_enc, errors="replace")
                break
            except Exception:
                continue
        else:
            log = _raw.decode("utf-8", errors="replace")
        if "Export encountered" in log or "Build error" in log:
            die("build logにエラー(Export encountered/Build error)。ログを調査")
        if "Exporting" not in log:
            die("build logに『✓ Exporting』が無い=ビルド未完了")
        out_manga = os.path.join(ROOT, "out", "manga")
        if not os.path.isdir(out_manga):
            die("out/manga が無い")
        n = sum(1 for _ in os.scandir(out_manga))
        if n < MIN_PAGES:
            die(f"out/manga = {n:,} < {MIN_PAGES:,}(欠損ビルド疑い。頁数×2≈132kが正常)")
        print(f"  OK   ビルド完了(out/manga {n:,} files・log正常)")
        # ★題名索引ハブ(2026-08-31 実踏): staging に titles-pages.json が未同期だと
        #   /titles が _empty のみ(2 files)の空ビルドになり sitemap が404を351件撒く。恒久番人。
        out_titles = os.path.join(ROOT, "out", "titles")
        tn = sum(1 for _ in os.scandir(out_titles)) if os.path.isdir(out_titles) else 0
        if tn < 100:
            die(f"out/titles = {tn} files(空ビルド疑い=titles-pages.json の staging 同期を確認。"
                "復旧= FEATURE_BUILD部分ビルド合流 [[partial_rebuild_merge_recovery]])")
        print(f"  OK   題名索引ハブ(out/titles {tn} files)")

        # 1.5 ★索引⊆生成頁の実測照合(2026-07-29 ユーザ発見「作品数がズレてる」の恒久ゲート):
        #   一覧索引に載るslugのHTMLが out/manga に無い=「検索に出るのに404」。過去3回再発した型
        #   ([[search_404_build_skip_validation]])なので、件数でなく集合差そのものをFAIL条件にする。
        _idx_p = os.path.join(ROOT, "data", "manga-list-index.json")
        _idx = json.load(open(_idx_p, encoding="utf-8"))
        _si = _idx["f"].index("slug")
        _out_slugs = {f[:-5] for f in os.listdir(out_manga) if f.endswith(".html")}
        _missing = sorted({str(r[_si]) for r in _idx["d"]} - _out_slugs)
        if _missing:
            die(f"索引に居るのに未生成 {len(_missing)}頁(=検索に出るのに404): {_missing[:8]}"
                f"{' …' if len(_missing) > 8 else ''}(ビルドskipと索引ガードの不整合。両方を揃えてから再実行)")
        print(f"  OK   索引⊆生成頁(索引 {len(_idx['d']):,} 行すべてHTMLあり)")

        # 2. sitemap
        if os.path.exists(os.path.join(ROOT, "out", "sitemap.xml")):
            print("  OK   sitemap.xml あり")
        else:
            print("  WARN sitemap.xml が無い(手順3.5 _gen-sitemap.py を忘れていないか)")

    # 3. 疎通(全PASSでないと先に進まない)
    args = [sys.executable, os.path.join(ROOT, "scripts", "_prod-smoke.py")]
    if "--no-post" in sys.argv:
        args.append("--no-post")
    r = subprocess.run(args)
    if r.returncode != 0:
        die("疎通確認にFAILあり")

    # 3.5 ★prune実証+台帳消し込み (2026-08-26 新設。旧=目視突合+手編集で、prune忘れ/消し込み忘れ
    #     がWARN止まりだった): pending-r2-prune.jsonl の各slugを本番に実プローブし、
    #     404/301=消えた→行を自動消し込み / 200=まだ生きている→prune未実施として abort。
    import urllib.request, urllib.error

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    _opener = urllib.request.build_opener(_NoRedirect)
    _pp = os.path.join(ROOT, "data", "seeds", "pending-r2-prune.jsonl")
    if os.path.exists(_pp):
        _lines = open(_pp, encoding="utf-8").read().splitlines()
        _rows = [(i, json.loads(l)) for i, l in enumerate(_lines)
                 if l.strip() and not l.lstrip().startswith("#")]
        _gone_idx, _alive = [], []
        for _i, _d in _rows:
            _slug = _d.get("slug")
            if not _slug:
                continue
            try:
                _rq = urllib.request.Request(f"https://mangal-db.com/manga/{_slug}",
                                             headers={"User-Agent": "Mozilla/5.0 (mangal-finalize)"})
                _st = _opener.open(_rq, timeout=30).status
            except urllib.error.HTTPError as _e:
                _st = _e.code
            except Exception:
                _st = None
            if _st == 200:
                _alive.append(_slug)
            elif _st in (301, 302, 404, 410):
                _gone_idx.append(_i)
        if _alive:
            die(f"prune待ち {len(_alive)} 頁がまだ本番200: {_alive[:5]} "
                f"(r2-sync に --prune を付けたか/中止されていないか確認して再実行)")
        if _gone_idx:
            _keep = [l for i, l in enumerate(_lines) if i not in set(_gone_idx)]
            open(_pp, "w", encoding="utf-8", newline="\n").write("\n".join(_keep) + ("\n" if _keep else ""))
            print(f"  OK   prune実証: {len(_gone_idx)} 頁が本番から消滅 → 台帳から自動消し込み"
                  f"(残 {len(_rows) - len(_gone_idx)})")
        else:
            print("  OK   prune待ち台帳: 消化対象なし")

    # 3.7 ★edge cache purge (2026-08-26 機械化。旧=worker /api/purge を手で叩く前提で
    #     「忘れると最長1週間前のまま配信」): 索引4本+data/*.json+calendar/*.json を購読purge。
    _env = {}
    for _name in (".env.local", ".env"):
        _p = os.path.join(ROOT, _name)
        if os.path.exists(_p):
            for _ln in open(_p, encoding="utf-8"):
                if "=" in _ln and not _ln.startswith("#"):
                    _k, _v = _ln.split("=", 1)
                    _env[_k.strip()] = _v.strip().strip('"').strip("'")
    _token = _env.get("R2_PURGE_TOKEN", "")
    if _token:
        _paths = ["/", "/manga-list-index.json", "/manga-list-head.json",
                  "/manga-alt-index.json", "/manga-catch-index.json"]
        # ★"/"=トップHTML(2026-08-27追記: コーナー変更週にホームだけ最長1日古いまま=ユーザ発見)
        for _sub in ("data", "calendar", "shinkan"):
            _dirp = os.path.join(ROOT, "out", _sub)
            if os.path.isdir(_dirp):
                _paths += [f"/{_sub}/{f}" for f in os.listdir(_dirp) if f.endswith(".json")]
        # ★sitemap(2026-08-31): 毎週変わるのに purge 漏れで最長1日旧配信だった(手動purgeで是正した週の恒久化)
        _paths += [f"/{f}" for f in os.listdir(os.path.join(ROOT, "out"))
                   if f.startswith("sitemap") and f.endswith(".xml")]
        import time as _t
        _purged, _pfail = 0, 0
        for _i in range(0, len(_paths), 10):
            try:
                _rq = urllib.request.Request("https://mangal-db.com/api/purge", method="POST",
                                             data=json.dumps({"paths": _paths[_i:_i + 10],
                                                              "token": _token}).encode(),
                                             headers={"content-type": "application/json",
                                                      "User-Agent": "Mozilla/5.0"})
                _purged += json.load(urllib.request.urlopen(_rq, timeout=60)).get("purged", 0)
            except Exception:
                _pfail += 1
            _t.sleep(0.3)
        print(f"  OK   edge purge: {len(_paths)}パス / purged {_purged} / 失敗batch {_pfail}"
              + ("(失敗分は≤1日で自然失効)" if _pfail else ""))
    else:
        print("  WARN R2_PURGE_TOKEN 未設定 → purge省略(索引/カレンダーの旧キャッシュが最長1日残る)")

    # 4. marker (★data_week=skip: diff-deployが data_commit を更新済・code_commit は前回フル基準のまま)
    if not data_week:
        h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if not h:
            die("git rev-parse HEAD 失敗")
        json.dump({"code_commit": h, "data_commit": h, "note": "週次蒸留"}, open(MARKER, "w"), indent=1)
        print(f"  OK   marker更新: {h[:12]}")

        # 5. pages-manifest
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_init-pages-manifest.py")])
        if r.returncode != 0:
            die("_init-pages-manifest.py 失敗(markerは書いたがmanifest欠け=diff-deployが過剰検出する。再実行を)")
        print("  OK   pages-manifest初期化")

    # 6. ★ISBN消失snapshot取り直し (2026-08-26 機械化。旧=skill散文で忘れると次週の監視が
    #     先週消えた分を延々と報告し続ける): smoke全PASS後=本番確定後にここで基準を取る。
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_audit-isbn-loss.py"), "--snapshot"])
    if r.returncode != 0:
        print("  WARN isbn-loss --snapshot 失敗(次週の監視基準が古いまま。手動で再実行を)")
    else:
        print("  OK   ISBN消失snapshot更新(次週の監視基準)")
    # 7. ★IndexNow drain (2026-09-04): r2-sync / diff-deploy が積んだ変更・削除URLを、edge purge 後の
    #    ここで送る(Bing/Yandex 系の即時クロール)。 --no-indexnow で抑止。 失敗は WARN 止まり。
    if "--no-indexnow" not in sys.argv:
        try:
            import _indexnow
            print("  " + _indexnow.drain().replace("\n", "\n  "))
        except Exception as _e:
            print(f"  WARN IndexNow 送信 skip({_e}) → 手動: python scripts/_indexnow.py --drain")
    print("\n→ 週次蒸留finalize完了(marker+manifest+snapshot確定。以後の差分反映はこの時点が基準)")


if __name__ == "__main__":
    main()
