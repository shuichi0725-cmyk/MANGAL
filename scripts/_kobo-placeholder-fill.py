# -*- coding: utf-8 -*-
"""仮書影(.gif)層を Kobo電子で埋める (= 2026-09-11 新設。HELLSING 2-4巻の per-case を型に展開)

★なぜ _kobo-covers.py で足りないか
  あちらの対象は「cover_url が**空**の巻」。この層は cover_url が**非null**(文字だけの .gif が
  入っている)ため、既存のどの書影監査にも出てこない。実測 9,412巻 / 3,037頁。
  照合ロジック(norm/VOLP/VOLP_BARE/kobo API)は _kobo-covers.py から import して再利用する。

★芯 = 「同じ頁に実物書影がある」1,410頁。装丁目視ゲートの比較元が取れる = HELLSING と同じ形。
  頁内が全部 .gif の 1,627頁は比較元が無いので別扱い(既定では queue に入れない)。

段取り:
  --build-queue        本番 data/manga.v2 を1パス走査して対象queueを作る(数分)
  --survey --limit N   Kobo に何巻あるかだけ数える(画像DLしない)。逐次保存・冪等再開
  --stats              現在地

出力:
  .cache/kobo-placeholder/queue.jsonl    対象(slug/title/gif巻/比較元)
  .cache/kobo-placeholder/survey.jsonl   1行1頁のKobo照合結果(hit巻番号→URL)
  .cache/kobo-placeholder/done.json      照会済みslug(冪等再開)
★このscriptは seed に書かない。書影の採否は装丁目視ゲートを通してから(別段)。
"""
import argparse
import importlib.util
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★照合ロジックは _kobo-covers.py の実装をそのまま使う(ハイフン名なので importlib)
_spec = importlib.util.spec_from_file_location("_kobo_covers", os.path.join(ROOT, "scripts", "_kobo-covers.py"))
_KC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_KC)

import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

KEEP = _KC.KEEP
OUTDIR = os.path.join(ROOT, ".cache", "kobo-placeholder")
QUEUE = os.path.join(OUTDIR, "queue.jsonl")
SURVEY = os.path.join(OUTDIR, "survey.jsonl")
DONE = os.path.join(OUTDIR, "done.json")
SRC = os.path.join(ROOT, "data", "manga.v2")
RE_GIF = re.compile(r"/(\d{13})\.gif")
os.makedirs(OUTDIR, exist_ok=True)


def is_placeholder(url: str) -> bool:
    return bool(url) and bool(RE_GIF.search(str(url)))


def build_queue(include_noanchor: bool) -> None:
    n_page = n_hit = 0
    with io.open(QUEUE, "w", encoding="utf-8", newline="\n") as out:
        for fn in sorted(os.listdir(SRC)):
            if not fn.endswith(".yml"):
                continue
            n_page += 1
            if n_page % 5000 == 0:
                print(f"  走査 {n_page} … 対象{n_hit}", flush=True)
            try:
                d = yaml.load(io.open(os.path.join(SRC, fn), encoding="utf-8"), Loader=L)
            except Exception:
                continue
            if not d:
                continue
            gif, real = [], []
            eds = {}  # ★版ごとの総巻数(= Kobo との突合ゲートに使う)
            for e in d.get("editions") or []:
                if e.get("type") not in KEEP:
                    continue
                et = e.get("type")
                nums = [v.get("number") for v in (e.get("volumes") or []) if v.get("number") is not None]
                eds[et] = {"total": len(nums), "max": max(nums) if nums else 0}
                for v in e.get("volumes") or []:
                    u = str(v.get("cover_url") or "")
                    ib = str(v.get("isbn13") or "")
                    if is_placeholder(u):
                        if len(ib) == 13 and v.get("number") is not None:
                            gif.append([et, v.get("number"), ib])
                    elif u:
                        real.append([et, v.get("number"), u])
            if not gif:
                continue
            if not real and not include_noanchor:
                continue
            n_hit += 1
            out.write(json.dumps({
                "slug": fn[:-4], "title": d.get("title"),
                "gif": gif, "anchor": real[:6], "n_gif": len(gif), "eds": eds,
            }, ensure_ascii=False) + "\n")
    print(f"queue作成: {n_hit}頁 (走査 {n_page}頁 / anchor無しを{'含む' if include_noanchor else '除外'})")


