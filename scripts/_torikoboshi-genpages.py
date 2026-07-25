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
from _kana_romaji import kana2romaji  # noqa: E402
# ★slug決定は **_slug-gen-v2.decide()** が正本(CLAUDE.mdの7分岐: latin題/カタカナ外来語の
#   音写フィルタ/数字4分岐/ヘボン)。 2026-07-25: ここで自前のkana→ヘボン1本に済ませて
#   BEM→bemu / ヴァージン・キラー→vaajin-kiraa という誤slugを作りかけた(ユーザ指摘)。
#   ★slugはrename困難なので**既存の判定器を必ず通す**。

DB = ROOT / ".cache" / "db-v2.sqlite"
# ★源頁の置き場 = data/seeds/source-pages(★git追跡=恒久)。 data/manga は .gitignore なので
#   そこに書くと git clean/別PCで消える(2026-07-25)。 promote は両方をスキャンする。
SRC = ROOT / "data" / "seeds" / "source-pages"
SRC_LEGACY = ROOT / "data" / "manga"
MANIFEST = ROOT / ".cache" / "madb-distill" / "merge-manifest-1.2.18.json"
LIVE_ISBN = ROOT / ".cache" / "isbn-page-index.json"
HARVEST = ROOT / ".cache" / "torikoboshi" / "harvest.jsonl"
IDX = ROOT / "data" / "manga-list-index.json"
SLUG_OVR = ROOT / "data" / "seeds" / "source-slug-overrides.yml"
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


def _rakuten_kana(it, s2_title):
    """楽天titleKanaから題ヨミを取る。 ★末尾の巻数トークンを落とす
    (「ニジュウヨジカン…カシマス　イチ」= 商品題『…。 1』の巻数がヨミにも入る 2026-07-25)。"""
    tk = (it.get("titleKana") or "").strip()
    if not tk:
        return None
    if re.search(r"[\s　]\d+$", str(it.get("title") or "")):
        tk = re.sub(r"[\s　]+[^\s　]+$", "", tk)      # 商品題が巻数で終わる → ヨミの末尾トークンも巻数
    return tk.strip()


def _authors_from(it, ndl_creators, ndl_ck):
    """種2に著者が無い時の補完。 楽天(著者/著者ヨミ)優先、無ければNDL典拠。
    ★役割は種2の既定と同じ writer_artist のみ(原作/作画の別は分からないので**推測しない**)。"""
    out = []
    names = [x.strip() for x in re.split(r"[/／]", str(it.get("author") or "")) if x.strip()]
    kanas = [x.strip() for x in re.split(r"[/／]", str(it.get("authorKana") or "")) if x.strip()]
    for i, nm in enumerate(names):
        nm2 = re.sub(r"[\s　]+", "", nm)
        ka = re.sub(r"[\s　]+", "", kanas[i]) if i < len(kanas) else ""
        out.append({"name": nm2, "kana": ka})
    if not out and ndl_creators:
        for i, c in enumerate(ndl_creators):
            nm2 = re.sub(r"[\s　]+", "", str(c).split(",")[0] + (str(c).split(",")[1] if "," in str(c) else ""))
            ka = ""
            if i < len(ndl_ck or []):
                ka = re.sub(r"[\s　,、]+", "", ndl_ck[i])
            out.append({"name": nm2, "kana": ka})
    return [a for a in out if a["name"]]


def _surname_romaji(rk, vv, ndl_ck=None):
    """従版suffix用の**姓ローマ字**([[slug_collision_year_rule]] -姓+発売年)。
    ①NDL典拠の著者ヨミ「サイトウ, ジュンイチロウ」= 姓と名がカンマで分かれる(最優先)
    ②楽天authorKana が空白で姓名に分かれている場合の先頭トークン
    どちらも取れなければ None = **推測せず保留**。"""
    for ck in (ndl_ck or []):
        if "," in ck or "、" in ck:
            sur = re.split(r"[,、]", ck)[0].strip()
            r = re.sub(r"[^a-z0-9]", "", kana2romaji(sur))
            if len(r) >= 2:
                return r
    for ib, _, _ in vv:
        ak = ((rk.get(ib) or {}).get("authorKana") or "").strip()
        if not ak:
            continue
        first = re.split(r"[/／,、]", ak)[0].strip()
        parts = re.split(r"[\s　]+", first)
        if len(parts) < 2:
            continue          # ★姓名が分かれていない読み = 姓を推測しない(保留にする)
        r = re.sub(r"[^a-z0-9]", "", kana2romaji(parts[0]))
        if len(r) >= 2:
            return r
    return None


