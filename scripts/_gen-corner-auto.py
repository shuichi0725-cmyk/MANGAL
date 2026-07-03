#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自動コーナー用データ生成(1パス): 周年(anniversaries.json) + 豪華版(deluxe-stock.json)。

- 周年: standard v1 の完全日付(YYYY-MM-DD)を持つ作品を MM-DD で束ねる(書影必須・成人除外・各日cap)。
  клиент(AnniversaryDaily)が「今日でN周年」を計算(round優先)。
- 豪華版: variants(特装/限定)のうち variant書影ありを列挙(成人除外)。
  ★価格は出力しない(2026-07-03 ユーザ裁定: 静的価格表示は絶対禁止 [[feedback-no-static-prices]])。
週次再生成対象(カレンダー/stock JSONと同じstale生成物クラス)。
"""
import glob, json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(ROOT, "public", "data")
os.makedirs(OUTD, exist_ok=True)
DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

ann = {}   # "MM-DD" -> [{s,t,y,c}]
dlx = []   # [{s,t,v,l,c}]
n = 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    n += 1
    try:
        d = yaml.load(open(p, encoding="utf-8"), Loader=L)
    except Exception:
        continue
    if not d or d.get("adult") or d.get("adult_us"):
        continue
    slug = d.get("slug") or os.path.basename(p)[:-4]
    title = d.get("title") or ""
    for e in d.get("editions") or []:
        if e.get("type") != "standard":
            continue
        for v in e.get("volumes") or []:
            # 周年: v1 完全日付+書影
            if v.get("number") == 1:
                m = DAY_RE.match(str(v.get("release_date") or ""))
                if m and v.get("cover_url"):
                    ann.setdefault(f"{m.group(2)}-{m.group(3)}", []).append(
                        {"s": slug, "t": title, "y": int(m.group(1)), "c": v["cover_url"]})
            # 豪華版: variant書影あり(価格は出力しない=表示禁止)
            for vr in v.get("variants") or []:
                if vr.get("cover_url"):
                    dlx.append({"s": slug, "t": title, "v": v.get("number"),
                                "l": vr.get("label") or "特装版", "c": vr["cover_url"]})

# 周年: 各日 古い順cap12(古い=周年数が大きく話題性が高い)
for k in ann:
    ann[k] = sorted(ann[k], key=lambda x: x["y"])[:12]
json.dump(ann, open(os.path.join(OUTD, "anniversaries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
dlx.sort(key=lambda x: (x["s"], x["v"] or 0))
json.dump(dlx, open(os.path.join(OUTD, "deluxe-stock.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
days = len(ann)
print(f"走査{n} → 周年: {sum(len(v) for v in ann.values())}件/{days}日分 / 豪華版: {len(dlx)}件")
