# -*- coding: utf-8 -*-
"""日替わり特集コーナーの stock 生成(2026-08-03 ユーザ採用。導線=案A/B日替わり・頁=案1/2日替わり・題材色)。

仕組み([[sansedai_archive_frozen_log]] と同じ凍結ログ思想):
- フィルタ軸(年代×ジャンル×対象×並び)からレシピをランダム抽選し、本番索引で件数ゲート
  (30作未満は引き直し)→ 上位100 slug を**その日の分として凍結**して stock に書く。
- ★既存日付は絶対に触らない(純粋追加)= 表示済み・生成済みの日は永久固定=過去ログが安定。
- 今日〜+45日分を常に確保(週次蒸留の事前再生成で再実行=補充)。
- 見た目: 導線 A/B・頁 1/2 を日付ハッシュで機械割当。色は題材(ジャンル)ごとのアクセント。

出力(★自己完結型=カレンダー方式。preview のsubset索引に依存せず、頁も22MB索引を読まない):
  public/data/tokushu/index.json          … {"days":{date:{"t","n","sty","c"}}} = 導線/過去ログ用(軽量)
  public/data/tokushu/<date>.json         … その号の全量 {"t","lead","n","q","sty","c",
        "items":[[slug,題,著者,書影URL,開始年,終了年|null,status], ...]} = 頁が単独で描画できる

使い方: python scripts/_gen-daily-feature.py [--days 45]
"""
import argparse
import io
import json
import os
import random
import sys
from datetime import date, timedelta

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "public", "data", "tokushu")
IDX = os.path.join(OUTDIR, "index.json")

RK_PRE = "https://thumbnail.image.rakuten.co.jp/@0_mall/"  # coverSlim.ts と同じ復元則


def full_cover(c):
    if not c:
        return None
    return c if c.startswith("http") else RK_PRE + c + "?_ex=300x300"

DEMO_JA = {"shounen": "少年漫画", "shoujo": "少女漫画", "seinen": "青年漫画", "josei": "女性漫画"}
SORT_JA = {"pop": "人気順", "score": "高評価順"}
# 題材色(ジャンル→アクセント/濃色)。無指定レシピは既定の赤。
GENRE_COLOR = {
    "romance": ("#d23f6f", "#a92752"), "romcom": ("#d23f6f", "#a92752"), "bl": ("#c65b9a", "#94406f"),
    "sci-fi": ("#2f5fd2", "#1f3f8f"), "mecha": ("#2f5fd2", "#1f3f8f"),
    "mystery": ("#34495e", "#22303e"), "suspense": ("#34495e", "#22303e"), "mind-game": ("#34495e", "#22303e"),
    "horror": ("#6b3fa0", "#4a2a73"), "yokai": ("#6b3fa0", "#4a2a73"), "supernatural": ("#6b3fa0", "#4a2a73"),
    "fantasy": ("#1f9a7a", "#126b54"), "isekai": ("#1f9a7a", "#126b54"), "mahou-shoujo": ("#c65b9a", "#94406f"),
    "sports": ("#e0892e", "#b0691f"), "baseball": ("#e0892e", "#b0691f"), "soccer": ("#2e9e4f", "#1f7038"),
    "historical": ("#7c5a35", "#59401f"), "samurai": ("#7c5a35", "#59401f"), "war": ("#5d6b46", "#414d30"),
    "gourmet": ("#c9702a", "#9a531d"), "gag": ("#d9a013", "#a67a0a"), "comedy": ("#d9a013", "#a67a0a"),
    "4-koma": ("#d9a013", "#a67a0a"), "slice-of-life": ("#4f9d4f", "#37703b"), "school": ("#4f9d4f", "#37703b"),
    "essay": ("#4f9d4f", "#37703b"), "music": ("#8a4fd2", "#63389a"),
}
DEFAULT_COLOR = ("#d23f3f", "#a92f2f")
MIN_WORKS = 30
TOP_N = 100


def load_index():
    raw = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = raw["f"]
    return [dict(zip(f, r)) for r in raw["d"]]


