#!/usr/bin/env python3
"""
タグ(要素)× 楽天あらすじ step1 = 学習準備 (= [[genre_from_rakuten_story_plan]] のタグ版)

ジャンル版と同一手法。違い:
- ラベル = AniList theme tags(Demographic 除外)。closed vocab = support≥MINSUP の theme tag。
- 表示語彙 = data/seeds/tag-i18n.yml(英tag→日本語)。
- held-out = ジャンル版と**同じ 3,000 work**(heldout-truth.jsonl の slug を再利用)→ 同一作で突合可。
  caption batch も既存 heldout-batches を再利用(再分類のみ)。

出力:
  .cache/genre-rakuten/heldout-tag-truth.jsonl   (= held-out の trusted theme tags)
  .cache/genre-rakuten/tag-vocab.json            (= closed vocab: key, ja, support)
  .cache/genre-rakuten/tag-rubric.md             (= LLM へ渡す語彙表)
  .cache/genre-rakuten/tag-cues.json             (= train由来の特徴語=学習の可読化)
"""
import json, sys, re, math
from pathlib import Path
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
CORPUS = OUT / "corpus.jsonl"
MANGA = ROOT / "data" / "manga.v2"

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

MINSUP = 50  # closed vocab に入れる theme tag の最低 support(caption×trusted内)

# tag-i18n(英tag→日本語)
ti = yaml.safe_load((ROOT / "data" / "seeds" / "tag-i18n.yml").read_text(encoding="utf-8"))
TAG_JA = {k: (v.get("ja") or k) for k, v in (ti.get("tags") or {}).items()}

STOP = set("物語 作品 描く 連載 コミック シリーズ 単行本 収録 登場 主人公 世界 少年 少女 "
           "彼女 彼ら 自分 一人 二人 始まる 始まり そして しかし だった ている である "
           "という ことが ような 描いた 贈る 雑誌 電子 限定 特典 試し読み 無料 配信".split())


def terms(cap):
    out = set()
    for m in re.findall(r"[゠-ヿーー]{2,6}", cap):
        out.add(m)
    for run in re.findall(r"[一-鿿]{2,}", cap):
        for n in (2, 3):
            for i in range(len(run) - n + 1):
                t = run[i:i+n]
                if t not in STOP:
                    out.add(t)
    return out


def main():
    # caption + trusted フラグ
    cap = {}; trusted = {}
    for line in CORPUS.open(encoding="utf-8"):
        r = json.loads(line)
        cap[r["slug"]] = r["caption"]; trusted[r["slug"]] = bool(r.get("trusted"))

    held_slugs = []
    for line in (OUT / "heldout-truth.jsonl").open(encoding="utf-8"):
        held_slugs.append(json.loads(line)["slug"])
    held_set = set(held_slugs)

    # manga.v2 から theme tags 収集(caption有り work のみ)
    tags_of = {}
    sup = Counter()  # trusted work での theme tag support
    for s in cap:
        fp = MANGA / f"{s}.yml"
        if not fp.exists():
            continue
        try:
            d = yaml.load(fp.read_text(encoding="utf-8"), Loader=Loader)
        except Exception:
            continue
        th = [t.get("name") for t in (d.get("tags") or [])
              if t.get("category") and t.get("category") != "Demographic" and t.get("name")]
        th = sorted(set(th))
        tags_of[s] = th
        if trusted.get(s) and th:
            for t in th:
                sup[t] += 1

    vocab = [t for t, c in sup.most_common() if c >= MINSUP]
    vocab_set = set(vocab)
    print(f"caption有り work: {len(cap):,}", flush=True)
    print(f"theme tag 種(caption内): {len(sup):,} / vocab(support≥{MINSUP}): {len(vocab)}", flush=True)

    # held-out tag truth(vocab に絞る)
    n_held_tag = 0
    with (OUT / "heldout-tag-truth.jsonl").open("w", encoding="utf-8") as f:
        for s in held_slugs:
            th = [t for t in tags_of.get(s, []) if t in vocab_set]
            f.write(json.dumps({"slug": s, "caption": cap[s], "tags": sorted(th)}, ensure_ascii=False) + "\n")
            if th:
                n_held_tag += 1
    print(f"held-out 3,000 のうち theme tag(vocab内)有り = {n_held_tag} 件(=tag評価母数)", flush=True)

    # vocab.json
    (OUT / "tag-vocab.json").write_text(json.dumps(
        [{"key": t, "ja": TAG_JA.get(t, t), "support": sup[t]} for t in vocab],
        ensure_ascii=False, indent=2), encoding="utf-8")

    # ===== train(held-out外 trusted theme-tag work)から特徴語採掘 =====
    train = [s for s in cap if trusted.get(s) and s not in held_set and tags_of.get(s)]
    df = Counter(); tdf = defaultdict(Counter); tcount = Counter()
    N = len(train)
    for s in train:
        tset = terms(cap[s])
        for w in tset:
            df[w] += 1
        for t in tags_of[s]:
            if t not in vocab_set:
                continue
            tcount[t] += 1
            for w in tset:
                tdf[t][w] += 1
    df = {w: c for w, c in df.items() if c >= 8}
    cues = {}
    for t in vocab:
        nt = tcount.get(t, 0)
        if not nt:
            cues[t] = []; continue
        scored = []
        for w, c_in in tdf[t].items():
            if w not in df or c_in < 4:
                continue
            c_all = df[w]
            lo = math.log(((c_in+0.5)/(nt+1)) / ((c_all-c_in+0.5)/(N-nt+1)))
            if lo > 0:
                scored.append((lo, c_in, w))
        scored.sort(reverse=True)
        cues[t] = [{"term": w, "lo": round(lo, 2), "n": c} for lo, c, w in scored[:12]]
    (OUT / "tag-cues.json").write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")

    # rubric.md
    lines = [f"# 要素タグ判定 rubric (closed vocab = theme tag support≥{MINSUP}, {len(vocab)}種)\n",
             "形式: `key`(日本語) — train特徴語\n"]
    for t in vocab:
        top = " / ".join(c["term"] for c in cues[t][:6]) or "(特徴語薄)"
        lines.append(f"- `{t}` ({TAG_JA.get(t,t)}) [sup {sup[t]}]: {top}")
    (OUT / "tag-rubric.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n-- vocab(support順)--", flush=True)
    for t in vocab:
        print(f"  {sup[t]:5d} {t:28s} {TAG_JA.get(t,t)}", flush=True)
    print(f"\nvocab→{OUT/'tag-vocab.json'} rubric→{OUT/'tag-rubric.md'} truth→{OUT/'heldout-tag-truth.jsonl'}", flush=True)


if __name__ == "__main__":
    main()
