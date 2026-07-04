#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""クレジット被覆の棚卸し (= 外部APIを一切叩かず「現在あるデータだけでどれだけ埋まるか」を測る。
2026-07-04 ユーザ方針: まず手持ち→残りだけ最後にlive、の第一歩)

測るもの(全66k頁):
 A. 著者ヨミ: 現在の被覆 / author-yomi.yml で追加で埋まる数 / どうやっても欠け
 B. 役割(肩書き): role が unknown/欠の著者数 / author-role-corrections.yml 等で埋まる数
 C. 出版社: edition.publisher 欠 / 頁 publisher(キー) 欠
 D. 連載誌: magazine 欠(现在の被覆)
出力: docs/production-diagnostics/credits-coverage.json + コンソール要約
"""
import glob, json, os, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 手持ち資産のロード
yomi = yaml.load(open(os.path.join(ROOT, "data", "seeds", "author-yomi.yml"), encoding="utf-8"), Loader=L) or {}
rolec_p = os.path.join(ROOT, "data", "seeds", "author-role-corrections.yml")
rolec = yaml.load(open(rolec_p, encoding="utf-8"), Loader=L) if os.path.exists(rolec_p) else {}
rolec_keys = set()
if isinstance(rolec, dict):
    for v in rolec.values():
        if isinstance(v, list):
            rolec_keys.update(str(x.get("name", "")) for x in v if isinstance(x, dict))
        elif isinstance(v, dict):
            rolec_keys.add(str(v.get("name", "")))
print(f"資産: author-yomi {len(yomi):,}キー / role-corrections {len(rolec) if isinstance(rolec, dict) else 0:,}件")

c = Counter()
missing_yomi_names = Counter()   # ヨミがどこにも無い著者名
missing_mag_recent = 0           # 2020年以降で雑誌欠(=live調達の主対象)
n = 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    n += 1
    try:
        d = yaml.load(open(p, encoding="utf-8"), Loader=L)
    except Exception:
        continue
    if not d:
        continue
    c["pages"] += 1
    auths = (d.get("authors") or []) + (d.get("original_authors") or [])
    for a in auths:
        c["authors_total"] += 1
        name = str(a.get("name") or "")
        if a.get("kana"):
            c["yomi_have"] += 1
        elif name in yomi:
            c["yomi_fillable_seed"] += 1     # seedに在るのに頁に無い=join漏れ
        else:
            c["yomi_missing"] += 1
            missing_yomi_names[name] += 1
        role = a.get("role")
        if role and role != "unknown":
            c["role_have"] += 1
        elif name in rolec_keys:
            c["role_fillable_seed"] += 1
        else:
            c["role_missing"] += 1
    if not auths:
        c["pages_no_author"] += 1
    # 出版社
    if d.get("publisher"):
        c["pub_key_have"] += 1
    else:
        c["pub_key_missing"] += 1
    eds = d.get("editions") or []
    if eds:
        if all(e.get("publisher") for e in eds):
            c["ed_pub_all"] += 1
        elif any(e.get("publisher") for e in eds):
            c["ed_pub_partial"] += 1
        else:
            c["ed_pub_none"] += 1
    # 連載誌
    if d.get("magazine"):
        c["mag_have"] += 1
    else:
        c["mag_missing"] += 1
        ys = d.get("year_started") or 0
        if isinstance(ys, int) and ys >= 2020:
            missing_mag_recent += 1

out = {
    "scanned": n, **{k: v for k, v in c.items()},
    "mag_missing_2020plus": missing_mag_recent,
    "yomi_missing_top_names": missing_yomi_names.most_common(30),
}
os.makedirs(os.path.join(ROOT, "docs", "production-diagnostics"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "docs", "production-diagnostics", "credits-coverage.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)

P = c["pages"] or 1
A = c["authors_total"] or 1
print(f"""
== クレジット被覆(現在あるデータのみ・API不使用) 頁{c['pages']:,} 著者延べ{c['authors_total']:,} ==
A. 著者ヨミ : 有 {c['yomi_have']:,} ({c['yomi_have']*100//A}%) / ★seedで埋まるのに頁に無い {c['yomi_fillable_seed']:,} / どこにも無い {c['yomi_missing']:,} ({c['yomi_missing']*100//A}%)
B. 役割    : 有 {c['role_have']:,} ({c['role_have']*100//A}%) / seed補正で埋まる {c['role_fillable_seed']:,} / 不明 {c['role_missing']:,}
   著者ゼロ頁: {c['pages_no_author']:,}
C. 出版社  : 頁キー欠 {c['pub_key_missing']:,} / 版publisher全欠 {c['ed_pub_none']:,} / 一部欠 {c['ed_pub_partial']:,}
D. 連載誌  : 有 {c['mag_have']:,} ({c['mag_have']*100//P}%) / 欠 {c['mag_missing']:,} (うち2020年以降 {missing_mag_recent:,})
→ docs/production-diagnostics/credits-coverage.json
""")
