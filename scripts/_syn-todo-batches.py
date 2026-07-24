"""synopsis和訳の未訳 delta を抽出 → 100件/batch で .cache/syn-batches-v2/ へ分割。

[[synopsis_ja_seed]] / CLAUDE.md「synopsis和訳 = git追跡 seed」の Step2 実体。
  対象 = enrich済み anilist_id ∧ synopsis-ja.json に未存在 ∧ AniList description 有。
  出力 = batch-NNN.json = [{anilist_id, romaji, native, english, volumes, genres, isAdult, desc}, ...]
  → AI が 60-120字の日本語要約を作り {aid: ja} で .cache/syn-out/ へ → _apply-synopsis.py で純粋追加。

read-only (= seed も DB も書かない)。 usage: python scripts/_syn-todo-batches.py [--size 100]
"""
import gzip
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ENRICH = ROOT / ".cache" / "anilist-enrich-map.json"
DUMP = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
MAP = ROOT / "data" / "seeds" / "synopsis-ja.json"
OUTDIR = ROOT / ".cache" / "syn-batches-v2"
TAG = re.compile(r"<[^>]+>")
# ★AniList は「あらすじ本体ゼロ + 注記だけ」の record が多い(= "Note: Includes one extra
#   chapter." 型が 212件)。 これを desc 有として拾うと、AI が巻数/ジャンルから定型文を
#   でっち上げる圧力になる(= [[feedback_accuracy_is_the_goal]] 違反)。 注記/出典を剥いだ
#   「本体」で長さ判定し、本体が無いものは対象外にする。
NOTE = re.compile(r"\s*Note:.*$", re.I | re.S)
SOURCE = re.compile(r"\(Source:[^)]*\)")


def clean(s):
    """AniList description は <br>/<i> 等の HTML 混じり。 素のテキストへ。"""
    s = TAG.sub(" ", s or "")
    s = s.replace("&quot;", '"').replace("&amp;", "&").replace("&#039;", "'")
    return re.sub(r"\s+", " ", s).strip()


def body(s):
    """注記(Note:)・出典(Source:)を剥いだ「あらすじ本体」。 これが空なら和訳不可。"""
    return SOURCE.sub("", NOTE.sub("", s)).strip()


def main():
    size = 100
    if "--size" in sys.argv:
        size = int(sys.argv[sys.argv.index("--size") + 1])

    aids = {str(v["anilist_id"]) for v in json.loads(ENRICH.read_text(encoding="utf-8")).values()
            if v.get("anilist_id")}
    have = set(json.loads(MAP.read_text(encoding="utf-8")).keys())
    todo_ids = aids - have
    print(f"enrich aid {len(aids):,} / 既訳 {len(have):,} / 未訳候補 {len(todo_ids):,}")

    todo, no_desc, note_only = [], 0, 0
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            aid = str(d.get("id"))
            if aid not in todo_ids:
                continue
            desc = clean(d.get("description"))
            if len(desc) < 30:
                no_desc += 1
                continue
            if len(body(desc)) < 20:      # ★注記だけ = あらすじ本体ゼロ → 和訳不可
                note_only += 1
                continue
            t = d.get("title") or {}
            todo.append({
                "anilist_id": aid, "romaji": t.get("romaji"), "native": t.get("native"),
                "english": t.get("english"), "volumes": d.get("volumes"),
                "genres": d.get("genres") or [], "isAdult": bool(d.get("isAdult")),
                "desc": desc[:1200],
            })
    # popularity 順ではなく aid 昇順 (= 決定論的・再開しやすい)
    todo.sort(key=lambda x: int(x["anilist_id"]))
    print(f"  ★和訳可 {len(todo):,} / desc無・短すぎ {no_desc:,} / "
          f"注記のみ(本体ゼロ) {note_only:,} (= 後2者は和訳不可、対象外)")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    for old in OUTDIR.glob("batch-*.json"):
        old.unlink()
    n = 0
    for i in range(0, len(todo), size):
        p = OUTDIR / f"batch-{i // size:03d}.json"
        p.write_text(json.dumps(todo[i:i + size], ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
    print(f"  → {OUTDIR} に {n} batch ({size}件/batch)")


if __name__ == "__main__":
    main()
