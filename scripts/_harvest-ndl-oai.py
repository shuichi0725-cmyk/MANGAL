"""NDL全国書誌データを OAI-PMH でハーベスト → 漫画書誌マップ(ISBN→典拠/主題/巻/版)構築。

★背景([[ndl-clustering-design]]): cm104凍結後の新刊は MADB に容器(シリーズ結線)が無い。
NDL全国書誌(OAI-PMH、 オープンデータ、 2022-10以降の全新着/更新)から、 新刊の
著者典拠ID/主題/巻番号/版 を bulk取得し、 分裂・版違い・巻番号を解く土台にする。
★API乱打(SRU per-ISBN)はレート制限/IP遮断+商用申請要のため不可 → OAI-PMHが正道。

エンドポイント: https://ndlsearch.ndl.go.jp/api/oaipmh
  verb=ListRecords & metadataPrefix=dcndl(_v3) & from/until(YYYY-MM-DDThh:mm:ssZ)
  ★set指定でなく、 各レコードの <setSpec> で iss-ndl-opac(全国書誌) を判別。
  earliestDatestamp=2022-10-01。 ~291件/日。 resumptionToken で継続。

★安全策(NDLへの礼儀 = 遮断回避):
  - 逐次(並列なし)・各リクエスト間に delay
  - 日付chunk(例 7日)で from/until を進める。 resumptionToken をループ
  - 進捗を .cache/ndl-harvest-progress.json に保存(中断耐性)
  - 取得済は .cache/ndl-biblio-map.json に追記

★未確認(初回実行で要検証): dcndl 直列化に著者典拠(auth/entity)が入るか。
  入らなければ metadataPrefix=dcndl_v3 を使う(本scriptは --format で切替可)。
  新着は完成版(~1ヶ月後)で典拠付与の可能性 → 過去寄りの日付から harvest 推奨。

使い方:
  python scripts/_harvest-ndl-oai.py --from 2024-01-01 --until 2024-02-01 [--format dcndl_v3]
  (引数なしなら 2022-10-01 → 今日 を 7日chunkで全ハーベスト=長時間)
"""
import sys
import re
import json
import time
import html
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://ndlsearch.ndl.go.jp/api/oaipmh"
MAP = ROOT / ".cache" / "ndl-biblio-map.json"
PROG = ROOT / ".cache" / "ndl-harvest-progress.json"
DELAY = 1.0          # リクエスト間秒(礼儀)
CHUNK_DAYS = 7
EARLIEST = "2022-10-01"
UA = {"User-Agent": "mangal-bib-harvest/1.0 (open-data, polite)"}


def fetch(params: dict, retries=4):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:        # レート制限 → 指数backoff
                wait = 30 * (i + 1)
                print(f"  429 → {wait}s backoff", file=sys.stderr); time.sleep(wait); continue
            if e.code == 503:
                time.sleep(20); continue
            raise
        except Exception:
            time.sleep(10)
    return ""


def parse_records(xml: str, fmt: str):
    """dcndl レコード群から漫画(NDC726 + setSpec iss-ndl-opac)を抽出。
    戻り: [{isbn, auths, title, volume, edition, seriesTitle}], resumptionToken。"""
    out = []
    for rec in xml.split("<record>")[1:]:
        setspecs = re.findall(r"<setSpec>(.*?)</setSpec>", rec)
        is_natbib = any("iss-ndl-opac" == s for s in setspecs)
        is_manga = ("726" in rec) or ("マンガ" in rec) or ("漫画" in rec)
        if not (is_natbib and is_manga):
            continue
        body = html.unescape(rec)
        isbn = ""
        m = re.search(r"(978[0-9]{10})", re.sub(r"[\-\s]", "", body))
        if m:
            isbn = m.group(1)
        if not isbn:
            continue
        auths = sorted(set(re.findall(r"id\.ndl\.go\.jp/auth/entity/(\d+)", body)))
        tb = re.search(r"<dc:title>(.*?)</dc:title>", body, re.S) or re.search(r"<dcterms:title>(.*?)</dcterms:title>", body, re.S)
        title = ""
        if tb:
            v = re.search(r"<rdf:value>(.*?)</rdf:value>", tb.group(1), re.S)
            title = re.sub(r"<[^>]+>", "", (v.group(1) if v else tb.group(1))).strip()

        def field(tag):
            mm = re.search(rf"<{tag}>(.*?)</{tag}>", body, re.S)
            return re.sub(r"<[^>]+>", "", mm.group(1)).strip() if mm else ""

        out.append({"isbn": isbn, "auths": auths, "title": title,
                    "volume": field("dcndl:volume"), "edition": field("dcndl:edition"),
                    "seriesTitle": field("dcndl:seriesTitle")})
    rt = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", xml)
    return out, (rt.group(1) if rt and rt.group(1).strip() else None)


def daterange_chunks(start: str, end: str, days: int):
    d = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    e = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    while d < e:
        nxt = min(d + timedelta(days=days), e)
        yield (d.strftime("%Y-%m-%dT00:00:00Z"), nxt.strftime("%Y-%m-%dT00:00:00Z"))
        d = nxt


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv
    fmt = "dcndl"
    if "--format" in args:
        fmt = args[args.index("--format") + 1]
    frm = args[args.index("--from") + 1] if "--from" in args else EARLIEST
    until = args[args.index("--until") + 1] if "--until" in args else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    bib = json.load(MAP.open(encoding="utf-8")) if MAP.exists() else {}
    print(f"harvest {frm} → {until} (fmt={fmt}, 既存map {len(bib):,})", file=sys.stderr)
    total_new = 0
    for f, u in daterange_chunks(frm, until, CHUNK_DAYS):
        params = {"verb": "ListRecords", "metadataPrefix": fmt, "from": f, "until": u}
        token = None
        while True:
            if token:
                params = {"verb": "ListRecords", "resumptionToken": token}
            xml = fetch(params)
            time.sleep(DELAY)
            if not xml:
                break
            recs, token = parse_records(xml, fmt)
            for r in recs:
                if r["isbn"] not in bib:
                    total_new += 1
                bib[r["isbn"]] = r
            if not token:
                break
        json.dump(bib, MAP.open("w", encoding="utf-8"), ensure_ascii=False)
        json.dump({"done_until": u, "fmt": fmt}, PROG.open("w", encoding="utf-8"), ensure_ascii=False)
        print(f"  ~{u[:10]}: map {len(bib):,} (+{total_new} new)", file=sys.stderr)
    print(f"完了: 漫画書誌 {len(bib):,}件 → {MAP}")


if __name__ == "__main__":
    main()
