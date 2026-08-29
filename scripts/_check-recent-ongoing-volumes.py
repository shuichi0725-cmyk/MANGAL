"""★連載中で最終巻が新しい作品の **末尾続刊 + 途中欠番** を楽天で一括点検(read-only)。

背景(2026-07-28 ユーザ指摘の「彼女の友達」で発覚):
  先行調査は「最終巻が2023年以前の3,367作」しか見ておらず、
  ★**最終巻が2024年以降の連載中 7,719作が丸ごと未検査**だった。 実例:
    - 白竜HADOU  当方48巻 / 実際49巻(2026-07) = 末尾の取りこぼし
    - 彼女の友達  当方1,2,3,4,6巻 = **5巻が欠番** かつ **7巻(2026-07)も未取得**
  つまりこの層は「末尾」と「途中欠番」の**両方**が起きる。 片方だけ見る検出器では拾えない。

判定(先行調査で潰した誤検出型をそのまま継承):
  ① size=コミック 必須      … ラノベ原作の小説巻を続刊と誤認しない
  ② same_series ゲート     … 「白竜」に対する「白竜HADOU」等の続編シリーズを弾く
  ③ セット/合本/分冊版 除外  … 既刊の詰め合わせ・電子の話売りを弾く
  ④ 著者一致ゲート          … 同名別作を弾く
  ⑤ 原作者名義のみゲート     … ★2026-08-29追加。 候補の著者が**全員 原作者**(作画者が1人も居ない)なら
                            小説の疑いとして弾く。 ①のsizeゲートと④の著者ゲートは
                            **帯救済(ISBN出版者記号一致)**で貫通するが、原作小説は同じ版元から出るので
                            帯では区別できなかった(断罪された悪役令嬢の9巻=原作ラノベ が通ってしまった)。

出力2種:
  TRAIL = 当方最大巻より大きい巻が実在(末尾の取りこぼし)
  GAP   = 当方最大巻**以下**なのに当方に無い巻が実在(途中欠番)
★取りこぼし方向にのみ誤る設計: 楽天に無い巻は「無い」と報告するだけで、当方に在る巻を消す判断はしない。

resumable(1作ごとjsonl追記)。 rate=_lookup.py の gate(1.3秒/host)。
usage: python scripts/_check-recent-ongoing-volumes.py [--limit N]
出力: .cache/recent-ongoing-volumes.jsonl

★2026-07-29 柱化(ユーザ裁定「逆照合を柱にして」= idle-run 柱⑨):
  日次蒸留は「未来窓の増加分」しか見ない前方視で、初回baseline切り捨て+発売済み+表記揺れの
  3つの穴があった(07-28実測: 同窓で日次73巻 vs 逆照合~940巻)。この逆方向照合(継続中頁→楽天題検索)を
  後方の安全網として常設する。
  --build-queue = queueを本番索引から再算出(status=連載中/休載の全頁を統一queue化。旧2分割を廃止)。
    既存の走行結果(.cache/recent-ongoing-volumes.jsonl)は .cache/zokkan-cycles/ へ日付付きrotate=次周回開始。
  運転(Sonnet)= --limit 200 を1バッチに再起動で続き。queue枯れ=一巡完了(自然停止)。
  ★収集のみ。登録(種4)は scripts/_zokkan-register.py = 上位モデル専権(ゲート+GO運用)。
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "recent-ongoing.json"
OUT = ROOT / ".cache" / "recent-ongoing-volumes.jsonl"

_c = importlib.util.spec_from_file_location("chk", str(ROOT / "scripts" / "_check-ongoing-continuation.py"))
C = importlib.util.module_from_spec(_c)
_c.loader.exec_module(C)          # norm / volnum / same_series / NOISE / author_ok を共用
L = C.L

# ★2026-08-05 巻抜けハントの教訓を移植(怪物事変/SERVAMP/アラフォー賢者で実証した4盲点):
#   ①剥き題クエリ = 頁題の括弧読み「怪物(けもの)事変」を生で投げると楽天0件=「異常なし」に誤記帳
#   ②truncated時プローブ = 分冊版等が30件枠を埋めると単行本が枠外に沈む→「題+巻数」で個別追撃
#   ③帯救済 = size=単行本(B6判コミックス型)と著者不一致(作画交代型)はISBN帯一致なら通す
#   ④near記録 = ゲートで弾いた候補を痕跡に残す(fail-visible。黙って捨てると後から検死できない)
import re as _re

_PAREN = _re.compile(r"[(（][^)）]{1,12}[)）]")
# 楽天の著者欄の区切り(「原作者/作画者」形式)
_AUSPLIT = _re.compile(r"[/／、,，・･]| ")


_ORIG_CACHE = {}


def _orig_authors_of(slug):
    """頁の original_authors を読む(queueに無い時のfallback)。"""
    if slug in _ORIG_CACHE:
        return _ORIG_CACHE[slug]
    out = []
    p = ROOT / "data" / "manga.v2" / f"{slug}.yml"
    if slug and p.exists():
        try:
            import yaml as _y
            d = _y.safe_load(p.open(encoding="utf-8")) or {}
            out = [a.get("name") for a in (d.get("original_authors") or []) if a.get("name")]
        except Exception:
            out = []
    _ORIG_CACHE[slug] = out
    return out


def novel_suspect(row, author_str):
    """★原作小説の巻を続刊と誤認しないゲート (2026-08-29 新設)。

    実害: 「断罪された悪役令嬢は、逆行して完璧な悪女を目指す」の9巻枠に**原作ラノベ**が入った
      (ユーザ報告「9巻だけラノベ汚染」)。原因は下の**帯救済**=「ISBN出版者記号が一致すれば
      著者不一致でも通す(作画交代型の救済)」で、小説は同じ版元から出るので帯が一致してしまう。

    判定: 頁が**原作者と作画者を別々に**持つ時、候補の著者欄に載っている人が
      **全員が原作者**(=作画者が1人も居ない)なら小説の疑い → 帯が一致しても通さない。
      ★作画交代型は「原作者 + **新しい**作画者」の2名以上になるので、このゲートには当たらない。
    """
    ors = row.get("orig_authors")
    if ors is None:
        # ★旧queue(2026-08-29以前に --build-queue した .cache/recent-ongoing.json)は
        #   orig_authors を持たない。 queue再算出を待たずに効かせるため頁から読み直す。
        ors = _orig_authors_of(row.get("slug"))
        row["orig_authors"] = ors
    ors = [x for x in (ors or []) if x]
    aus = [x for x in (row.get("authors") or []) if x]
    if not ors or not aus:
        return False
    if C.author_ok(aus, author_str):
        return False                     # 作画者が載っている = 正常
    names = [n for n in _AUSPLIT.split(str(author_str or "")) if n.strip()]
    if not names:
        return False
    # 載っている人が全員「原作者」なら小説疑い
    return all(C.author_ok(ors, n) for n in names)


def strip_paren(s):
    return _PAREN.sub("", str(s or "")).strip()


def series_match(base, found, subtitles=()):
    """same_series を 生題/剥き題 の両方で判定(括弧読み型対応)。
    ★subtitles=学習済み副題(君の刀型 2026-08-05): 頁既知ISBNのヒットに付く残余語=正当な副題として許可。"""
    if C.same_series(base, found):
        return True
    sb = strip_paren(base)
    if sb and sb != base and C.same_series(sb, found):
        return True
    nb = C.norm(found)
    for sub in subtitles:
        for nt0 in (C.norm(base), C.norm(strip_paren(base))):
            if nt0 and nb.startswith(nt0):
                resid = nb[len(nt0):]
                if sub and sub in resid:
                    resid = resid.replace(sub, "", 1)
                if C.RESIDUAL_OK.fullmatch(resid):
                    return True
    return False


def build_queue():
    """本番索引から queue を再算出(連載中+休載の全頁)。走行結果は日付rotateして次周回へ。"""
    import time
    import yaml
    idx = json.load((ROOT / "data" / "manga-list-index.json").open(encoding="utf-8"))
    fl = idx["f"]
    SI, TI, ST = fl.index("slug"), fl.index("title"), fl.index("status")
    targets = [(str(r[SI]), str(r[TI])) for r in idx["d"] if str(r[ST]) in ("ongoing", "hiatus")]
    rows = []
    for slug, title in targets:
        p = ROOT / "data" / "manga.v2" / f"{slug}.yml"
        if not p.exists():
            continue  # slug≠ファイル名(夜明け型)は少数=次周回に譲る
        d = yaml.safe_load(p.open(encoding="utf-8")) or {}
        vols = set()
        years = []
        bands = set()
        isbns = set()
        for e in d.get("editions") or []:
            for v in e.get("volumes") or []:
                if isinstance(v.get("number"), int):
                    vols.add(v["number"])
                rd = str(v.get("release_date") or "")
                if rd[:4].isdigit():
                    years.append(rd[:4])
                ib = str(v.get("isbn13") or "")
                if len(ib) == 13:
                    bands.add(ib[:8])   # ★ISBN出版者記号帯(帯救済ゲート用)
                    isbns.add(ib)       # ★既知ISBN(副題学習ゲート用)
        if not vols:
            continue
        aus = [a.get("name") for a in (d.get("authors") or []) if a.get("name")]
        # ★原作者(2026-08-29): 原作小説の巻を続刊と誤認しないゲート用。 [[novel_in_manga_page]]
        ors = [a.get("name") for a in (d.get("original_authors") or []) if a.get("name")]
        rows.append({"slug": slug, "title": title, "authors": aus, "orig_authors": ors,
                     "vols": sorted(vols), "last_year": max(years) if years else "",
                     "bands": sorted(bands), "isbns": sorted(isbns)})
    if OUT.exists():
        arc = ROOT / ".cache" / "zokkan-cycles"
        arc.mkdir(parents=True, exist_ok=True)
        OUT.rename(arc / f"recent-ongoing-volumes-{time.strftime('%Y%m%d-%H%M')}.jsonl")
        print(f"前周回の結果を {arc} へrotate")
    json.dump(rows, SRC.open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"queue再算出: {len(rows)}作(連載中/休載) → {SRC}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--build-queue", action="store_true", help="queueを本番索引から再算出+前周回rotate")
    a = ap.parse_args()
    if a.build_queue:
        build_queue()
        return

    rows = json.load(SRC.open(encoding="utf-8"))
    done = set()
    if OUT.exists():
        for ln in OUT.open(encoding="utf-8"):
            try:
                done.add(json.loads(ln)["slug"])
            except Exception:
                pass
    todo = [r for r in rows if r["slug"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"対象 {len(rows):,} / 既済 {len(done):,} / 今回 {len(todo):,} "
          f"(推定 {len(todo) * 1.3 / 60:.0f}分)", flush=True)

    env = L._env()
    ntr = ngp = 0
    with OUT.open("a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            have = set(r["vols"])
            mv = max(have) if have else 0
            bands = set(r.get("bands") or [])
            known = set(r.get("isbns") or [])
            subtitles = set()   # ★既知ISBNヒットの残余語=このシリーズの副題(君の刀型)
            trail, gap, near = [], [], []
            trunc = False
            seen_v = set()

            def learn(it):
                """既知ISBNのヒットから副題(残余語)を学習"""
                if str(it.get("isbn") or "") not in known:
                    return
                nb = C.norm(str(it.get("title") or ""))
                m2 = _re.search(r"[0-9]+$", nb)
                if m2:
                    nb = nb[: m2.start()]
                for nt0 in (C.norm(r["title"]), C.norm(strip_paren(r["title"]))):
                    if nt0 and nb.startswith(nt0) and len(nb) > len(nt0):
                        subtitles.add(nb[len(nt0):])

            def judge(it):
                """1候補をゲート審査。採用→(rec,'trail'/'gap') / 弾き→(near記録,None) / 対象外→(None,None)"""
                t, au = str(it.get("title") or ""), str(it.get("author") or "")
                if not series_match(r["title"], t, subtitles):
                    return None, None
                if C.NOISE.search(t):
                    return None, None
                v = C.volnum(t)
                if v is None or v in seen_v:
                    return None, None
                ib = str(it.get("isbn") or "")
                band_ok = bool(bands) and ib[:8] in bands
                size = str(it.get("size") or "")
                why = None
                if novel_suspect(r, au):
                    # ★帯救済より前に置く(帯一致でも通さない)。 小説は同じ版元から出るため
                    #   帯だけでは原作小説と作画交代を区別できない(2026-08-29 断罪…で実踏)。
                    why = f"原作者名義のみ({au[:16]})"
                elif size != "コミック" and not (size == "単行本" and band_ok):
                    why = f"size({size})"        # ★帯一致の単行本は救済(B6判コミックス型)
                elif not C.author_ok(r["authors"], au) and not band_ok:
                    why = f"著者({au[:16]})"      # ★帯一致なら著者不一致でも通す(作画交代型)
                if why:
                    if len(near) < 5:
                        near.append({"vol": v, "why": why, "isbn": ib, "title": t[:40]})
                    return None, None
                seen_v.add(v)
                rec = {"vol": v, "isbn": ib, "date": it.get("salesDate"), "title": t[:60]}
                return (rec, "trail") if v > mv else ((rec, "gap") if v not in have else (None, None))

            try:
                items = L.rakuten_live_retry(env, title=r["title"], hits=30) or []
                trunc = len(items) >= 30          # ★30件上限に当たった=長期連載は取りこぼしうる
                for it in items:
                    learn(it)
                for it in items:
                    rec, kind = judge(it)
                    if rec:
                        (trail if kind == "trail" else gap).append(rec)
                # ★剥き題フォールバック(怪物事変型): 生題で同シリーズ候補ゼロ かつ 題に括弧がある
                sp = strip_paren(r["title"])
                if not seen_v and not near and sp != r["title"]:
                    for it in L.rakuten_live_retry(env, title=sp, hits=30) or []:
                        rec, kind = judge(it)
                        if rec:
                            (trail if kind == "trail" else gap).append(rec)
                # ★truncated時の末尾プローブ(SERVAMP型): 枠がノイズで埋まると単行本が沈む
                #   → 「題+巻数」で mv+1 から連続2ミスまで個別追撃(上限+15)
                if trunc and not trail:
                    miss = 0
                    v = mv + 1
                    q = sp if sp != r["title"] else r["title"]
                    while miss < 2 and v <= mv + 15:
                        hit = False
                        for it in L.rakuten_live_retry(env, title=f"{q} {v}", hits=10) or []:
                            rec, kind = judge(it)
                            if rec and rec["vol"] == v:
                                (trail if kind == "trail" else gap).append(rec)
                                hit = True
                                break
                        miss = 0 if hit else miss + 1
                        v += 1
            except Exception as e:
                print(f"    ✗ {r['slug']} {str(e)[:60]}", flush=True)
            if trail:
                ntr += 1
            if gap:
                ngp += 1
            f.write(json.dumps({"slug": r["slug"], "title": r["title"], "our_max": mv,
                                "our_vols": sorted(have), "trail": trail, "gap": gap,
                                "truncated": trunc, "near": near}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 200 == 0:
                print(f"  {i:,}/{len(todo):,}  末尾{ntr:,} / 欠番{ngp:,}", flush=True)
    print(f"\n完了 {len(todo):,}作 / ★末尾続刊あり {ntr:,} / ★途中欠番あり {ngp:,} → {OUT}")


if __name__ == "__main__":
    main()
