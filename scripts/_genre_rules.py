# -*- coding: utf-8 -*-
"""派生ジャンル規則(共有モジュール)= 「注ぎ手がいない枯れキー」を既存シグナルから決定的に導出する。

★なぜ(2026-08-03 ユーザ裁定「自動で増えない構造を改善したい」):
  romcom/4-koma/gag/yokai/war/samurai/mahou-shoujo は、注ぎ手(AniListマッピング/楽天/AI fill)が
  これらのキーを出力しない構造で、バックフィル(ラブコメ復権)をしても**新規作品でまた枯れる**。
  そこで promote(本流+予約ストリーム)が毎頁この規則を通す= ★蒸留で入る新規作品も自動で増える。

設計原則:
- **明記主義(fail-closed)**: タグ名(AniList訳語/楽天/AI)・題名・紹介文(catch/synopsis)に
  **明記**がある時だけ。推測しない([[feedback_accuracy_is_the_goal]])。
- union only・フラグ(genres_provisional等)不変 = genre-append.yml と同じ流儀。
- ★war は**タグのみ**(紹介文の「戦争」は受験戦争/お家騒動/戦争孤児等の合成・背景語で誤爆する)。
- ★4コマの紹介文判定は「巻末/おまけ/併録/収録」を含む文を除外(おまけ4コマ型の誤爆)。
- romcom の本丸(romance∩comedy で明記なし)の裁定は skill romcom-judge(AI)。ここは明記層のみ。

CLI(バックフィル用):
  python scripts/_genre_rules.py --list          # 全頁走査→追加候補TSV+集計(書き込みなし)
  出力: docs/production-diagnostics/genre-rules-backfill.tsv (stem \t 追加キー \t 根拠)
"""
import io
import json
import os
import sys

# タグ名 → ジャンルキー。★page.tags[].name は **AniList英語原名のまま**格納され(Youkai/War等)、
# 表示時に tag-i18n.yml で和訳される構造(2026-08-03実踏: 和名だけで引いたら war が6件しか出ず発覚)。
# 楽天/AI由来タグは和名。→ 英和両方の語彙で引く。
TAG_TO_GENRE = {
    # AniList英語原名
    "Youkai": "yokai",
    "War": "war",
    "Military": "war",
    "Mahou Shoujo": "mahou-shoujo",
    "Samurai": "samurai",
    "4-koma": "4-koma",
    # 和名(楽天/AIタグ・tag-i18n訳語)
    "妖怪": "yokai",
    "戦争": "war",
    "ミリタリー": "war",
    "魔法少女": "mahou-shoujo",
    "時代劇": "samurai",
    "4コマ": "4-koma",
    "４コマ": "4-koma",
    "ギャグ": "gag",
    "ラブコメ": "romcom",
}
# ★タグ採用の最低rank(2026-08-03目視検品): AniListタグは大半がrank60。AI生成タグ(rank55)は
#   証拠力が弱いので弾く。rank無しタグ(手動等)は通す。
MIN_TAG_RANK = 60
# 題名の明記(部分一致)
TITLE_TO_GENRE = (("4コマ", "4-koma"), ("４コマ", "4-koma"), ("よんこま", "4-koma"))
# 紹介文(catch+synopsis)の明記(部分一致)。
# ★war はここに置かない(受験戦争/お家騒動等の合成・背景語で誤爆)。
# ★時代劇・魔法少女もタグのみ(2026-08-03目視検品: 「時代劇が大好きなJK」(クロエの流儀)、
#   「魔法少女ものから…まで の短編集」(歌姫Fight!)= 趣味言及・列挙言及の偽陽性型)。
TEXT_TO_GENRE = (
    ("ラブコメ", "romcom"),
    ("ギャグ", "gag"),
    ("4コマ", "4-koma"),
    ("４コマ", "4-koma"),
    ("妖怪", "yokai"),
)
_4KOMA_TEXT_EXCLUDE = ("巻末", "おまけ", "併録", "収録")


def _tag_hits(tags):
    for t in tags or ():
        if not isinstance(t, dict):
            continue
        rank = t.get("rank")
        if rank is not None and rank < MIN_TAG_RANK:
            continue
        g = TAG_TO_GENRE.get(str(t.get("name") or ""))
        if g:
            yield g, t.get("name")


def derive(title: str, tags, text: str) -> set:
    """明記シグナル → 派生ジャンルキー集合。tags= page.tags のdict列(name/rank)。
    呼び側で valid_gens と交差させること。"""
    out = set()
    t = title or ""
    for pat, g in TITLE_TO_GENRE:
        if pat in t:
            out.add(g)
    for g, _n in _tag_hits(tags):
        out.add(g)
    x = text or ""
    for pat, g in TEXT_TO_GENRE:
        if pat not in x:
            continue
        if g == "4-koma" and any(e in x for e in _4KOMA_TEXT_EXCLUDE):
            continue  # 「巻末おまけ4コマ収録」型は本編4コマの証拠にならない
        out.add(g)
    return out


def _reasons(title, tags, text):
    """--list 用: どの根拠で付いたか(人が目視できる形)。"""
    rs = []
    for pat, g in TITLE_TO_GENRE:
        if pat in (title or ""):
            rs.append(f"{g}<title:{pat}")
    for g, n in _tag_hits(tags):
        rs.append(f"{g}<tag:{n}")
    for pat, g in TEXT_TO_GENRE:
        if pat in (text or ""):
            if g == "4-koma" and any(e in (text or "") for e in _4KOMA_TEXT_EXCLUDE):
                continue
            rs.append(f"{g}<text:{pat}")
    return rs


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import glob
    import yaml
    try:
        from yaml import CSafeLoader as _L
    except ImportError:
        from yaml import SafeLoader as _L
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outp = os.path.join(ROOT, "docs", "production-diagnostics", "genre-rules-backfill.tsv")
    from collections import Counter
    per_key = Counter()
    n_pages = 0
    rows = []
    files = sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))) + \
        sorted(glob.glob(os.path.join(ROOT, "data", "seeds", "preorder-pages", "*.yml")))
    for i, p in enumerate(files, 1):
        if i % 20000 == 0:
            print(f"  … {i}", flush=True)
        try:
            d = yaml.load(io.open(p, encoding="utf-8"), Loader=_L)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        cur = set(d.get("genres") or [])
        text = f"{d.get('catch') or ''}／{d.get('synopsis') or ''}"
        tags = d.get("tags") or []
        add = derive(d.get("title") or "", tags, text) - cur
        if not add:
            continue
        n_pages += 1
        for g in add:
            per_key[g] += 1
        stem = os.path.basename(p)[:-4]
        src = "preorder" if "preorder-pages" in p else "manga.v2"
        rows.append(f"{stem}\t{src}\t{','.join(sorted(add))}\t{';'.join(_reasons(d.get('title') or '', tags, text))}")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    io.open(outp, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + ("\n" if rows else ""))
    print(f"追加候補: {n_pages}頁 → {outp}")
    print("キー別:", dict(per_key.most_common()))


if __name__ == "__main__":
    main()
