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
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.build_queue:
        build_queue(a.include_noanchor)
    elif a.survey:
        survey(a.limit)
    elif a.stats:
        stats()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
