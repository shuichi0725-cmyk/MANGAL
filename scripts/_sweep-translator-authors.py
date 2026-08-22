# -*- coding: utf-8 -*-
"""訳者混入の掃引 (2026-08-22 GTO型=ユーザGO)。

型: MADB raw(metadata101)のcreatorは「[訳]名前」「[共訳]名前」等の役割マーカーを持つが、
cleanが役割prefixを剥がすため翻訳者が著者に化ける(GTO=バイリンガル版のStuart Atkin型)。

検出(一次証拠=rawの役割マーカー):
  1. raw metadata101 を走査し、[訳]/[共訳]/[翻訳]/[監訳]/[編訳] 付きcreatorを ISBN単位で収集
  2. db-v2で ISBN→series_key に解決し、series_key単位に訳者集合を集約
  3. ガード: 同一series内で**マーカー無しcreator**としても現れる人物は除外(著者兼訳は触らない)
  4. 本番頁の著者欄に実在する訳者のみ対象(無影響keyはskip)
適用: author-role-corrections.yml へ remove+credits(role=翻訳) を純粋追加 → 対象頁再生成。

usage: python scripts/_sweep-translator-authors.py [--apply]   (無印=dry-run報告のみ)
"""
import glob
import io
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
APPLY = "--apply" in sys.argv
RAW = ROOT / ".cache" / "madb" / "metadata101.json"
CORR = ROOT / "data" / "seeds" / "author-role-corrections.yml"

YAKU_RE = re.compile(r"^\[([^\]]*訳[^\]]*)\]\s*(.+)$")


def _to13(s: str) -> str | None:
    s = re.sub(r"[^0-9Xx]", "", s or "")
    if len(s) == 13:
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        chk = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
        return core + str((10 - chk % 10) % 10)
    return None