def kobo_retry(title: str, page: int) -> dict:
    """429 は backoff で吸収。連続429(実スロットル)だけ Throttled を投げる。"""
    for w in (0, 3, 8, 20, 45):
        if w:
            time.sleep(w)
        try:
            return _KC.kobo(title, page)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            print(f"    429 backoff {w}s", flush=True)
    raise RuntimeError("Throttled")


def survey(limit: int) -> None:
    if not os.path.exists(QUEUE):
        sys.exit("queue が無い。先に --build-queue")
    done = set(json.load(io.open(DONE, encoding="utf-8"))) if os.path.exists(DONE) else set()
    rows = [json.loads(l) for l in io.open(QUEUE, encoding="utf-8") if l.strip()]
    todo = [r for r in rows if r["slug"] not in done]
    print(f"queue {len(rows)}頁 / 済 {len(done)} / 残 {len(todo)} → 今回 {min(limit, len(todo))}", flush=True)
    n_hit = n_none = n_vol = 0
    out = io.open(SURVEY, "a", encoding="utf-8", newline="\n")
    try:
        for i, r in enumerate(todo[:limit], 1):
            slug, title = r["slug"], r["title"] or ""
            pt = _KC.norm(title)
            vols, bare = {}, {}
            pg = 1
            try:
                # ★Kobo側の総巻数を数えたいので「欲しい巻が揃ったら打ち切り」はしない
                #   (版ゲートが巻数一致を見るため、undercount は誤マッチを通してしまう)。
                #   代わりに「そのページで新しい一致が1件も増えなければ止める」= 実質2req で済む。
                while pg <= 4:
                    before = len(vols) + len(bare)
                    res = kobo_retry(title, pg)
                    for it in (res.get("Items") or []):
                        t2 = unicodedata.normalize("NFKC", str(it.get("title"))).strip()
                        img = str(it.get("largeImageUrl") or "")
                        if not img or "noimage" in img:
                            continue
                        m = _KC.VOLP.search(t2)
                        if m and _KC.norm(_KC.VOLP.sub("", t2)) == pt:
                            vols.setdefault(int(m.group(1)), img)
                            continue
                        mb = _KC.VOLP_BARE.search(t2)
                        if mb and _KC.norm(_KC.VOLP_BARE.sub("", t2)) == pt:
                            bare.setdefault(int(mb.group(1)), img)
                    if len(vols) + len(bare) == before:
                        break  # このページで新規一致ゼロ = 以降も出ない(関連度順)
                    pg += 1
                    time.sleep(1.3)
            except RuntimeError:
                print("★連続429 = 実スロットル。中断(残りは次回)", flush=True)
                break
            except Exception as e:
                print(f"  {slug}: kobo ERR {e}", flush=True)
                out.write(json.dumps({"slug": slug, "error": str(e)[:200]}, ensure_ascii=False) + "\n")
                out.flush()
                done.add(slug)
                continue
            if not vols and len(bare) >= 3:
                vols = bare  # 直結数字型(まるごし刑事69型)

            # ★版ゲート(2026-09-11 100億の男で発覚): 巻番号だけで突き合わせると、同一頁に
            #   通常版と文庫版が同居する時に「文庫3巻へ通常版3巻の書影」を付けてしまう。
            #   = [[kobo_cover_wrong_for_old_print]] のゴルゴ文庫(SPコミックス表紙混入)と同じ事故型。
            #   Koboがどの版を電子化したかは巻数でしか判らないので、**総巻数が一致する版にだけ**充当する。
            n_kobo = len(vols)
            eds = r.get("eds") or {}
            by_ed = {}
            for et, vn, ib in r["gif"]:
                by_ed.setdefault(et, []).append((int(vn), ib))
            ed_rows, fills = [], []
            for et, items in sorted(by_ed.items()):
                total_ed = (eds.get(et) or {}).get("total") or 0
                gate = "OK" if (n_kobo and total_ed == n_kobo) else "COUNT_MISMATCH"
                got = [(vn, ib, vols[vn]) for vn, ib in sorted(items) if vn in vols]
                ed_rows.append({"type": et, "total": total_ed, "n_gif": len(items),
                                "gate": gate, "n_match": len(got)})
                if gate == "OK":
                    fills += [{"type": et, "number": vn, "isbn13": ib, "cover_url": u} for vn, ib, u in got]
            out.write(json.dumps({
                "slug": slug, "title": title, "n_gif": r["n_gif"],
                "n_kobo": n_kobo, "editions": ed_rows,
                "n_hit": len(fills), "fills": fills,
                "anchor": r["anchor"][:1],
            }, ensure_ascii=False) + "\n")
            out.flush()
            done.add(slug)
            json.dump(sorted(done), io.open(DONE, "w", encoding="utf-8"))
            if fills:
                n_hit += 1
                n_vol += len(fills)
            else:
                n_none += 1
            if i % 25 == 0:
                print(f"  [{i}/{min(limit,len(todo))}] 充当可{n_hit}頁/{n_vol}巻 / 充当なし{n_none}", flush=True)
            time.sleep(1.3)
    finally:
        out.close()
        json.dump(sorted(done), io.open(DONE, "w", encoding="utf-8"))
    print(f"\n=== survey ===  hit頁 {n_hit} / 一致なし {n_none} / 充当可 {n_vol}巻", flush=True)


