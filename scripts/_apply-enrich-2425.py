"""enrich-2024-2025 ワークフロー結果を seed へ適用。
- synopsis → data/seeds/distill-synopsis-2026.json (slug→synopsis、 promoteが新作に焼く)
- catch    → data/seeds/catch-copy.json (slug→catch) ※promoteのcatch_map源
- genres   → 既存が provisional/空 の時のみ補完(2024/2025は既存有が多い=尊重)
純粋追加・既存上書き最小。 usage: python _apply-enrich-2425.py [--apply]
"""
import json, os, sys, yaml
ROOT = "C:/Users/shuic/code/MANGAL"
APPLY = "--apply" in sys.argv
GENVOCAB = set('action,adventure,fantasy,sci-fi,mystery,horror,gag,comedy,romcom,romance,drama,slice-of-life,school,sports,baseball,soccer,historical,samurai,mecha,yokai,gourmet,4-koma,essay,isekai,bl,suspense,music,supernatural,ecchi,mind-game,mahou-shoujo,war'.split(','))

res = json.load(open(f"{ROOT}/.cache/enrich-results.json", encoding="utf-8"))
# 検証
ok = [r for r in res if r.get("slug") and os.path.exists(f"{ROOT}/data/manga.v2/{r['slug']}.yml")]
notexist = len(res) - len(ok)
print(f"results {len(res)} / manga.v2実在 {len(ok)} / 不在 {notexist}")

# --- synopsis seed (slug keyed, 新作用) ---
syn_path = f"{ROOT}/data/seeds/distill-synopsis-2026.json"
syn = json.load(open(syn_path, encoding="utf-8")) if os.path.exists(syn_path) else {}
syn_add = 0
for r in ok:
    s = (r.get("synopsis") or "").strip()
    if s and len(s) >= 20 and r["slug"] not in syn:
        syn[r["slug"]] = s
        syn_add += 1

# --- catch seed (slug keyed) ---
catch_path = f"{ROOT}/data/seeds/catch-ja.json"
catch = json.load(open(catch_path, encoding="utf-8")) if os.path.exists(catch_path) else {}
catch_add = 0
for r in ok:
    c = (r.get("catch") or "").strip()
    if c and r["slug"] not in catch:
        catch[r["slug"]] = c
        catch_add += 1

# --- genres: 既存尊重、 空/provisionalのみ補完 ---
genre_seed_path = f"{ROOT}/data/seeds/genre-enrich-2425.json"
gen_fill = {}
gen_add = 0
for r in ok:
    gs = [g for g in (r.get("genres") or []) if g in GENVOCAB]
    if not gs:
        continue
    p = f"{ROOT}/data/manga.v2/{r['slug']}.yml"
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    cur = d.get("genres") or []
    prov = d.get("genres_provisional")
    if not cur or prov:   # 空 or AI低信頼のみ上書き候補
        gen_fill[r["slug"]] = gs[:4]
        gen_add += 1

print(f"適用予定: synopsis +{syn_add} / catch +{catch_add} / genre補完(空or暫定) {gen_add}")
if not APPLY:
    print("(dry-run。 --apply で seed書込)")
    # サンプル
    for r in ok[:3]:
        print(f"  {r['slug']}: catch='{r['catch']}' syn='{r['synopsis'][:40]}...' gen={r['genres']}")
    sys.exit()

import shutil
ts = "2026-06-28"
for pth in (syn_path, catch_path):
    if os.path.exists(pth):
        shutil.copy2(pth, pth + f".bak-{ts}")
json.dump(syn, open(syn_path, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(catch, open(catch_path, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(gen_fill, open(genre_seed_path, "w", encoding="utf-8"), ensure_ascii=False)
print(f"適用完了: synopsis {len(syn)} / catch {len(catch)} / genre-enrich {len(gen_fill)}")
print(f"  seeds: distill-synopsis-2026.json / catch-copy.json / genre-enrich-2425.json")