def main() -> None:
    # 1) raw を record単位でロード(668MB=clean 463MBのjson.load実績に倣うfull-load。誤ペア無し)
    per_isbn_yaku: dict = defaultdict(set)     # isbn13 -> {(role, name)}
    per_isbn_plain: dict = defaultdict(set)    # isbn13 -> {name}(マーカー無し)
    g = json.load(io.open(RAW, encoding="utf-8"))
    rows = g.get("@graph", g) if isinstance(g, dict) else g
    n_rec = 0
    for r in rows:
        cr = r.get("schema:creator")
        if not cr:
            continue
        names = cr if isinstance(cr, list) else [cr]
        yaku, plain = set(), set()
        for nm in names:
            if not isinstance(nm, str):
                continue
            nm = nm.strip()
            ym = YAKU_RE.match(nm)
            if ym:
                yaku.add((ym.group(1), ym.group(2).strip()))
            else:
                plain.add(re.sub(r"^\[[^\]]*\]\s*", "", nm).strip())
        if not yaku:
            continue
        i = r.get("schema:isbn")
        if isinstance(i, list):
            i = i[0] if i else None
        k = _to13(str(i)) if i else None
        if not k:
            continue
        n_rec += 1
        per_isbn_yaku[k] |= yaku
        per_isbn_plain[k] |= plain
    del g, rows
    print(f"raw走査: 訳者付きrecord {n_rec:,} / 訳者付きISBN {len(per_isbn_yaku):,}", flush=True)

    # 2) ISBN→series_key
    con = sqlite3.connect(ROOT / ".cache" / "db-v2.sqlite")
    key_yaku = defaultdict(set)    # series_key -> {(role,name)}
    key_plain = defaultdict(set)   # series_key -> {plain names}(同series全ISBNの無印creator)
    for isbn, pairs in per_isbn_yaku.items():
        r = con.execute(
            "select s.series_key from series s join editions e on e.series_id=s.id "
            "join volumes v on v.edition_id=e.id where v.isbn13=?", (isbn,)).fetchone()
        if not r:
            continue
        key_yaku[r[0]] |= pairs
        key_plain[r[0]] |= per_isbn_plain.get(isbn, set())
    print(f"series_key解決: {len(key_yaku):,} key", flush=True)

    # 3) ガード: 同series内で無印creatorにも出る名前は除外
    final = {}
    guarded = []
    for k, pairs in key_yaku.items():
        names = {}
        for role, nm in pairs:
            if nm in key_plain.get(k, set()):
                guarded.append((k, nm))
                continue
            names[nm] = role
        if names:
            final[k] = names
    print(f"ガード除外(著者兼訳の疑い): {len(guarded)} / 対象key: {len(final):,}", flush=True)

    # 4) 本番影響: 頁著者に訳者名が実在するもののみ
    all_names = {nm for names in final.values() for nm in names}
    name_pat = re.compile("|".join(re.escape(n) for n in sorted(all_names, key=len, reverse=True)))
    affected_pages = {}
    for f in glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")):
        t = io.open(f, encoding="utf-8").read()
        am = re.search(r"(?ms)^authors:\n(.*?)^(?:original_authors|publisher|magazine|editions):", t)
        if not am:
            continue
        hits = set(name_pat.findall(am.group(1))) if all_names else set()
        if hits:
            affected_pages[Path(f).stem] = hits
    print(f"本番影響頁: {len(affected_pages)}", flush=True)

    # 既存corrections取り込み(重複skip)
    doc = yaml.safe_load(io.open(CORR, encoding="utf-8")) or {}
    have = {}
    for e in doc.get("corrections", []):
        have[e.get("series_key")] = set(e.get("remove") or [])

    page_names = {nm for hs in affected_pages.values() for nm in hs}
    emit = []
    for k, names in sorted(final.items()):
        todo = {nm: role for nm, role in names.items() if nm in page_names and nm not in have.get(k, set())}
        if todo:
            emit.append((k, todo))
    print(f"corrections追加対象: {len(emit)} key / のべ {sum(len(v) for _, v in emit)} 名")

    # レポートTSV
    outp = ROOT / "docs" / "production-diagnostics" / "translator-author-sweep.tsv"
    with io.open(outp, "w", encoding="utf-8", newline="\n") as w:
        w.write("series_key\t訳者\trole\n")
        for k, todo in emit:
            for nm, role in sorted(todo.items()):
                w.write(f"{k}\t{nm}\t{role}\n")
        for k, nm in guarded:
            w.write(f"{k}\t{nm}\t(ガード=無印creator兼任・未処理)\n")
    print("TSV:", outp)
    # 影響頁リスト(regen用)
    io.open(ROOT / ".cache" / "translator-sweep-pages.txt", "w", encoding="utf-8", newline="\n").write(
        "\n".join(sorted(affected_pages)))

    if not APPLY:
        for k, todo in emit[:10]:
            print("  例:", k, "→", list(todo))
        print("(dry-run。--apply で corrections へ追記)")
        return

    NOTE = "訳者混入掃引2026-08-22(GTO型): raw metadata101の[訳]/[共訳]等マーカーを一次証拠に除去。表示はcredits(翻訳)へ"
    with io.open(CORR, "a", encoding="utf-8", newline="\n") as w:
        for k, todo in emit:
            w.write("- series_key: " + json.dumps(k, ensure_ascii=False) + "\n")
            w.write("  remove:\n")
            for nm in sorted(todo):
                w.write("  - " + json.dumps(nm, ensure_ascii=False) + "\n")
            w.write("  credits:\n")
            for nm, role in sorted(todo.items()):
                w.write("  - name: " + json.dumps(nm, ensure_ascii=False) + "\n")
                w.write("    role: " + json.dumps(role if "訳" in role else "翻訳", ensure_ascii=False) + "\n")
            w.write("  note: " + json.dumps(NOTE, ensure_ascii=False) + "\n")
    print(f"corrections += {len(emit)} entries")


if __name__ == "__main__":
    main()
