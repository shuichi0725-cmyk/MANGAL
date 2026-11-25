#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kindle版ASIN 収穫(Creators API・作者名で一括)。2026-11-21 試行版。

流れ: 作者名で KindleStore を searchItems(1回10件・1検索最大100件=itemPage<=10)
      → 自サイトのその作者の頁の巻(isbn13あり)と 題+巻番号+発売日 で照合 → 候補を書く。
      ★seed(data/seeds/kindle-asin.jsonl)へは書かない(apply は別・ユーザGO後)。

使い方:
  python scripts/_kindle-asin-harvest.py trial [--n 10] [--seed 1121]   # 作者を50音・年代で散らして選び試行
  python scripts/_kindle-asin-harvest.py author "<作者名>"              # 1人だけ
  python scripts/_kindle-asin-harvest.py harvest [--max-pages N]        # ★本番収穫(全頁・続きから・予算/429で自然停止)
  python scripts/_kindle-asin-harvest.py status                         # 進み具合
出力: .cache/kindle-asin/<run>/ items.jsonl(取れたKindle版) / match.tsv(照合) / report.txt
鍵: .env の AMAZON_CREATORS_CLIENT_ID / AMAZON_CREATORS_SECRET。 ★12秒/回・24時間の回数上限なし(既定 KINDLE_ASIN_BUDGET=0)・200以外1回で即停止(2026-11-25 ユーザ指定を既定に)。 台帳 .cache/kindle-asin/calls.log
"""
import os, re, sys, json, time, random, argparse, unicodedata, datetime, urllib.request, urllib.error
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "kindle-asin")
os.makedirs(CACHE, exist_ok=True)
CALLS = Counter()


# ---------------- API ----------------
def _env():
    kv = {}
    for ln in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        if "=" in ln:
            k, v = ln.strip().split("=", 1)
            kv[k] = v.strip().strip('"').strip("'")
    return kv


def _post(url, body, h, with_headers=False):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **h})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = (r.status, r.read().decode("utf-8", "replace"), dict(r.headers))
    except urllib.error.HTTPError as e:
        out = (e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {}))
    return out if with_headers else out[:2]


_TOK = os.path.join(CACHE, "token.json")


def _token():
    try:
        d = json.load(open(_TOK))
        if d["exp"] > time.time() + 60:
            return d["t"]
    except Exception:
        pass
    kv = _env()
    st, t = _post("https://api.amazon.co.jp/auth/o2/token",
                  {"grant_type": "client_credentials", "client_id": kv["AMAZON_CREATORS_CLIENT_ID"],
                   "client_secret": kv["AMAZON_CREATORS_SECRET"], "scope": "creatorsapi::default"}, {})
    if st != 200:
        raise SystemExit(f"token HTTP {st}: {t[:200]}")
    d = json.loads(t)
    json.dump({"t": d["access_token"], "exp": time.time() + int(d.get("expires_in", 3600))}, open(_TOK, "w"))
    return d["access_token"]


_last = [0.0]
# ★2026-11-21 ユーザ「一番まずいのはやりすぎて使えなくなること」= 安全側に倒す3点:
#   ①間隔 2.0秒(公表上限 1TPS の半分) ②回数の台帳(直近24時間・プロセスをまたいで数える)で 1日の予算を超えたら止める
#     (2026-11-21 ユーザ裁定 8,000回=公表の初期上限 8,640/日の手前。 30日目以降は売上連動で下がり得る→429即停止で守る)
#   ③429 が1回でも出たら取り直さずに即停止(その日は終わり)・非200が5回続いたら停止。
# ★2026-11-21 実測で確定した枠の形(ユーザ指摘「8640/日=10秒に1回を24時間」):
#   枠は「10秒に1単位ずつ戻る」桶で、 getItems は**冊数ぶん**数える(10冊まとめ=10単位)。
#   15:40(冊数換算 約7,200で429)→ 18:18 再開 → 18:39 に約970単位で再び429 = 休んだ約3時間で戻った約1,070単位とほぼ一致。
#   → 叩く間隔を「単位×11秒」(戻りより少し遅く)にすれば、 1日中流しても桶は減らない。
# ★2026-11-23 見直し(ユーザ相談「止まる法則が謎」): 公式 api-rates = 「1回の呼び出し=1 transaction」(getItems は10冊でも1回)・
#   TPD は最初の30日 8,640、以後は直近30日の売上で毎日更新。 台帳9,700回の照合で 429 時点の「直近24時間の呼出数」が
#   11/22 約6,400 → 11/23 2,839〜2,893 に揃って下がっていた = 直近24時間の回数で切る TPD(売上連動で縮小中)。
#   上の「10秒に1単位戻る桶/getItemsは冊数」は誤り(休むと24時間前の分が抜けて空くだけ)。
#   → 間隔は呼び出し1回につき PACE 秒(ユーザ裁定 15秒で試す)+ 直近24時間の呼出数が予算に達したら 429 を待たずに休む。
PACE_PER_UNIT = float(os.environ.get("KINDLE_ASIN_PACE", "12"))  # ★2026-11-25 ユーザ指定 12秒(既定に焼いた)
PACE = PACE_PER_UNIT
# ★2026-11-21 ユーザ裁定 A: 24時間の予算チェックは既定で外す(0=無効)。 守りは「単位×11秒の間隔(=戻る速さより遅い)」+「429で即停止」。
#   使いたい時は KINDLE_ASIN_BUDGET=<単位> で有効化(単位=getItemsは冊数)。
DAILY_BUDGET = int(os.environ.get("KINDLE_ASIN_BUDGET", "0"))  # ★2026-11-25 ユーザ「総計をみて開始しないので修正して」= 既定は上限なし(0=無効)。
#   旧既定2700のまま起動すると直近24時間の総数だけ見て何時間も休み、始まらなかった。守りは間隔+200以外1回で即停止
_429LOG = os.path.join(CACHE, "throttle-429.jsonl")  # 429/403 の見出し・本文・その時の直近24時間回数(上限の推移を追う)
_LEDGER = os.path.join(CACHE, "calls.log")  # 1行1呼び出し: epoch秒 op status
_bad = [0]
_next_ok = [0.0]  # 次に叩いてよい時刻(前回の単位数 × PACE_PER_UNIT 後)
# ★2026-11-22 ユーザ裁定: 「429 が出るまで1秒間隔、出たら 10.2秒間隔で電子・紙問わず回す」。
#   FAST=1 の間は種別・冊数に関係なく1秒。 429 が出たら FAST=0 にして 10.2秒/回(冊数で掛けない)へ落とし、
#   その1件は少し待って取り直す。 落とした後にもう一度 429 が出たら、 従来どおり即停止。
MODE = {"fast": os.environ.get("KINDLE_ASIN_FAST", "0") == "1", "slow_pace": 10.2, "fast_pace": 1.0}


def _units(op, body):
    return 1  # 公式: getItems は10冊まとめても1 transaction


def _used_24h():
    now = time.time()
    try:
        tot = 0
        for ln in open(_LEDGER, encoding="utf-8"):
            p_ = ln.split()
            if len(p_) > 1 and p_[1] != "wait" and now - float(p_[0]) < 86400:
                tot += 1  # 呼び出し回数で数える(公式どおり。 旧4列目の冊数は使わない)
        return tot
    except FileNotFoundError:
        return 0


def _wait_budget():
    """直近24時間の呼出数が予算に達していたら、24時間前の分が抜けて空くまで休む(429を待たない)。 STOP札は休み中も見る。"""
    announced = False
    while True:
        now = time.time()
        ts = []
        try:
            for ln in open(_LEDGER, encoding="utf-8"):
                p_ = ln.split()
                if len(p_) > 1 and p_[1] != "wait" and now - float(p_[0]) < 86400:
                    ts.append(float(p_[0]))
        except FileNotFoundError:
            return
        if len(ts) < DAILY_BUDGET:
            return
        ts.sort()
        until = ts[len(ts) - DAILY_BUDGET] + 86400 + 5
        if not announced:
            print(f"[{time.strftime('%H:%M')}] 直近24時間 {len(ts)} 回 = 予算 {DAILY_BUDGET} → "
                  f"{time.strftime('%H:%M', time.localtime(until))} まで休む(429を待たない)", flush=True)
            announced = True
        if os.path.exists(os.path.join(CACHE, "harvest", "STOP")):
            raise SystemExit("休み中に STOP 札を見て停止")
        with open(_LEDGER, "a", encoding="utf-8") as f:  # 二重起動ガード用の生存印(回数には数えない)
            f.write(f"{now:.0f} wait 0 0\n")
        time.sleep(min(60, max(1, until - now)))


def call(op, body):
    if DAILY_BUDGET:
        _wait_budget()
    w = _next_ok[0] - time.time()
    if w > 0:
        time.sleep(w)
    u = _units(op, body)
    body = {"marketplace": "www.amazon.co.jp", "partnerTag": "mangal08-22", **body}
    _last[0] = time.time()
    hd = {}
    try:
        st, t, hd = _post(f"https://creatorsapi.amazon/catalog/v1/{op}", body,
                          {"Authorization": "Bearer " + _token(), "x-marketplace": "www.amazon.co.jp"}, with_headers=True)
    except Exception as e:  # 通信エラーも1回と数える
        st, t = 0, f"{type(e).__name__}: {getattr(e, 'reason', e)}"  # ★11/26: 理由も残す(旧=型名だけで原因が追えなかった)
    CALLS[op] += 1
    CALLS["units"] += u
    # ★2026-11-22 確定: 10.2秒/回(冊数で掛けない)で54分・126回目に429 = 冊数換算369単位 > 戻り約320単位。
    #   = getItems は冊数で数えられる。 既定(FAST=0)は「単位×11秒」(11/21夜〜16時間429なしの実績)に戻す。
    # ★2026-11-22 ユーザ裁定: 検索=10.2秒・紙照会(10冊)=101秒(=冊数×10.1秒)。
    _next_ok[0] = time.time() + (MODE["fast_pace"] if MODE["fast"] else u * PACE_PER_UNIT)  # ★11/22 16:26 10.2/101秒は3時間で429 → 実績のある 11秒/単位に戻す
    with open(_LEDGER, "a", encoding="utf-8") as f:
        f.write(f"{time.time():.0f} {op} {st} {u}\n")
    if st in (429, 403):
        with open(_429LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "status": st, "op": op,
                                "used_24h": _used_24h(), "pace": PACE_PER_UNIT, "headers": hd, "body": t[:2000]},
                               ensure_ascii=False) + "\n")
        ra = hd.get("Retry-After") or hd.get("retry-after")
        if ra:
            print(f"[{time.strftime('%H:%M:%S')}] 429 Retry-After={ra}", flush=True)
    if st == 429:
        if MODE["fast"] and os.environ.get("KINDLE_ASIN_STOP_ON_429") == "1":
            raise SystemExit(f"429(1秒間隔で枠切れ)= 即停止(KINDLE_ASIN_STOP_ON_429)。 本文: {t[:200]}")
        if MODE["fast"]:
            MODE["fast"] = False
            print(f"[{time.strftime('%H:%M:%S')}] 429 → 1秒間隔をやめて {MODE['slow_pace']}秒間隔へ(この1件は60秒待って取り直す)", flush=True)
            time.sleep(60)
            _next_ok[0] = 0.0
            return call(op, {k: v for k, v in body.items() if k not in ("marketplace", "partnerTag")})
        raise SystemExit(f"429 = 取り直さずに即停止(直近24時間 {_used_24h()} 回・記録 {_429LOG})。 本文: {t[:200]}")
    if st == 403:
        raise SystemExit(("403 AssociateNotEligible = 直近30日の売上条件(適格売上10件)を外れた=資格切れ。売上が戻れば数日で自動復旧"
                          if "AssociateNotEligible" in t else f"403 = 停止して調べる。 本文: {t[:200]}"))
    _bad[0] = 0 if st == 200 else _bad[0] + 1
    # ★2026-11-25 ユーザ裁定「エラー出たらすぐ止める」: KINDLE_ASIN_STOP_ON_ANY_ERROR=1 なら 200 以外(通信エラー含む)1回で停止
    if _bad[0] >= (1 if os.environ.get("KINDLE_ASIN_STOP_ON_ANY_ERROR", "1") == "1" else 5):  # ★既定=1(2026-11-25 焼いた)
        raise SystemExit(f"200 以外で停止(連続{_bad[0]}回・最後 HTTP {st}{'=通信エラー' if st == 0 else ''})= 停止して調べる。 {t[:200]}")
    try:
        return st, json.loads(t)
    except Exception:
        return st, {"raw": t[:300]}


RES = ["itemInfo.title", "itemInfo.byLineInfo", "itemInfo.contentInfo", "itemInfo.classifications"]
# ★2026-11-21 ユーザ「一緒に取れる情報を捨てて取り直すことがあった」→ 取得前に全項目を調査して、価格・在庫(offersV2=
#   静的表示禁止・規約上1時間)以外は全部取る。 成人判定(productInfo.isAdultProduct)・ジャンル売り場(browseNodes)・
#   役割つき著者(byLineInfo)・頁数/紙の発売日/電子の配信日(contentInfo/productInfo)・書影URL(images=手元だけ・公開しない)。
FULL = ["browseNodeInfo.browseNodes", "browseNodeInfo.browseNodes.ancestor", "browseNodeInfo.browseNodes.salesRank",
        "browseNodeInfo.websiteSalesRank", "images.primary.large", "images.variants.large",
        "itemInfo.byLineInfo", "itemInfo.classifications", "itemInfo.contentInfo", "itemInfo.contentRating",
        "itemInfo.externalIds", "itemInfo.features", "itemInfo.manufactureInfo", "itemInfo.productInfo",
        "itemInfo.technicalInfo", "itemInfo.title", "itemInfo.tradeInInfo", "parentASIN"]
RAW_DIR = os.path.join(CACHE, "raw")
os.makedirs(RAW_DIR, exist_ok=True)
_CAMPAIGN = re.compile(r"キャンペーン|ポイント|クーポン|セール|まとめ買い|まとめ|Custom Stores|Experiment|Mystery|Offer|"
                       r"CompMatch|スタンプ|チャレンジ|円以下|_delete|\d{4}年|manga \d", re.I)


def _chain(bn):
    out = []
    while bn:
        out.append(bn.get("displayName", ""))
        bn = bn.get("ancestor")
    return out


def strip_item(it):
    """生の応答から販促用の売り場分類(1件80KB の大半)だけ落とす。 他は全部残す。"""
    bi = it.get("browseNodeInfo") or {}
    if not bi:
        return it
    keep = [b for b in bi.get("browseNodes") or [] if not any(_CAMPAIGN.search(x) for x in _chain(b))]
    return {**it, "browseNodeInfo": {**bi, "browseNodes": keep}}


def save_raw(kind, req, st, d, slug=None):
    """生の応答を .cache/kindle-asin/raw/YYYYMM.jsonl.gz へ追記(取り直し防止の一次保存)。"""
    import gzip
    d2 = d
    if isinstance(d, dict):
        for key in ("searchResult", "itemsResult"):
            if isinstance(d.get(key), dict) and d[key].get("items"):
                d2 = {**d, key: {**d[key], "items": [strip_item(x) for x in d[key]["items"]]}}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "slug": slug, "req": req, "status": st, "resp": d2}
    with gzip.open(os.path.join(RAW_DIR, time.strftime("%Y%m") + ".jsonl.gz"), "at", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def kindle_by_author(name):
    """→ (items, total, capped)。 1検索最大100件。"""
    items, total = [], None
    for page in range(1, 11):
        st, d = call("searchItems", {"author": name, "searchIndex": "KindleStore", "itemCount": 10,
                                     "itemPage": page, "resources": RES})
        if st != 200:
            print(f"   searchItems HTTP {st} {str(d)[:160]}")
            break
        sr = d.get("searchResult") or {}
        total = sr.get("totalResultCount", total)
        its = sr.get("items") or []
        for it in its:
            ii = it.get("itemInfo") or {}
            items.append({
                "asin": it["asin"],
                "title": (ii.get("title") or {}).get("displayValue", ""),
                "date": ((ii.get("contentInfo") or {}).get("publicationDate") or {}).get("displayValue", "")[:10],
                "binding": ((ii.get("classifications") or {}).get("binding") or {}).get("displayValue", ""),
                "authors": [c.get("name") for c in ((ii.get("byLineInfo") or {}).get("contributors") or [])],
            })
        if len(its) < 10:
            break
    return items, total, (total or 0) > len(items)


# ---------------- 自サイト ----------------
_PAT_VOL = re.compile(r"- number: (\S+)\n(?:\s+\w+:.*\n)*?\s+isbn13: '?(\d{13})'?\n(?:\s+(?!- )\w+:.*\n)*?\s+release_date: '?([\d-]*)'?")


def load_pages():
    """作者名 → [{slug,title,vols:[(number,isbn13,date)]}]"""
    by = defaultdict(list)
    d = os.path.join(ROOT, "data", "manga.v2")
    for f in os.listdir(d):
        if not f.endswith(".yml"):
            continue
        s = open(os.path.join(d, f), encoding="utf-8").read()
        m = re.search(r"^title: (.*)$", s, re.M)
        yr = re.search(r"^year_started: (\d+)", s, re.M)
        names = re.findall(r"^- name: (.*)$", s.split("\noriginal_authors:")[0], re.M)
        vols = []
        for num, isbn, dt in _PAT_VOL.findall(s):
            try:
                vols.append((float(num), isbn, dt))
            except ValueError:
                pass
        if not vols or not m:
            continue
        rec = {"slug": f[:-4], "title": m.group(1).strip().strip("'\""), "year": int(yr.group(1)) if yr else None,
               "kana": (re.search(r"^title_kana: (.*)$", s, re.M) or [None, ""])[1], "vols": vols}
        for n in names:
            by[n.strip().strip("'\"")].append(rec)
    return by


# ---------------- 照合 ----------------
def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"【[^】]*】", "", s)  # ★【男女比1:100】型: 両側から同じく外す(Kindle 側だけ外すと題が合わなくなる)
    return re.sub(r"[\s・:：!！?？、。,.\-‐―ー~〜'\"「」『』【】\[\]()（）]", "", s)


_LABEL = re.compile(r"\s*[\(（][^()（）]*(コミックス|comics|文庫|digital|ＤＩＧＩＴＡＬ|ブックス|books|レーベル|シリーズ)[^()（）]*[\)）]\s*$", re.I)
_BAD = re.compile(r"分冊|単話|話売り|連載版|第\d+話|特装|限定版|試し読み|無料|お試し|合本|セット|画集|ファンブック|公式ガイド|小説|ノベル|ベストセレクション|傑作選|傑作集|総集編|名作選|アンソロジー", re.I)


_UEGE = {"上": "U", "前編": "U", "前": "U", "中": "M", "下": "S", "後編": "S", "後": "S"}


def vol_of(t):
    """Kindle題 → (本体題, 巻番号 or None or "U"/"M"/"S"=上中下)。
    ★2026-11-21 「完全版 紳士協定を結ぼう! 上【電子特典付き】」を読めなかった → 【…】[…]を外し、上中下/前後編を読む。"""
    t = unicodedata.normalize("NFKC", t)
    t = _LABEL.sub("", t).strip()
    t = re.sub(r"[【\[][^】\]]*[】\]]", "", t).strip()
    t = _LABEL.sub("", t).strip()
    m = re.match(r"^(.*?)[\s]*(上|中|下|前編|後編)(巻)?$", t)
    if m and m.group(1):
        return m.group(1).strip(), _UEGE[m.group(2)]
    for p in (r"^(.*?)[\s　]*[\(（](\d+)[\)）]\s*$", r"^(.*?)[\s　]*第?(\d+)巻?\s*$", r"^(.*?)\s*(\d+)\s*[\(（]", r"^(.*?\D)(\d+)$"):
        m = re.match(p, t)
        if m:
            return m.group(1).strip(), int(m.group(2))
    return t, None


def days(a, b):
    try:
        da = datetime.date.fromisoformat(a[:10]) if len(a) >= 10 else datetime.date.fromisoformat(a[:7] + "-15")
        db = datetime.date.fromisoformat(b[:10]) if len(b) >= 10 else datetime.date.fromisoformat(b[:7] + "-15")
        return abs((da - db).days)
    except Exception:
        return None


def match_author(pages, items):
    """→ rows(巻ごと)。 grade = A(題+巻+日付±62日) / B(題+巻・日付ズレ/欠け) / -(なし)。"""
    kin = []
    for it in items:
        if it["binding"] and "Kindle" not in it["binding"]:
            continue
        if _BAD.search(it["title"]):
            continue
        base, n = vol_of(it["title"])
        kin.append({**it, "base": norm(base), "n": n, "color": "カラー" in it["title"],
                    "au": [norm(a) for a in it.get("authors") or [] if a]})
    # 上中下 → 番号(同じ本体題に「中」があれば 下=3、無ければ 下=2)
    has_mid = {k["base"] for k in kin if k["n"] == "M"}
    for k in kin:
        if k["n"] in ("U", "M", "S"):
            k["n"] = {"U": 1, "M": 2, "S": 3 if k["base"] in has_mid else 2}[k["n"]]
    rows = []
    for pg in pages:
        nt = norm(pg["title"])
        pa = norm(pg.get("author") or "")
        single = len(pg["vols"]) == 1
        for num, isbn, dt in pg["vols"]:
            cands = []
            for k in kin:
                # ★Kindle題 ⊇ 自サイト題 のみ(「まんが版 〜」の前置きは許す)。 逆向き(自サイト題がKindle題を含む)は
                #   「〜対マイコン電児ラン」に「マイコン電児ラン(1)」が当たる誤りになる(2026-11-21 試行で実踏)。
                if not nt or nt not in k["base"]:
                    continue
                # ★作者は空白・中黒を抜いて照合(Amazon「こうじま 奈月」⇔ サイト「こうじま奈月」 2026-11-21)
                if pa and k["au"] and not any(pa in a or a in pa for a in k["au"]):
                    continue
                if k["n"] is None and k["base"] != nt:  # 巻番号なしのKindle題は題が完全一致の時だけ
                    continue
                if len(k["base"]) > len(nt) * 2.2 + 6:  # 題が長すぎる=別作品(外伝・関連本)の疑い
                    continue
                if k["n"] is not None and k["n"] != int(num):
                    continue
                if k["n"] is None and not single and int(num) != 1:
                    continue
                dd = days(dt, k["date"]) if dt and k["date"] else None
                cands.append((0 if (dd is not None and dd <= 62) else 1, k["color"], dd if dd is not None else 99999, k))
            cands.sort(key=lambda x: (x[0], x[1], x[2]))
            if cands:
                g = "A" if cands[0][0] == 0 else "B"
                k = cands[0][3]
                amb = len([c for c in cands if c[0] == cands[0][0] and c[1] == cands[0][1]]) > 1
                rows.append((pg["slug"], pg["title"], int(num), isbn, dt, g + ("?" if amb else ""), k["asin"], k["date"],
                             k["title"], cands[0][2]))
            else:
                rows.append((pg["slug"], pg["title"], int(num), isbn, dt, "-", "", "", "", ""))
    return rows


# ---------------- 頁モード(題名+第1作者で Kindle 検索 + 紙ISBNを getItems) ----------------
def i10(s):
    s = str(s)
    if len(s) != 13 or not s.startswith("978"):
        return None
    b = s[3:12]
    c = (11 - sum((10 - i) * int(b[i]) for i in range(9)) % 11) % 11
    return b + ("X" if c == 10 else str(c))


def _item_brief(it):
    ii = it.get("itemInfo") or {}
    return {"asin": it["asin"], "title": (ii.get("title") or {}).get("displayValue", ""),
            "date": ((ii.get("contentInfo") or {}).get("publicationDate") or {}).get("displayValue", "")[:10],
            "binding": ((ii.get("classifications") or {}).get("binding") or {}).get("displayValue", ""),
            "authors": [c.get("name") for c in ((ii.get("byLineInfo") or {}).get("contributors") or [])]}


def harvest_page(pg, author):
    """→ (kindle_items, paper_found{isbn13:asin}, paper_invalid[isbn13], calls)。 応答は全部 save_raw。"""
    c0 = (CALLS['searchItems'] + CALLS['getItems'])
    items = []
    for page in range(1, 11):
        req = {"title": pg["title"], "author": author, "searchIndex": "KindleStore", "itemCount": 10,
               "itemPage": page, "resources": FULL}
        st, d = call("searchItems", req)
        save_raw("kindle-search", req, st, d, pg["slug"])
        if st != 200:
            break
        its = (d.get("searchResult") or {}).get("items") or []
        items += [_item_brief(x) for x in its]
        if len(its) < 10:
            break
    found, invalid = {}, []
    ids = {}
    for _, isbn, _ in pg["vols"]:
        k = i10(isbn)
        if k:
            ids[k] = isbn
    keys = list(ids)
    for j in range(0, len(keys), 10):
        req = {"itemIds": keys[j:j + 10], "itemIdType": "ASIN", "resources": FULL}
        st, d = call("getItems", req)
        save_raw("paper-get", req, st, d, pg["slug"])
        if st != 200:
            continue
        for it in (d.get("itemsResult") or {}).get("items") or []:
            if it["asin"] in ids:
                found[ids[it["asin"]]] = it["asin"]
        for e in d.get("errors") or []:
            m = re.search(r"ItemIds (\S+) provided", e.get("message", ""))
            if m and m.group(1) in ids:
                invalid.append(ids[m.group(1)])
    return items, found, invalid, (CALLS['searchItems'] + CALLS['getItems']) - c0


def first_author(slug):
    s = open(os.path.join(ROOT, "data", "manga.v2", slug + ".yml"), encoding="utf-8").read()
    head = s.split("\noriginal_authors:")[0]
    ms = re.findall(r"^- name: (.*)\n\s+role: (\S+)", head, re.M)
    for n, r in ms:  # 作画・作画兼作者を優先(原作者名だと Kindle 側の著者表記とずれることがある)
        if r in ("writer_artist", "artist"):
            return n.strip().strip("'\"")
    return ms[0][0].strip().strip("'\"") if ms else ""


def run_pages(authors, by, tag, max_pages):
    od = os.path.join(CACHE, tag)
    os.makedirs(od, exist_ok=True)
    fm = open(os.path.join(od, "match.tsv"), "w", encoding="utf-8")
    fm.write("author\tslug\ttitle\tnumber\tisbn13\tour_date\tgrade\tkindle_asin\tkindle_date\tkindle_title\tdays\tpaper\n")
    seen, rep, tot = set(), [], Counter()
    pages = []
    for a in authors:
        for pg in by.get(a, []):
            if pg["slug"] in seen or first_author(pg["slug"]) != a:
                continue
            seen.add(pg["slug"])
            pages.append((a, pg))
    pages = pages[:max_pages]
    print(f"対象 {len(pages)}頁 / {sum(len(p['vols']) for _, p in pages)}巻", flush=True)
    for a, pg in pages:
        items, found, invalid, calls = harvest_page(pg, a)
        rows = match_author([pg], items)
        g = Counter(r[5][0] for r in rows)
        for r in rows:
            pap = "有" if r[3] in found else ("無" if r[3] in invalid else "?")
            fm.write(a + "\t" + "\t".join(str(x) for x in r) + "\t" + pap + "\n")
        line = (f"{pg['title'][:24]}({a}) 呼出{calls} Kindle{len(items)} / {len(rows)}巻 → A{g['A']} B{g['B']} なし{g['-']}"
                f" / 紙 有{len(found)} 無{len(invalid)}")
        print(" ", line, flush=True)
        rep.append(line)
        tot.update({"calls": calls, "vols": len(rows), "A": g["A"], "B": g["B"], "none": g["-"],
                    "paper_ok": len(found), "paper_ng": len(invalid), "kitems": len(items)})
    s = (f"\n計: {len(pages)}頁 呼出{tot['calls']} / Kindle {tot['kitems']}件 / 自サイト{tot['vols']}巻 → "
         f"A {tot['A']} ({tot['A'] / max(1, tot['vols']):.0%}) / B {tot['B']} / なし {tot['none']}"
         f" / 紙の商品頁 有{tot['paper_ok']} 無{tot['paper_ng']}")
    print(s)
    open(os.path.join(od, "report.txt"), "w", encoding="utf-8").write("\n".join(rep) + s + "\n")
    print("出力:", od, "/ 生の応答:", RAW_DIR)


# ---------------- 本番収穫(harvest): 全頁・再開可・紙照会は頁をまたいで10冊ずつ ----------------
# 判定(2026-11-21 ユーザ裁定「そろってれば取る」):
#   A  = 題+巻番号+発売日(±62日)一致 → 採る
#   B  = 題+巻番号は一致・日付ズレ(電子の復刊で Kindle の日付が配信日)→ その版の巻番号が Kindle 側で
#        **全部そろっている時だけ**採る(版が1冊なら、その1冊の題が完全一致で当たっていれば「そろっている」)
#   それ以外(版の一部だけ当たった B・同点の候補が複数)= 見直し行き(review)。 照合なし = none。
HV = os.path.join(CACHE, "harvest")
os.makedirs(HV, exist_ok=True)
DONE = os.path.join(HV, "done.txt")           # 済んだ頁(slug)
CAND = os.path.join(HV, "candidates.jsonl")   # 巻ごとの判定結果(採る/見直し/なし)
PAPER = os.path.join(HV, "paper.jsonl")       # 紙の商品頁 有/無(isbn13)


def page_info(path):
    import yaml
    d = yaml.load(open(path, encoding="utf-8"), Loader=yaml.CSafeLoader)
    if not isinstance(d, dict):
        return None
    au = ""
    for a in d.get("authors") or []:
        if a.get("role") in ("writer_artist", "artist"):
            au = a.get("name") or ""; break
    if not au and d.get("authors"):
        au = d["authors"][0].get("name") or ""
    eds = []
    for i, e in enumerate(d.get("editions") or []):
        vs = []
        for v in e.get("volumes") or []:
            if v.get("isbn13") and v.get("number") is not None:
                try:
                    vs.append((float(v["number"]), str(v["isbn13"]), str(v.get("release_date") or ""), v.get("kindle_asin")))
                except (TypeError, ValueError):
                    pass
        if vs:
            eds.append({"idx": i, "label": e.get("label") or e.get("type"), "vols": vs})
    if not eds or not d.get("title"):
        return None
    return {"slug": d.get("slug") or os.path.basename(path)[:-4], "src": os.path.basename(path)[:-4],
            "title": str(d["title"]), "author": au, "eds": eds}


def judge_page(pi, items):
    """→ [{isbn13, number, edition, verdict(take/review/none), grade, asin, ...}]"""
    out = []
    for ed in pi["eds"]:
        pg = {"slug": pi["slug"], "title": pi["title"], "author": pi["author"],
              "vols": [(n, i, dt) for n, i, dt, _ in ed["vols"]]}
        rows = match_author([pg], items)
        graded = [r for r in rows if r[5] != "-"]
        asins = [r[6] for r in graded]
        complete = (len(graded) == len(rows)) and len(set(asins)) == len(asins)
        for r, (_, _, _, cur) in zip(rows, ed["vols"]):
            g = r[5]
            if g == "-":
                v = "none"
            elif g.endswith("?"):
                v = "review"
            elif g == "A":
                v = "take"
            else:
                v = "take" if complete else "review"
            out.append({"src": pi["src"], "slug": pi["slug"], "edition": ed["label"], "number": r[2], "isbn13": r[3],
                        "our_date": r[4], "grade": g, "verdict": v, "kindle_asin": r[6], "kindle_date": r[7],
                        "kindle_title": r[8], "days": r[9], "already": cur or None})
    return out


def search_kindle(pi, with_author):
    items = []
    pa, nt = norm(pi["author"]), norm(pi["title"])
    for page in range(1, 11):
        if with_author:
            req = {"title": pi["title"], "author": pi["author"], "searchIndex": "KindleStore", "itemCount": 10,
                   "itemPage": page, "resources": FULL}
        else:
            q = re.sub(r"[!！?？]+", " ", pi["title"]).strip()
            req = {"title": q, "searchIndex": "KindleStore", "itemCount": 10, "itemPage": page, "resources": FULL}
        st, resp = call("searchItems", req)
        save_raw("kindle-search" + ("" if with_author else "-titleonly"), req, st, resp, pi["src"])
        if st != 200:
            break
        its = (resp.get("searchResult") or {}).get("items") or []
        br = [_item_brief(x) for x in its]
        items += br
        if len(its) < 10:
            break
        # 2頁目以降で「題も作者も合う物」が1件も無い頁が出たら、 その先は別作品ばかり = めくらない(回数の節約)
        if page >= 2 and not any(nt in norm(vol_of(b["title"])[0]) and
                                 (not pa or any(pa in norm(a) or norm(a) in pa for a in b["authors"] if a))
                                 for b in br):
            break
    return items


STOPF = os.path.join(HV, "STOP")              # ★これが在ると次の頁の前で止まる(skill「Kindle収穫止めて」)


def _another_running():
    """台帳(calls.log)の最終行が5分以内 = 別の収穫が走っている(二重起動は叩く速さが倍になる=禁止)。"""
    if not os.path.exists(_LEDGER):
        return False
    last = ""
    with open(_LEDGER, "rb") as f:
        f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 200))
        ls = f.read().decode("utf-8", "ignore").strip().splitlines()
        last = ls[-1] if ls else ""
    try:
        return time.time() - float(last.split()[0]) < 300
    except (ValueError, IndexError):
        return False


def harvest(order_seed, max_pages, kindle_only=False):
    # ★2026-11-23 ユーザ裁定「まずは電子書籍を優先して落としたい」= --kindle-only は紙の照会(getItems・単位の約7割)をしない。
    #   紙は後で isbn13 ごとに paper.jsonl と突き合わせて未照会分だけ回せる(done.txt とは独立)。
    if _another_running():
        raise SystemExit("台帳に5分以内の呼出あり = 別の収穫が走っている。二重起動しない(止めるなら STOP ファイル)")
    if os.path.exists(STOPF):
        os.remove(STOPF)
    done = set()
    if os.path.exists(DONE):
        done = set(open(DONE, encoding="utf-8").read().split())
    d = os.path.join(ROOT, "data", "manga.v2")
    files = sorted(f for f in os.listdir(d) if f.endswith(".yml"))
    random.Random(order_seed).shuffle(files)  # ★人気順にしない(決まった種で混ぜた順=途中で止めても偏らない)
    todo = [f for f in files if f[:-4] not in done]
    print(f"全{len(files)}頁 / 済{len(done)} / 残{len(todo)} / 直近24時間 {_used_24h()} 単位", flush=True)
    queue = []  # 紙照会待ち (isbn10, isbn13, src)
    paper_known = set()
    if os.path.exists(PAPER):
        paper_known = {json.loads(ln)["isbn13"] for ln in open(PAPER, encoding="utf-8")}
    stat = Counter()
    t0 = time.time()

    def flush(force=False):
        while len(queue) >= 10 or (force and queue):
            chunk, queue[:] = queue[:10], queue[10:]
            ids = {a: (i13, src) for a, i13, src in chunk}
            req = {"itemIds": list(ids), "itemIdType": "ASIN", "resources": FULL}
            st, resp = call("getItems", req)
            save_raw("paper-get", req, st, resp, None)
            if st != 200:
                continue
            ok = {it["asin"] for it in (resp.get("itemsResult") or {}).get("items") or []}
            with open(PAPER, "a", encoding="utf-8") as f:
                for a, (i13, src) in ids.items():
                    f.write(json.dumps({"isbn13": i13, "isbn10": a, "src": src, "paper": a in ok,
                                        "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
                    stat["paper_ok" if a in ok else "paper_ng"] += 1

    n = 0
    try:
        for f in todo:
            if max_pages and n >= max_pages:
                break
            if os.path.exists(STOPF):
                print(f"[{time.strftime('%H:%M')}] STOP ファイルを見て停止", flush=True)
                os.remove(STOPF)
                break
            if not os.path.exists(os.path.join(d, f)):
                continue  # 頁の作り直し中などで一時的に無い = 記録せず次回に回す(落ちない)
            pi = page_info(os.path.join(d, f))
            if pi is not None and pi["author"] in ("(unknown)", "unknown", "不明"):
                pi["author"] = ""  # 作者不明 = 題名だけで検索(照合は題名一致で絞られる)
            if pi is None:
                with open(DONE, "a", encoding="utf-8") as fo:
                    fo.write(f[:-4] + "\n")
                stat["skip"] += 1
                continue
            # ★2段(2026-11-21 v3): ①題名+作者(精度が高い・短い題名でも埋もれない=シャッター型)
            #   ②①で1冊も当たらない時だけ題名だけ(作者表記の空白ゆれ=「こうじま 奈月」型の救済)。 作者は照合側で空白抜きで確かめる。
            items = search_kindle(pi, with_author=bool(pi["author"]))
            rows = judge_page(pi, items)
            if pi["author"] and not any(r["verdict"] != "none" for r in rows):
                items += search_kindle(pi, with_author=False)
                rows = judge_page(pi, items)
            with open(CAND, "a", encoding="utf-8") as fo:
                for r in rows:
                    fo.write(json.dumps({**r, "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
                    stat[r["verdict"]] += 1
            for ed in ([] if kindle_only else pi["eds"]):
                for _, i13, _, _ in ed["vols"]:
                    a10 = i10(i13)
                    if a10 and i13 not in paper_known:
                        queue.append((a10, i13, pi["src"]))
                        paper_known.add(i13)
            flush()
            with open(DONE, "a", encoding="utf-8") as fo:
                fo.write(pi["src"] + "\n")
            n += 1
            if n % 50 == 0:
                el = time.time() - t0
                print(f"[{time.strftime('%H:%M')}] {n}頁 / 巻 採る{stat['take']} 見直し{stat['review']} なし{stat['none']}"
                      f" / 紙 有{stat['paper_ok']} 無{stat['paper_ng']} / 呼出{(CALLS['searchItems'] + CALLS['getItems'])}"
                      f" / {el / n:.1f}秒/頁 / 24h {_used_24h()}単位", flush=True)
    except SystemExit as e:
        print(f"停止: {e}", flush=True)
        # ★紙照会待ちは done にした頁の分。 次回は該当頁を再走しないので、 ここで捨てずに保留ファイルへ。
        with open(os.path.join(HV, "paper-pending.jsonl"), "a", encoding="utf-8") as fo:
            for a, i13, src in queue:
                fo.write(json.dumps({"isbn10": a, "isbn13": i13, "src": src}, ensure_ascii=False) + "\n")
        queue.clear()
    else:
        try:
            flush(force=True)
        except SystemExit as e:
            print(f"停止(紙照会の最後): {e}", flush=True)
    print(f"\n今回 {n}頁 / 巻 採る{stat['take']} 見直し{stat['review']} なし{stat['none']} / 紙 有{stat['paper_ok']}"
          f" 無{stat['paper_ng']} / skip{stat['skip']} / 呼出{dict(CALLS)} / 24h {_used_24h()}単位", flush=True)


def summary():
    c, seen = Counter(), {}
    if os.path.exists(CAND):
        for ln in open(CAND, encoding="utf-8"):
            r = json.loads(ln)
            seen[(r["src"], r["edition"], r["number"], r["isbn13"])] = r
    for r in seen.values():
        c[r["verdict"]] += 1
    p = Counter()
    if os.path.exists(PAPER):
        for ln in open(PAPER, encoding="utf-8"):
            p["有" if json.loads(ln)["paper"] else "無"] += 1
    done = len(open(DONE, encoding="utf-8").read().split()) if os.path.exists(DONE) else 0
    total = sum(1 for f in os.listdir(os.path.join(ROOT, "data", "manga.v2")) if f.endswith(".yml"))
    run = "走っている" if _another_running() else "止まっている"
    print(f"[{run}] 全{total}頁中 済 {done}頁 (残{total - done}) / 巻: 採る {c['take']} / 見直し {c['review']} / なし {c['none']} / 紙の商品頁: {dict(p)}"
          f" / 直近24時間の呼出 {_used_24h()} / 予算 {DAILY_BUDGET}")


# ---------------- 実行 ----------------
ROW = "アカサタナハマヤラワ"


def pick_authors(by, n, seed):
    """50音の行 × 年代が偏らないように(人気順にしない)。 巻3〜150冊の作者から。"""
    rnd = random.Random(seed)
    pool = defaultdict(list)
    for a, pgs in by.items():
        tot = sum(len(p["vols"]) for p in pgs)
        if not (3 <= tot <= 150) or len(a) < 2:
            continue
        yrs = [p["year"] for p in pgs if p["year"]]
        if not yrs:
            continue
        dec = (min(yrs) // 10) * 10
        pool[dec].append(a)
    decs = sorted(d for d in pool if d >= 1960)
    out = []
    i = 0
    while len(out) < n and i < 200:
        d = decs[i % len(decs)]
        c = rnd.choice(pool[d])
        if c not in out:
            out.append(c)
        i += 1
    return out


def run(authors, by, tag):
    od = os.path.join(CACHE, tag)
    os.makedirs(od, exist_ok=True)
    fi = open(os.path.join(od, "items.jsonl"), "w", encoding="utf-8")
    fm = open(os.path.join(od, "match.tsv"), "w", encoding="utf-8")
    fm.write("author\tslug\ttitle\tnumber\tisbn13\tour_date\tgrade\tkindle_asin\tkindle_date\tkindle_title\tdays\n")
    rep = []
    tot = Counter()
    for a in authors:
        c0 = (CALLS['searchItems'] + CALLS['getItems'])
        items, total, capped = kindle_by_author(a)
        for it in items:
            fi.write(json.dumps({"author_q": a, **it}, ensure_ascii=False) + "\n")
        rows = match_author(by.get(a, []), items)
        for r in rows:
            fm.write(a + "\t" + "\t".join(str(x) for x in r) + "\n")
        g = Counter(r[5][0] for r in rows)
        calls = (CALLS['searchItems'] + CALLS['getItems']) - c0
        line = (f"{a}: 呼出{calls} / Kindle {len(items)}件(総{total}{'・100件の壁' if capped else ''}) / "
                f"自サイト {len(by.get(a, []))}頁 {len(rows)}巻 → A {g['A']} / B {g['B']} / なし {g['-']}")
        print(line, flush=True)
        rep.append(line)
        tot.update({"calls": calls, "items": len(items), "vols": len(rows), "A": g["A"], "B": g["B"], "none": g["-"]})
    s = (f"\n計: 呼出{tot['calls']} / Kindle {tot['items']}件 / 自サイト{tot['vols']}巻 → "
         f"A {tot['A']} ({tot['A'] / max(1, tot['vols']):.0%}) / B {tot['B']} / なし {tot['none']}")
    print(s)
    open(os.path.join(od, "report.txt"), "w", encoding="utf-8").write("\n".join(rep) + s + "\n")
    print("出力:", od)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trial"); t.add_argument("--n", type=int, default=10); t.add_argument("--seed", type=int, default=1121)
    o = sub.add_parser("author"); o.add_argument("name")
    pp = sub.add_parser("pages"); pp.add_argument("--n", type=int, default=10); pp.add_argument("--seed", type=int, default=2211)
    pp.add_argument("--max-pages", type=int, default=60)
    hv = sub.add_parser("harvest"); hv.add_argument("--max-pages", type=int, default=0); hv.add_argument("--seed", type=int, default=20261121)
    hv.add_argument("--kindle-only", action="store_true", help="紙の照会をしない(電子優先)")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "harvest":
        return harvest(a.seed, a.max_pages, a.kindle_only)
    if a.cmd == "status":
        return summary()
    print("自サイトの頁を読み込み中…", flush=True)
    by = load_pages()
    if a.cmd == "trial":
        au = pick_authors(by, a.n, a.seed)
        print("選んだ作者:", " / ".join(au))
        run(au, by, f"trial-{time.strftime('%Y%m%d-%H%M')}")
    elif a.cmd == "pages":
        au = pick_authors(by, a.n, a.seed)
        print("選んだ作者:", " / ".join(au))
        run_pages(au, by, f"pages-{time.strftime('%Y%m%d-%H%M')}", a.max_pages)
    else:
        run([a.name], by, f"author-{time.strftime('%Y%m%d-%H%M')}")


if __name__ == "__main__":
    main()