def pick_recipe(rows, rng, genre_names, used_keys):
    """レシピ抽選 → (key, 題, lead素材, 対象rows, browseクエリ, 色)。ゲート落ち/重複は None。"""
    shape = rng.choice(["dg", "g", "mg", "md", "dgm"])  # 年代×ジャンル / ジャンル / 対象×ジャンル / 対象×年代 / 三軸
    decade = rng.choice(range(1960, 2030, 10)) if "d" in shape else None
    genre = rng.choice(list(genre_names)) if "g" in shape else None
    demo = rng.choice(list(DEMO_JA)) if "m" in shape else None
    sort = rng.choice(["pop", "pop", "score"])  # 人気順を厚めに
    key = f"{decade}|{genre}|{demo}|{sort}"
    if key in used_keys:
        return None
    sel = []
    for m in rows:
        if decade is not None:
            y = m.get("year_started") or 0
            if not (decade <= y < decade + 10):
                continue
        if genre and genre not in (m.get("genres") or []):
            continue
        if demo and m.get("demographic") != demo:
            continue
        if not m.get("cover"):
            continue  # 棚型の見た目が崩れるので書影必須
        if sort == "score" and not m.get("score"):
            continue
        sel.append(m)
    if len(sel) < MIN_WORKS:
        return None
    sel.sort(key=lambda m: -(m.get("popularity") or 0) if sort == "pop" else -(m.get("score") or 0))
    sel = sel[:TOP_N]
    # 題: 「80年代ラブコメ 100選」「少女漫画のSF 45選」「90年代の青年漫画 100選」
    parts = []
    if decade is not None:
        parts.append(f"{str(decade)[2:4]}年代" if decade < 2000 else f"{decade}年代")
    if demo:
        parts.append(DEMO_JA[demo] + ("の" if genre else ""))
    if genre:
        parts.append(genre_names[genre])
    if not genre and demo:
        parts[-1] = DEMO_JA[demo]  # 「の」を戻す
    label = "".join(parts) if (genre or demo) else (parts[0] + "の漫画")
    title = f"{label} {len(sel)}選"
    top3 = "、".join(m["title"] for m in sel[:3])
    lead = f"{top3}——。{label}から{SORT_JA[sort]}に{len(sel)}作。"
    q = []
    if genre:
        q.append(f"genre={genre}")
    if demo:
        q.append(f"demographic={demo}")
    if decade is not None:
        q.append(f"yearMin={decade}&yearMax={decade + 9}")
    q.append("sort=popularity" if sort == "pop" else "sort=score")
    color = GENRE_COLOR.get(genre or "", DEFAULT_COLOR)
    return key, title, lead, sel, "&".join(q), color


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45)
    a = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    idx = {"days": {}}
    if os.path.exists(IDX):
        idx = json.load(open(IDX, encoding="utf-8"))
    days = idx.setdefault("days", {})
    rows = load_index()
    gy = yaml.safe_load(io.open(os.path.join(ROOT, "data", "genres.yml"), encoding="utf-8"))
    genre_names = {k: v["name"] for k, v in gy.items()}
    used = {v.get("k") for v in days.values() if v.get("k")}
    today = date.today()
    added = 0
    for i in range(a.days + 1):
        d = (today + timedelta(days=i)).isoformat()
        if d in days and os.path.exists(os.path.join(OUTDIR, d + ".json")):
            continue  # ★凍結: 既存日付は触らない
        rng = random.Random(d)  # 日付シード=再実行しても同じ日は同じ結果(冪等)
        got = None
        for _ in range(200):
            got = pick_recipe(rows, rng, genre_names, used)
            if got:
                break
        if not got:
            print(f"! {d}: レシピ抽選200回失敗(skip)")
            continue
        key, title, lead, sel, q, color = got
        used.add(key)
        h = sum(ord(c) for c in d)
        sty = {"l": "A" if h % 2 == 0 else "B", "p": 1 if (h // 2) % 2 == 0 else 2}
        col = {"a": color[0], "d": color[1]}
        items = [[m["slug"], m["title"],
                  "・".join(x.split("\t")[0] for x in (m.get("authors") or [])[:2]),
                  full_cover(m.get("cover")), m.get("year_started"), m.get("year_ended"),
                  m.get("status")] for m in sel]
        day_doc = {"t": title, "lead": lead, "n": len(sel), "q": q, "sty": sty, "c": col, "items": items}
        json.dump(day_doc, io.open(os.path.join(OUTDIR, d + ".json"), "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, separators=(",", ":"))
        days[d] = {"k": key, "t": title, "n": len(sel), "sty": sty, "c": col}
        added += 1
    json.dump(idx, io.open(IDX, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
    print(f"stock: 追加{added}日 / 総{len(days)}日 → {OUTDIR}")
    t = days.get(today.isoformat())
    if t:
        print(f"今日: {t['t']} (導線{t['sty']['l']}/頁{t['sty']['p']}/{t['c']['a']})")


if __name__ == "__main__":
    main()
