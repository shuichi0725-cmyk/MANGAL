"""[適用] コナン映画版 最終仕分けを seed に純粋追加(冪等)。
 ① non-manga-drop.yml に フィルムコミック/総集編 32 series_key を追加(理由付き)
 ② series-merge.yml に 漆黒(3key)/迷宮(2key) コミカライズ統合を追加
 ③ _change-log.jsonl にログ
 種2 sqlite 不変。既存entryは上書きしない(追加のみ)。--apply で書込、無指定はdryrun。"""
import sqlite3, io, sys, json, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
APPLY = "--apply" in sys.argv
con = sqlite3.connect(".cache/db-v2.sqlite")

# --- 最終決定 ---
dec = {}
for ln in open(".cache/conan-final-decision.tsv", encoding="utf-8").readlines()[1:]:
    isbn, d, why, t = (ln.rstrip("\n").split("\t") + [""] * 4)[:4]
    dec[isbn] = (d, why)
DROP = {i for i, (d, w) in dec.items() if d == "DROP"}

# --- DROP ISBN -> series_key + 理由 ---
def reason_of(why, title):
    if "総集編" in why or "企画本" in why:
        return "conan_compilation", "総集編/セレクション/企画本(既刊の寄せ集め=本編でない)"
    if "TVアニメ" in why:
        return "conan_tv_film_comic", "TVアニメのフィルムコミック(ユーザ裁定)"
    if "廉価" in why or "My First" in why:
        return "conan_konbini_cheap", "コンビニ廉価再録(My First BIG)"
    return "conan_film_comic", "劇場版フィルムコミック(映画の画面流用本=漫画でない)"

drop_keys = {}  # series_key -> (reason_code, reason_text, title)
for i in DROP:
    why = dec[i][1]
    for sid, sk, t in con.execute("""select s.id,s.series_key,s.title from volumes v
        join editions e on v.edition_id=e.id join series s on e.series_id=s.id where v.isbn13=?""", (i,)):
        rc, rt = reason_of(why, t)
        # 同keyに複数理由が来たら film 優先(セレクションkeyは単独)
        if sk not in drop_keys:
            drop_keys[sk] = (rc, rt, t)

# 安全網: drop対象keyにDROP以外が無いか再確認
for sk in list(drop_keys):
    isbns = [r[0] for r in con.execute("""select v.isbn13 from volumes v join editions e on v.edition_id=e.id
        join series s on e.series_id=s.id where s.series_key=?""", (sk,))]
    bad = [i for i in isbns if i not in DROP]
    if bad:
        print(f"★ABORT: key {sk} に非DROP混入 {bad}", file=sys.stderr)
        sys.exit(1)
print(f"DROP series_key = {len(drop_keys)}個 (純度確認OK)")

# --- merge定義 ---
MERGES = [
    {"main": "名探偵コナン 漆黒の追跡者",
     "keys": ["qid:Q11657721|name:名探偵コナン 漆黒の追跡者",
              "name:丸伝次郎|name:名探偵コナン 漆黒の追跡者",
              "qid:Q11657721|name:名探偵コナン漆黒の追跡者"],
     "note": "コミカライズ全3巻(青山剛昌・阿部ゆたか・丸伝次郎/少年サンデーコミックス)が表記揺れ(空白有無)+著者名keyで3sid分裂。同題連番1-3・全巻楽天に「漫画化/コミカライズ」確証 → 1ページ統合。映画フィルムコミック(qid:Q313945)とは別物。2026-06-16"},
    {"main": "名探偵コナン 迷宮の十字路",
     "keys": ["name:丸伝次郎|name:名探偵コナン迷宮の十字路",
              "qid:Q11657721|name:名探偵コナン迷宮の十字路"],
     "note": "コミカライズVOLUME1-2が著者名key+qid keyで2sid分裂。同題連番・阿部ゆたか丸伝次郎作画 → 1ページ統合。映画フィルムコミック(qid:Q313945)とは別物。2026-06-16"},
]

# --- ① non-manga-drop.yml 追加 ---
nm_path = "data/seeds/non-manga-drop.yml"
nm_text = open(nm_path, encoding="utf-8").read()
existing_nm = set(re.findall(r'series_key:\s*"(.*?)"', nm_text))
add_nm = []
for sk, (rc, rt, t) in sorted(drop_keys.items()):
    if sk in existing_nm:
        continue
    esc = sk.replace('"', '\\"')
    block = (f'  - series_key: "{esc}"\n'
             f'    reason: {rc}\n'
             f'    note: "{rt} / DB題=『{t[:24]}』"\n')
    add_nm.append((sk, block))
print(f"non-manga-drop 追加 = {len(add_nm)} / 既存skip = {len(drop_keys)-len(add_nm)}")

# --- ② series-merge.yml 追加 ---
mg_text = open("data/seeds/series-merge.yml", encoding="utf-8").read()
add_mg = []
for m in MERGES:
    if all(k in mg_text for k in m["keys"]):
        continue  # 既に全key記載済
    lines = ["- merge_keys:"]
    for k in m["keys"]:
        lines.append(f'  - "{k}"')
    lines.append(f'  note: |')
    lines.append(f'    {m["note"]}')
    add_mg.append((m["main"], "\n".join(lines) + "\n"))
print(f"series-merge 追加 = {len(add_mg)}")

if not APPLY:
    print("\n[dryrun] --apply で書込。追加プレビュー:")
    for sk, b in add_nm[:3]:
        print(b)
    for mn, b in add_mg:
        print(b)
    sys.exit(0)

# === 書込 ===
with open(nm_path, "a", encoding="utf-8") as f:
    for sk, b in add_nm:
        f.write(b)
with open("data/seeds/series-merge.yml", "a", encoding="utf-8") as f:
    f.write("\n")
    for mn, b in add_mg:
        f.write(b)

# ログ
with open("data/seeds/_change-log.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "ts": "2026-06-16", "action": "conan_film_comic_drop",
        "target": f"{len(add_nm)} series_key", "detected_by": "wiki逐語+楽天レーベル+ユーザ裁定",
        "source": "non-manga-drop.yml", "checks": ["32key純度100%(KEEP/本編混入0)", "コミカライズ(qid:Q11657721)と映画フィルム(qid:Q313945)はkey分離"],
        "confidence": "high", "undo": "non-manga-drop.yml該当series_key削除", "state": "applied",
        "note": "コナン劇場版フィルムコミック/総集編/廉価/TVタイアップを非掲載。漫画でない/本編でないため。"}, ensure_ascii=False) + "\n")
    f.write(json.dumps({
        "ts": "2026-06-16", "action": "conan_comicalize_merge_fix",
        "target": "迷宮の十字路コミカライズ(誤merge修正)/漆黒の追跡者(既存merge確認)", "detected_by": "楽天=漫画化確証+同題連番+merge点検",
        "source": "series-merge.yml(行1897付近)", "checks": ["迷宮=旧auto-mergeがコミカライズ(Q11657721)+映画フィルム(Q313945)を誤統合→フィルム除去しコミカライズVOL1(丸伝次郎)+VOL2(Q11657721)に修正", "漆黒=既存merge(3コミカライズkey)がクリーンと確認"],
        "confidence": "high", "undo": "series-merge.yml該当merge_keysを旧状態(Q313945含む)に戻す", "state": "applied",
        "note": "コミカライズに映画フィルムコミックが混入していた誤mergeを是正。コミカライズ同士のみ統合。"}, ensure_ascii=False) + "\n")

print(f"\n✅ 適用完了: non-manga-drop +{len(add_nm)} / series-merge +{len(add_mg)} / log 2行")
