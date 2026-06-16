#!/usr/bin/env python3
"""
genre×楽天あらすじ step0 (= [[genre_from_rakuten_story_plan]])

目的: 教師コーパスの作品単位件数を確定する (= trusted ∩ 楽天キャプション有り)。
副産物: 再利用可能な corpus.jsonl を永続化 → ISBN↔caption の重い join を二度とやり直さない。

入力:
  .cache/rakuten-isbn.jsonl       (= ISBN→item.itemCaption。楽天収穫)
  data/manga.v2/*.yml             (= 本番DB。work→genres / genres_provisional / isbn13)

出力:
  .cache/genre-rakuten/corpus.jsonl       (= caption有りの全work。trusted=教師, provisional=適用対象)
  .cache/genre-rakuten/step0-summary.json (= 件数サマリ)

trusted の定義 = genres があり、 'other' 単独でなく、 genres_provisional が立っていない work。
  (= promote が AniList genres+themes ∪ Wiki/手動 をマージした信頼ラベル。 [[genre_quality_improvement]])
"""
import json, sys, gzip, time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAK = ROOT / ".cache" / "rakuten-isbn.jsonl"
MANGA = ROOT / "data" / "manga.v2"
OUT_DIR = ROOT / ".cache" / "genre-rakuten"
OUT_DIR.mkdir(parents=True, exist_ok=True)

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

MIN_CAP = 40  # 分類に使えるキャプション最小長 (= memory実測の閾値)


def to_isbn13(s):
    if not s:
        return None
    s = str(s).replace("-", "").replace(" ", "").strip()
    if len(s) == 13 and s.isdigit():
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        try:
            tot = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(core))
        except ValueError:
            return None
        return core + str((10 - tot % 10) % 10)
    return None


def clean_caption(c):
    if not c:
        return ""
    c = c.replace("\r", " ").replace("\n", " ").replace("　", " ")
    while "  " in c:
        c = c.replace("  ", " ")
    return c.strip()


def load_captions():
    """ISBN13 → 最長キャプション (≥MIN_CAP)。"""
    cap = {}
    n = 0
    t0 = time.time()
    with open(RAK, encoding="utf-8") as f:
        for line in f:
            n += 1
            if n % 40000 == 0:
                print(f"  rakuten {n:,} 行... ({len(cap):,} caption) [{time.time()-t0:.0f}s]", flush=True)
            try:
                r = json.loads(line)
            except Exception:
                continue
            item = r.get("item") or {}
            cstr = clean_caption(item.get("itemCaption"))
            if len(cstr) < MIN_CAP:
                continue
            isbn = to_isbn13(r.get("isbn") or item.get("isbn"))
            if not isbn:
                continue
            old = cap.get(isbn)
            if old is None or len(cstr) > len(old):
                cap[isbn] = cstr
    print(f"  楽天キャプション: {len(cap):,} ISBN (≥{MIN_CAP}字) / {n:,} 行 [{time.time()-t0:.0f}s]", flush=True)
    return cap


def best_caption_for_work(vols, cap):
    """work の volumes から最良 caption を選ぶ: 1巻優先 → なければ最長。"""
    cands = []  # (number_or_big, isbn13, caption)
    for v in vols:
        isbn = to_isbn13(v.get("isbn13"))
        if not isbn:
            continue
        c = cap.get(isbn)
        if not c:
            continue
        num = v.get("number")
        num = num if isinstance(num, int) else 9999
        cands.append((num, isbn, c))
    if not cands:
        return None, None
    # 1巻があればそれ。 無ければ最長キャプション。
    v1 = [c for c in cands if c[0] == 1]
    if v1:
        v1.sort(key=lambda x: -len(x[2]))
        return v1[0][1], v1[0][2]
    cands.sort(key=lambda x: -len(x[2]))
    return cands[0][1], cands[0][2]


