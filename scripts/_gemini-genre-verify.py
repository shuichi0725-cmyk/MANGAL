#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本番のprovisionalジャンル/要素をGeminiで検品(2026-07-14 ユーザ設計)。

対象 = data/manga.v2 で genres_provisional: true の頁(~25,000)。
Geminiにはブラインドで(現ジャンルを見せず)書誌だけ渡して同定させ、オフラインで突合する。
要素(themes)は現リストを見せて「明らかに不適合」だけ挙げさせる。

運転:
  python scripts/_gemini-genre-verify.py            # queue先頭から429まで照会(再開可能)
  python scripts/_gemini-genre-verify.py --report   # 突合レポート(一致/部分/不一致)を出す
適用は別工程(不一致をAIが目視レビュー→ゲート通過分のみ)。このscriptは照会と報告のみ。
queue順 = ①材料なし頁(catch/synopsis空=題名だけでAI付与された疑い濃) ②残り(slug昇順=端から全件)。
429(無料枠~500req/日・PT深夜=JST16時リセット)で即中断・翌日そのまま再実行。
"""
import json, os, sys, time, glob, argparse, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = f"{ROOT}/.cache/gemini-genre"
os.makedirs(OUT_DIR, exist_ok=True)
OUT = f"{OUT_DIR}/verify-results.jsonl"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

ap = argparse.ArgumentParser()
ap.add_argument("--report", action="store_true")
ap.add_argument("--limit", type=int, default=10**9)
a = ap.parse_args()

MASTER = set(yaml.safe_load(open(f"{ROOT}/data/genres.yml", encoding="utf-8")).keys())

def load_results():
    res = {}
    if os.path.exists(OUT):
        for ln in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(ln); res[r["slug"]] = r
            except Exception:
                pass
    return res

def build_queue():
    q1, q2 = [], []
    for p in sorted(glob.glob(f"{ROOT}/data/manga.v2/*.yml")):
        txt = open(p, encoding="utf-8").read()
        if "genres_provisional: true" not in txt:
            continue
        m = yaml.safe_load(txt)
        if not m.get("genres"):
            continue
        slug = os.path.basename(p)[:-4]
        rec = {"slug": slug, "title": str(m.get("title")), "kana": str(m.get("title_kana") or ""),
               "authors": [x.get("name") for x in (m.get("authors") or [])],
               "year": m.get("year_started"), "year_end": m.get("year_ended"),
               "publisher": m.get("publisher") or "",
               "vols": sum(len(e.get("volumes") or []) for e in m.get("editions", [])),
               "genres_now": m.get("genres"), "themes_now": (m.get("themes") or [])[:12]}
        nomaterial = not ((m.get("catch") or "").strip() or (m.get("synopsis") or "").strip())
        (q1 if nomaterial else q2).append(rec)
    return q1 + q2

PROMPT = """日本の漫画作品の同定タスク。以下の書誌について、あなたが実際に知っている情報だけで答えよ。知らない場合は必ず known=false とし、推測でジャンルを付けないこと。

題名: {title}(ヨミ: {kana})
著者: {authors}
出版: {publisher} {year}〜{year_end}年 全{vols}巻

質問1: この作品に合うジャンルを次のリストから0-3個選べ(該当なしは空):
action,adventure,fantasy,sci-fi,mystery,horror,gag,comedy,romcom,romance,drama,slice-of-life,school,sports,baseball,soccer,historical,samurai,mecha,yokai,gourmet,4-koma,essay,isekai,bl,suspense,music,supernatural,ecchi,mind-game,mahou-shoujo,war
質問2: 現在この作品には要素タグ {themes} が付いている。作品内容と明らかに合わないものだけ挙げよ(全部妥当なら空)。

厳密なJSONのみで回答(コードブロック禁止):
{{"known": true/false, "work_type": "story_manga|short_collection|essay_manga|educational_manga|art_book|non_manga|unknown",
 "description": "40字以内(知らなければ空)", "genres": [], "bad_tags": [], "confidence": "high|medium|low"}}"""

def call(t):
    p = PROMPT.format(title=t["title"], kana=t["kana"], authors="、".join(t["authors"]) or "不明",
                      publisher=t["publisher"], year=t["year"] or "?", year_end=t["year_end"] or "",
                      vols=t["vols"], themes=json.dumps(t["themes_now"], ensure_ascii=False))
    body = {"contents": [{"parts": [{"text": p}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}}
    env = {}
    for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.strip().split("=", 1); env[k] = v
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={env['GEMINI_API_KEY']}",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return d["candidates"][0]["content"]["parts"][0]["text"]

done = load_results()

if a.report:
    agree = partial = disagree = unknown = 0
    rows = []
    for slug, r in done.items():
        ans = r.get("ans", {})
        if not ans.get("known") or ans.get("confidence") == "low":
            unknown += 1; continue
        gg = set(x for x in (ans.get("genres") or []) if x in MASTER)
        cur = set(r.get("genres_now") or [])
        bad = ans.get("bad_tags") or []
        inter = gg & cur
        if gg == cur and not bad: agree += 1
        elif inter or (not gg and not cur): partial += 1
        else:
            disagree += 1
            rows.append((slug, r.get("title",""), sorted(cur), sorted(gg), bad, ans.get("description","")))
        if bad and (gg == cur or inter):
            rows.append((slug, r.get("title",""), sorted(cur), sorted(gg), bad, "タグ不適合のみ"))
    print(f"照会済 {len(done)} / 一致 {agree} / 部分一致 {partial} / 不一致 {disagree} / unknown・low {unknown}")
    with open(f"{ROOT}/docs/production-diagnostics/genre-verify-disagree.tsv", "w", encoding="utf-8") as f:
        f.write("slug\ttitle\t現行\tGemini案\tbad_tags\tdesc\n")
        for row in rows:
            f.write("\t".join(json.dumps(x, ensure_ascii=False) if isinstance(x, (list,)) else str(x) for x in row) + "\n")
    print(f"不一致tsv → docs/production-diagnostics/genre-verify-disagree.tsv ({len(rows)}行)")
    sys.exit(0)

queue = [t for t in build_queue() if t["slug"] not in done]
print(f"queue {len(queue)} 件(照会済{len(done)}除外)", flush=True)
n_ok = n_err = 0
for i, t in enumerate(queue[:a.limit]):
    try:
        raw = call(t).strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try: ans = json.loads(raw)
        except Exception: ans = {"parse_error": raw[:200]}
        rec = {"slug": t["slug"], "title": t["title"], "genres_now": t["genres_now"],
               "themes_now": t["themes_now"], "model": MODEL, "ans": ans}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n_ok += 1
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"★429(日次quota)→中断。今回 {n_ok} 件", flush=True)
            sys.exit(2)
        if e.code >= 500: time.sleep(20)
        n_err += 1
    except Exception:
        n_err += 1
    if (i + 1) % 50 == 0:
        print(f"  {i+1} (ok {n_ok} / err {n_err})", flush=True)
    time.sleep(4.5)
print(f"完了: ok {n_ok} / err {n_err}", flush=True)
