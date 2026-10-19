"""既存の作品頁(manga.v2 / .preview-data)に other_names 欄を一括で書く(= フルpromoteを待たずに全頁へ)。

★2026-10-19 他言語名の見直し(ユーザ裁定A1 = AIが埋めた英題は表示しない・「ok」で全頁適用)。
  規則の正本 = scripts/_other_names.py(promote と同じ build を呼ぶ)。 既存頁は種3キーを持たないので
  AI判定は「題+値」と推定(表記ゆれ・持ち主が全部AI)で行う。 次のフルpromoteからはキー判定に切り替わる。

- 書き方 = 頁末尾に other_names ブロックを足す(既に在れば差し替え)。 他の欄は1文字も触らない
- 空でも [] を書く(= 処理済みの印。 表示は欄が在れば新表示=alternative_titles.en を出さない)
- 可逆: --apply 時に .cache/other-names-bak-<日付>/manga.v2.tar.gz へ退避(preview は git 追跡なので不要)
- 記録: data/seeds/other-names-changelog.jsonl に概要1行 + 頁ごとの前後一覧(tsv.gz)

使い方:
  python scripts/_apply-other-names.py            # 下見(書かない・件数と見本)
  python scripts/_apply-other-names.py --apply
"""
from __future__ import annotations

import datetime
import gzip
import json
import os
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _other_names  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIRS = [ROOT / "data" / "manga.v2", ROOT / ".preview-data" / "manga"]
TODAY = datetime.date.today().strftime("%Y%m%d")
BAK = ROOT / ".cache" / f"other-names-bak-{TODAY}" / "manga.v2.tar.gz"
DETAIL = ROOT / "data" / "seeds" / f"other-names-apply-{TODAY}.tsv.gz"
CHANGELOG = ROOT / "data" / "seeds" / "other-names-changelog.jsonl"
KEYS = {"slug", "title", "title_kana", "subtitle", "title_romaji", "anilist_id",
        "work_wikidata_qid", "alternative_titles"}


def _split(text: str):
    """(other_names ブロックを除いた本文, 判定に要る上位キーだけの dict)。 全体の yaml 解析はしない(速度)。"""
    body, keep, cur, in_on = [], [], None, False
    for ln in text.split("\n"):
        top = bool(ln) and not ln[0].isspace() and not ln.startswith(("-", "#"))
        if top:
            k = ln.split(":", 1)[0]
            in_on = (k == "other_names")
            cur = k if k in KEYS else None
        if in_on:
            continue                               # other_names ブロック(要素行「- lang:」「  name:」も)は捨てて末尾に書き直す
        body.append(ln)
        if cur:
            keep.append(ln)
    d = yaml.load("\n".join(keep), Loader=yaml.CSafeLoader) or {}
    return "\n".join(body).rstrip("\n") + "\n", d


def _process(args):
    path, src = args
    text = path.read_text(encoding="utf-8")
    body, d = _split(text)
    names = _other_names.build(d, src)
    block = yaml.dump({"other_names": names}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    new = body + block
    en = str((d.get("alternative_titles") or {}).get("en") or "").strip()
    return path, (new != text), new, d, en, names


def main():
    apply = "--apply" in sys.argv
    src = _other_names.Sources()
    print(f"出所: {src.summary()}")
    files = [p for dd in DIRS for p in sorted(dd.glob("*.yml"))]
    print(f"対象: {len(files):,}ファイル(" + ", ".join(f"{dd.name}={len(list(dd.glob('*.yml'))):,}" for dd in DIRS) + ")")

    if apply:
        BAK.parent.mkdir(parents=True, exist_ok=True)
        if not BAK.exists():
            print(f"退避: {BAK} …")
            with tarfile.open(BAK, "w:gz", compresslevel=3) as tf:
                tf.add(DIRS[0], arcname="manga.v2")
            print(f"  退避済 {BAK.stat().st_size / 1e6:.0f}MB")

    stats = {"files": 0, "changed": 0, "nonempty": 0, "en_shown": 0, "en_kept": 0, "en_new": 0,
             "ai_en_hidden": 0, "ai_en_replaced": 0, "other_en_dropped": 0, "other_en_replaced": 0}
    rows = []
    samples = {"ai_en_hidden": [], "ai_en_replaced": [], "other_en_dropped": [], "other_en_replaced": [], "en_new": []}
    with ThreadPoolExecutor(8) as ex:
        for path, changed, new, d, en, names in ex.map(_process, [(p, src) for p in files], chunksize=200):
            stats["files"] += 1
            is_main = path.parent == DIRS[0]
            ens = [o["name"] for o in names if o["lang"] == "en"]
            if is_main:
                if names:
                    stats["nonempty"] += 1
                kind = ""
                if en:
                    stats["en_shown"] += 1
                    if en in ens:
                        kind = "en_kept"
                    elif _other_names.is_ai_en(src, d.get("title"), en):
                        kind = "ai_en_replaced" if ens else "ai_en_hidden"
                    else:   # AIでないが出さない(題と同じ・ローマ字の写し・レーベル名等)
                        kind = "other_en_replaced" if ens else "other_en_dropped"
                elif ens:
                    kind = "en_new"
                if kind:
                    stats[kind] += 1
                    if kind in samples and len(samples[kind]) < 6:
                        samples[kind].append(f"{path.stem}: {en or '(なし)'} → {' / '.join(ens) or '(出さない)'}")
                rows.append("\t".join([path.stem, en, kind,
                                       " | ".join(f"{o['lang']}:{o['name']}" for o in names)]))
            if changed:
                stats["changed"] += 1
                if apply:
                    path.write_text(new, encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
    for k, v in samples.items():
        print(f"-- {k}")
        for s in v:
            print(f"   {s}")
    if not apply:
        print("(下見のみ。 書くには --apply)")
        return
    with gzip.open(DETAIL, "wt", encoding="utf-8") as f:
        f.write("stem\tbefore_en\tkind\tafter_other_names\n" + "\n".join(rows) + "\n")
    rec = {"slug": "*", "op": "other-names-apply", "at": datetime.datetime.now().isoformat(timespec="seconds"),
           "rule": "scripts/_other_names.py(A1=AI英題は表示しない)", **stats,
           "detail": str(DETAIL.relative_to(ROOT)).replace(os.sep, "/"),
           "backup": str(BAK.relative_to(ROOT)).replace(os.sep, "/"),
           "revert": "other_names ブロックを外せば旧表示に戻る(他の欄は不変)"}
    with CHANGELOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"記録: {CHANGELOG.relative_to(ROOT)} / 明細 {DETAIL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