def dhash(path: str, size: int = 8) -> int:
    """差分ハッシュ(64bit)。縮小+グレースケールなので JPEG圧縮差・解像度差に強い。"""
    from PIL import Image
    im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.tobytes())  # mode "L" = 1バイト/画素の行優先。getdata()は Pillow14 で廃止
    bits = 0
    for r in range(size):
        row = px[r * (size + 1):(r + 1) * (size + 1)]
        for c in range(size):
            bits = (bits << 1) | (1 if row[c] < row[c + 1] else 0)
    return bits


def pairs(limit: int, thresh: int) -> None:
    """★装丁ゲートの機械化(2026-09-11)
    同じ頁の「紙の実物書影がある巻」と「Koboの**同じ巻番号**」を突き合わせる。
    同装丁なら同じ絵なのでハッシュ距離は小さい。HELLSING で人手でやった比較そのもの。
    距離が大きい = 別装丁/別版のカバー([[kobo_cover_wrong_for_old_print]]) → AI/目視へ回す。

    ★閾値較正(2026-09-11 HELLSING実測。決め打ちでなく実データで引いた線):
        同巻・同装丁        紙1↔Kobo1 = 5 / 紙5↔Kobo5 = 14 (紙5は帯付きで下部が隠れる)
        別巻同士(=誤採用したら事故) 20〜29
        仮書影(文字だけ)↔実物        31
      → 既定 thresh=12。帯付きは DIFF 側に落ちてAI審査へ回るが、**誤採用より安全**
        (無書影 ＞ 誤書影)。比較は重なり巻を最大2つ取り min を採るので、片方が帯でも救われる。
    """
    import urllib.request
    rows = [json.loads(l) for l in io.open(SURVEY, encoding="utf-8") if l.strip()]
    hits = [d for d in rows if d.get("n_hit")]
    donep = os.path.join(OUTDIR, "pairs-done.json")
    out_p = os.path.join(OUTDIR, "pairs.jsonl")
    done = set(json.load(io.open(donep, encoding="utf-8"))) if os.path.exists(donep) else set()
    todo = [d for d in hits if d["slug"] not in done]
    imgdir = os.path.join(OUTDIR, "img")
    os.makedirs(imgdir, exist_ok=True)
    print(f"充当可 {len(hits)}頁 / 済 {len(done)} / 残 {len(todo)} → 今回 {min(limit,len(todo))}", flush=True)
    cnt = collections_Counter()
    out = io.open(out_p, "a", encoding="utf-8", newline="\n")
    try:
        for i, d in enumerate(todo[:limit], 1):
            slug = d["slug"]
            ftypes = {f["type"] for f in d["fills"]}
            # 頁の実体から「その版の実物書影を持つ巻」を取る(survey時に保存していないので読み直す)
            paper = {}
            try:
                y = yaml.load(io.open(os.path.join(SRC, slug + ".yml"), encoding="utf-8"), Loader=L)
                for e in y.get("editions") or []:
                    if e.get("type") not in ftypes:
                        continue
                    for v in e.get("volumes") or []:
                        u = str(v.get("cover_url") or "")
                        if u and not is_placeholder(u) and v.get("number") is not None:
                            paper[int(v["number"])] = u
            except Exception as e:
                print(f"  {slug}: yml読めず {e}", flush=True)
            # Kobo を引き直して全巻の URL を得る(survey は gif巻のURLしか保存していない)
            title = d.get("title") or ""
            pt = _KC.norm(title)
            vols, bare, pg = {}, {}, 1
            try:
                while pg <= 4:
                    before = len(vols) + len(bare)
                    res = kobo_retry(title, pg)
                    for it in (res.get("Items") or []):
                        t2 = unicodedata.normalize("NFKC", str(it.get("title"))).strip()
                        img = str(it.get("largeImageUrl") or "")
                        if not img or "noimage" in img:
                            continue
                        m = _KC.VOLP.search(t2)
                        if m and _KC.norm(_KC.VOLP.sub("", t2)) == pt:
                            vols.setdefault(int(m.group(1)), img)
                            continue
                        mb = _KC.VOLP_BARE.search(t2)
                        if mb and _KC.norm(_KC.VOLP_BARE.sub("", t2)) == pt:
                            bare.setdefault(int(mb.group(1)), img)
                    if len(vols) + len(bare) == before:
                        break
                    pg += 1
                    time.sleep(1.3)
            except RuntimeError:
                print("★連続429 = 実スロットル。中断(残りは次回)", flush=True)
                break
            if not vols and len(bare) >= 3:
                vols = bare
            overlap = sorted(set(paper) & set(vols))
            verdict, dists, used = "NOPAIR", [], []
            for vn in overlap[:2]:
                try:
                    pp = os.path.join(imgdir, f"{slug}-p{vn}.jpg")
                    kp = os.path.join(imgdir, f"{slug}-k{vn}.jpg")
                    urllib.request.urlretrieve(paper[vn], pp)
                    urllib.request.urlretrieve(vols[vn], kp)
                    dist = bin(dhash(pp) ^ dhash(kp)).count("1")
                    dists.append(dist)
                    used.append(vn)
                except Exception as e:
                    print(f"  {slug} v{vn}: 画像比較失敗 {e}", flush=True)
            if dists:
                verdict = "MATCH" if min(dists) <= thresh else "DIFF"
            out.write(json.dumps({"slug": slug, "title": title, "verdict": verdict,
                                  "dists": dists, "cmp_vols": used, "n_overlap": len(overlap),
                                  "n_fill": d["n_hit"], "fills": d["fills"]}, ensure_ascii=False) + "\n")
            out.flush()
            done.add(slug)
            json.dump(sorted(done), io.open(donep, "w", encoding="utf-8"))
            cnt[verdict] += 1
            if i % 25 == 0:
                print(f"  [{i}/{min(limit,len(todo))}] " + " / ".join(f"{k}{v}" for k, v in cnt.most_common()), flush=True)
            time.sleep(1.3)
    finally:
        out.close()
        json.dump(sorted(done), io.open(donep, "w", encoding="utf-8"))
    print("\n=== pairs === " + " / ".join(f"{k}{v}" for k, v in cnt.most_common()), flush=True)


