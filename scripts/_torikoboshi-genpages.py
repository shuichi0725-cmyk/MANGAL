"""取りこぼし頁化 = 種2に在るのに頁が無い作品の**源頁(data/manga/*.yml)**を生成する。

promote は元頁駆動([[orphan_series_promote_is_srcpage_driven]])なので、源頁さえ作れば
巻/著者/出版社/書影は promote が種2+seedから組み立てる。 源頁に要るのは
  slug / title / _skey(series_key) / title_kana (+ segmented)
だけ(★db側の title_kana が NULL なので kana は必ず源頁に入れる)。

★順番固定([[new_manga_registration_order]]):
  1. **ISBN照合** = そのISBNが既に本番に在れば作らない(別頁の巻として収録済みの型を防ぐ。
     2026-07-25 ソーサリアン6巻を新規頁にしかけた実害)。
  2. **ヨミの確定** = NDL(dcndl:transcription = ★分かち書き)を優先、無ければ楽天titleKana。
     ★どちらも無ければ**作らない**(登録保留)。 捏造しない。
  3. **slug** = 確定ヨミから `_kana_romaji.kana2romaji`(単一ソース)で1度だけ生成。
     既存slug(本番+今回分)と衝突したら `-姓+年` でなく安全側に `-年` suffix、それでも衝突なら保留。
  4. 生成後は promote --only → preview で確認 → GO後に本番。

usage:
  python scripts/_torikoboshi-genpages.py --list                 # 対象と可否だけ出す
  python scripts/_torikoboshi-genpages.py --run [--limit N]      # 源頁を書く(NDL照会あり)
  対象の既定 = 1.2.18 の新規series(=今月の新刊)。 --keys-file で任意のseries_keyリストも可。
"""
import argparse
import collections
import importlib.util
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _kana_romaji import kana2romaji          # noqa: E402  ★slug変換の単一ソース

DB = ROOT / ".cache" / "db-v2.sqlite"
SRC = ROOT / "data" / "manga"
MANIFEST = ROOT / ".cache" / "madb-distill" / "merge-manifest-1.2.18.json"
LIVE_ISBN = ROOT / ".cache" / "isbn-page-index.json"
HARVEST = ROOT / ".cache" / "torikoboshi" / "harvest.jsonl"
IDX = ROOT / "data" / "manga-list-index.json"
KANA_OK = re.compile(r"^[ァ-ヶーｦ-ﾟ\s　・]+$")


def _norm_t(s):
    import unicodedata
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[（(].*?[)）]|[【\[].*?[\]】]", "", s)          # 巻表記・注記
    s = re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.,'’\"]", "", s)
    return re.sub(r"\d+$", "", s).lower()


def _same_title(rakuten_title, s2_title):
    """楽天商品題と種2題が同一作品の題か(巻番号・記号差は無視)。 副題付きは不一致扱い。"""
    a, b = _norm_t(rakuten_title), _norm_t(s2_title)
    return bool(a) and bool(b) and a == b


