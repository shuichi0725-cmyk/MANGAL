#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""genre:other残737のうち楽天材料なし分をGeminiで同定(カテゴリのみ。2026-07-13ユーザ裁定)。

- モデル: gemini-3.1-flash-lite(無料枠15RPM/1000RPD・検索グラウンディング無し=単体知識)
- 対象: data/manga.v2 で genres==["other"] かつ FLAG(genre-other-flags.tsv)に無い頁
- 出力: .cache/gemini-genre/results.jsonl へ逐次追記(再開可能・429で即中断)
- 適用は別工程(known/confidence/master32検証後)。このscriptは照会のみ。
"""
import json, os, sys, time, glob, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = f"{ROOT}/.cache/gemini-genre"
os.makedirs(OUT_DIR, exist_ok=True)
OUT = f"{OUT_DIR}/results.jsonl"
MODEL = "gemini-3.1-flash-lite"

env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1); env[k] = v
KEY = env["GEMINI_API_KEY"]

# FLAG済み(裁定待ち)は除外
flags = set()
fp = f"{ROOT}/docs/production-diagnostics/genre-other-flags.tsv"
if os.path.exists(fp):
    for i, ln in enumerate(open(fp, encoding="utf-8")):
        if i == 0: continue
        flags.add(ln.split("\t")[0].strip())

done = set()
if os.path.exists(OUT):
    for ln in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(ln)["slug"])
        except Exception: pass

# 対象抽出
targets = []
for p in sorted(glob.glob(f"{ROOT}/data/manga.v2/*.yml")):
    slug = os.path.basename(p)[:-4]
    if slug in flags or slug in done: continue
    txt = open(p, encoding="utf-8").read()
    if "- other" not in txt: continue
    m = yaml.safe_load(txt)
    if (m.get("genres") or []) != ["other"]: continue
    vols = sum(len(e.get("volumes") or []) for e in m.get("editions", []))
    pub = m.get("publisher") or ""
    targets.append({"slug": slug, "title": str(m.get("title")), "kana": str(m.get("title_kana") or ""),
                    "authors": [a.get("name") for a in (m.get("authors") or [])],
                    "year": m.get("year_started"), "year_end": m.get("year_ended"),
                    "publisher": pub, "vols": vols})
print(f"対象 {len(targets)} 件(既照会{len(done)}除外済)", flush=True)

PROMPT = """日本の漫画作品の同定タスク。以下の書誌について、あなたが実際に知っている情報だけで答えよ。知らない場合は必ず known=false とし、推測でジャンルを付けないこと。

題名: {title}(ヨミ: {kana})
著者: {authors}
出版: {publisher} {year}〜{year_end}年 全{vols}巻

厳密なJSONのみで回答(コードブロック禁止):
{{"known": true/false,
 "work_type": "story_manga|short_collection|essay_manga|educational_manga|art_book|non_manga|unknown",
 "description": "60字以内の内容説明(知らなければ空)",
 "genres": ["次のリストから0-3個(該当なしは空): action,adventure,fantasy,sci-fi,mystery,horror,gag,comedy,romcom,romance,drama,slice-of-life,school,sports,baseball,soccer,historical,samurai,mecha,yokai,gourmet,4-koma,essay,isekai,bl,suspense,music,supernatural,ecchi,mind-game,mahou-shoujo,war"],
 "confidence": "high|medium|low"}}"""

def call(t):
    p = PROMPT.format(title=t["title"], kana=t["kana"], authors="、".join(t["authors"]) or "不明",
                      publisher=t["publisher"], year=t["year"] or "?", year_end=t["year_end"] or "", vols=t["vols"])
    body = {"contents": [{"parts": [{"text": p}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return d["candidates"][0]["content"]["parts"][0]["text"]

n_ok = n_err = 0
for i, t in enumerate(targets):
    try:
        raw = call(t)
        raw_s = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            ans = json.loads(raw_s)
        except Exception:
            ans = {"parse_error": raw_s[:200]}
        rec = {"slug": t["slug"], "title": t["title"], "model": MODEL, "ans": ans}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n_ok += 1
    except urllib.error.HTTPError as e:
        code = e.code
        if code == 429:
            print(f"★429(日次quota到達の可能性)→中断。処理済 {n_ok}", flush=True)
            sys.exit(2)
        if code >= 500:
            time.sleep(20)  # 一時混雑は1回だけ待って続行(次ループで再試行はしない=take next)
        n_err += 1
    except Exception as ex:
        n_err += 1
    if (i + 1) % 25 == 0:
        print(f"  {i+1}/{len(targets)} (ok {n_ok} / err {n_err})", flush=True)
    time.sleep(4.5)  # 15RPM遵守
print(f"完了: ok {n_ok} / err {n_err} → {OUT}", flush=True)
