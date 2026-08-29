#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""試し読みリンク収集エンジン (BookLive title_id)。skill tameshiyomi-harvest の実体。

設計方針(弱いモデル運転前提): 判断はscriptに焼く。AIの仕事は --review で出る保留の裁定のみ。
  1. 対象選定 = 人気順上位のうち未収集・未保留の作品 (--limit N)
  2. TinyFish検索 site:booklive.jp <題> <著者> → title_id をURLから正規表現抽出
  3. ゲート: 題の正規化一致(部分不可・完全一致のみ) + 著者姓一致 → 不一致は自動採用しない(保留)
  4. 検証: bviewer cid=<title_id>_001 を HEAD 200 確認(失敗=保留)
  5. 出力: data/seeds/tameshiyomi-booklive.jsonl に純粋追加(証拠込み、= シリーズ単位のanchor)。
     保留= docs/production-diagnostics/tameshiyomi-holds.tsv
  再開可能(収集済み/保留済みはskip)。429/失敗は即中断。

★全巻展開 (= 2026-07-12発見。ユーザ指摘「ドラゴンボールなら42巻分取らないとダメ」で判明):
  BookLiveのtitle_idは**シリーズ/版単位**で、vol_no(product頁)やcid末尾3桁(bviewerの巻番号)を
  変えるだけで**同一title_idのまま全巻に到達できる**(TinyFish検索不要・HEADチェックのみ)。
  実証: title_id/582763(チェンソーマン)でvol_no/001→1巻、/002→2巻。
        title_id/185409(BLEACHモノクロ版)で_001/_025/_100相当のcidが全部HEAD200。
  帰結: アンカー(シリーズ→title_id)さえ集めれば、巻数分の追加検索は不要、
  cid=f"{title_id}_{vol:03d}" をmax_edition_volumes分HEAD検証するだけで全巻リンクが揃う。

使い方:
  python scripts/_tameshiyomi-harvest.py --limit 50          # 上位50作のtitle_id(アンカー)を収集
  python scripts/_tameshiyomi-harvest.py --expand --expand-limit 100  # アンカー済みシリーズを全巻展開(検索不要・高速)
  python scripts/_tameshiyomi-harvest.py --review            # 保留一覧を表示(AIが裁定)
  python scripts/_tameshiyomi-harvest.py --accept slug=ID    # 保留を手動採用(裁定後)
  python scripts/_tameshiyomi-harvest.py --stats             # 進捗