def collections_Counter():
    import collections
    return collections.Counter()


def selfcheck(limit: int) -> None:
    """★Kobo側のプレースホルダ検出 (2026-09-11 akane-banashi で発覚)
    Kobo v24 が「JUMP COMICS DIGITAL のロゴだけ」= Kobo自身の仮画像だった。
    紙との距離比較(pairs)は DIFF で弾けるが、★NOPAIR頁は比較元が無いので素通りする。
    そこで **頁の中だけで完結する2つの検査** を足す(API不要・既にDL済みの画像で判る):
      LOGO     … ほぼ白地(小さなロゴだけ)。明るい画素が85%以上
      TEMPLATE … 別の巻なのに絵が同じ = 全巻共通テンプレ
                 (グループ・ゼロ「マンガの金字塔」型 [[kobo_cover_wrong_for_old_print]])
    """
    import urllib.request
    from PIL import Image
    src = os.path.join(OUTDIR, "pairs.jsonl")
    rows = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()][:limit]
    imgdir = os.path.join(OUTDIR, "img")
    os.makedirs(imgdir, exist_ok=True)
    out = io.open(os.path.join(OUTDIR, "selfcheck.jsonl"), "w", encoding="utf-8", newline="\n")
    cnt = collections_Counter()
    for i, r in enumerate(rows, 1):
        hs, flags = [], []
        for f in r["fills"][:12]:
            p = os.path.join(imgdir, f"{r['slug']}-kk{f['number']}.jpg")
            if not os.path.exists(p):
                try:
                    req = urllib.request.Request(f["cover_url"], headers={"User-Agent": "Mozilla/5.0"})
                    open(p, "wb").write(urllib.request.urlopen(req, timeout=25).read())
                except Exception:
                    continue
            try:
                im = Image.open(p).convert("L")
                px = im.tobytes()
                bright = sum(1 for b in px if b > 235) / max(len(px), 1)
                if bright >= 0.85:
                    flags.append(f"LOGO:v{f['number']}")
                hs.append((f["number"], dhash(p)))
            except Exception:
                continue
        dup = 0
        for x in range(len(hs)):
            for y in range(x + 1, len(hs)):
                if bin(hs[x][1] ^ hs[y][1]).count("1") <= 6:
                    dup += 1
        if len(hs) >= 2 and dup >= max(1, len(hs) // 3):
            flags.append(f"TEMPLATE:{dup}組")
        verdict = r["verdict"] if not flags else "FLAGGED"
        cnt[verdict] += 1
        out.write(json.dumps({**r, "verdict2": verdict, "flags": flags}, ensure_ascii=False) + "\n")
        if i % 50 == 0:
            print(f"  [{i}/{len(rows)}] " + " / ".join(f"{k}{v}" for k, v in cnt.most_common()), flush=True)
    out.close()
    print("=== selfcheck === " + " / ".join(f"{k}{v}" for k, v in cnt.most_common()))


TRIAGE = "triage.jsonl"


def triage() -> None:
    """selfcheck の結果を最終区分に落とす。★LOGO は巻単位の旗なので巻だけ外す
    (頁ごと捨てると 10巻中1巻がロゴの頁で 9巻を失う)。TEMPLATE は頁全体が疑わしいので審査へ。
      AUTO   … 装丁ゲートMATCH かつ TEMPLATE無し = 自動確定してよい
      REVIEW … NOPAIR(比較元なし)/DIFF(距離大)/TEMPLATE = 目視・AI審査へ
      EMPTY  … 外した結果 充当できる巻が残らない = 対象外
    """
    rows = [json.loads(l) for l in io.open(os.path.join(OUTDIR, "selfcheck.jsonl"), encoding="utf-8") if l.strip()]
    cnt, vol = collections_Counter(), collections_Counter()
    with io.open(os.path.join(OUTDIR, TRIAGE), "w", encoding="utf-8", newline="\n") as out:
        for r in rows:
            logos = {int(m.group(1)) for f in (r.get("flags") or [])
                     for m in [re.match(r"LOGO:v(\d+)", f)] if m}
            tmpl = any(f.startswith("TEMPLATE") for f in (r.get("flags") or []))
            clean = [f for f in r["fills"] if f["number"] not in logos]
            if not clean:
                bucket = "EMPTY"
            elif tmpl:
                bucket = "TEMPLATE"
            elif r["verdict"] == "MATCH":
                bucket = "AUTO"
            else:
                bucket = r["verdict"]  # NOPAIR / DIFF
            cnt[bucket] += 1
            vol[bucket] += len(clean)
            out.write(json.dumps({"slug": r["slug"], "title": r.get("title"), "bucket": bucket,
                                  "verdict": r["verdict"], "dists": r.get("dists"),
                                  "flags": r.get("flags"), "n_fill": len(clean),
                                  "fills": clean}, ensure_ascii=False) + "\n")
    for k, n in cnt.most_common():
        print(f"  {k:10} {n:>4}頁 / {vol[k]:>5}巻")
    print(f"★AUTO {cnt['AUTO']}頁/{vol['AUTO']}巻 / 要審査 "
          f"{cnt['NOPAIR']+cnt['DIFF']+cnt['TEMPLATE']}頁/"
          f"{vol['NOPAIR']+vol['DIFF']+vol['TEMPLATE']}巻")


def sheets(verdicts: str, per_sheet: int, limit: int) -> None:
    """AI/目視審査用のコンタクトシート。★1頁=1行に詰めて1枚に複数頁を載せる
    (1頁1枚にすると審査画像が数百枚になり、[[feedback_agent_fanout_token_cost]] の轍を踏む)。
    行の左 = その作品の紙の実物書影(比較元)、右 = 採用候補の Kobo書影。
    ★API は叩かない(必要なURLは survey/pairs が持っている + 紙は頁の実体から読む)。
    """
    import urllib.request
    from PIL import Image, ImageDraw
    want = {v.strip().upper() for v in verdicts.split(",") if v.strip()}
    # ★selfcheck が走っていればその判定(verdict2 = LOGO/TEMPLATE を加味)を使う
    tg = os.path.join(OUTDIR, TRIAGE)
    sc = os.path.join(OUTDIR, "selfcheck.jsonl")
    src = tg if os.path.exists(tg) else (sc if os.path.exists(sc) else os.path.join(OUTDIR, "pairs.jsonl"))
    key = "bucket" if src == tg else ("verdict2" if src == sc else "verdict")
    rows = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
    rows = [d for d in rows if d.get(key) in want][:limit]
    imgdir = os.path.join(OUTDIR, "img")
    shdir = os.path.join(OUTDIR, "sheets")
    os.makedirs(imgdir, exist_ok=True)
    os.makedirs(shdir, exist_ok=True)

    def grab(url: str, key: str):
        p = os.path.join(imgdir, key + ".jpg")
        if not os.path.exists(p):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                open(p, "wb").write(urllib.request.urlopen(req, timeout=25).read())
            except Exception:
                return None
        try:
            return Image.open(p).convert("RGB")
        except Exception:
            return None

    CW, CH, PAD, LBL = 112, 158, 6, 14
    manifest = []
    print(f"対象 {len(rows)}頁 ({','.join(sorted(want))}) → 1枚{per_sheet}頁", flush=True)
    for si in range(0, len(rows), per_sheet):
        chunk = rows[si:si + per_sheet]
        ncol = 8  # 紙2 + 区切り1 + Kobo5
        W = ncol * (CW + PAD) + 160
        RH = CH + LBL * 2 + PAD
        sheet = Image.new("RGB", (W, RH * len(chunk)), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        for ri, r in enumerate(chunk):
            y0 = ri * RH
            d.line([(0, y0), (W, y0)], fill=(200, 200, 200))
            d.text((4, y0 + 4), f"{si+ri+1}. {r['slug']}", fill=(0, 0, 0))
            d.text((4, y0 + 18), f"{(r.get('title') or '')[:18]}", fill=(90, 90, 90))
            d.text((4, y0 + 32), f"{r.get('bucket') or r.get('verdict')} d={r.get('dists')}", fill=(160, 0, 0))
            if r.get("flags"):
                d.text((4, y0 + 60), ",".join(r["flags"])[:22], fill=(200, 0, 0))
            d.text((4, y0 + 46), f"充当{r['n_fill']}巻", fill=(90, 90, 90))
            ftypes = {f["type"] for f in r["fills"]}
            paper = []
            try:
                y = yaml.load(io.open(os.path.join(SRC, r["slug"] + ".yml"), encoding="utf-8"), Loader=L)
                for e in y.get("editions") or []:
                    for v in e.get("volumes") or []:
                        u = str(v.get("cover_url") or "")
                        if u and not is_placeholder(u) and v.get("number") is not None:
                            same = e.get("type") in ftypes
                            paper.append((0 if same else 1, e.get("type"), int(v["number"]), u))
            except Exception:
                pass
            paper.sort()
            col = 0
            for _, et, vn, u in paper[:2]:
                im = grab(u, f"{r['slug']}-pp{et}{vn}")
                x = 160 + col * (CW + PAD)
                if im:
                    im.thumbnail((CW, CH))
                    sheet.paste(im, (x, y0 + LBL + 2))
                d.text((x, y0 + 2), f"紙 {et[:6]} v{vn}", fill=(0, 100, 0))
                col += 1
            col = 3
            for f in r["fills"][:5]:
                im = grab(f["cover_url"], f"{r['slug']}-kk{f['number']}")
                x = 160 + col * (CW + PAD)
                if im:
                    im.thumbnail((CW, CH))
                    sheet.paste(im, (x, y0 + LBL + 2))
                d.text((x, y0 + 2), f"Kobo v{f['number']}", fill=(0, 0, 160))
                col += 1
        out = os.path.join(shdir, f"sheet-{si//per_sheet + 1:03d}.png")
        sheet.save(out)
        manifest.append({"sheet": out, "slugs": [r["slug"] for r in chunk]})
        print(f"  {out}  ({len(chunk)}頁)", flush=True)
    json.dump(manifest, io.open(os.path.join(OUTDIR, "sheets.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"シート {len(manifest)}枚")



def accept(dry: bool) -> None:
    """triage の AUTO + 目視審査を通った頁を cover-override.jsonl へ純粋追加。
    ★却下は .cache/kobo-placeholder/rejects.tsv(slug	理由)に置く = 台帳として残す。
    既に同じ isbn13 が seed に在れば触らない(冪等)。"""
    rej = {}
    rp = os.path.join(OUTDIR, "rejects.tsv")
    if os.path.exists(rp):
        for i, ln in enumerate(io.open(rp, encoding="utf-8")):
            if i == 0 or not ln.strip():
                continue
            a = ln.rstrip("\n").split("\t")
            rej[a[0]] = a[1] if len(a) > 1 else ""
    seed = os.path.join(ROOT, "data", "seeds", "cover-override.jsonl")
    have = set()
    for ln in io.open(seed, encoding="utf-8"):
        if ln.strip():
            have.add(str(json.loads(ln).get("isbn13")))
    rows = [json.loads(l) for l in io.open(os.path.join(OUTDIR, TRIAGE), encoding="utf-8") if l.strip()]
    today = time.strftime("%Y-%m-%d")
    n_page = n_vol = n_skip = 0
    slugs = []
    out = None if dry else io.open(seed, "a", encoding="utf-8", newline="\n")
    for r in rows:
        if r["bucket"] == "EMPTY" or r["slug"] in rej:
            continue
        how = "装丁ゲートMATCH(自動)" if r["bucket"] == "AUTO" else f"目視審査OK({r['bucket']})"
        wrote = 0
        for f in r["fills"]:
            if str(f["isbn13"]) in have:
                n_skip += 1
                continue
            rec = {"isbn13": str(f["isbn13"]), "cover_url": f["cover_url"], "slug": r["slug"],
                   "number": f["number"],
                   "reason": f"楽天紙=仮.gif(実物なし)→Kobo電子で補完。{how} d={r.get('dists')}",
                   "at": today}
            if out:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            have.add(str(f["isbn13"]))
            wrote += 1
        if wrote:
            n_page += 1
            n_vol += wrote
            slugs.append(r["slug"])
    if out:
        out.close()
    tag = "(dry-run) " if dry else ""
    print(f"{tag}追記 {n_page}頁 / {n_vol}巻 / 既在skip {n_skip} / 却下 {len(rej)}頁")
    io.open(os.path.join(OUTDIR, "accepted-slugs.txt"), "w", encoding="utf-8").write(",".join(slugs))
    print(f"反映対象slug → {len(slugs)}件 → accepted-slugs.txt")



def stats() -> None:
    q = sum(1 for l in io.open(QUEUE, encoding="utf-8") if l.strip()) if os.path.exists(QUEUE) else 0
    done = len(json.load(io.open(DONE, encoding="utf-8"))) if os.path.exists(DONE) else 0
    n_hit = n_vol = n_none = n_err = n_gate = n_gatevol = 0
    if os.path.exists(SURVEY):
        for l in io.open(SURVEY, encoding="utf-8"):
            if not l.strip():
                continue
            d = json.loads(l)
            if d.get("error"):
                n_err += 1
                continue
            for e in d.get("editions") or []:
                if e.get("gate") == "COUNT_MISMATCH" and e.get("n_match"):
                    n_gate += 1
                    n_gatevol += e["n_match"]
            if d.get("n_hit"):
                n_hit += 1
                n_vol += d["n_hit"]
            else:
                n_none += 1
    print(f"queue {q}頁 / 照会済 {done} / 残 {q-done}")
    print(f"  ★充当可(版ゲートOK) {n_hit}頁 / {n_vol}巻")
    print(f"  充当なし {n_none}頁 / ERR {n_err}")
    print(f"  版ゲートで留保(巻数不一致=別版の表紙が付く危険) {n_gate}版 / {n_gatevol}巻")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-queue", action="store_true")
    ap.add_argument("--include-noanchor", action="store_true", help="頁内が全部.gif(比較元なし)も対象に含める")
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--pairs", action="store_true", help="装丁ゲート: 紙×Koboの同巻をハッシュ比較")
    ap.add_argument("--thresh", type=int, default=12, help="dhash距離のMATCH閾値")
    ap.add_argument("--sheets", type=str, default="", help="審査シート生成: 例 DIFF,NOPAIR")
    ap.add_argument("--selfcheck", action="store_true", help="Kobo側プレースホルダ(LOGO/TEMPLATE)検出")
    ap.add_argument("--triage", action="store_true", help="最終区分 AUTO/NOPAIR/DIFF/TEMPLATE/EMPTY")
    ap.add_argument("--accept", action="store_true", help="seedへ純粋追加(rejects.tsv は除外)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--per-sheet", type=int, default=6)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.build_queue:
        build_queue(a.include_noanchor)
    elif a.survey:
        survey(a.limit)
    elif a.pairs:
        pairs(a.limit, a.thresh)
    elif a.selfcheck:
        selfcheck(a.limit)
    elif a.triage:
        triage()
    elif a.accept:
        accept(a.dry_run)
    elif a.sheets:
        sheets(a.sheets, a.per_sheet, a.limit)
    elif a.stats:
        stats()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
