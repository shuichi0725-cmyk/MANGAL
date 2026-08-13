# -*- coding: utf-8 -*-
"""アニメ化フラグ差分(2026-08-11 新設。アイドル運転柱⑥の後段)。

背景: anime_adapted は種3の初回AI fill(2026-05)で焼かれたきり更新機構が無かった(ユーザ指摘)。
dump-v3+delta(柱⑥が鮮度維持)の relations から「ADAPTATION×ANIME」を再計算し、
本番頁がまだ false/無印の作品を洗い出す。

処理:
  1. dump-v3 + anilist-delta.jsonl を last-wins で重ね、aid→アニメ化有無を再計算
  2. .cache/anilist-enrich-map.json の該当entryへ anime:true をパッチ(promoteのunion経路が読む)
  3. 本番頁(anilist_id 逆引き=.cache/anilist-to-slug.json)で anime_adapted 未設定の slug を列挙
     → .cache/anime-flag-worklist.txt (1行1slug)
  4. 逆方向(頁true・dump無)は報告のみ(false化しない=AniListの関係削除は稀・誤りの可能性)

使い方:
  python scripts/_anime-flag-delta.py           # 差分レポート+enrich mapパッチ+worklist出力
  反映 = python scripts/_reflect-targeted.py --only-file .cache/anime-flag-worklist.txt --push -m "..."
         (--only-file が無い版なら --only へカンマ結合で渡す)
"""
import gzip
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
DELTA = os.path.join(ROOT, ".cache", "anilist-delta.jsonl")
ENRICH = os.path.join(ROOT, ".cache", "anilist-enrich-map.json")
AID2SLUG = os.path.join(ROOT, ".cache", "anilist-to-slug.json")
WORKLIST = os.path.join(ROOT, ".cache", "anime-flag-worklist.txt")


def has_anime(row):
    for edge in ((row.get("relations") or {}).get("edges") or []):
        nd = edge.get("node") or {}
        if edge.get("relationType") == "ADAPTATION" and nd.get("type") == "ANIME":
            return True
    return False


def main():
    # ★aid→slugマップは必ず再構築してから使う(2026-08-13 実踏): 7/12製の古いマップを使い続けた結果、
    #   7/18のリンク検証で頁から剥がされた誤リンク17件(atagoul/死角/Tokyo tribe等=親作品・同名異作への
    #   誤結線)がworklistに再出現し続け、「反映しても頁が変わらない」空振りを起こした。
    #   マップ=頁ymlのanilist_id逆引きなので、頁の現在形から作り直せば誤リンク層は自然に消える。
    import subprocess
    print("aid→slugマップ再構築(_anime-season-join.py --rebuild-map)…")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_anime-season-join.py"), "--rebuild-map"],
                   check=True)
    aid_anime = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            aid_anime[r.get("id")] = has_anime(r)
    n_dump = len(aid_anime)
    n_delta = 0
    if os.path.exists(DELTA):
        for line in io.open(DELTA, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            aid_anime[r.get("id")] = has_anime(r)  # last-wins
            n_delta += 1
    print(f"dump {n_dump:,}行 + delta {n_delta:,}行 → アニメ化あり {sum(1 for v in aid_anime.values() if v):,} aid")

    # enrich map パッチ(promote union 経路)
    em = json.load(io.open(ENRICH, encoding="utf-8"))
    patched = 0
    for ent in em.values():
        aid = ent.get("anilist_id")
        if aid_anime.get(aid) and not ent.get("anime"):
            ent["anime"] = True
            patched += 1
    if patched:
        io.open(ENRICH, "w", encoding="utf-8").write(json.dumps(em, ensure_ascii=False))
    print(f"enrich map: anime:true パッチ {patched:,}件")

    # 本番頁の未設定分 = worklist
    if not os.path.exists(AID2SLUG):
        print(f"★ {AID2SLUG} が無い。 python scripts/_anime-season-join.py --rebuild-map で作ってから再実行")
        sys.exit(2)
    a2s = json.load(io.open(AID2SLUG, encoding="utf-8"))
    a2s = a2s.get("anilist", a2s)  # 実体は {"anilist": {aid: slug}, "titles": {...}} の入れ子
    import yaml
    try:
        from yaml import CSafeLoader as L
    except ImportError:
        from yaml import SafeLoader as L
    # ★裁定済みの除外(2026-08-11): false化済みはcur=falseで自然に消えるが、HOLD(真アニメ疑い=
    #   リンク修理候補)はtrue維持のため毎回revに再出現する→台帳在籍分はスキップ。
    holds = set()
    hp = os.path.join(ROOT, "docs", "production-diagnostics", "anime-flag-holds.tsv")
    if os.path.exists(hp):
        for ln in io.open(hp, encoding="utf-8").readlines()[1:]:
            holds.add(ln.split("\t")[0])
    todo, rev = [], []
    for aid_s, slug in a2s.items():
        anime = aid_anime.get(int(aid_s))
        if anime is None:
            continue
        p = os.path.join(ROOT, "data", "manga.v2", f"{slug}.yml")
        if not os.path.exists(p):
            continue
        d = yaml.load(open(p, encoding="utf-8"), Loader=L) or {}
        cur = bool(d.get("anime_adapted"))
        if anime and not cur:
            todo.append(slug)
        elif cur and not anime and slug not in holds:
            rev.append(slug)
    with io.open(WORKLIST, "w", encoding="utf-8") as f:
        for s in sorted(todo):
            f.write(s + "\n")
    print(f"★フラグ立て対象(本番false→dumpアニメ化あり): {len(todo):,}頁 → {os.path.relpath(WORKLIST, ROOT)}")
    if rev:
        print(f"逆方向(頁true・dump無)= {len(rev)}頁 ※false化はしない・参考報告のみ: {rev[:10]}{'…' if len(rev) > 10 else ''}")


if __name__ == "__main__":
    main()