def _slug_decider():
    """_slug-gen-v2.decide(title, seg, kana, a_rom, a_eng) → (slug, source, conf, ratio)。"""
    argv = sys.argv
    sys.argv = ["x"]
    try:
        spec = importlib.util.spec_from_file_location("sg2", ROOT / "scripts" / "_slug-gen-v2.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.argv = argv


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

    db_authors = collections.defaultdict(list)
    for sid_, nm in con.execute(
            "SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"):
        if sid_ in sids:
            db_authors[sid_].append(nm)

    live = json.loads(LIVE_ISBN.read_text(encoding="utf-8")) if LIVE_ISBN.exists() else {}
    rk = {}
    if HARVEST.exists():
        for ln in HARVEST.open(encoding="utf-8"):
            d = json.loads(ln)
            if d.get("item"):
                rk[d["isbn"]] = d["item"]

    idx = json.loads(IDX.read_text(encoding="utf-8"))
    _si, _yi = idx["f"].index("slug"), idx["f"].index("year_started")
    used = {r[_si] for r in idx["d"]}
    prod_year = {r[_si]: r[_yi] for r in idx["d"] if r[_yi]}
    # ★自己衝突を避ける: 前回このスクリプトが作った源頁(=今回の対象と同じ _skey)は
    #   「既存slug」に数えない(再実行で自分の出力と衝突扱いになり保留が増える 2026-07-25)。
    _mine = set()
    for _p in SRC.glob("*.yml"):
        _m = re.search(r"^_skey: (.+)$", _p.read_text(encoding="utf-8"), re.M)
        if _m and _m.group(1).strip() in {v[0] for v in meta.values()}:
            _mine.add(_p.stem)
    used |= ({p.stem for p in SRC.glob("*.yml")} - _mine) | {p.stem for p in SRC_LEGACY.glob("*.yml")}

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
    SG = _slug_decider()
    # ★slug判定フロー #1 = 手動override が最優先(数字題の4分岐など機械が確定できない題)
    import yaml as _yaml
    ovr = _yaml.safe_load(SLUG_OVR.read_text(encoding="utf-8")) if SLUG_OVR.exists() else {}
    ovr = {k: (v.get("slug") if isinstance(v, dict) else v) for k, v in (ovr or {}).items()}
    made, hold = [], []
    for n, (sid, vv) in enumerate(todo, 1):
        key, title = meta[sid]
        vv.sort(key=lambda x: (x[2] or "", x[1] or 0))
        kana = seg = None
        ndl_ck = []
        ndl_creators = []
        # ★ヨミ: NDL(分かち書き) → 楽天(連結) の順
        for ib, _, _ in vv[:2]:
            try:
                recs = L.ndl_live_retry(f'isbn="{ib}"', maximum=3)
            except Exception:
                recs = []
            for r in recs:
                if r.get("creators_kana"):
                    ndl_ck = r["creators_kana"]
                if r.get("creators"):
                    ndl_creators = r["creators"]
                tk = (r.get("title_kana") or "").strip()
                if tk and KANA_OK.match(tk):
                    seg, kana = tk, tk.replace(" ", "").replace("　", "")
                    break
            if kana:
                break
        rk_item = None
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
                    tk2 = _rakuten_kana(it, title)
                    if tk2:
                        kana = tk2.replace(" ", "").replace("　", "")
                        rk_item = it
                    break
        if not kana:
            hold.append((key, title, "ヨミ不明(NDL/楽天とも無し)"))
            continue
        if key in ovr:
            base, src_kind, conf, _ratio = ovr[key], "manual-override", "high", ""
        else:
            base, src_kind, conf, _ratio = SG.decide(title, seg or "", kana, "", "")
        base = re.sub(r"[^a-z0-9-]", "", (base or "").lower()).strip("-")
        if len(base) < 2:
            hold.append((key, title, f"slug生成不可({src_kind})"))
            continue
        if conf != "high":
            # ★確度が high でないものは自動確定しない(= _slug-gen-v2 の設計「人がレビュー→GO」)。
            #   数字題の4分岐は未実装なので必ずここに落ちる。
            hold.append((key, title, f"slug要レビュー({src_kind}/{conf}: {base})"))
            continue
        slug = base
        if slug in used:
            # ★衝突解決(2026-07-25 ユーザ裁定「基本は一番古いものを主版」):
            #   既存が古い → 既存が無印のまま / 新規に **-姓+発売年** を付ける。
            #   新規の方が古い場合は既存のrenameが要る=高コスト → 保留にして報告。
            #   ★裸の西暦suffixは禁止([[slug_collision_year_rule]])。
            yr = (sorted(v[2] for v in vv if v[2]) or [""])[0][:4]
            ex_year = prod_year.get(base)
            if ex_year and yr and int(yr) < int(ex_year):
                hold.append((key, title, f"slug衝突: 新規({yr})の方が既存({ex_year})より古い → 主版入替の裁定要"))
                continue
            sur = _surname_romaji(rk, vv, ndl_ck)
            if not (sur and yr):
                hold.append((key, title, f"slug衝突(既存 {base}) だが姓/年が確定できず保留"))
                continue
            slug = f"{base}-{sur}{yr}"
            if slug in used:
                hold.append((key, title, f"slug衝突(再: {slug})"))
                continue
        used.add(slug)
        if a.run:
            body = [f"slug: {slug}", f"title: {title}", f"_skey: {key}",
                    f"title_kana: {kana}"]
            if not db_authors.get(sid):
                it0 = rk_item or next((rk.get(ib) for ib, _, _ in vv if rk.get(ib)), None) or {}
                aus = _authors_from(it0, ndl_creators, ndl_ck)
                if aus:
                    body.append("authors:")
                    for au in aus:
                        body.append(f"- name: {au['name']}")
                        body.append("  role: writer_artist")
                        if au.get("kana"):
                            body.append(f"  kana: {au['kana']}")
            if seg:
                body.append(f"title_kana_segmented: {seg}")
            body.append(f"_note_origin: torikoboshi 2026-07-25 (種2新規series・ヨミ={'NDL' if seg else '楽天'})")
            SRC.mkdir(parents=True, exist_ok=True)
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
