#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巻説明(volume-desc)の材料収集 (= skill volume-desc の Step1)

対象slugの全巻ISBNについて楽天の紹介文(itemCaption+contents)を
キャッシュ(preorders→rakuten-isbn-delta 1パス)→live の順で集め、AI生成用の材料jsonlを書く。
  出力: .cache/voldesc/materials.jsonl
    {slug, title, authors, vols: [{vol, isbn, edition, caption, contents}], missing: [{vol, isbn, edition}]}
既に seed(data/seeds/volume-desc-ja.jsonl) に説明があるISBNは対象から除外(純粋追加運用)。
使い方:
  python scripts/_voldesc-material.py --slugs a,b,c [--live]
  python scripts/_voldesc-material.py --slugs-file list.txt [--live]   # 大量時(WinError206回避)
  python scripts/_voldesc-material.py [--take 100] [--live]            # ★auto: slug無し=端から順(ファイル名順)に
                                                                       #   seed未生成の巻を--take件ぶん自動選定(人気順禁止方針)
レート: live 1.2s/req・429即中断。auto再開はcursor不要(seed既存ISBN除外が実質cursor)。
"""
import argparse, glob as _g, json, os, re, sys, time, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(f"{ROOT}/.cache/voldesc", exist_ok=True)
OUT = f"{ROOT}/.cache/voldesc/materials.jsonl"
SEED = f"{ROOT}/data/seeds/volume-desc-ja.jsonl"
DELTA = f"{ROOT}/.cache/rakuten-isbn-delta.jsonl"
# ★ローカル楽天キャッシュは2本ある(deltaだけだとliveに落ちる)。両方をローカル層で舐める。
#   rakuten-isbn.jsonl(373MB・歴史harvest全件)と delta(828MB・新着差分)は別カバレッジ。
#   測定: R6のcaption 119件中110件(92%)が rakuten-isbn.jsonl 側に在り、liveはほぼ不要だった。
RFULL = f"{ROOT}/.cache/rakuten-isbn.jsonl"
LOCAL_RAKUTEN = [p for p in (RFULL, DELTA) if os.path.exists(p)]
# ★材料なし(caption無しと確定)ISBNの蓄積台帳。auto除外に加えてカーソルを真に前進させる
# (無いと材料なし巻を毎回先頭から再照会し、蓄積で--take枠を食い潰して停滞する)。単発実行は無影響。
NOMAT = f"{ROOT}/.cache/voldesc/no-material.txt"

ap = argparse.ArgumentParser()
ap.add_argument("--slugs")
ap.add_argument("--slugs-file")
ap.add_argument("--src", default="data/manga.v2")
ap.add_argument("--live", action="store_true")
ap.add_argument("--local-only", dest="local_only", action="store_true",
                help="liveを一切叩かず、ローカル2本に無い=材料なしとして台帳記録(bulk用・実測で局所未収=captionほぼ皆無)")
ap.add_argument("--limit", type=int, default=10**9)
ap.add_argument("--take", type=int, default=100, help="autoモードで集める未生成巻数の目安")
ap.add_argument("--recheck-nomaterial", type=int, metavar="N", default=0,
                help="材料なし台帳(no-material.txt)の先頭N件を★live再照会し、captionが在れば救済"
                     "(cache追加+台帳から除去)。ローカル未収=材料なしの偽陰性(実測10%)を回収する常設パス。")
a = ap.parse_args()

# 既seedのISBNは除外(純粋追加)。★seed_only=説明済み判定用(NOMATを混ぜない)
done = set()
seed_only = set()
if os.path.exists(SEED):
    for ln in open(SEED, encoding="utf-8"):
        try:
            ib = json.loads(ln)["isbn13"]
            done.add(ib); seed_only.add(ib)
        except Exception:
            pass
# ★材料なし確定ISBNも除外(=カーソル前進・再照会防止)
if os.path.exists(NOMAT):
    for ln in open(NOMAT, encoding="utf-8"):
        ib = ln.strip()
        if len(ib) == 13:
            done.add(ib)

def primary_volumes(d):
    """★主版選定(2026-07-22 ユーザ裁定): 巻説明の対象=「最初に出た通常版」の巻だけ。
    他版(文庫合本・新装・全集等)は対象外。ただし主版巻のcaptionが無い時だけ、
    同じ巻番号の他版captionをフォールバック材料に使う(別巻割の巻は考慮しない)。
    選定 = type==standard のうち最古発売の版。standard皆無なら全版から最古。"""
    eds = [e for e in (d.get("editions") or []) if e.get("volumes")]
    def first_date(e):
        ds = [str(v.get("release_date") or "9999") for v in e["volumes"] if v.get("release_date")]
        return min(ds) if ds else "9999"
    cands = [e for e in eds if e.get("type") == "standard"] or eds
    if not cands:
        return None, []
    prim = min(cands, key=first_date)
    return prim, list(prim["volumes"])


def target_volumes(d):
    """★対象巻の共通選定(2026-07-22): 主版の各巻について
    - 同じ巻番号がどこかの刷(versions)/他版で説明済み(seed) → 巻として完了=対象外(二重生成防止。うる星=新装カバー刷に34巻分既存の型)
    - 主版ISBNが材料なし確定(NOMAT) → 対象外
    それ以外を {vol, isbn, edition, alt_isbns} で返す。alt_isbns=同巻番号の全代替ISBN(他版+全刷)。"""
    prim, pvols = primary_volumes(d)
    if prim is None:
        return []
    alt_by_num = {}
    def _collect(vlist):
        for v in vlist or []:
            ib = str(v.get("isbn13") or ""); n = v.get("number")
            if len(ib) == 13 and n is not None:
                alt_by_num.setdefault(n, []).append(ib)
    for e in d.get("editions") or []:
        if e is not prim:
            _collect(e.get("volumes"))
        for vv in e.get("versions") or []:
            _collect(vv.get("volumes"))
    out = []
    prim_ibs = {str(v.get("isbn13") or "") for v in pvols}
    for v in pvols:
        ib = str(v.get("isbn13") or "")
        if len(ib) != 13:
            continue
        alts = [a2 for a2 in alt_by_num.get(v.get("number"), []) if a2 != ib and a2 not in prim_ibs]
        if ib in seed_only or any(a2 in seed_only for a2 in alts):
            continue  # 巻としてどこかに説明済み
        if ib in done:
            continue  # 材料なし確定(NOMAT)含む
        out.append({"vol": v.get("number"), "isbn": ib,
                    "edition": prim.get("type"), "alt_isbns": alts})
    return out


slugs = []
if a.slugs:
    slugs = [s.strip() for s in a.slugs.split(",") if s.strip()]
if a.slugs_file:
    slugs += [s.strip() for s in open(a.slugs_file, encoding="utf-8") if s.strip()]
if not slugs and not a.recheck_nomaterial:
    # ★auto: ファイル名順(=端から全件、人気順禁止 [[feedback_no_popularity_priority]])に
    #   seed未生成ISBNを持つ頁を --take 巻ぶん選定。seed除外が実質cursorなので再実行=続きから。
    n_isbn = 0
    for p in sorted(_g.glob(os.path.join(ROOT, a.src, "*.yml"))):
        if n_isbn >= a.take:
            break
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
        except Exception:
            continue
        fresh = [v["isbn"] for v in target_volumes(d)]  # ★主版×巻グループ判定(2026-07-22)
        if fresh:
            slugs.append(os.path.basename(p)[:-4])
            n_isbn += len(fresh)
    print(f"auto選定: {len(slugs)}頁 / ~{n_isbn}巻 (ファイル名順・seed未生成のみ)")
slugs = slugs[: a.limit]

env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
ORIGIN = env.get("RAKUTEN_REFERER", "").rstrip("/")


def live_item(isbn):
    q = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "isbn": isbn, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(q))
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        items = d.get("Items") or []
        return items[0] if items else None
    except Exception as e:
        if "429" in str(e):
            print("★429→中断"); sys.exit(2)
        return None


# ==== recheck モード: 材料なし台帳をlive再照会して偽陰性を救済 ====
#   ローカルキャッシュは harvest 履歴=全楽天ではないため、--local-only 時のローカル未収を
#   「材料なし」と恒久記録してしまう(実測10%が実はlive有)。ここで live で拾い直す。
#   冪等(台帳に残る分だけ照会)・逐次保存(1件ごとにcache追記+台帳書換)・429即中断=アイドル運転安全。
if a.recheck_nomaterial:
    if not os.path.exists(NOMAT):
        print("no-material.txt 無し=対象なし"); sys.exit(0)
    todo = [l.strip() for l in open(NOMAT, encoding="utf-8") if len(l.strip()) == 13]
    batch = todo[: a.recheck_nomaterial]
    print(f"recheck: 台帳 {len(todo)}件 の先頭 {len(batch)}件を live再照会 (~{len(batch)*1.2/60:.0f}分)")
    CAPCACHE = f"{ROOT}/.cache/voldesc/captions-cache.jsonl"
    cached = set()
    if os.path.exists(CAPCACHE):
        for ln in open(CAPCACHE, encoding="utf-8"):
            try:
                cached.add(json.loads(ln)["isbn"])
            except Exception:
                pass
    recovered, checked = {}, set()
    RECOV = f"{ROOT}/.cache/voldesc/recovered.jsonl"   # 救済分(Opusが説明を書く材料)
    fo_r = open(RECOV, "a", encoding="utf-8")
    fo_c = open(CAPCACHE, "a", encoding="utf-8")
    for i, ib in enumerate(batch):
        checked.add(ib)
        item = live_item(ib)
        cap = (item.get("itemCaption") or "").strip() if item else ""
        if cap:
            recovered[ib] = cap
            if ib not in cached:
                fo_c.write(json.dumps({"isbn": ib, "caption": cap}, ensure_ascii=False) + "\n"); fo_c.flush()
                cached.add(ib)
            fo_r.write(json.dumps({"isbn": ib, "caption": cap,
                                   "contents": (item.get("contents") or "").strip(),
                                   "title": item.get("title")}, ensure_ascii=False) + "\n"); fo_r.flush()
        time.sleep(1.2)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(batch)} 救済 {len(recovered)}")
    fo_r.close(); fo_c.close()
    # 台帳を更新: 照会済み(checked)は台帳から落とす(救済も"cap無し確定"も、もう再照会不要)
    remain = [ib for ib in todo if ib not in checked]
    with open(NOMAT, "w", encoding="utf-8") as f:
        f.write("\n".join(remain) + ("\n" if remain else ""))
    print(f"recheck完了: 照会 {len(batch)} / 救済(caption回収) {len(recovered)} / 台帳 {len(todo)}→{len(remain)}")
    print(f"救済分 → {os.path.relpath(RECOV, ROOT)} (Opusがこれを材料に説明生成→_voldesc-apply)")
    sys.exit(0)

# 対象巻の収集(slug→[{vol,isbn,edition}])
pages, want = {}, set()
for slug in slugs:
    p = os.path.join(ROOT, a.src, slug + ".yml")
    if not os.path.exists(p):
        # slug-override頁: slugフィールドで探す前にSRC名前提なので警告のみ
        print(f"  ! 見つからない: {slug} (SRC stem名で指定する)"); continue
    d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
    # ★主版基準+巻グループ判定(2026-07-22): 共通ヘルパー target_volumes に集約
    vols = target_volumes(d)
    for v in vols:
        want.add(v["isbn"])
        want.update(v.get("alt_isbns") or [])  # 代替源もキャッシュ照合対象に(材料化のみ・生成対象ではない)
    pages[slug] = {"title": d.get("title"),
                   "authors": [x.get("name") for x in (d.get("authors") or [])],
                   "vols": vols}
print(f"対象 {len(pages)}頁 / 未生成ISBN {len(want)}件 (seed既存 {len(done)}件は除外)")

caps = {}  # isbn -> {"caption":..., "contents":...}

# 層1: 予約キャッシュ
pj = f"{ROOT}/.cache/preorders/preorders-latest.jsonl"
if os.path.exists(pj):
    for l in open(pj, encoding="utf-8"):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("isbn") in want and r.get("caption"):
            caps.setdefault(r["isbn"], {"caption": r["caption"], "contents": ""})

# 層1.5: 収集済み永続キャッシュ(captions-cache.jsonl = 過去収集+Sonnetアイドル救済分[recovered]も入る)。
#   ★ローカル専用運転(2026-07-21 ユーザ指示=生成セッションはliveを叩かない)の重要源。巨大2本より先に引く。
_cc_path = f"{ROOT}/.cache/voldesc/captions-cache.jsonl"
if os.path.exists(_cc_path):
    _cc_hit = 0
    _cc_rest = want - set(caps)
    for ln in open(_cc_path, encoding="utf-8"):
        try:
            _d = json.loads(ln)
        except Exception:
            continue
        _ib = _d.get("isbn")
        if _ib in _cc_rest and _ib not in caps and (_d.get("caption") or "").strip():
            caps[_ib] = {"caption": _d["caption"].strip(), "contents": ""}
            _cc_hit += 1
    print(f"captions-cache(救済分含む) 1パス: hit {_cc_hit}")

# 層2: ローカル楽天キャッシュ(rakuten-isbn.jsonl 373MB + delta 828MB)を順に1パス。
#   残り(rest)が尽きたら次ファイルは読まずに打ち切り(速い方から)。両方合わせてliveをほぼ消す。
for path in LOCAL_RAKUTEN:
    rest = want - set(caps)
    if not rest:
        break
    t0 = time.time()
    hit = 0
    for ln in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r'^\{"isbn": ?"(\d{13})"', ln)
        ib = m.group(1) if m else None
        if ib is None or ib in caps or ib not in rest:
            continue
        try:
            item = json.loads(ln).get("item") or {}
        except Exception:
            continue
        cap = (item.get("itemCaption") or "").strip()
        if cap:
            caps[ib] = {"caption": cap, "contents": (item.get("contents") or "").strip()}
            hit += 1
    print(f"{os.path.basename(path)} 1パス: hit {hit} ({time.time()-t0:.0f}秒)")

# 層3: live(残りだけ)
rest = sorted(want - set(caps))
if a.live and rest:
    print(f"live照会 {len(rest)}件 (~{len(rest)*1.2/60:.0f}分)")
    for i, ib in enumerate(rest):
        item = live_item(ib)
        if item:
            cap = (item.get("itemCaption") or "").strip()
            if cap:
                caps[ib] = {"caption": cap, "contents": (item.get("contents") or "").strip()}
        time.sleep(1.2)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(rest)}")

n_miss = 0
with open(OUT, "w", encoding="utf-8") as fo:
    for slug, pg in pages.items():
        vols, missing = [], []
        for v in pg["vols"]:
            c = caps.get(v["isbn"])
            src = v["isbn"]
            if not c:
                # ★同巻番号の他版captionをフォールバック(うる星型。説明の帰属は主版ISBNのまま)
                for aib in v.get("alt_isbns") or []:
                    if caps.get(aib):
                        c, src = caps[aib], aib
                        break
            vv = {k: v[k] for k in ("vol", "isbn", "edition")}
            if c:
                vols.append({**vv, "caption": c["caption"], "contents": c["contents"],
                             **({"caption_src": src} if src != v["isbn"] else {})})
            else:
                missing.append(vv)
        vols.sort(key=lambda x: (x["vol"] is None, x["vol"]))
        n_miss += len(missing)
        fo.write(json.dumps({"slug": slug, "title": pg["title"], "authors": pg["authors"],
                             "vols": vols, "missing": missing}, ensure_ascii=False) + "\n")
print(f"材料書出 → {OUT} (caption有 {len(caps)} / 材料なし {n_miss} = 欠落表へ)")

# ★収集した caption を永続キャッシュへ追記(applyの丸写しゲートがここを参照)。
#   materials.jsonl は毎回/スライス毎に上書きされるため、ゲートの照合元にすると
#   並列運転で他スライスのcaptionが見えず素通りする(2026-07-20 実測48件すり抜けの根因)。
CAPCACHE = f"{ROOT}/.cache/voldesc/captions-cache.jsonl"
_cached = set()
if os.path.exists(CAPCACHE):
    for ln in open(CAPCACHE, encoding="utf-8"):
        try:
            _cached.add(json.loads(ln)["isbn"])
        except Exception:
            pass
with open(CAPCACHE, "a", encoding="utf-8") as f:
    for ib, c in caps.items():
        if ib not in _cached:
            f.write(json.dumps({"isbn": ib, "caption": c["caption"]}, ensure_ascii=False) + "\n")

# ★このラウンドで材料なしと確定したISBNを台帳に追記(次回auto除外=カーソル前進)。
#   ただしlive未実行(--live無し)だと"未照会"を誤って材料なし扱いする恐れ→liveの時だけ記録。
if (a.live or a.local_only) and not a.slugs and not a.slugs_file:
    prev = set()
    if os.path.exists(NOMAT):
        prev = {l.strip() for l in open(NOMAT, encoding="utf-8") if l.strip()}
    add = [v["isbn"] for pg in pages.values() for v in pg["vols"]
           if v["isbn"] not in caps and not any(a2 in caps for a2 in (v.get("alt_isbns") or []))]
    new = [ib for ib in add if ib not in prev]
    if new:
        with open(NOMAT, "a", encoding="utf-8") as f:
            for ib in new:
                f.write(ib + "\n")
        print(f"材料なし台帳 +{len(new)}件 → {os.path.basename(NOMAT)} (累計 {len(prev)+len(new)})")
