#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""統一ルックアップ (= 楽天/NDL/キャッシュ/本番の一発照会。 external-data-access skill の実体。 2026-07-04)

「どのキャッシュに何が入っているか」を思い出さなくてよい・レート事故を起こさない、が目的。
キャッシュ層(即答) → 本番/種2索引 → --live で楽天→NDL(1.3秒/req・429即中断) の順に引く。

使い方:
  python scripts/_lookup.py --isbn 9784091204417            # 1件(カンマ区切りで複数=delta1パス共有)
  python scripts/_lookup.py --isbn 978409...,978406... --live
  python scripts/_lookup.py --title "うる星やつら" [--max 20] [--live]

出所ラベル付きで出す。liveの叩き方(endpoint/header/レート)はここに封じ込め=他所でコピペ実装しない。
"""
import argparse, json, gzip, os, re, sys, time, html, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rate_gate  # ★プロセス間グローバル・レートゲート(複数柱並走時の合算429を防ぐ)
C = lambda *p: os.path.join(ROOT, ".cache", *p)
RATE = 1.3  # NDL/楽天 live 共通(秒/req)。★これ未満に縮めない(429/IP遮断の実績)
# ★叩く直前に _rate_gate.wait(host, RATE) を通す=柱が何本並走しても host単位で1本の1.3sストリームに直列化。


def _env():
    env = {}
    p = os.path.join(ROOT, ".env.local")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def norm_isbn(s):
    return re.sub(r"[^0-9X]", "", str(s or ""))


# ---------- キャッシュ層 ----------

def cache_title_map(isbns):
    p = C("isbn-title-map.json")
    if not os.path.exists(p):
        return {}
    tm = json.load(open(p, encoding="utf-8"))
    return {i: tm[i] for i in isbns if i in tm}


def cache_delta_scan(isbns):
    """rakuten-isbn-delta.jsonl(~830MB) 1パスで複数ISBNのfull itemを回収(1-3分)。"""
    p = C("rakuten-isbn-delta.jsonl")
    if not os.path.exists(p):
        return {}
    want = set(isbns)
    out = {}
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if not want:
                break
            if not any(w in ln for w in want):
                continue
            d = json.loads(ln)
            ib = norm_isbn(d.get("isbn"))
            if ib in want and ib not in out:
                out[ib] = d.get("item") or {}
                want.discard(ib)
    return out


def cache_covers(isbns):
    p = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
    if not os.path.exists(p):
        return {}
    want = set(isbns)
    out = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            if d.get("isbn13") in want:
                out[d["isbn13"]] = d.get("cover_url")
    return out


def cache_page_index(isbns):
    p = C("isbn-page-index.json")
    if not os.path.exists(p):
        return {}
    ii = json.load(open(p, encoding="utf-8"))
    return {i: ii[i] for i in isbns if i in ii}


def title_map_search(q, mx):
    p = C("isbn-title-map.json")
    if not os.path.exists(p):
        return []
    tm = json.load(open(p, encoding="utf-8"))
    ql = q.lower()
    return sorted((ib, t) for ib, t in tm.items() if ql in t.lower())[:mx]


# ---------- live層 (★叩き方の正はここ。 コピペ再実装しない) ----------

class Throttled(Exception):
    """楽天429(= 一時スロットル)。 長時間ジョブが自前でbackoff再試行するための signal。"""


def rakuten_live(env, *, isbn=None, title=None, hits=30, exit_on_429=True):
    """楽天Books live。 ★endpoint=openapi.rakuten.co.jp + Referer/Origin header 必須
    (app.rakuten.co.jp 直や header 無しは 400)。 ★outOfStockFlag=1 必須(絶版/品切れが既定で消える)。

    ★exit_on_429: 既定True = 対話照会の安全設計(429で即プロセス終了・連打しない)。
      **長時間の一括ハーベストはFalseにして `Throttled` を捕まえ、backoff再試行すること**
      (2026-07-25: 取りこぼし柱が429の即exitで73分で停止した。既存の3日運転柱は再試行を持っていた)。"""
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "outOfStockFlag": "1",
         "hits": str(hits), "format": "json", "formatVersion": "2"}
    if isbn:
        p["isbn"] = isbn
    if title:
        p["title"] = title
    origin = env.get("RAKUTEN_REFERER", "").rstrip("/")
    req = urllib.request.Request(
        "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", origin + "/")
    req.add_header("Origin", origin)
    req.add_header("User-Agent", "Mozilla/5.0")
    _rate_gate.wait("rakuten", RATE)  # ★グローバル間隔(全楽天呼出で共有=並走合算429を防ぐ)
    try:
        r = urllib.request.urlopen(req, timeout=25)
        return json.loads(r.read()).get("Items") or []
    except urllib.error.HTTPError as e:
        if e.code == 429:
            if exit_on_429:
                print("★楽天429 → 即中断。しばらく(数分)休ませる"); sys.exit(2)
            raise Throttled("rakuten 429")
        raise


def rakuten_live_retry(env, *, backoff=(2, 5, 15, 45), **kw):
    """★長時間ハーベスト用: 429/瞬断を backoff 再試行で吸収する楽天呼出。

    2026-07-25 の型: 対話用 `rakuten_live` は 429 で即 sys.exit する安全設計だが、
    それを数千件のループで使うと **1回の一時スロットルで柱ごと止まる**
    (取りこぼし柱が73分で停止)。 3日運転できていた既存柱(_rakuten-fill-covers)は
    再試行を持っていた = 差はレートでなく再試行の有無。 長時間ジョブはこちらを使う。

    戻り: Items list。 全試行が失敗したら **最後の例外を送出**(呼び側で1件skip等を決める)。
    """
    last = None
    for i, wait_s in enumerate(backoff):
        try:
            return rakuten_live(env, exit_on_429=False, **kw)
        except Exception as e:              # Throttled / HTTPError / URLError / timeout
            last = e
            if i < len(backoff) - 1:
                time.sleep(wait_s)
    raise last


def ndl_live(query, maximum=30, start=1, exit_on_429=True):
    """NDL SRU live。 ★1.3秒/req厳守・429=即中断。 ★一般語のtitle単独クエリはtimeoutする
    → creator束縛を優先し、timeoutは握りつぶして続行してよい。 ★NDL不在≠不存在(BL/小出版は収録弱)。
    ★start=startRecord(2026-07-18追加): 大物(数百版)は 1,201,401… とページングして全取得する
    (skill external-data-access「1頁だけ取る実装は禁止」)。短い頁(件数<maximum)が終端。"""
    p = {"operation": "searchRetrieve", "query": query, "recordSchema": "dcndl",
         "maximumRecords": str(maximum), "startRecord": str(start)}
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(p))
    req.add_header("User-Agent", "Mozilla/5.0")
    _rate_gate.wait("ndl", RATE)  # ★グローバル間隔(全NDL呼出で共有)
    try:
        xml = html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except Exception as e:
        print(f"  NDL query失敗(続行可): {e}")
        return []
    if "Too Many Requests" in xml:
        if exit_on_429:
            print("★NDL429 → 即中断。回復するので慌てず休ませる(1時間単位)"); sys.exit(2)
        raise Throttled("ndl 429")
    out = []
    # ★recordData単位で分割(BibResource分割より確実=ひおあきらヤマト検証 2026-07-08)
    recs = re.findall(r"<recordData>(.*?)</recordData>", xml, re.S) or re.split(r"<dcndl:BibResource", xml)[1:]
    for r in recs:
        g = lambda pat: (re.search(pat, r, re.S) or [None, ""])[1] if re.search(pat, r, re.S) else ""
        # ISBN10/13両対応(古典はISBN10)。creator複数(アンソロ/原作+作画)
        _isbn = g(r'ISBN">([0-9\-]+)') or g(r"(97[89][\d\-]{10,16})")
        creators = re.findall(r"<dcterms:creator>.*?<foaf:name>([^<]+)", r, re.S) or re.findall(r"<dc:creator>([^<]+)", r)
        # ★著者ヨミ = 典拠紐付きレコードの dcndl:transcription。 「サイトウ, ジュンイチロウ」と
        #   **姓と名がカンマで分かれる** = slug衝突時の「-姓+年」suffix の姓が取れる(2026-07-25追加)。
        creators_kana = re.findall(r"<dcterms:creator>.*?<dcndl:transcription>([^<]+)", r, re.S)
        # ★題ヨミ = dc:title 内の dcndl:transcription(分かち書き)。 NDLヨミは ground truth
        #   ([[furigana_ndl_audit]])。 slug生成/索引ガードの土台になるので必ず拾う(2026-07-25追加)。
        _tk = re.search(r"<dc:title>.*?<dcndl:transcription>([^<]+)", r, re.S)
        _sk = re.search(r"<dcndl:seriesTitle>.*?<dcndl:transcription>([^<]+)", r, re.S)
        out.append({
            "title_kana": (_tk.group(1).strip() if _tk else ""),
            "series_kana": (_sk.group(1).strip() if _sk else ""),
            "title": g(r"<dcterms:title>([^<]+)"),
            "vol": g(r"<dcndl:volume>.*?<rdf:value>([^<]+)"),
            "date": g(r"<dcterms:date>([^<]+)"),
            "isbn": norm_isbn(_isbn),
            "pub": g(r"<dcterms:publisher>.*?<foaf:name>([^<]+)") or g(r"<foaf:name>([^<]+)"),
            "series": g(r"<dcndl:seriesTitle>.*?<rdf:value>([^<]+)"),
            "creators": [c.replace("/", "") for c in creators],
            "creators_kana": [c.strip() for c in creators_kana],
        })
    return out


def ndl_live_retry(query, *, backoff=(3, 10, 30, 90), **kw):
    """★長時間ジョブ用: NDLの429/瞬断を backoff 再試行で吸収する(対話用 ndl_live は429で即exit)。
    2026-07-25: 楽天で同じ型の事故(429即exitで柱が73分で停止)を踏んだのでNDL側にも用意。
    NDLの回復は楽天より遅い(時間単位)ので待ちを長めに取る。"""
    last = None
    for i, wait_s in enumerate(backoff):
        try:
            return ndl_live(query, exit_on_429=False, **kw)
        except Exception as e:
            last = e
            if i < len(backoff) - 1:
                time.sleep(wait_s)
    raise last


# ---------- main ----------

def fmt_item(it):
    img = str(it.get("largeImageUrl") or it.get("mediumImageUrl") or "")
    cover = "書影有" if img and "noimage" not in img else "書影無"
    return (f"「{it.get('title', '')}」 {it.get('author', '')} / {it.get('publisherName', '')} / "
            f"{it.get('salesDate', '')} / {it.get('itemPrice', '')}円 / {cover} / series={it.get('seriesName', '')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--isbn")
    ap.add_argument("--title")
    ap.add_argument("--creator", help="作者名でNDL SRUを束縛検索(古典/多同名作の全巻回収。--titleと併用可)")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max", type=int, default=20)
    a = ap.parse_args()
    env = _env()

    if a.isbn:
        isbns = [norm_isbn(x) for x in a.isbn.split(",") if norm_isbn(x)]
        tm = cache_title_map(isbns)
        pg = cache_page_index(isbns)
        cv = cache_covers(isbns)
        need_delta = [i for i in isbns]
        print("== キャッシュ(即答層) ==")
        for i in isbns:
            print(f" {i}")
            print(f"   題(title-map): {tm.get(i, '─ 無し')}")
            print(f"   本番頁(page-index): {pg.get(i, '─ 未描画')}")
            print(f"   書影seed(covers): {'有' if i in cv else '─ 無し'}")
        print("== 楽天delta(full item・1パス走査中…) ==")
        dl = cache_delta_scan(need_delta)
        for i in isbns:
            print(f" {i}: {fmt_item(dl[i]) if i in dl else '─ delta無し'}")
        if a.live:
            print("== live(1.3s/req) ==")
            for i in isbns:
                if i in dl:
                    continue  # deltaにあればliveは省略(レート節約)
                items = rakuten_live(env, isbn=i)
                print(f" 楽天 {i}: {fmt_item(items[0]) if items else '─ ヒットなし'}")
                nd = ndl_live(f"isbn={i}", 3)
                nd = [x for x in nd if x.get("title")]
                print(f" NDL  {i}: " + (f"「{nd[0]['title']}」vol={nd[0]['vol']} {nd[0]['date']}" if nd else "─ 無し(※不在≠不存在)"))
        return

    # ★作者束縛NDL検索(ユーザ手作業のTSVエクスポート代替=作品名+作者名。古典/同名多発作の全巻回収)
    if a.creator:
        cql = f'creator="{a.creator}"' + (f' AND title="{a.title}"' if a.title else "")
        print(f"== NDL SRU 作者束縛検索: {cql} ==")
        recs = ndl_live(cql, maximum=a.max)
        # 版(seriesTitle)ごとに巻を束ねて表示(=版分離の下ごしらえ)
        from collections import defaultdict
        by_series = defaultdict(list)
        for r in recs:
            by_series[r["series"] or "(シリーズ記載なし)"].append(r)
        for ser, lst in by_series.items():
            print(f"\n【{ser}】")
            for r in sorted(lst, key=lambda x: (x["vol"] or "", x["date"] or "")):
                print(f"  巻={r['vol'] or '-':4} ISBN={r['isbn'] or '無':13} {r['date'] or '?':10} {r['pub'] or '?'} | {r['title']} | 著者={r['creators']}")
        print(f"\n計 {len(recs)}件 / {len(by_series)}版")
        return

    if a.title:
        print(f"== キャッシュ題検索(部分一致) ==")
        hits = title_map_search(a.title, a.max)
        for ib, t in hits:
            print(f" {ib} {t[:50]}")
        print(f" {len(hits)}件")
        print("== 本番存在(_exists相当は scripts/_exists.py --title を使う) ==")
        if a.live:
            print("== 楽天live title検索 ==")
            for it in rakuten_live(env, title=a.title, hits=min(30, a.max))[:a.max]:
                print(" ", fmt_item(it))
            print("== NDL作者束縛検索は --creator を使う(--titleだけではNDLを叩かない) ==")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
