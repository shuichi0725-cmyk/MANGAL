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
import argparse, gzip, json, os, re, sys, time, unicodedata, urllib.request
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


def head_ok(cid):
    try:
        req = urllib.request.Request(f"https://booklive.jp/bviewer/s/?cid={cid}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=20).status == 200
    except Exception:
        return False


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


def expand_volumes(expand_limit, workers=8):
    """アンカー済み(title_id確定)シリーズを対象に、TinyFish検索なしでHEADのみ全巻展開する。
    ★HEADは並列8本(2026-07-13)。BookLive=大手CDNの軽いHEADのみなので安全。
    ★2026-07-20: checked台帳で200/404両方を記録。完了=全1..nがchecked(ヒット数でなく)。
    これで404欠け巻の無限再チェックと後方飢餓を解消し、ループが実際に枯れる。"""
    from concurrent.futures import ThreadPoolExecutor

    anchors, _ = load_done()
    n_by_slug = volume_target_n()
    checked = load_vol_checked()
    os.makedirs(os.path.dirname(VOL_CHECKED), exist_ok=True)
    targets = []
    for slug, rec in anchors.items():
        n = n_by_slug.get(slug)
        if not n:
            continue
        ck = checked.get(slug, set())
        if all(v in ck for v in range(1, n + 1)):
            continue  # 全巻チェック済み(200/404問わず)=完了
        targets.append((slug, rec["title_id"], n, ck))
    remaining = len(targets)
    targets = targets[:expand_limit]
    print(f"展開対象 {len(targets)} シリーズ(未チェック巻あり・残 {remaining}) / HEAD {workers}並列", flush=True)
    out = gzip.open(VOLSEED, "at", encoding="utf-8")
    ckout = open(VOL_CHECKED, "a", encoding="utf-8")
    total_new = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for slug, tid, n, ck in targets:
            todo = [v for v in range(1, n + 1) if v not in ck]
            results = list(pool.map(lambda v: (v, head_ok(f"{tid}_{v:03d}")), todo))
            added = 0
            for vol, ok in results:
                ckout.write(json.dumps({"slug": slug, "v": vol}, ensure_ascii=False) + "\n")  # 200も404も記録
                if ok:
                    rec = {"slug": slug, "volume": vol, "title_id": tid, "cid": f"{tid}_{vol:03d}",
                           "verified": "head200", "at": time.strftime("%Y-%m-%d")}
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    added += 1
            out.flush(); ckout.flush()
            total_new += added
            print(f"  {slug}: +{added}hit/{len(todo)}chk (n={n})", flush=True)
            time.sleep(0.2)
    print(f"展開完了 +{total_new}巻 hit (seed={os.path.relpath(VOLSEED, ROOT)})")


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
        cand = {}
        for h in (res.get("results") or []):
            m = re.search(r"title_id/(\d+)", h.get("url", ""))
            if not m:
                continue
            ht = norm(re.sub(r"[|｜].*$", "", h.get("title", "")))
            ht = re.sub(r"(【[^】]*】|\d+巻?$|第\d+巻)", "", ht)
            exact = (ht == tn) or ht.startswith(tn + "1") or (tn == re.sub(r"\d+$", "", ht))
            au_ok = (not au) or (norm(au)[:4] and norm(au)[:4] in norm(h.get("title", "") + h.get("snippet", "")))
            cand.setdefault(m.group(1), {"exact": False, "au": False, "ev": h.get("title", "")[:60]})
            if exact:
                cand[m.group(1)]["exact"] = True
            if au_ok:
                cand[m.group(1)]["au"] = True
        strong = prefer_bound([tid for tid, c in cand.items() if c["exact"] and c["au"]], cand)
        if len(strong) == 1 and head_ok(f"{strong[0]}_001"):
            rec = {"slug": slug, "title": title, "title_id": strong[0],
                   "cid1": f"{strong[0]}_001", "verified": "head200",
                   "evidence": cand[strong[0]]["ev"], "at": time.strftime("%Y-%m-%d")}
            seed.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seed.flush()
            n_ok += 1
            print(f"  OK {slug} → {strong[0]}", flush=True)
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
        import concurrent.futures as _cf
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
        with _cf.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(head_ok, f"{t}_001"): (s, t) for s, t in pairs}
            for fu in _cf.as_completed(futs):
                s, t = futs[fu]
                try:
                    if fu.result(): ok_pairs.append((s, t))
                    else: ng += 1
                except Exception: ng += 1
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
