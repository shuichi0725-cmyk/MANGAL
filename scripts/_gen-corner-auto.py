#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自動コーナー用データ生成(1パス): 周年(anniversaries.json) + 豪華版(deluxe-stock.json)
   + 愛蔵版(aizouban-stock.json)。

- 周年: standard v1 の完全日付(YYYY-MM-DD)を持つ作品を MM-DD で束ねる(書影必須・成人除外・各日cap)。
  клиент(AnniversaryDaily)が「今日でN周年」を計算(round優先)。
- 豪華版: variants(特装/限定)のうち variant書影ありを列挙(成人除外)。
  ★価格は出力しない(2026-07-03 ユーザ裁定: 静的価格表示は絶対禁止 [[feedback-no-static-prices]])。
- ★愛蔵版(2026-09-06 新設 = 豪華版コーナーの置き換え候補): 通常版・文庫版以外の版のうち
  **通常版より巻数が圧縮された合本だけ**。ユーザ裁定「新装版は冊数が一緒なら普通(=だめ)」。
  ゲート4枚 = ①圧縮率 0.30〜0.70(3冊→2冊以上の合本。同数=普通の再版、0.3未満=巻の登録もれ疑い)
  ②巻番号が連番完備(取りこぼしで"圧縮"に見えるものを排除) ③1巻に書影 ④成人除外。
  ★「◯◯デラックス」レーベル名だけの版(KCデラックス等=中身は普通の単行本)は①で自動的に落ちる。
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
aiz = []   # [{s,t,e,l,v,sv,c,d}] = 愛蔵版コーナー(合本のみ)
AIZ_MIN, AIZ_MAX = 0.30, 0.70   # 通常版比の巻数(下限=登録もれ除け / 上限=同数の普通再版除け)
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
    eds = d.get("editions") or []

    # ★愛蔵版コーナー(2026-09-06 ユーザ裁定): 「通常版と冊数が同じ版」は判型も値段も普通の
    #   再版なので豪華本ではない → **通常版より巻数が圧縮された版=合本**だけを候補にする。
    std_vols = max((len(e.get("volumes") or []) for e in eds if e.get("type") == "standard"),
                   default=0)
    if std_vols:
        for e in eds:
            t = e.get("type")
            if t in ("standard", "bunkobon") or not t:
                continue
            vols = e.get("volumes") or []
            c = len(vols)
            if not c:
                continue
            r = c / std_vols
            if not (AIZ_MIN <= r <= AIZ_MAX):
                continue  # 同数(=普通の再版)・巻の登録もれで少なく見えるだけ、を除外
            nums = [v.get("number") for v in vols if isinstance(v.get("number"), int)]
            if len(nums) != c or len(set(nums)) != c or max(nums) != c:
                continue  # ★連番完備でないもの= 巻の取りこぼしで「圧縮」に見えている疑い
            v1 = next((v for v in vols if v.get("number") == 1), None)
            if not (v1 and v1.get("cover_url")):
                continue  # 1巻書影が無いとコーナーの見た目が崩れる
            aiz.append({"s": slug, "t": title, "e": t, "l": e.get("imprint") or "",
                        "v": c, "sv": std_vols, "c": v1["cover_url"],
                        "d": str(v1.get("release_date") or "")[:4]})

    for e in eds:
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

# ★愛蔵版: 並びが命(週の窓=連続4件)。 slug順のままだと旧豪華版コーナーと同じ
#   「4点とも同じ作品」事故になる(実測31%の週)。 → ハッシュで決定的に散らし、さらに
#   同一作品が窓4件の中に入らないよう貪欲に入替える(= 再実行しても同じ並び)。
def _h(x):
    v = 2166136261
    for ch in (x["s"] + "|" + x["e"]):
        v = ((v ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return v


aiz.sort(key=_h)
W = 4
spread, pending = [], list(aiz)
while pending:
    recent = {r["s"] for r in spread[-(W - 1):]}
    i = next((j for j, r in enumerate(pending) if r["s"] not in recent), 0)
    spread.append(pending.pop(i))
json.dump(spread, open(os.path.join(OUTD, "aizouban-stock.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))

days = len(ann)
bytype = {}
for r in aiz:
    bytype[r["e"]] = bytype.get(r["e"], 0) + 1
print(f"走査{n} → 周年: {sum(len(v) for v in ann.values())}件/{days}日分 / 豪華版: {len(dlx)}件 / "
      f"愛蔵版: {len(spread)}版/{len({r['s'] for r in aiz})}作品 {bytype}")