"""
import argparse, datetime, gzip, json, os, re, sys, time, unicodedata, urllib.error, urllib.request
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
SEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl")
# ★2026-08-12 gzip化(50.9MBがGitHub推奨50MB超え警告): 追記はgzipマルチメンバー(covers seedと同方式)。
VOLSEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive-volumes.jsonl.gz")
HOLDS = os.path.join(ROOT, "docs", "production-diagnostics", "tameshiyomi-holds.tsv")


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[ァ-ヶ]", lambda m: chr(ord(m.group(0)) - 0x60), s)
    return re.sub(r"[\s　・!！?？:：〜~ー\-。、．.「」『』()（）☆★♥]", "", s)


def load_done():
    done, holds = {}, set()
    if os.path.exists(SEED):
        for line in open(SEED, encoding="utf-8"):
            r = json.loads(line)
            done[r["slug"]] = r
    if os.path.exists(HOLDS):
        for line in open(HOLDS, encoding="utf-8"):
            holds.add(line.split("\t")[0])
    return done, holds


# ★再検査campaign(2026-08-20 ユーザ指示「古い順に調べ直したい・アイドル運転」):
#   --list-file = slugリスト(1行1slug、ファイル順に処理=呼び手が古い順に並べる)。
#   --retry-holds = 保留済みslugも再検索(BookLive在庫は増えるので過去の候補0が今は在ることがある)。
#   attempted台帳(.cache) = このcampaignで試行済みのslug。再held分の無限再試行を防ぐ収束カーソル。
ATTEMPTED = os.path.join(ROOT, ".cache", "tameshiyomi", "recheck-attempted.txt")


def load_attempted():
    if os.path.exists(ATTEMPTED):
        return {l.strip() for l in open(ATTEMPTED, encoding="utf-8") if l.strip()}
    return set()


def targets_from_file(limit, list_file, retry_holds):
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = li["f"]
    isl, it, ia = f.index("slug"), f.index("title"), f.index("authors")
    rowmap = {r[isl]: (r[it], [au_name(a) for a in (r[ia] or [])]) for r in li["d"]}
    done, holds = load_done()
    attempted = load_attempted()
    out = []
    for line in open(list_file, encoding="utf-8"):
        s = line.strip()
        if not s or len(out) >= limit:
            if len(out) >= limit:
                break
            continue
        if s in done or s in attempted:
            continue
        if s in holds and not retry_holds:
            continue
        if s not in rowmap:
            continue
        out.append((s, rowmap[s][0], rowmap[s][1]))
    return out


def dedupe_holds_keep_last():
    """再検索で同一slugの保留行が積み上がるのを防ぐ(最後の結果だけ残す)。"""
    if not os.path.exists(HOLDS):
        return
    rows = open(HOLDS, encoding="utf-8").readlines()
    last = {}
    for l in rows:
        last[l.split("\t", 1)[0]] = l
    if len(last) < len(rows):
        open(HOLDS, "w", encoding="utf-8").writelines(last.values())


def targets(limit):
    # ★デルタ恒常化(2026-08-06 ユーザ指示「日々増える新作を取得」):
    #   ①popularity=0の足切りを廃止(新作・マイナー作はpop0=旧ゲートだと永久に収集されなかった)
    #   ②並び=latest_date降順(新しい作品から先に拾う=日次蒸留の新規頁が次バッチの先頭に来る)
    #   除外=収集済み(seed)∪保留(holds)。queueは索引から毎回再算出なので新規頁は自動で列に入る。
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = li["f"]
    isl, it, ia = f.index("slug"), f.index("title"), f.index("authors")
    ild = f.index("latest_date")
    rows = sorted(li["d"], key=lambda r: str(r[ild] or ""), reverse=True)
    done, holds = load_done()
    out = []
    for r in rows:
        if len(out) >= limit:
            break
        if r[isl] in done or r[isl] in holds:
            continue
        out.append((r[isl], r[it], [au_name(a) for a in (r[ia] or [])]))
    return out


# ★分冊版並走の自動解決(2026-08-12 コインランドリー型=ユーザ発見): 本編と分冊版/単話/マイクロが
#   両方 exact+au で並ぶと旧ロジックは複数候補=保留に落としていた(実測474件)。試し読みの底本は
#   常に本編(単行本)なので、分冊系マーカー候補を除外して一意に絞れるなら採用する。
BUNSATSU_RE = re.compile(r"分冊|単話|話売り|ばら売り|マイクロ|プチキス|プチデザ")

def prefer_bound(strong, cand):
    if len(strong) <= 1:
        return strong
    keep = [t for t in strong if not BUNSATSU_RE.search(cand[t].get("ev", ""))]
    return keep if keep else strong


# ============================================================================
# ★BookLive アクセス規約 (2026-08-29 制定。 規制を受けた事故の再発防止)
#   事故: 2026-08-28に入れた「尾の自動再訪」が、最終配信巻より上の404を毎回未チェック扱いに
#   戻すため **同じシリーズを永久に叩き直す無限ループ**になり、60シリーズに 231万リクエストを
#   投げてBookLiveに規制された(名探偵コナン単独で38万回)。命中率は途中から0%のまま。
#   ★以後はこの4本を必ず守る。ゆるめる時はユーザ裁定を取る。
#     ① 直列1本・最短間隔 REQ_INTERVAL 秒 (並列禁止)
#     ② 1回の実行で MAX_REQ_PER_RUN 件まで。超えたら正常終了して次回に回す
#     ③ 200/404 以外(429/403/5xx/timeout/接続断)は **1件でも即中断**。台帳に書かない
#        = 「規制されている」を「試し読みが無い」と誤記録しない(偽404の永久固定を防ぐ)
#     ④ 連続 MAX_CONSEC_MISS 件ヒット無しでも中断(静かな規制=200で別頁を返す型の保険)
# ============================================================================
REQ_INTERVAL = 2.0          # 秒/リクエスト(直列)。NDLの1.3秒より更に保守的にする
MAX_REQ_PER_RUN = 1500      # 1実行あたりの上限
MAX_REQ_PER_DAY = 5000      # 1日あたりの上限(プロセスをまたいで数える)
MAX_CONSEC_MISS = 300       # 連続ヒット無しでの打ち切り
UA = "MangalBot/1.0 (+https://mangal.shuichi0725.workers.dev; contact shuichi0725@gmail.com)"
DAYCOUNT = os.path.join(ROOT, ".cache", "tameshiyomi", "booklive-daycount.json")
BLOCK_FLAGS = (os.path.join(ROOT, "docs", "production-diagnostics", "BOOKLIVE-BLOCKED.md"),
               os.path.join(ROOT, ".cache", "tameshiyomi", "BLOCKED"))
_req_count = [0]


class Blocked(Exception):
    """規制/障害が疑われる応答。台帳に書かずに即中断するための例外。"""


def _assert_not_blocked():
    """★停止札があるうちは1リクエストも出さない(規制中の再突入防止)。"""
    for f in BLOCK_FLAGS:
        if os.path.exists(f):
            raise SystemExit(
                "停止札あり(%s) = BookLive規制中。リクエストを出さずに終了する。\n"
                "解除はユーザが『復帰した』と言った時だけ。手順は札の中身。" % os.path.relpath(f, ROOT))


def _day_bump():
    """日次カウンタ(プロセス間)。上限を超えたら Blocked 相当で止める。"""
    today = time.strftime("%Y-%m-%d")
    d = {"date": today, "n": 0}
    try:
        d = json.load(open(DAYCOUNT, encoding="utf-8"))
        if d.get("date") != today:
            d = {"date": today, "n": 0}
    except Exception:
        pass
    d["n"] = int(d.get("n") or 0) + 1
    try:
        os.makedirs(os.path.dirname(DAYCOUNT), exist_ok=True)
        json.dump(d, open(DAYCOUNT, "w", encoding="utf-8"))
    except OSError:
        pass
    if d["n"] > MAX_REQ_PER_DAY:
        raise Blocked("1日の上限%d件に到達(明日以降に回す)" % MAX_REQ_PER_DAY)


def _throttle():
    """★BookLive宛は _rate_gate でプロセス間グローバル直列化する(楽天/NDL/wikiと同じ機構)。
    per-プロセスの間隔だけでは、柱を2本起動した瞬間に合算レートが倍になる = 事故の元。"""
    _assert_not_blocked()
    _day_bump()
    try:
        import _rate_gate
        _rate_gate.wait("booklive", REQ_INTERVAL)
    except Exception:
        time.sleep(REQ_INTERVAL)
    _req_count[0] += 1


def check_cid(cid):
    """試し読みcidの存否を返す。 True=あり / False=無い(404だけ)。
    ★404以外の異常は Blocked を投げる(呼び手は台帳に書かずに中断すること)。"""
    _throttle()
    req = urllib.request.Request(f"https://booklive.jp/bviewer/s/?cid={cid}",
                                 headers={"User-Agent": UA}, method="HEAD")
    try:
        return urllib.request.urlopen(req, timeout=20).status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False            # ★これだけが「本当に試し読みが無い」
        raise Blocked(f"HTTP {e.code} cid={cid}")
    except Exception as e:
        raise Blocked(f"{type(e).__name__} cid={cid}")


def head_ok(cid):
    """旧API(--accept 等の単発検証用)。 例外は False に潰す。"""
    try:
        return check_cid(cid)
    except Blocked:
        return False


# ★商品頁照会ゲート(2026-08-20 ユーザGO=領民0人型): 検索snippet頼みを卒業し、採用直前に
#   BookLive商品頁(vol1)のJSON-LDから category/genre/author を直接読む。
#   ①カテゴリ検証 = ライトノベル/文芸/小説なら不採用(→保留 reason=ラノベ/小説)。
#     ラノベ原作コミカライズで検索が小説版を拾う誤アンカーを構造的に遮断。
#   ②著者検証 = snippetに著者が出ないだけの偽保留(早野先生型609件)を商品頁著者で救済。
NOVEL_CAT = re.compile(r"ライトノベル|ラノベ|文芸|小説|BLノベル|TLノベル")


def product_gate(tid, au):
    """→ (verdict, detail)。verdict: 'ok' / 'novel' / 'author_ng' / 'fetch_ng'"""
    _throttle()   # ★2026-08-29: 商品頁GETも同じレート規約に乗せる
    try:
        req = urllib.request.Request(f"https://booklive.jp/product/index/title_id/{tid}/vol_no/001",
                                     headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception as e:
        return "fetch_ng", type(e).__name__
    cat = re.search(r'"category":\s*"([^"]+)"', html)
    gen = re.search(r'"genre":\s*"([^"]+)"', html)
    catgen = (cat.group(1) if cat else "") + "/" + (gen.group(1) if gen else "")
    if NOVEL_CAT.search(catgen):
        return "novel", catgen
    # 著者: JSON-LD author name(複数可)を平坦に集める
    prod_au = " ".join(re.findall(r'"@type":\s*"Person",\s*"name":\s*"([^"]+)"', html))
    if au and norm(au)[:4] and norm(au)[:4] not in norm(prod_au):
        return "author_ng", prod_au[:60]
    return "ok", catgen


def load_volumes_done():
    """slug -> set(volume已検証)"""
    done = {}
    if os.path.exists(VOLSEED):
        for line in gzip.open(VOLSEED, "rt", encoding="utf-8"):
            r = json.loads(line)
            done.setdefault(r["slug"], set()).add(r["volume"])
    return done


def volume_target_n():
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = li["f"]
    isl = f.index("slug")
    itv = f.index("total_volumes")
    imv = f.index("max_edition_volumes")
    out = {}
    for r in li["d"]:
        n = max(r[itv] or 0, r[imv] or 0)
        if n:
            out[r[isl]] = n
    return out


# ★チェック済み台帳(2026-07-20): HEADで200/404どちらを引いたか(slug,vol)を記録=再チェック防止。
#   これが無いと「404の欠け巻」を毎バッチ叩き直し、部分カバレッジ(幽遊白書型)が永久に未完了で
#   先頭に居座り、後方アンカーが飢餓する(枯れない根因)。cache置き=git非追跡・冪等カーソル。
VOL_CHECKED = os.path.join(ROOT, ".cache", "tameshiyomi", "vol-checked.jsonl")


def load_vol_checked():
    """slug -> set(checkedしたvolume。200も404も)。全1..nがcheckedならそのシリーズは完了。"""
    ck = {}
    if os.path.exists(VOL_CHECKED):
        for line in open(VOL_CHECKED, encoding="utf-8"):
            try:
                r = json.loads(line)
                ck.setdefault(r["slug"], set()).add(r["v"])
            except Exception:
                pass
    return ck


def load_blmax():
    """slug -> HEAD200確認済みの最大volume(volumes seedから)。★尾の再訪判定用(2026-08-28)。"""
    mx = {}
    if os.path.exists(VOLSEED):
        for line in gzip.open(VOLSEED, "rt", encoding="utf-8"):
            try:
                r = json.loads(line)
                v = int(r.get("volume") or 0)
                if v > mx.get(r["slug"], 0):
                    mx[r["slug"]] = v
            except Exception:
                pass
    return mx


# ★掃引済み台帳(2026-08-29 新設): シリーズごとに「巻数nまで全部チェックし終えた日」を記録する。
#   これが無いと、下の「尾の自動再訪」がそのシリーズを毎バッチ叩き直す無限ループになる(=規制事故)。
SWEPT = os.path.join(ROOT, ".cache", "tameshiyomi", "expand-swept.jsonl")
TAIL_RECHECK_DAYS = 30      # 尾(最終配信巻より上)を再訪する間隔。 n が増えた時は日数に関係なく再訪


def load_swept():
    """slug -> {'n': 掃引時の巻数, 'at': 'YYYY-MM-DD'}"""
    sw = {}
    if os.path.exists(SWEPT):
        for line in open(SWEPT, encoding="utf-8"):
            try:
                r = json.loads(line)
                sw[r["slug"]] = r
            except Exception:
                pass
    return sw


def _days_since(d):
    try:
        y, m, dd = (int(x) for x in str(d).split("-"))
        return (datetime.date.today() - datetime.date(y, m, dd)).days
    except Exception:
        return 10 ** 6


def expand_volumes(expand_limit, workers=1):
    """アンカー済み(title_id確定)シリーズを、直列HEADで全巻展開する。

    ★2026-08-29 全面改訂(BookLive規制事故の是正)。workers は互換のため残すが常に直列。
      1. 完了判定は **掃引済み台帳(SWEPT)**。「1..n を全部チェックした」を1行残す。
      2. 尾の再訪(新刊で試し読みが増える件)は **n が増えた時** か **前回掃引から
         TAIL_RECHECK_DAYS 日以上経った時** だけ。毎バッチ再訪しない(=無限ループの根)。
      3. 404以外の応答が1件でも来たら Blocked で即中断。台帳に書かずに抜ける
         (= 規制中の応答を「試し読み無し」として永久固定しない)。
      4. レート = REQ_INTERVAL 秒/件、1実行 MAX_REQ_PER_RUN 件まで。
    """
    anchors, _ = load_done()
    n_by_slug = volume_target_n()
    checked = load_vol_checked()
    blmax = load_blmax()
    swept = load_swept()
    os.makedirs(os.path.dirname(VOL_CHECKED), exist_ok=True)
    targets = []
    for slug, rec in anchors.items():
        n = n_by_slug.get(slug)
        if not n:
            continue
        ck = set(checked.get(slug, set()))
        sw = swept.get(slug)
        if sw:
            grew = n > int(sw.get("n") or 0)
            stale = _days_since(sw.get("at")) >= TAIL_RECHECK_DAYS
            if not grew and not stale:
                continue                      # 掃引済み・巻も増えていない = 触らない
            # 再訪は「最終配信巻より上」だけ(下の404=真の配信欠けは叩き直さない)
            bl = blmax.get(slug, 0)
            ck = {v for v in ck if v <= bl}
        todo = [v for v in range(1, n + 1) if v not in ck]
        targets.append((slug, rec["title_id"], n, todo))
    remaining = len(targets)
    targets = targets[:expand_limit]
    print("展開対象 %d シリーズ(未チェック巻あり・残 %d) / 直列 %.1f秒/件・上限%d件"
          % (len(targets), remaining, REQ_INTERVAL, MAX_REQ_PER_RUN), flush=True)
    out = gzip.open(VOLSEED, "at", encoding="utf-8")
    ckout = open(VOL_CHECKED, "a", encoding="utf-8")
    swout = open(SWEPT, "a", encoding="utf-8")
    total_new, consec_miss, stopped = 0, 0, None
    try:
        for slug, tid, n, todo in targets:
            if _req_count[0] >= MAX_REQ_PER_RUN:
                stopped = "1実行の上限%d件に到達(続きは次回)" % MAX_REQ_PER_RUN
                break
            added, done_all = 0, True
            for vol in todo:
                if _req_count[0] >= MAX_REQ_PER_RUN:
                    done_all = False
                    stopped = "1実行の上限%d件に到達(続きは次回)" % MAX_REQ_PER_RUN
                    break
                ok = check_cid("%s_%03d" % (tid, vol))       # ★Blockedは投げさせる
                ckout.write(json.dumps({"slug": slug, "v": vol}, ensure_ascii=False) + "\n")
                if ok:
                    rec2 = {"slug": slug, "volume": vol, "title_id": tid,
                            "cid": "%s_%03d" % (tid, vol),
                            "verified": "head200", "at": time.strftime("%Y-%m-%d")}
                    out.write(json.dumps(rec2, ensure_ascii=False) + "\n")
                    added += 1
                    consec_miss = 0
                else:
                    consec_miss += 1
                    if consec_miss >= MAX_CONSEC_MISS:
                        done_all = False
                        stopped = "連続%d件ヒット無し(静かな規制の疑い)" % MAX_CONSEC_MISS
                        break
            out.flush()
            ckout.flush()
            total_new += added
            if done_all:
                swout.write(json.dumps({"slug": slug, "n": n,
                                        "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
                swout.flush()
            print("  %s: +%dhit/%dchk (n=%d)" % (slug, added, len(todo), n), flush=True)
            if stopped:
                break
    except Blocked as e:
        print("★中断: BookLiveから 200/404 以外の応答 (%s)。台帳には書いていない。" % e,
              file=sys.stderr, flush=True)
        out.close()
        ckout.close()
        swout.close()
        print("展開中断 +%d巻 hit / 送信%d件" % (total_new, _req_count[0]))
        sys.exit(2)
    out.close()
    ckout.close()
    swout.close()
    if stopped:
        print("打ち切り: %s" % stopped, flush=True)
    print("展開完了 +%d巻 hit / 送信%d件 (seed=%s)"
          % (total_new, _req_count[0], os.path.relpath(VOLSEED, ROOT)))


def harvest(limit, list_file=None, retry_holds=False):
    from _tinyfish import search
    done, _ = load_done()
    if list_file:
        todo = targets_from_file(limit, list_file, retry_holds)
        os.makedirs(os.path.dirname(ATTEMPTED), exist_ok=True)
        att = open(ATTEMPTED, "a", encoding="utf-8")
        print(f"対象 {len(todo)} 作(リスト順・campaign未試行)", flush=True)
    else:
        att = None
        todo = targets(limit)
        print(f"対象 {len(todo)} 作(人気順・未収集)", flush=True)
    seed = open(SEED, "a", encoding="utf-8")
    holds = open(HOLDS, "a", encoding="utf-8")
    n_ok = n_hold = 0
    for k, (slug, title, authors) in enumerate(todo):
        au = (authors[0] if authors else "")
        try:
            res = search(f"site:booklive.jp {title} {au}")
        except Exception as e:
            print(f"★検索失敗で中断(再実行で再開可): {e}")
            break
        tn = norm(title)
        hits = list(res.get("results") or [])
        # ★第2クエリ(2026-08-20 ユーザGO②): 「題+著者」がtitle_id候補0なら題のみで再検索。
        #   precisionは商品頁ゲート(カテゴリ=マンガ+著者JSON-LD照合)が担保する。
        if not any(re.search(r"title_id/(\d+)", h.get("url", "")) for h in hits):
            try:
                res2 = search(f"site:booklive.jp {title}")
                hits += list(res2.get("results") or [])
            except Exception as e:
                print(f"★検索失敗で中断(再実行で再開可): {e}")
                break
        cand = {}
        for h in hits:
            m = re.search(r"title_id/(\d+)", h.get("url", ""))
            if not m:
                continue
            raw = re.sub(r"[|｜].*$", "", h.get("title", ""))
            # ★型1(2026-08-20): 検索結果題の「 - 著者名」等の末尾セグメントを剥ぐ(473件が偽保留だった)
            raw = re.sub(r"\s+[-–]\s+[^-–]*$", "", raw)
            ht = norm(raw)
            ht = re.sub(r"(【[^】]*】|\d+巻?$|第\d+巻)", "", ht)
            ht = re.sub(r"(上|中|下)巻?$", "", ht)  # ★型2: 上/下/中巻suffix
            exact = (ht == tn) or ht.startswith(tn + "1") or (tn == re.sub(r"\d+$", "", ht))
            au_ok = (not au) or (norm(au)[:4] and norm(au)[:4] in norm(h.get("title", "") + h.get("snippet", "")))
            cand.setdefault(m.group(1), {"exact": False, "au": False, "ev": h.get("title", "")[:60]})
            if exact:
                cand[m.group(1)]["exact"] = True
            if au_ok:
                cand[m.group(1)]["au"] = True
        strong = prefer_bound([tid for tid, c in cand.items() if c["exact"] and c["au"]], cand)
        # ★型3(2026-08-20): exact一意だがsnippetに著者が出ないだけの候補は商品頁著者で裁定する
        gate_note = ""
        if not strong:
            ex_only = prefer_bound([tid for tid, c in cand.items() if c["exact"]], cand)
            if len(ex_only) == 1:
                strong = ex_only
                gate_note = "+au未確認(商品頁で裁定)"
        if len(strong) == 1 and head_ok(f"{strong[0]}_001"):
            # ★商品頁ゲート: ラノベ/小説カテゴリ排除(領民0人型)+著者最終確認
            gv, gd = product_gate(strong[0], au)
            if gv == "ok":
                rec = {"slug": slug, "title": title, "title_id": strong[0],
                       "cid1": f"{strong[0]}_001", "verified": f"head200+category({gd})",
                       "evidence": cand[strong[0]]["ev"] + gate_note, "at": time.strftime("%Y-%m-%d")}
                seed.write(json.dumps(rec, ensure_ascii=False) + "\n")
                seed.flush()
                n_ok += 1
                print(f"  OK {slug} → {strong[0]} ({gd})", flush=True)
            else:
                reason = {"novel": "ラノベ/小説", "author_ng": "著者不一致(商品頁)", "fetch_ng": "商品頁取得失敗"}[gv]
                holds.write(f"{slug}\t{title}\t{au}\t{reason}\t{json.dumps(cand, ensure_ascii=False).replace(chr(9),' ').replace(chr(10),' ')} gate={gd}\n")
                holds.flush()
                n_hold += 1
            if att:
                att.write(slug + "\n")
                att.flush()
            time.sleep(1.0)
            continue
        else:
            reason = "候補0" if not cand else ("完全一致なし" if not strong else ("複数候補" if len(strong) > 1 else "HEAD失敗"))
            # ★[:200]切り詰め禁止(2026-07-18実害: 9,674保留の候補が評価不能化していた)。タブ/改行だけ潰して全量書く
            holds.write(f"{slug}\t{title}\t{au}\t{reason}\t{json.dumps(cand, ensure_ascii=False).replace(chr(9),' ').replace(chr(10),' ')}\n")
            holds.flush()
            n_hold += 1
        if att:  # ★試行完了後に記録(検索失敗breakの取りこぼしを防ぐ)
            att.write(slug + "\n")
            att.flush()
        time.sleep(1.0)
    if list_file:
        dedupe_holds_keep_last()
    print(f"収集 {n_ok} / 保留 {n_hold} (seed={os.path.relpath(SEED, ROOT)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--accept", help="slug=title_id 形式で保留を手動採用")
    ap.add_argument("--accept-file", help="一括採用TSV(slug<TAB>title_id)。裁定済み前提・HEADゲート同等")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--resolve-holds", action="store_true", help="保留(複数候補)へ分冊版除外規則を適用し一意化できた分を採用")
    ap.add_argument("--expand", action="store_true", help="アンカー済みシリーズを全巻展開(検索不要)")
    ap.add_argument("--expand-limit", type=int, default=50, help="--expand で処理するシリーズ数上限")
    ap.add_argument("--list-file", help="対象slugリスト(1行1slug、ファイル順=呼び手が並べる)。索引順選定を使わない")
    ap.add_argument("--retry-holds", action="store_true", help="--list-file時、保留済みも再検索(古い保留行は最終結果で置換)")
    a = ap.parse_args()
    if a.resolve_holds:
        anch = set()
        if os.path.exists(SEED):
            for l in open(SEED, encoding="utf-8"):
                anch.add(json.loads(l)["slug"])
        rows = open(HOLDS, encoding="utf-8").readlines() if os.path.exists(HOLDS) else []
        seedf = open(SEED, "a", encoding="utf-8")
        resolved = set()
        n_try = n_ok2 = 0
        for l in rows:
            pcs = l.rstrip().split(chr(9))
            if len(pcs) < 5 or pcs[3] != "複数候補" or pcs[0] in anch:
                continue
            try:
                cand = json.loads(pcs[4])
            except Exception:
                continue
            strong = prefer_bound([t for t, c in cand.items() if c.get("exact") and c.get("au")], cand)
            if len(strong) != 1:
                continue
            n_try += 1
            if head_ok(f"{strong[0]}_001"):
                rec = {"slug": pcs[0], "title": pcs[1], "title_id": strong[0],
                       "cid1": f"{strong[0]}_001", "verified": "head200",
                       "evidence": cand[strong[0]].get("ev", "") + " [resolve-holds:分冊版除外]",
                       "at": time.strftime("%Y-%m-%d")}
                seedf.write(json.dumps(rec, ensure_ascii=False) + chr(10))
                seedf.flush()
                resolved.add(pcs[0])
                n_ok2 += 1
                if n_ok2 % 25 == 0:
                    print(f"  …{n_ok2}件採用", flush=True)
            time.sleep(0.2)
        seedf.close()
        if resolved:
            keep = [l for l in rows if l.split(chr(9), 1)[0] not in resolved]
            open(HOLDS, "w", encoding="utf-8").writelines(keep)
        print(f"resolve-holds: 対象{n_try} → 採用{n_ok2}(HEAD検証済)。保留から{len(resolved)}行除去")
        return

    if a.stats:
        done, holds = load_done()
        vol_done = load_volumes_done()
        n_by_slug = volume_target_n()
        checked = load_vol_checked()
        vol_rows = sum(len(v) for v in vol_done.values())
        # ★完了=全1..nがchecked(200/404問わず)。残=未チェック巻ありのアンカー数(=真のキュー長)
        anchored = [s for s in done if n_by_slug.get(s)]
        remain = sum(1 for s in anchored
                     if not all(v in checked.get(s, set()) for v in range(1, n_by_slug[s] + 1)))
        print(f"収集済(アンカー) {len(done)} / 保留 {len(holds)}")
        print(f"全巻展開 = {vol_rows}巻hit / チェック済台帳 {sum(len(v) for v in checked.values())}巻")
        print(f"★expandキュー残 = {remain} / {len(anchored)} アンカー(=未チェック巻あり。0で枯れる)")
        return
    if a.expand:
        expand_volumes(a.expand_limit)
        return
    if a.review:
        if os.path.exists(HOLDS):
            print(open(HOLDS, encoding="utf-8").read())
        return
    if a.accept_file:
        # ★一括採用(2026-07-18 保留裁定バッチ用): TSV(slug<TAB>title_id)を1行ずつ --accept と同じ保証で処理
        #   (HEAD200ゲート/seed追記/保留行除去)。裁定自体はAIが済ませた前提=このscriptは検証と簿記のみ。
        pairs = []
        seen_seed = set()
        if os.path.exists(SEED):
            for l in open(SEED, encoding="utf-8"):
                try: seen_seed.add(json.loads(l)["slug"])
                except Exception: pass
        for l in open(a.accept_file, encoding="utf-8"):
            c = l.rstrip("\n").split("\t")
            if len(c) >= 2 and c[0] and not c[0].startswith("#") and c[0] not in seen_seed:
                pairs.append((c[0], c[1]))
        print(f"一括採用: 対象{len(pairs)}(seed既存はskip済)")
        ok_pairs, ng = [], 0
        # ★2026-08-29: 8並列HEADをやめ直列に(BookLive規制事故の是正。 check_cid が間隔を守る)
        for s, t in pairs:
            try:
                if check_cid(f"{t}_001"): ok_pairs.append((s, t))
                else: ng += 1
            except Blocked as e:
                print(f"★中断: BookLiveから200/404以外の応答 ({e})。ここまでの分だけ採用する。",
                      file=sys.stderr)
                break
        with open(SEED, "a", encoding="utf-8") as f:
            for s, t in ok_pairs:
                f.write(json.dumps({"slug": s, "title_id": t, "cid1": f"{t}_001",
                                    "verified": "head200+manual", "at": time.strftime("%Y-%m-%d")},
                                   ensure_ascii=False) + "\n")
        done = {s for s, _ in ok_pairs}
        if os.path.exists(HOLDS):
            lines = [l for l in open(HOLDS, encoding="utf-8") if l.split("\t", 1)[0] not in done]
            open(HOLDS, "w", encoding="utf-8").writelines(lines)
        print(f"採用 {len(ok_pairs)} / HEAD失敗 {ng} (失敗分は保留のまま)")
        return
    if a.accept:
        slug, tid = a.accept.split("=", 1)
        if not head_ok(f"{tid}_001"):
            print("★HEAD失敗=採用しない")
            sys.exit(1)
        with open(SEED, "a", encoding="utf-8") as f:
            f.write(json.dumps({"slug": slug, "title_id": tid, "cid1": f"{tid}_001",
                                "verified": "head200+manual", "at": time.strftime("%Y-%m-%d")},
                               ensure_ascii=False) + "\n")
        # 保留行を除去
        if os.path.exists(HOLDS):
            lines = [l for l in open(HOLDS, encoding="utf-8") if not l.startswith(slug + "\t")]
            open(HOLDS, "w", encoding="utf-8").writelines(lines)
        print("採用:", slug, tid)
        return
    harvest(a.limit, list_file=a.list_file, retry_holds=a.retry_holds)


if __name__ == "__main__":
    main()