def _lookup():
    spec = importlib.util.spec_from_file_location("lookup", ROOT / "scripts" / "_lookup.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--keys-file", default=None)
    a = ap.parse_args()

    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    if a.keys_file:
        want = {l.strip() for l in open(a.keys_file, encoding="utf-8") if l.strip()}
        sids = [r[0] for r in con.execute("SELECT id, series_key FROM series") if r[1] in want]
    else:
        sids = json.loads(MANIFEST.read_text(encoding="utf-8"))["new_series_ids"]
    sids = set(sids)

    meta = {i: (k, t) for i, k, t in con.execute("SELECT id, series_key, title FROM series") if i in sids}
    vols = collections.defaultdict(list)
    for sid, ib, num, rd in con.execute(
        "SELECT e.series_id, v.isbn13, v.number, v.release_date FROM volumes v "
            "JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"):
        if sid in sids:
            vols[sid].append((ib, num, rd or ""))

    live = json.loads(LIVE_ISBN.read_text(encoding="utf-8")) if LIVE_ISBN.exists() else {}
    rk = {}
    if HARVEST.exists():
        for ln in HARVEST.open(encoding="utf-8"):
            d = json.loads(ln)
            if d.get("item"):
                rk[d["isbn"]] = d["item"]

    idx = json.loads(IDX.read_text(encoding="utf-8"))
    used = {r[idx["f"].index("slug")] for r in idx["d"]}
    used |= {p.stem for p in SRC.glob("*.yml")}

    todo, skip = [], collections.Counter()
    for sid, vv in sorted(vols.items()):
        if any(ib in live for ib, _, _ in vv):
            skip["既に本番に在る(ISBN一致)"] += 1
            continue
        todo.append((sid, vv))
    print(f"対象 {len(meta)} series / ISBN持ち {len(vols)} / 生成候補 {len(todo)}  (skip: {dict(skip)})")
    if a.limit:
        todo = todo[:a.limit]
    if a.list and not a.run:
        for sid, vv in todo[:20]:
            print(f"   {meta[sid][1][:34]:36s} {len(vv)}巻 {sorted(v[2] for v in vv)[0][:7]}")
        return

    L = _lookup()
    made, hold = [], []
    for n, (sid, vv) in enumerate(todo, 1):
        key, title = meta[sid]
        vv.sort(key=lambda x: (x[2] or "", x[1] or 0))
        kana = seg = None
        # ★ヨミ: NDL(分かち書き) → 楽天(連結) の順
        for ib, _, _ in vv[:2]:
            try:
                recs = L.ndl_live_retry(f'isbn="{ib}"', maximum=3)
            except Exception:
                recs = []
            for r in recs:
                tk = (r.get("title_kana") or "").strip()
                if tk and KANA_OK.match(tk):
                    seg, kana = tk, tk.replace(" ", "").replace("　", "")
                    break
            if kana:
                break
        if not kana:
            # ★楽天titleKanaは**商品題(副題込み)のヨミ**なので、種2の題と一致する時だけ使う。
            #   (バクギャル → 楽天ヨミ「バクギャルレイワギャルガバクマツヲアゲル」= 副題混入。
            #    題と食い違うヨミを title_kana に入れるのは誤データ = 入れない)
            for ib, _, _ in vv:
                it = rk.get(ib) or {}
                tk = (it.get("titleKana") or "").strip()
                if not (tk and KANA_OK.match(tk)):
                    continue
                if _same_title(it.get("title"), title):
                    kana = tk.replace(" ", "").replace("　", "")
                    break
        if not kana:
            hold.append((key, title, "ヨミ不明(NDL/楽天とも無し)"))
            continue
        base = kana2romaji(seg or kana)
        base = re.sub(r"[^a-z0-9-]", "", base).strip("-")
        if len(base) < 2:
            hold.append((key, title, f"slug生成不可({base!r})"))
            continue
        slug = base
        if slug in used:
            yr = (sorted(v[2] for v in vv if v[2]) or [""])[0][:4]
            slug = f"{base}-{yr}" if yr else base
        if slug in used:
            hold.append((key, title, f"slug衝突({base})"))
            continue
        used.add(slug)
        if a.run:
            body = [f"slug: {slug}", f"title: {title}", f"_skey: {key}",
                    f"title_kana: {kana}"]
            if seg:
                body.append(f"title_kana_segmented: {seg}")
            body.append(f"_note_origin: torikoboshi 2026-07-25 (種2新規series・ヨミ={'NDL' if seg else '楽天'})")
            (SRC / f"{slug}.yml").write_text("\n".join(body) + "\n", encoding="utf-8")
        made.append((slug, title, kana, "NDL" if seg else "楽天"))
        if n % 25 == 0:
            print(f"  ...{n}/{len(todo)} 生成{len(made)} 保留{len(hold)}", flush=True)

    print(f"\n★源頁 生成 {len(made)} / 保留 {len(hold)}")
    for s, t, k, src in made[:15]:
        print(f"   {s[:40]:42s} 「{t[:20]:22s}」 {k[:16]:18s} ({src})")
    if hold:
        print("\n保留(作らない):")
        for k, t, w in hold[:15]:
            print(f"   {t[:26]:28s} {w}")
    (ROOT / ".cache" / "torikoboshi" / "genpages-last.json").write_text(
        json.dumps({"made": [m[0] for m in made],
                    "hold": [{"key": h[0], "title": h[1], "why": h[2]} for h in hold]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n→ .cache/torikoboshi/genpages-last.json (promote --only 用の slug 一覧)")


if __name__ == "__main__":
    main()
