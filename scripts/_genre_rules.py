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
- ★isekai/gourmet は「タグ+題名/紹介文の明記」が揃った時だけ(CORROBORATED・2026-09-24)。タグ単独は精度不足。
- ★時代劇/魔法少女は除外・許可つきの明記規則(_jidai_mahou_hits)、BL/4コマ/時代劇は専門レーベル規則(IMPRINT_RULES)。
  derive() の第4引数 imprints = 頁の全版の imprint(promote の本流/予約ストリームとも渡す)。

CLI(バックフィル用):
  python scripts/_genre_rules.py --list          # 全頁走査→追加候補TSV+集計(書き込みなし)
  出力: docs/production-diagnostics/genre-rules-backfill.tsv (stem \t 追加キー \t 根拠)
"""
import io
import json
import os
import re
import sys
import unicodedata

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
# ★時代劇・魔法少女はここ(単純な部分一致)に置かない(2026-08-03目視検品: 「時代劇が大好きなJK」(クロエの流儀)、
#   「魔法少女ものから…まで の短編集」(歌姫Fight!)= 趣味言及・列挙言及の偽陽性型)。
#   → 2026-09-24 に除外/許可つきの専用規則 _jidai_mahou_hits で再導入(下)。
TEXT_TO_GENRE = (
    ("ラブコメ", "romcom"),
    ("ギャグ", "gag"),
    ("4コマ", "4-koma"),
    ("４コマ", "4-koma"),
    ("妖怪", "yokai"),
)
_4KOMA_TEXT_EXCLUDE = ("巻末", "おまけ", "併録", "収録")

# ★タグ+明記の二段(2026-09-24 ユーザGO「要素とジャンルのずれを揃える」):
#   要素欄は rank60 のタグ(AniList)や楽天あらすじ由来タグも表示するのに、ジャンルへ写すのは AniList rank70 以上
#   だけだった(_build-anilist-enrich-map.py の THEME_RANK)= 要素「異世界」722作・「料理」740作にジャンルが無かった。
#   ただしタグ単独は精度が足りない(抜き取り: 異世界71〜86%・グルメ50〜80%)ので、題名/紹介文の**明記**が揃った時だけ。
#   ・楽天タグは同じ楽天の紹介文から作られている=紹介文での裏付けが独立でない → 語の要求数を上げる。
#   ・抜き取り(各16〜18作): 異世界 楽天18/18・AniList18/18 / グルメ 楽天(2語)16/16・AniList(1語)17/18。
#   ★BLは入れない: 腐女子もの・ゲイに囲まれる女性・LGBT一般作が語では弾けず約75%= レーベル側で別途。
#   ★語は部分一致。別の語を含む語(「ご飯」⊃「飯」)は1回の言及を2語と数えるので入れない。
ISEKAI_WORDS = ("異世界", "転生", "転移", "召喚", "トリップ", "別世界", "ゲームの世界", "乙女ゲー",
                "小説の世界", "物語の世界", "漫画の世界", "前世")
GOURMET_WORDS = ("料理", "グルメ", "食堂", "ごはん", "飯", "レシピ", "美食", "食べ歩き", "食卓", "弁当",
                 "パン屋", "ラーメン", "寿司", "スイーツ", "お菓子", "和菓子", "洋菓子", "ケーキ", "ビール",
                 "ワイン", "日本酒", "お酒", "珈琲", "コーヒー", "喫茶", "居酒屋", "屋台", "定食", "調理",
                 "シェフ", "板前", "晩酌")
# (ジャンル, 対象タグ名, 明記語, 必要語数[AniList等の独立タグ], 必要語数[楽天タグ])
CORROBORATED = (
    ("isekai", frozenset({"Isekai"}), ISEKAI_WORDS, 1, 1),
    ("gourmet", frozenset({"Food"}), GOURMET_WORDS, 1, 2),
)

# ★時代劇・魔法少女の明記(2026-09-24 ユーザGO「234も検証して付与」= 08-03 にタグのみへ退避した2キーの再挑戦)。
#   時代劇: 紹介文の「〜時代劇」はほぼジャンル説明(本格時代劇/人情時代劇/時代劇アクション…)。
#     除外= 趣味・俳優・撮影の文脈(「時代劇が大好きなJK」クロエの流儀)と「〜から時代劇まで」の列挙だけ。
#     ★「時代劇ドラマ」は除外しない(御用金・賊軍土方歳三=ジャンル説明として書かれていた)。候補109→採用103。
#   魔法少女: 除外方式でも列挙(「猫耳の魔法少女」プリコネ/「教師、アイドル、魔法少女」)が残った → 紹介文は
#     **はっきりした書き方の時だけ**採る(肯定形の許可リスト)。題名の「魔法少女」は28作中26作が当たり
#     (外れ2=列挙「魔法少女も」・「無口な魔法少女でした」=魔法使いの少女 → _MAHOU_TITLE_NG で除外)。
_JIDAI_NG = re.compile(r"時代劇(?:が好き|好き|が大好き|大好き|ファン|マニア|オタク|俳優|役者|スター|の撮影|撮影|ロケ|映画|"
                       r"ごっこ|番組|チャンネル|まで|に憧|への憧)")
# 題名も列挙(「異能バトルも魔法少女も…」佐々木とピーちゃん)と「無口な魔法少女でした」(=魔法使いの少女)を除く
_MAHOU_TITLE_NG = re.compile(r"魔法少女(?:アニメ|もの|物|オタク|ファン|好き|が好き|大好き|DVD|グッズ|番組|ごっこ|コスプレ|学園|も|でした)")
_MAHOU_TEXT_OK = re.compile(r"(?:見習い|新米|現役|元・?)魔法少女|魔法少女」?(?:コメディ|漫画|マンガ|アクション|ファンタジー|バトル|"
                            r"物語|ストーリー|に変身|へ変身|になった|になって|になる|として|だった|の力|たち)")


def _jidai_mahou_hits(title, text):
    """時代劇(samurai)/魔法少女(mahou-shoujo)の明記。yield (genre, 根拠)。"""
    t, x = title or "", text or ""
    for src, s in (("title", t), ("text", x)):
        for m in re.finditer("時代劇", s):
            if not _JIDAI_NG.match(s, m.start()):
                yield "samurai", f"samurai<{src}:時代劇"
                break
    if "魔法少女" in t and not _MAHOU_TITLE_NG.search(t):
        yield "mahou-shoujo", "mahou-shoujo<title:魔法少女"
    elif _MAHOU_TEXT_OK.search(x):
        yield "mahou-shoujo", f"mahou-shoujo<text:{_MAHOU_TEXT_OK.search(x).group(0)}"


# ★レーベル(imprint)の明記(2026-09-24 同上・方法2): 専門レーベルは「中身の推測」でなく刊行の事実。
#   実測: BL専門レーベルでも bl ジャンルは4〜8割しか付いていなかった(ディアプラス48%/Chara53%/花音45%/Be-boy42%)。
#   ★一覧は「データで割合が高い」×「抜き取りで全件その種の作品」を満たしたものだけ。表記揺れは正規化(_norm_imprint)後の部分一致。
#   ★罠(実踏): 「KC BL」「講談社コミックスBL」「BLKC」= BE・LOVE(女性誌)の略 / 「Blade comics」= 一般 /
#     「TL junet」「ショコラブ」「Pink cherie」= 男女もの(TL) / 「DARIA ESSAY」= エッセイ / 「Animage chara comics」= 一般。
#     → 「bl」の文字では拾わない。除外語(NG)を先に見る。
#   ★見送り: ジーンピクシブ(一般混在)/ 爆男COMICS(ゲイ向け=BLとは別物の可能性)/ POE BACKS(JUNE復刻・同人選集が混在)/
#     まんがタイムKRコミックス(きららフォワード系のストーリー漫画が混在)/ マイパル(実話アンソロジー)/ SPコミックス(ゴルゴ13等の一般)。
IMPRINT_RULES = (
    ("bl", ("ディアプラス", "dear+", "characomics", "charaコミックス", "キャラコミックス", "花音コミックス", "be-boy", "be×boy",
            "ビーボーイ", "gush", "dariacomics", "ダリアコミックス", "marblecomics", "マーブルコミックス", "gateau", "onblue",
            "オンブルー", "cannacomics", "craftseries", "craftシリーズ", "craftcomics", "h&c", "ihrhertz", "ihertz",
            "ルチルコレクション", "rutile", "drap", "edgecomix", "arcacomics", "citron", "シトロン", "cl-dx", "b's-lovey",
            "fleurcomics", "フルールコミックス", "chéri+", "cheri+", "glanzbl", "eyescomicsbloom", "eyescomicsblink",
            "アンダルシュ", "&arche", "fromred", "karencomic", "karenコミック", "babycomics", "アクアコミックス", "liqulle",
            "リキューレ", "honeymilk", "caramelコミックス", "marginal", "ビボピー", "ビポピー", "qpa", "麗人",
            "ジュネットコミックス", "ジュネット文庫", "ラキッシュ", "カチcomi", "tullecomics", "kircomics", "g-lish",
            "hanamaru", "花丸コミックス", "blanket", "ボーイズduo", "ボーイズアニマ", "ラブキスボーイズ",
            "バンブーコミックスmoment", "bamboocomicsmoment", "blシリーズ", "bl(boyslove)", "光文社blcomics",
            "kobunshablcomics", "秒で分かるbl", "easternbl"),
     ("animage", "dariaessay", "tljunet", "ジーンピクシブ", "blade", "kcbl", "講談社コミックスbl", "kodanshacomicsbl",
      "blkc", "beinlove", "爆男", "poebacks")),
    ("4-koma", ("まんがタイムコミックス", "mangatimecomics", "4コマkingsぱれっと", "4コマ", "4koma"),
     ("kr", "マイパル", "mypal")),
    ("samurai", ("時代劇", "時代コミックス", "乱コミックス"), ()),
)
_IMPRINT_EXACT = {"bl": {"bloom"}}


def _norm_imprint(s) -> str:
    """表記揺れの正規化: NFKC(全角＆→&・全角英数→半角)+小文字+空白/中黒/ピリオド除去。"""
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s・.．。　]", "", s)


def _imprint_hits(imprints):
    """yield (genre, 根拠レーベル)。"""
    for raw in imprints or ():
        n = _norm_imprint(raw)
        if not n:
            continue
        for g, keys, ngs in IMPRINT_RULES:
            if any(ng in n for ng in ngs):
                continue
            if n in _IMPRINT_EXACT.get(g, ()) or any(k in n for k in keys):
                yield g, raw


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


def _corroborated_hits(title, tags, text):
    """タグ+明記の二段(CORROBORATED)。yield (genre, 根拠文字列)。"""
    body = f"{title or ''}／{text or ''}"
    for g, names, words, need_ind, need_rkt in CORROBORATED:
        best_need = None
        for t in tags or ():
            if not isinstance(t, dict) or t.get("name") not in names:
                continue
            rank = t.get("rank")
            if rank is not None and rank < MIN_TAG_RANK:
                continue
            need = need_rkt if (t.get("category") or "") == "Rakuten" else need_ind
            best_need = need if best_need is None else min(best_need, need)
        if best_need is None:
            continue
        hits = [w for w in words if w in body]
        if len(hits) >= best_need:
            yield g, f"{g}<tag+text:{'/'.join(hits[:3])}"


def derive(title: str, tags, text: str, imprints=()) -> set:
    """明記シグナル → 派生ジャンルキー集合。tags= page.tags のdict列(name/rank)。
    imprints= 頁の全版の imprint(レーベル)文字列。呼び側で valid_gens と交差させること。"""
    out = set()
    for g, _r in _jidai_mahou_hits(title, text):
        out.add(g)
    for g, _r in _imprint_hits(imprints):
        out.add(g)
    t = title or ""
    for pat, g in TITLE_TO_GENRE:
        if pat in t:
            out.add(g)
    for g, _n in _tag_hits(tags):
        out.add(g)
    for g, _r in _corroborated_hits(title, tags, text):
        out.add(g)
    x = text or ""
    for pat, g in TEXT_TO_GENRE:
        if pat not in x:
            continue
        if g == "4-koma" and any(e in x for e in _4KOMA_TEXT_EXCLUDE):
            continue  # 「巻末おまけ4コマ収録」型は本編4コマの証拠にならない
        out.add(g)
    return out


def _reasons(title, tags, text, imprints=()):
    """--list 用: どの根拠で付いたか(人が目視できる形)。"""
    rs = [r for _g, r in _jidai_mahou_hits(title, text)]
    rs += [f"{g}<imprint:{lab}" for g, lab in _imprint_hits(imprints)]
    for pat, g in TITLE_TO_GENRE:
        if pat in (title or ""):
            rs.append(f"{g}<title:{pat}")
    for g, n in _tag_hits(tags):
        rs.append(f"{g}<tag:{n}")
    for _g, r in _corroborated_hits(title, tags, text):
        rs.append(r)
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
        imps = [e.get("imprint") for e in (d.get("editions") or []) if isinstance(e, dict)]
        add = derive(d.get("title") or "", tags, text, imps) - cur
        if not add:
            continue
        n_pages += 1
        for g in add:
            per_key[g] += 1
        stem = os.path.basename(p)[:-4]
        src = "preorder" if "preorder-pages" in p else "manga.v2"
        rows.append(f"{stem}\t{src}\t{','.join(sorted(add))}\t{';'.join(_reasons(d.get('title') or '', tags, text, imps))}")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    io.open(outp, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + ("\n" if rows else ""))
    print(f"追加候補: {n_pages}頁 → {outp}")
    print("キー別:", dict(per_key.most_common()))


if __name__ == "__main__":
    main()