def main():
    print("=== step0: 楽天あらすじ × trusted ジャンル 教師コーパス確定 ===", flush=True)
    cap = load_captions()

    files = sorted(MANGA.glob("*.yml"))
    print(f"  manga.v2: {len(files):,} works を走査...", flush=True)

    corpus_path = OUT_DIR / "corpus.jsonl"
    cf = corpus_path.open("w", encoding="utf-8")

    st = {
        "total": 0, "trusted": 0, "provisional": 0, "other_only": 0, "no_genre": 0,
        "has_caption": 0, "teacher": 0, "apply_target": 0,
    }
    genre_label_counts = {}      # 教師コーパス内の genre 出現数
    teacher_multi = {}           # ラベル数ヒストグラム
    t0 = time.time()

    for i, fp in enumerate(files):
        if i % 8000 == 0 and i:
            print(f"  ...{i:,}/{len(files):,} [{time.time()-t0:.0f}s]", flush=True)
        try:
            d = yaml.load(fp.read_text(encoding="utf-8"), Loader=Loader)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        st["total"] += 1
        genres = d.get("genres") or []
        prov = bool(d.get("genres_provisional"))
        # 分類
        if not genres:
            st["no_genre"] += 1
            is_trusted = False
        elif genres == ["other"]:
            st["other_only"] += 1
            is_trusted = False
        elif prov:
            st["provisional"] += 1
            is_trusted = False
        else:
            st["trusted"] += 1
            is_trusted = True

        # caption 収集
        vols = []
        for ed in (d.get("editions") or []):
            for v in (ed.get("volumes") or []):
                vols.append(v)
        cap_isbn, caption = best_caption_for_work(vols, cap)
        if not caption:
            continue
        st["has_caption"] += 1

        rec = {
            "slug": d.get("slug"),
            "title": d.get("title"),
            "anilist_id": d.get("anilist_id"),
            "label": sorted(genres) if is_trusted else [],
            "provisional": prov,
            "trusted": is_trusted,
            "genres_current": sorted(genres),
            "genres_anilist": d.get("genres_anilist") or [],
            "caption_isbn": cap_isbn,
            "caption": caption,
        }
        cf.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if is_trusted:
            st["teacher"] += 1
            for g in genres:
                genre_label_counts[g] = genre_label_counts.get(g, 0) + 1
            teacher_multi[len(genres)] = teacher_multi.get(len(genres), 0) + 1
        elif prov:
            st["apply_target"] += 1

    cf.close()

    # master 32 キー順で並べる
    master_order = list(yaml.safe_load((ROOT / "data" / "genres.yml").read_text(encoding="utf-8")).keys())
    glc_sorted = sorted(genre_label_counts.items(), key=lambda x: -x[1])

    summary = {
        "min_caption_len": MIN_CAP,
        "rakuten_caption_isbn": len(cap),
        "stats": st,
        "genre_label_counts": dict(glc_sorted),
        "teacher_label_cardinality": dict(sorted(teacher_multi.items())),
        "master_genres": master_order,
    }
    (OUT_DIR / "step0-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n========== step0 結果 ==========", flush=True)
    print(f"manga.v2 総work数        : {st['total']:,}", flush=True)
    print(f"  trusted (信頼ラベル)   : {st['trusted']:,}", flush=True)
    print(f"  provisional (AI暫定)   : {st['provisional']:,}", flush=True)
    print(f"  other単独              : {st['other_only']:,}", flush=True)
    print(f"  genre無               : {st['no_genre']:,}", flush=True)
    print(f"楽天caption有 work       : {st['has_caption']:,}", flush=True)
    print(f"★教師コーパス (trusted∩caption) : {st['teacher']:,}", flush=True)
    print(f"★適用対象 (provisional∩caption) : {st['apply_target']:,}", flush=True)
    print("\n-- 教師コーパス ジャンル別ラベル数 (上位) --", flush=True)
    for g, c in glc_sorted:
        bar = "#" * (c // 200)
        print(f"  {g:14s} {c:6,d} {bar}", flush=True)
    print(f"\ncorpus → {corpus_path}", flush=True)
    print(f"summary → {OUT_DIR / 'step0-summary.json'}", flush=True)


if __name__ == "__main__":
    main()
