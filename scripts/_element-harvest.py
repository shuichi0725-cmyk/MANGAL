#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要素収集 (element-harvest) の実行体 = ジャンル・要素を付ける前段の「材料集め」。 2026-10-08 新設。

役割分担(正本 = skill element-harvest):
  道具(これ)    = 検索・取得・保存・同定の機械検査・止め札/robots・上限・束づくり
  運転者(Haiku) = どの検索結果を開くか / どの段落が材料か / 打ち切るか を「番号で指す」だけ
  ★運転者は材料の文面を打たない(pick は段落番号だけを受け取り、文面は保存済み本文から道具が切り出す)。
  ★ここは集めるだけ。 ジャンル・要素の付与は別工程。 本番データ・seed には一切書かない。

usage:
  open <stem> [--model haiku-5.5] [--fresh]     同定カード + 機械で取れる分(AniList・Wikipedia)
  search <stem> <種別> [--q 1|2] [--query "…"]   魚で検索(定型クエリ。--query は自由文)
  fetch <stem> <検索ID> <番号,番号>              検索結果を番号で指して取得
  fetch-url <stem> <種別> <URL>                  URLを直に取得
  show <stem> <出所> [--range 3-9] [--from 41]   段落の一覧 / 指定範囲の全文
  pick <stem> <出所> <段落 3-5,9> --as <役割> [--same "句"]   段落を指して採用
  unpick <stem> <採用番号>                       採用の取り消し(指し間違えた時)
  skip <stem> <出所> --why <理由>                不採用
  none <stem> <種別> --why <理由>                その種別は材料なし
  done <stem>                                    束(material.md/json)を作って報告
  status [<stem>]                                進み具合
  probe <stem> 語,語,…                           点検用: 集めた材料に語が在るか
  auto <stem> [--fresh] [--model claude-haiku-5-5]  ★自動運転: 開く頁・採る段落を道具が Haiku に1回ずつ聞いて done まで進める
種別 = wiki / 公式(official) / 考察(analysis) / ネタバレ(spoiler)
役割 = 物語(story) / 作風(style) / 人物(people) / 主題(theme) / 展開(plot = ネタバレ印) / タグ(tags = 他サイトのタグ一覧)
"""
import argparse, datetime, hashlib, json, os, re, shutil, sys, unicodedata
import urllib.error, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _rate_gate, _site_gate  # noqa: E402

VERSION = "v0.5"  # v0.5: 関連作の票は「本筋」のエントリだけ引き継ぐ(登録者の少ないエントリ・おまけ映像は使わない)/ rebundle  # v0.2: 折り返し行をつなぐ/タグ一覧を機械で採る/全文を見せて読んでから指す/公式の検索語
# v0.3(2026-10-09): 出所を英字(A,B,C…)に=検索結果の番号との取り違え防止 / 取れなかった頁は取得数に数えない / 壊れた検索URLを直す
# v0.4(2026-10-09): 自動運転(auto)= 道具が Haiku を土台なしで1回ずつ呼ぶ / AniList のネタバレ印を「何件中何件」で持つ
ME = "python scripts/_element-harvest.py"
QUIET = False  # True = 取得時に段落の一覧を出さない(自動運転)
TEST_ROOT = os.environ.get("EH_ROOT")  # 試験用: 置き場と台帳を丸ごと別フォルダへ逃がす
BASE = TEST_ROOT or os.path.join(ROOT, ".cache", "element-harvest")
LEDGER = os.path.join(TEST_ROOT or os.path.join(ROOT, "data", "element-harvest"), "ledger.jsonl")
UA = _site_gate.UA

KINDS = ["wiki", "公式", "考察", "ネタバレ"]
KIND_ALIAS = {"official": "公式", "analysis": "考察", "spoiler": "ネタバレ"}
AS = ["物語", "作風", "人物", "主題", "展開", "タグ"]
AS_ALIAS = {"story": "物語", "style": "作風", "people": "人物", "theme": "主題", "plot": "展開", "tags": "タグ"}
# ★材料にしない種類のサイト(2026-10-08 試走で、検索に pixiv の二次創作小説・知恵袋・海外wiki が混ざった)。
#   二次創作は原作に無い設定を書く = 一字一句の根拠検査を通ってしまう一番危ない混入。 道具が取得を断る。
NOT_MATERIAL = {
    "二次創作・投稿小説": ["pixiv.net", "syosetu.org", "syosetu.com", "kakuyomu.jp", "alphapolis.co.jp", "novel.daysneo.com"],
    "Q&A・掲示板": ["chiebukuro.yahoo.co.jp", "oshiete.goo.ne.jp", "reddit.com", "5ch.net", "2ch.sc", "open2ch.net", "togetter.com"],
    "SNS・動画": ["x.com", "twitter.com", "instagram.com", "tiktok.com", "facebook.com", "youtube.com", "nicovideo.jp"],
    "海外のwiki": ["baidu.com", "moegirl.org.cn", "fandom.com", "wikipedia.org"],  # ja.wikipedia.org だけは別扱い(API)
    "売り場・フリマ": ["mercari.com", "auctions.yahoo.co.jp", "lifetunes-mall.jp"],
}


def fix_url(u):
    """「/url?…&q=https://…」(検索の中継URL)から本当のURLを取り出す。"""
    if u.startswith("/url?") or re.match(r"^https?://(www\.)?google\.[a-z.]+/url\?", u):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
        for k in ("q", "url"):
            if q.get(k) and q[k][0].startswith("http"):
                return q[k][0]
    return u


# robots.txt で断られると分かっているサイト(検索結果に印を付けるためだけの表。 可否の正本は _site_gate の実判定)
KNOWN_ROBOTS_DENY = ("dic.pixiv.net", "manba.co.jp", "ebookjapan.yahoo.co.jp")


def not_material(host):
    if host in ("ja.wikipedia.org", "dic.pixiv.net"):  # 百科(dic.pixiv.net)は種類でなく robots で断られる = 門に任せる
        return None
    for why, ds in NOT_MATERIAL.items():
        if any(host == d or host.endswith("." + d) for d in ds):
            return why
    return None
SKIP_WHY = ["別作品", "薄い", "書誌や商品情報だけ", "重複", "本文なし", "その他"]
NONE_WHY = ["検索に出ない", "出たが別作品", "取得できない", "見たが薄い"]
CAP = {
    "search": {"wiki": 3, "公式": 3, "考察": 3, "ネタバレ": 3},   # 定型2 + 自由文1
    "fetch": {"wiki": 5, "公式": 4, "考察": 4, "ネタバレ": 3},
    "adopt": {"wiki": 3, "公式": 2, "考察": 2, "ネタバレ": 2},     # wiki の3 = 作品記事 + 主要人物の記事
    "chars_source": 2500, "chars_wikipedia": 5000, "chars_work": 16000, "fetch_work": 20,
}
QUERIES = {
    "wiki": ["{t} アニヲタWiki", "{t} 登場人物 キャラクター紹介"],  # ピクシブ百科=robots拒否 / ニコニコ大百科=403(実踏)
    # ★1本目は頁の題そのもの(副題つき)+レーベル。 原作小説と版元が同じ漫画化(俺ガイル@comic)で、
    #   「題+版元」だと小説側の頁ばかり出た(2026-10-08 試走)
    "公式": ["{full} {imprint} 公式", "{t} {a} 1巻 あらすじ"],
    "考察": ["{t} 考察 テーマ", "{t} 魅力 解説 レビュー"],
    "ネタバレ": ["{t} ネタバレ あらすじ 全巻", "{t} 最終回 ネタバレ 感想"],
}
PURPOSE = "漫画『{t}』({a})の内容(あらすじ・作風・テーマ・登場人物)が日本語で書かれたページを探す。通販の商品一覧や動画は不要。"
WIKI_SEC = [  # Wikipedia から機械で採る節: (見出し名の候補, 役割, 上限字数)
    (("作風", "概要", "作品概要", "特徴", "作品解説", "解説", "テーマ"), "作風", 1200),
    (("あらすじ", "ストーリー", "物語", "あらまし", "内容"), "物語", 900),
    (("登場人物", "主な登場人物", "主要登場人物", "キャラクター", "登場キャラクター"), "人物", 1500),
]


# ───────── 小道具 ─────────
def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def die(msg):
    print("✖ " + msg)
    sys.exit(1)


def stop(msg):
    """外部の失敗 = 何も記録せずに止まる(失敗を「材料なし」に化けさせない)。"""
    print("■ 中断: " + msg + "\n  ★この頁については何も記録していない。 繰り返し叩かず、このまま報告する。")
    sys.exit(2)


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s\W_]+", "", s)


def base_title(t):
    """副題・版名を落とした題(同定と検索に使う)。 例: 「…まちがっている。-妄言録-」→「…まちがっている。」"""
    t = unicodedata.normalize("NFKC", str(t or "")).strip()
    m = re.search(r"[-‐―—@~〜(\[【]", t[4:])
    b = t[:4 + m.start()].strip() if m else t
    return b if len(norm(b)) >= 4 else t


def clip(text, n):
    if len(text) <= n:
        return text, False
    cut = text[:n]
    k = max(cut.rfind(c) for c in "。．!?！？")
    if k >= n * 0.5:
        cut = cut[:k + 1]
    return cut, True


def clean_md(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"^\s*(?:[-+*・>]+|\d+[.)])\s+", "", s)
    s = re.sub(r"[*`|]+|_{2,}", "", s)
    return re.sub(r"\s+", " ", s).strip()


TAG_MARK = re.compile(r"^[▽▼■◆●○・\s]*(?:タグ一覧|関連タグ)[\s:：]*$")  # アニヲタWiki 等の「▽タグ一覧」
PROSE = re.compile(r"[。、！？!?…─]")


def _join(lines):
    """折り返された行をつなぐ。 日本語はそのまま、英数字どうしの継ぎ目だけ空白を入れる。"""
    out = ""
    for x in lines:
        x = x.strip()
        if out and x and out[-1].isascii() and out[-1].isalnum() and x[0].isascii() and x[0].isalnum():
            out += " "
        out += x
    return out


def to_paras(text, per_line=False):
    """本文 → 段落の列。 h>0 = 見出し(採れない)。 tag=True = 直前が「タグ一覧」の印だった段落。
    per_line=True(Wikipedia)は1行=1段落。 それ以外(魚のMarkdown)は空行で区切った塊を1段落にし、
    塊の中の改行はつなぐ(★v0.1 は行ごとに切って20字未満を捨てたため、1文を14行に折り返した公式の紹介文が
    3行だけ残り「薄い」と判断された=2026-10-08 試走)。 ナビ・権利表記・数字だけ違う同型の行は落とす。"""
    # 1) 行 → 塊(空行で区切る)。 塊ごとに「直前の空き行数」を覚える(水平線は大きな切れ目)
    blocks, cur, gap, cur_gap = [], [], 9, 9
    for ln in text.replace("\r", "").split("\n"):
        s = ln.strip()
        hr = bool(re.fullmatch(r"[-*_=]{3,}", s))
        alone = bool(s) and not hr and (per_line or bool(re.match(r"^(#{1,6}\s|=+\s*.+?\s*=+$|[-+*・]\s|\d+[.)]\s|\|)", s)))
        if not s or hr or alone:
            if cur:
                blocks.append((cur, cur_gap, False))
                cur, gap = [], 0
            if alone:
                blocks.append(([s], gap, True))
                gap = 0
            else:
                gap += 9 if hr else 1
            continue
        if not cur:
            cur_gap = gap
        cur.append(s)
    if cur:
        blocks.append((cur, cur_gap, False))
    # 2) 文の途中で割れた塊をつなぐ。 アニヲタWiki は文中のリンクが独立した塊になる:
    #    「…通り「」「ぼっち」「」「残念な青春」が話の主軸…」。 空き1行で、前が文末(。！？」等)で終わっていない時だけつなぐ
    END = "。．！？!?」』）)…─"
    units, tag_next = [], False
    for lines, g, alone in blocks:
        prev = units[-1] if units else None
        if prev and prev["glue"] and not alone and not tag_next and g == 1 and prev["n"] < 8 and len(prev["t"]) < 600:
            prev["t"] = _join([prev["t"]] + lines)
            prev["raw"] += lines
            prev["n"] += 1
            u = prev
        else:
            u = {"t": _join(lines), "raw": list(lines), "n": 1, "alone": alone, "tag": tag_next}
            units.append(u)
            tag_next = False
        c = clean_md(u["t"])
        mark = bool(TAG_MARK.match(c))
        # つなぎ始めの塊が20字未満の時は、開きかっこ・助詞で終わる時だけ続きを待つ(署名や日付の行を次の段落に
        # 吸い込ませない)。 いったんつなぎ始めたら、文末が来るまで待つ(「…通り「」+「ぼっち」+「」「残念な青春」が…」)
        u["glue"] = (not alone and not u["tag"] and not mark and not per_line and bool(c) and c[-1] not in END
                     and (u["n"] >= 2 or len(c) >= 20 or c[-1] in "「『(（はがをにのとでもへや、・"))
        if mark:
            tag_next = True
    # 3) 見出し・タグ一覧の印・ナビ・権利表記を仕分ける
    out, seen, tag_next = [], set(), False
    for u in units:
        b = u["raw"]
        if u["alone"] and u["n"] == 1:
            m = re.match(r"^(=+)\s*(.+?)\s*=+$", b[0]) or re.match(r"^(#{1,6})\s+(.+)$", b[0])
            if m:
                h = clean_md(m.group(2))
                if h:
                    out.append({"h": len(m.group(1)), "t": h})
                tag_next = bool(TAG_MARK.match(h))
                continue
        linked = sum(len(x) for ln in b for x in re.findall(r"\[([^\]]*)\]\([^)]*\)", ln))
        body = clean_md(u["t"])
        if TAG_MARK.match(body):  # 印そのものは段落にしない。 次の段落がタグ一覧
            tag_next = True
            continue
        is_tag, tag_next = tag_next or u["tag"], False
        if not is_tag:
            if len(body) < 20 or (not PROSE.search(body) and linked >= len(body) * 0.6):
                continue  # 短すぎる行 / 文になっていないリンクの塊(ナビ)
            if re.match(r"^(©|\(c\)|copyright)", body, re.I) or "all rights reserved" in body.lower():
                continue  # 権利表記
        key = re.sub(r"\d+", "#", body)  # 数字だけ違う同型の行(巻一覧・日付つきのお知らせ)は最初の1行だけ残す
        if key in seen or len(body) < 4:
            continue
        seen.add(key)
        out.append({"h": 0, "t": body, "tag": True} if is_tag else {"h": 0, "t": body})
    return out


def parse_ranges(spec, n):
    idx = []
    for part in str(spec).replace("p", "").split(","):
        part = part.strip()
        if not part:
            continue
        a, _, b = part.partition("-")
        if not a.isdigit() or (b and not b.isdigit()):
            die(f"段落の指し方が読めない: {spec}(例 3-5,9)")
        lo, hi = int(a), int(b or a)
        if lo < 1 or hi > n or lo > hi:
            die(f"段落番号が範囲外: {part}(この出所は 1〜{n})")
        idx += list(range(lo, hi + 1))
    return list(dict.fromkeys(idx))


def pick_enum(val, choices, alias=None, what=""):
    v = (alias or {}).get(str(val).lower(), val)
    if str(v).isdigit() and 1 <= int(v) <= len(choices):
        return choices[int(v) - 1]
    if v in choices:
        return v
    part = [c for c in choices if str(v) and str(v) in c]  # 「書誌」→「書誌や商品情報だけ」のように一意に決まれば通す
    if len(part) == 1:
        return part[0]
    die(f"{what}は次のどれか(番号でも可): " + " / ".join(f"{i}={c}" for i, c in enumerate(choices, 1)))


# ───────── 状態 ─────────
def wdir(stem):
    return os.path.join(BASE, stem)


def load(stem):
    p = os.path.join(wdir(stem), "state.json")
    if not os.path.exists(p):
        die(f"まだ開いていない: {ME} open {stem}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(st):
    d = wdir(st["stem"])
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "state.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(d, "state.json"))


def L(n):
    """出所の番号 → 英字(1=A, 2=B, … 27=AA)。 ★検索結果の番号(1〜10)・段落番号と取り違えないため、出所だけ英字で呼ぶ。
    v0.2 の試走で運転者が「検索結果の5番」と「出所5」を取り違え、公式のあらすじが載った頁を不採用にした。"""
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def src(st, sid):
    if not isinstance(sid, int):
        x = str(sid).strip().upper()
        if not x.isalpha():
            die(f"出所は英字で指す(例: C)。 数字は検索結果の番号と段落の番号だけ → {ME} status {st['stem']}")
        sid = 0
        for ch in x:
            sid = sid * 26 + (ord(ch) - 64)
    for s in st["sources"]:
        if s["id"] == sid:
            return s
    die(f"出所 {L(sid)} は無い({ME} status {st['stem']})")


def paras_of(st, sid):
    with open(os.path.join(wdir(st["stem"]), "paras", f"{sid}.json"), encoding="utf-8") as f:
        return json.load(f)


def raw_of(st, sid):
    with open(os.path.join(wdir(st["stem"]), "raw", f"{sid}.txt"), encoding="utf-8") as f:
        return f.read()


def n_fetch(st, kind=None):
    """本文が取れた頁の数(★v0.2 の試走で、本文が空だった小学館の頁2つが 公式 の取得枠4の半分を食った)。"""
    return sum(1 for s in st["sources"] if s["origin"] != "auto" and s["status"] == "fetched"
               and (kind is None or s["kind"] == kind))


def n_tried(st):
    """外へ取りに行った回数(空・失敗・頁なしも数える。 断られた分は数えない)。"""
    return sum(1 for s in st["sources"] if s["origin"] != "auto" and s["status"] != "refused")


def human_chars(st, sid):
    """運転者が指して採った字数(道具が機械で採ったタグ一覧は数えない = 頁を「判断済み」にしない)。"""
    return sum(p["chars"] for p in st["picks"] if p["src"] == sid and not p.get("mech"))


def adopted(st, kind):
    return [s["id"] for s in st["sources"] if s["kind"] == kind and s["origin"] != "auto" and human_chars(st, s["id"])]


def pending(st):
    return [s for s in st["sources"] if s["origin"] != "auto" and s["status"] == "fetched" and not s["skip"]
            and not human_chars(st, s["id"])]


def chars_src(st, sid):
    return sum(p["chars"] for p in st["picks"] if p["src"] == sid)


def chars_all(st):
    return sum(p["chars"] for p in st["picks"])


# ───────── 同定カード ─────────
def build_card(stem):
    import yaml
    try:
        from yaml import CSafeLoader as L
    except ImportError:
        from yaml import SafeLoader as L
    p = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
    if not os.path.exists(p):
        die(f"頁が無い: data/manga.v2/{stem}.yml\n  題から探す: python scripts/_exists.py --title <題の一部>")
    with open(p, encoding="utf-8") as f:
        d = yaml.load(f, Loader=L) or {}
    eds = d.get("editions") or []
    vols = []
    for e in eds:
        vols += e.get("volumes") or []
        for ver in e.get("versions") or []:
            vols += ver.get("volumes") or []
    std = next((e for e in eds if e.get("type") == "standard"), eds[0] if eds else {})
    numbered = sorted([v for v in (std.get("volumes") or []) if v.get("isbn13")],
                      key=lambda v: v.get("number") if isinstance(v.get("number"), (int, float)) else 9999)
    names = lambda key: [str(a.get("name")) for a in (d.get(key) or []) if isinstance(a, dict) and a.get("name")]  # noqa: E731
    alt = d.get("alternative_titles") or {}
    title = str(d.get("title") or "")
    return {
        "stem": stem, "slug": d.get("slug") or stem, "title": title, "base_title": base_title(title),
        "title_kana": d.get("title_kana"), "title_en": alt.get("en") if isinstance(alt, dict) else None,
        "authors": names("authors"), "original_authors": names("original_authors"),
        "publisher": std.get("publisher") or d.get("publisher"), "imprint": std.get("imprint"),
        "magazine": d.get("magazine"), "year_started": d.get("year_started"), "year_ended": d.get("year_ended"),
        "status": d.get("status"), "demographic": d.get("demographic"), "genres": d.get("genres") or [],
        "volumes": len(std.get("volumes") or []), "isbn_vol1": numbered[0].get("isbn13") if numbered else None,
        "anilist_id": d.get("anilist_id"), "anime_adapted": bool(d.get("anime_adapted")),
        "synopsis": d.get("synopsis") or "", "catch": d.get("catch") or "",
        "volume_descriptions": [str(v.get("description")) for v in vols if v.get("description")][:30],
        "tags_on_page": [t.get("name") for t in (d.get("tags") or []) if isinstance(t, dict)],
    }


def identity(card, text):
    """題と著者名が頁に出るか(機械検査)。 OK=両方 / 要確認=題だけ / 別作品の疑い=題なし"""
    T = norm(text)
    ts = [t for t in dict.fromkeys([norm(card["title"]), norm(card["base_title"]), norm(card.get("title_en"))]) if len(t) >= 2]
    au = [a for a in dict.fromkeys(card["authors"] + card["original_authors"]) if len(norm(a)) >= 2]
    t_hit = any(t in T for t in ts)
    a_hit = [a for a in au if norm(a) in T]
    return {"verdict": "OK" if (t_hit and a_hit) else "要確認" if t_hit else "別作品の疑い", "authors_hit": a_hit}


def own_text(card):
    return norm(" ".join([card["synopsis"], card["catch"]] + card["volume_descriptions"] + card["authors"]
                         + card["original_authors"] + [str(card.get("publisher") or ""), str(card.get("imprint") or "")]))


# ───────── 機械で取れる分: AniList / Wikipedia ─────────
ANI_Q = ("query($ids:[Int]){Page(perPage:50){media(id_in:$ids){id type format popularity startDate{year} "
         "title{native romaji} genres tags{name rank category isAdult isMediaSpoiler isGeneralSpoiler} "
         "relations{edges{relationType node{id type format title{native romaji}}}}}}}")


def anilist_call(ids):
    _rate_gate.wait("anilist", 2.0)
    req = urllib.request.Request("https://graphql.anilist.co",
                                 data=json.dumps({"query": ANI_Q, "variables": {"ids": ids}}).encode(),
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())["data"]["Page"]["media"]
    except urllib.error.HTTPError as e:
        stop(f"AniList が HTTP {e.code}")
    except Exception as e:
        stop(f"AniList に届かない({type(e).__name__})")


def anilist_family(card):
    """頁の anilist_id から、関係(原作・アニメ・別版)を題が同じ範囲だけ辿ってタグを集める。"""
    aid = card.get("anilist_id")
    if not aid:
        return {"entries": [], "skipped": [], "note": "頁に anilist_id が無い"}
    base = norm(card["base_title"])
    seen, todo, skipped = {}, [int(aid)], {}
    for _ in range(4):
        todo = [i for i in todo if i not in seen][:50]
        if not todo or len(seen) >= 30:
            break
        nxt = []
        for m in anilist_call(todo):
            seen[m["id"]] = m
            for e in (m.get("relations") or {}).get("edges") or []:
                n = e["node"]
                if n["id"] in seen or n["id"] in nxt:
                    continue
                tt = n.get("title") or {}
                nb = norm(tt.get("native"))
                if len(base) >= 4 and nb and (base in nb or (len(nb) >= 4 and nb in base)):
                    nxt.append(n["id"])
                else:  # 題が違う関連(別題の続編・クロスオーバー等)は辿らない
                    skipped[n["id"]] = {"id": n["id"], "type": n.get("type"), "format": n.get("format"),
                                        "title": tt.get("native") or tt.get("romaji"), "rel": e.get("relationType")}
        todo = nxt
    entries = []
    for m in seen.values():
        grp = "自分" if m["id"] == int(aid) else "小説" if m.get("format") == "NOVEL" else "アニメ" if m.get("type") == "ANIME" else "漫画"
        entries.append({"id": m["id"], "group": grp, "type": m.get("type"), "format": m.get("format"),
                        "year": (m.get("startDate") or {}).get("year"), "popularity": m.get("popularity"),
                        "title": (m.get("title") or {}).get("native"), "genres": m.get("genres") or [],
                        "tags": [{"name": t["name"], "rank": t["rank"], "category": t["category"], "adult": bool(t.get("isAdult")),
                                  "spoiler": bool(t.get("isMediaSpoiler") or t.get("isGeneralSpoiler"))} for t in m.get("tags") or []]})
    return {"entries": entries, "skipped": [v for k, v in skipped.items() if k not in seen], "note": ""}


# ★関連作(小説・アニメ)の票を引き継ぐのは「本筋」のエントリだけ。
#   2026-10-09 30作の試行で実害: 登録者468人の小説1件の票で うみねこ に「ギャンブル・麻薬・美男子日常」が、
#   おまけ映像(SPECIAL)1件の票で 君に届け に「演劇」が表に出た。 AniList の票は賛成の「割合」で、登録者が少ないエントリでは
#   1人が付けたタグがそのまま 79 になる(投票の人数は API に無い)。 人数の代わりに登録者数(popularity)で線を引く。
ANI_MIN_POP = 1000                       # 小説・アニメ: 登録者がこの人数に満たないエントリからは引き継がない
ANI_SIDE_RATIO = 0.1                     # アニメ: 登録者がいちばん多いアニメの1割に満たないもの(おまけ・脇の映像)からは引き継がない
ANI_SIDE_FORMATS = {"SPECIAL", "MUSIC"}  # おまけ映像・ミュージックビデオ


def ani_main(ani):
    """→ 票を使う「本筋」のエントリの id。 自分は常に本筋(今の取り込みと同じ扱い)。 他の漫画(アンソロジー等)は元から付与に使わない。"""
    ents = (ani or {}).get("entries") or []
    top = max([e.get("popularity") or 0 for e in ents if e["group"] == "アニメ"] or [0])
    main = set()
    for e in ents:
        pop = e.get("popularity") or 0
        if e["group"] == "自分" or (e["group"] == "小説" and pop >= ANI_MIN_POP):
            main.add(e["id"])
        elif e["group"] == "アニメ" and pop >= ANI_MIN_POP and pop >= ANI_SIDE_RATIO * top and e.get("format") not in ANI_SIDE_FORMATS:
            main.add(e["id"])
    return main


def anilist_merged(ani):
    """タグごとに 自分/小説/アニメ/他の漫画 の最高票を並べる(付与はしない。材料として渡すだけ)。
    小説・アニメは本筋のエントリ(ani_main)の票だけ。 本筋でないエントリの票は weak に残す(使わない。 見えるようにするだけ)。"""
    rows = {}
    main = ani_main(ani)
    for e in (ani or {}).get("entries") or []:
        col = {"自分": "self", "小説": "novel", "アニメ": "anime", "漫画": "other"}[e["group"]]
        if col != "other" and e["id"] not in main:
            col = "weak"
        for t in e["tags"]:
            r = rows.setdefault(t["name"], {"name": t["name"], "category": t["category"], "self": 0, "novel": 0,
                                           "anime": 0, "other": 0, "weak": 0, "spoiler": False, "adult": False, "n": 0, "ns": 0})
            r[col] = max(r[col], t["rank"])
            r["adult"] |= t["adult"]
            if col == "weak":
                continue
            r["spoiler"] |= t["spoiler"]
            if col != "other":  # 印の粗さを見るため: 自分・小説・アニメ(本筋)のうち、この語を持つ件数と印つきの件数
                r["n"] += 1
                r["ns"] += 1 if t["spoiler"] else 0
    return sorted(rows.values(), key=lambda r: -max(r["self"], r["novel"], r["anime"], r["other"]))


def wiki_get(title):
    from _wiki_host import cooldown_check, cooldown_set
    cooldown_check()  # 冷却中はここで exit(3)
    _rate_gate.wait("wiki", 1.2)
    q = {"action": "query", "format": "json", "redirects": 1, "titles": title, "prop": "extracts|categories|pageprops",
         "explaintext": 1, "exsectionformat": "wiki", "cllimit": "max", "clshow": "!hidden", "ppprop": "disambiguation"}
    req = urllib.request.Request("https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            cooldown_set(60, by="element-harvest")
        stop(f"Wikipedia が HTTP {e.code}")
    except Exception as e:
        stop(f"Wikipedia に届かない({type(e).__name__})")
    pg = next(iter(((d.get("query") or {}).get("pages") or {}).values()), None)
    if not pg or "missing" in pg or "invalid" in pg or "disambiguation" in (pg.get("pageprops") or {}):
        return None
    text = pg.get("extract") or ""
    if len(text) < 200:
        return None
    return {"title": pg.get("title"), "text": text,
            "categories": [c["title"].split(":", 1)[-1] for c in pg.get("categories") or []]}


def wiki_auto(st):
    card = st["card"]
    b = card["base_title"]
    cands = list(dict.fromkeys([card["title"], b, b.rstrip("。.!！?？ "), b.rstrip("。.!！?？ ") + " (漫画)"]))
    for t in cands:
        w = wiki_get(t)
        if not w:
            continue
        s, paras = register_text(st, "wiki", "auto", "https://ja.wikipedia.org/wiki/" + urllib.parse.quote(w["title"]),
                                 "Wikipedia「%s」" % w["title"], w["text"])
        st["wiki"] = {"title": w["title"], "source": s["id"], "categories": w["categories"], "identity": s["identity"]["verdict"]}
        if s["identity"]["verdict"] == "OK":
            wiki_autopick(st, s, paras)
        return
    st["wiki"] = {"title": None, "source": None, "categories": [], "identity": "記事なし", "tried": cands}


def wiki_autopick(st, s, paras):
    sec, cur = {}, "(冒頭)"
    for i, p in enumerate(paras, 1):
        if p["h"] == 2:
            cur = p["t"]
        elif not p["h"]:
            sec.setdefault(cur, []).append(i)
    got = set()
    for names, as_, cap in WIKI_SEC:
        name = next((n for n in names if n in sec), None)
        if name and add_pick(st, s, paras, sec[name], as_, auto=True, cap=cap, label=name):
            got.add(as_)
    if not ({"物語", "作風"} & got) and sec.get("(冒頭)"):  # 節の無い短い記事は冒頭が全部
        add_pick(st, s, paras, sec["(冒頭)"], "作風", auto=True, cap=600, label="冒頭")


# ───────── 取得と採用 ─────────
def register_text(st, kind, origin, url, title, text, final_url=None, ref=None):
    sid = len(st["sources"]) + 1
    d = wdir(st["stem"])
    for sub in ("raw", "paras"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    with open(os.path.join(d, "raw", f"{sid}.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    paras = to_paras(text, per_line=_site_gate.host_of(final_url or url) == "ja.wikipedia.org")
    with open(os.path.join(d, "paras", f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(paras, f, ensure_ascii=False)
    s = {"id": sid, "kind": kind, "origin": origin, "url": url, "final_url": final_url or url, "title": title,
         "domain": _site_gate.host_of(final_url or url), "status": "fetched", "why": "",
         "identity": identity(st["card"], (title or "") + "\n" + text), "chars": len(text),
         "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(), "paras": len(paras), "ref": ref, "at": now(), "skip": None}
    st["sources"].append(s)
    return s, paras


def note_source(st, kind, origin, url, status, why, ref=None):
    st["sources"].append({"id": len(st["sources"]) + 1, "kind": kind, "origin": origin, "url": url, "final_url": url,
                          "title": "", "domain": _site_gate.host_of(url), "status": status, "why": why, "identity": None,
                          "chars": 0, "sha1": "", "paras": 0, "ref": ref, "at": now(), "skip": None})


def cap_src(s):
    """1頁から採れる字数。 Wikipedia は一番確かな出所なので枠を広く取る。"""
    return CAP["chars_wikipedia"] if s["domain"] == "ja.wikipedia.org" else CAP["chars_source"]


def add_pick(st, s, paras, idxs, as_, auto=False, cap=None, label="", mech=False):
    room = min(cap_src(s) - chars_src(st, s["id"]), CAP["chars_work"] - chars_all(st), cap or 10 ** 9)
    if room < 40:
        return None
    text, trunc = clip("\n".join(paras[i - 1]["t"] for i in idxs), room)
    if len(text) < (4 if mech else 20):
        return None
    p = {"id": max([x["id"] for x in st["picks"]] + [0]) + 1, "src": s["id"], "paras": idxs, "as": as_, "text": text,
         "chars": len(text), "truncated": trunc, "spoiler": as_ == "展開", "auto": auto,
         "mech": mech, "label": label, "at": now()}
    st["picks"].append(p)
    return p


def autopick_tags(st, s, paras):
    """「タグ一覧」の印の直後の段落を、役割=タグ で道具が採る(同定が通っている頁だけ呼ぶ)。
    ★v0.1 では印の行(6字)が短い行として落ち、運転者にはタグ一覧だと分からず採られなかった(2026-10-08 試走)。"""
    used = {i for p in st["picks"] if p["src"] == s["id"] for i in p["paras"]}
    got = []
    for i, p in enumerate(paras, 1):
        if p.get("tag") and i not in used and add_pick(st, s, paras, [i], "タグ", cap=600, label="タグ一覧", mech=True):
            got.append(i)
    return got


def outline(paras, start=1, limit=45, full=0, seen=None):
    """段落の一覧。 full(字数)が残っている間は全文、使い切ったら頭62字だけ。 全文を見せた段落番号は seen に入れる。"""
    shown = 0
    for i, p in enumerate(paras, 1):
        if i < start:
            continue
        if shown >= limit:
            print(f"   … 続きは --from {i}(全{len(paras)}段落)")
            break
        tag = "[タグ一覧] " if p.get("tag") else ""
        if p["h"]:
            print(f"      {'#' * min(p['h'], 4)} {p['t'][:50]}")
        elif full > 0 or len(p["t"]) <= 62:
            print(f"  p{i:<4}({len(p['t'])}字) {tag}{p['t']}")
            full -= len(p["t"])
            if seen is not None:
                seen.add(i)
        else:
            print(f"  p{i:<4}({len(p['t'])}字) {tag}{p['t'][:62]}… [頭だけ]")
        shown += 1


def do_fetch(st, kind, url, origin, ref=None):
    if any(url in (s["url"], s["final_url"]) for s in st["sources"]):
        print(f"  既に扱った頁: {url}")
        return
    if n_fetch(st, kind) >= CAP["fetch"][kind] or n_tried(st) >= CAP["fetch_work"]:
        print(f"  ✖ 取得の上限に達した({kind} 取れた頁 {n_fetch(st, kind)}/{CAP['fetch'][kind]}・試した総数 {n_tried(st)}/{CAP['fetch_work']})")
        return
    host = _site_gate.host_of(url)
    m = re.match(r"^https?://ja\.(?:m\.)?wikipedia\.org/wiki/([^?#]+)", url)
    if m:  # Wikipedia は魚でなく公式APIで取る
        w = wiki_get(urllib.parse.unquote(m.group(1)).replace("_", " "))
        if not w:
            note_source(st, kind, origin, url, "notfound", "Wikipedia に記事なし", ref)
            print(f"  記事なし: {url}")
            return
        s, paras = register_text(st, kind, origin, url, "Wikipedia「%s」" % w["title"], w["text"], ref=ref)
    else:
        if sum(1 for s in st["sources"] if s["domain"] == host and s["status"] == "error") >= 2:
            print(f"  ✖ {host} は今回2回失敗している → もう取らない")
            return
        if any(s["domain"] == host and s["status"] == "empty" for s in st["sources"]):
            print(f"  ✖ {host} は今回すでに本文が取れなかった(画面を組み立てる型の頁)→ 取らない。 他の結果へ")
            return
        nm = not_material(host)
        if nm:
            note_source(st, kind, origin, url, "refused", f"材料にしない種類({nm})", ref)
            print(f"  ✖ 取らない: {host} は材料にしない種類({nm})。 他の結果へ。")
            return
        v = _site_gate.check(url)
        if not v["ok"]:
            note_source(st, kind, origin, url, "refused", v["why"], ref)
            print(f"  ✖ 取らない: {v['why']}\n     ★別の手段(WebFetch 等)で取りに行かない。 他の結果へ。")
            return
        _site_gate.pace(url)
        _rate_gate.wait("tinyfish", 1.5)
        import _tinyfish
        try:
            res = _tinyfish.fetch([url])
        except SystemExit as e:
            stop(f"魚が失敗を返した: {str(e)[:160]}")
        except Exception as e:
            stop(f"魚に届かない({type(e).__name__})")
        results = res.get("results") or []
        if not results:
            e = (res.get("errors") or [{}])[0]
            code = e.get("status")
            if code in (404, 410):
                note_source(st, kind, origin, url, "notfound", f"HTTP {code}", ref)
                print(f"  頁なし(HTTP {code}): {url}")
            elif e.get("error") == "empty_content":  # 魚が中身を取れなかった(画面を組み立てる型の頁など)
                note_source(st, kind, origin, url, "empty", "本文が取れない(empty_content)", ref)
                print(f"  本文なし(魚が中身を取れない頁): {url}")
            else:  # 403・429・5xx・timeout = 一時的な失敗として残す(「材料なし」の根拠にしない)
                note_source(st, kind, origin, url, "error", f"{e.get('error')} (status={code})", ref)
                print(f"  取得失敗: {e.get('error')} (status={code}) {url}")
            return
        r = results[0]
        text = r.get("text")
        if not isinstance(text, str) or len(text.strip()) < 200:
            note_source(st, kind, origin, url, "empty", "本文が取れない(JS・ログイン壁の可能性)", ref)
            print(f"  本文なし: {url}")
            return
        s, paras = register_text(st, kind, origin, url, r.get("title") or "", text, final_url=r.get("final_url") or url, ref=ref)
    idn = s["identity"]
    print(f"\n出所{L(s['id'])} [{kind}] {s['domain']} 「{(s['title'] or '')[:40]}」 {s['chars']}字・{s['paras']}段落")
    print(f"  同定 = {idn['verdict']}" + (f"(著者名 {'・'.join(idn['authors_hit'])} あり)" if idn["authors_hit"] else "")
          + {"OK": "", "要確認": " → 採る時は pick に --same を付ける(例: pick <stem> <出所> <段落> --as 人物 --same \"主人公の氏名\")",
             "別作品の疑い": " → 題が頁に出てこない。 採れない(skip --why 別作品)"}[idn["verdict"]])
    c = st["card"]
    if norm(c["title"]) != norm(c["base_title"]) and norm(c["title"]) in norm((s["title"] or "") + text if not m else w["text"]):
        print(f"  ★副題つきの題「{c['title']}」が在る = この漫画そのものの頁。 あらすじ・紹介の段落を必ず読んで採る")
    tags = [i for i, p in enumerate(paras, 1) if p.get("tag")]
    if tags and idn["verdict"] == "OK":
        got = autopick_tags(st, s, paras)
        print(f"  ★タグ一覧 p{','.join(map(str, got))} は道具が採った(役割=タグ)。 本文の段落は別に判断する")
    elif tags and idn["verdict"] == "要確認":
        print(f"  ★タグ一覧 = p{','.join(map(str, tags))}。 この頁で --same が通った時に道具が自動で採る")
    if QUIET:  # 自動運転: 段落は judge_page がモデルに渡す
        return
    seen = set()
    outline(paras, full=2500, seen=seen)  # 先頭2,500字ぶんは全文で見せる(読むための往復を減らす)
    s["seen"] = sorted(seen)


# ───────── コマンド ─────────
def show_card(c):
    print(f"■ {c['title']}  ({c['stem']})")
    print(f"  著者 {'・'.join(c['authors']) or '-'}" + (f" / 原作 {'・'.join(c['original_authors'])}" if c["original_authors"] else "")
          + f" / {c.get('publisher') or '-'} {c.get('imprint') or ''} / 掲載誌 {c.get('magazine') or '-'}")
    print(f"  {c.get('year_started') or '?'}〜{c.get('year_ended') or ''} {c.get('status') or ''} 全{c['volumes']}巻"
          f" / ジャンル {','.join(c['genres']) or '-'} / AniList {c.get('anilist_id') or 'なし'}")
    if c["synopsis"]:
        print(f"  あらすじ(頁): {c['synopsis'][:110]}")


def show_status(st):
    print(f"  材料 {chars_all(st)}/{CAP['chars_work']}字 ・ 取りに行った回数 {n_tried(st)}/{CAP['fetch_work']}")
    for k in KINDS:
        ns = sum(1 for q in st["searches"] if q["kind"] == k)
        kc = sum(p["chars"] for p in st["picks"] if src(st, p["src"])["kind"] == k)
        extra = f" ・ none={st['none'][k]}" if k in st["none"] else ""
        print(f"  {k:<5} 検索 {ns}/{CAP['search'][k]} 取得 {n_fetch(st, k)}/{CAP['fetch'][k]} "
              f"採用 {len(adopted(st, k))}/{CAP['adopt'][k]} ({kc}字){extra}")
    for s in st["sources"]:
        v = (s["identity"] or {}).get("verdict", "-")
        tail = (f"採用{chars_src(st, s['id'])}字" if human_chars(st, s["id"]) or s["origin"] == "auto" else f"不採用={s['skip']}" if s["skip"]
                else "タグ一覧だけ採った・本文は未判断" if chars_src(st, s["id"]) else s["why"] or "未判断")
        print(f"   出所{L(s['id']):<2} {s['kind']:<5} {s['status']:<8} {v:<6} {s['domain'][:26]:<26} {tail}")


def hint(st):
    stem = st["stem"]
    print("\n── 次にやること ──")
    if st.get("done_at"):
        print("  済。 やり直すなら open --fresh")
        return
    pend = pending(st)
    if pend:  # 取った頁は、次へ進む前に必ず判断する
        s = pend[0]
        print(f"  [{s['kind']}] 出所{L(s['id'])}({s['domain']})が未判断 → {ME} show {stem} {L(s['id'])} --range <段落> で読み、pick か skip"
              + (f"(ほかに未判断 {len(pend) - 1}頁)" if len(pend) > 1 else ""))
        return
    for k in KINDS:
        if k in st["none"]:
            continue
        want = {"wiki": 2, "考察": 2}.get(k, 1)  # 目安の頁数(wiki=作品記事+主人公 / 考察=主題は1頁だと偏る)
        if len(adopted(st, k)) >= want or (k == "wiki" and any(p["auto"] for p in st["picks"]) and n_fetch(st, k) >= 2):
            continue
        if adopted(st, k) and (n_fetch(st, k) >= CAP["fetch"][k] or sum(1 for q in st["searches"] if q["kind"] == k) >= CAP["search"][k]):
            continue
        ns = sum(1 for q in st["searches"] if q["kind"] == k)
        room = n_fetch(st, k) < CAP["fetch"][k] and n_tried(st) < CAP["fetch_work"]
        last = next((q for q in reversed(st["searches"]) if q["kind"] == k), None)
        used = {s["ref"] for s in st["sources"] if s.get("ref")}
        fresh = [r["n"] for r in (last or {}).get("results", []) if f"{last['id']}:{r['n']}" not in used] if last else []
        if room and fresh:
            print(f"  [{k}] 検索 {last['id']} の結果から開く頁を番号で指す → {ME} fetch {stem} {last['id']} <番号,番号>")
        elif room and ns < CAP["search"][k]:
            print(f"  [{k}] → {ME} search {stem} {k}" + (f" --q {ns + 1}" if 0 < ns < 2 else ""))
        else:
            print(f"  [{k}] 上限まで見て採用0 → {ME} none {stem} {k} --why <{' | '.join(NONE_WHY)}>")
        return
    print(f"  全種別に採用か none がある → {ME} done {stem}")
    print("  (採用枠が残る種別は、1頁目に無い情報 = 人物・主題 がある頁だけ追加してよい)")


def cmd_open(a):
    d = wdir(a.stem)
    if os.path.exists(os.path.join(d, "state.json")) and not a.fresh:
        st = load(a.stem)
        print("続きから:")
    else:
        if os.path.exists(d):
            arch = os.path.join(BASE, "_archive")
            os.makedirs(arch, exist_ok=True)
            shutil.move(d, os.path.join(arch, f"{a.stem}-{datetime.datetime.now():%Y%m%d-%H%M%S}"))
        st = {"stem": a.stem, "version": VERSION, "model": a.model, "opened_at": now(), "card": build_card(a.stem),
              "anilist": None, "wiki": None, "searches": [], "sources": [], "picks": [], "none": {}, "done_at": None}
        save(st)
    c = st["card"]
    show_card(c)
    if st["anilist"] is None:  # None = まだ試していない(中断後の再開でここから)
        st["anilist"] = anilist_family(c)
        save(st)
    if st["wiki"] is None:
        wiki_auto(st)
        save(st)
    ani = st["anilist"]
    grp = {}
    for e in ani["entries"]:
        grp[e["group"]] = grp.get(e["group"], 0) + 1
    top = [f"{r['name']}{max(r['self'], r['novel'], r['anime'], r['other'])}" for r in anilist_merged(ani)[:14]]
    nweak = sum(1 for e in ani["entries"] if e["group"] != "漫画" and e["id"] not in ani_main(ani))
    print(f"\n[機械] AniList: " + (ani["note"] or f"関連 {len(ani['entries'])}件({'・'.join(f'{k}{v}' for k, v in grp.items())}) "
                                   f"タグ {len(anilist_merged(ani))}種: {', '.join(top)}"
                                   + (f" / 票を使わないエントリ {nweak}件(登録者が少ない・おまけ映像)" if nweak else "")))
    w = st["wiki"]
    if w["source"]:
        auto = [f"{p['label']}→{p['as']} {p['chars']}字" for p in st["picks"] if p["auto"]]
        print(f"[機械] Wikipedia「{w['title']}」= 出所{L(w['source'])}・同定 {w['identity']}・カテゴリ {len(w['categories'])}件"
              f"\n        自動で採った節: {' / '.join(auto) or 'なし(同定が OK でないため。 pick --same で採れる)'}")
    else:
        print("[機械] Wikipedia: 記事が見つからない(題のまま・副題なし・(漫画) で試した)")
    show_status(st)
    hint(st)


def unusable(st, url):
    """この検索結果を開けない理由(開けるなら空文字)。 可否の正本は取得時の _site_gate。 ここは一覧に印を付けるための早見。"""
    host = _site_gate.host_of(url)
    if any(host == d or host.endswith("." + d) for d in _site_gate.DENY):
        return "止め札"
    if not_material(host):
        return "対象外"
    if any(host == d or host.endswith("." + d) for d in KNOWN_ROBOTS_DENY):
        return "robots"
    if any(x["domain"] == host and x["status"] == "empty" for x in st["sources"]):
        return "今回は空"
    return ""


def run_search(st, k, query=None, qi=None):
    """魚で検索して記録する(定型クエリ qi=1|2、または自由文)。 → 検索の記録"""
    c = st["card"]
    if query:
        q = query.strip()
    else:
        qi = qi or min(sum(1 for x in st["searches"] if x["kind"] == k and not x.get("free")) + 1, 2)
        au = (c["authors"] or c["original_authors"] or [""])[0]
        q = QUERIES[k][qi - 1].format(t=c["base_title"], full=c["title"], a=au, pub=c.get("publisher") or "",
                                      imprint=c.get("imprint") or c.get("publisher") or "")
        q = re.sub(r"\s+", " ", q).strip()
    _rate_gate.wait("tinyfish", 1.5)
    import _tinyfish
    au_all = "・".join(c["authors"] + c["original_authors"])
    try:
        res = _tinyfish.search(q, purpose=PURPOSE.format(t=c["base_title"], a=au_all), location="JP")
    except SystemExit as e:
        stop(f"魚の検索が失敗を返した: {str(e)[:160]}")
    except Exception as e:
        stop(f"魚に届かない({type(e).__name__})")
    rows = []
    for i, r in enumerate((res.get("results") or [])[:10], 1):
        rows.append({"n": i, "title": r.get("title") or "", "url": fix_url(r.get("url") or ""), "snippet": (r.get("snippet") or "")[:200]})
    rec = {"id": f"s{len(st['searches']) + 1}", "kind": k, "q": q, "free": bool(query), "at": now(), "results": rows}
    st["searches"].append(rec)
    save(st)
    return rec


def cmd_search(a):
    st = load(a.stem)
    k = pick_enum(a.kind, KINDS, KIND_ALIAS, "種別")
    ns = sum(1 for q in st["searches"] if q["kind"] == k)
    if ns >= CAP["search"][k]:
        die(f"{k} の検索は上限({CAP['search'][k]}回)に達した")
    if a.q and int(a.q) not in (1, 2):
        die("--q は 1 か 2")
    rec = run_search(st, k, query=a.query, qi=int(a.q) if a.q else None)
    sid, q, rows = rec["id"], rec["q"], rec["results"]
    print(f"検索 {sid} [{k}] 「{q}」 → {len(rows)}件")
    for r in rows:
        host = _site_gate.host_of(r["url"])
        mark = unusable(st, r["url"])
        print(f"  {r['n']:>2}. {('✖' + mark + ' ') if mark else ''}[{host}] {r['title'][:46]}\n      {r['snippet'][:96]}")
    print(f"\n開く頁を番号で指す: {ME} fetch {a.stem} {sid} <番号,番号>   (この種別の取得残り {CAP['fetch'][k] - n_fetch(st, k)}頁)")


def cmd_fetch(a):
    st = load(a.stem)
    q = next((x for x in st["searches"] if x["id"] == a.sid), None)
    if not q:
        die(f"検索 {a.sid} は無い")
    for n in [int(x) for x in re.findall(r"\d+", a.nums)]:
        r = next((r for r in q["results"] if r["n"] == n), None)
        if not r:
            print(f"  番号 {n} は検索 {a.sid} に無い")
            continue
        do_fetch(st, q["kind"], r["url"], "search", ref=f"{a.sid}:{n}")
        save(st)
    hint(st)


def cmd_fetch_url(a):
    st = load(a.stem)
    do_fetch(st, pick_enum(a.kind, KINDS, KIND_ALIAS, "種別"), a.url.strip(), "url")
    save(st)
    hint(st)


def cmd_show(a):
    st = load(a.stem)
    s = src(st, a.src)
    if s["status"] != "fetched":
        die(f"出所{L(s['id'])} は本文が無い({s['status']}: {s['why']})")
    paras = paras_of(st, s["id"])
    print(f"出所{L(s['id'])} [{s['kind']}] {s['domain']} 「{(s['title'] or '')[:40]}」 同定={s['identity']['verdict']} {s['url']}")
    seen = set(s.get("seen") or [])
    if not a.range:
        outline(paras, start=int(a.frm or 1), seen=seen)
    else:
        used, total = {i for p in st["picks"] if p["src"] == s["id"] for i in p["paras"]}, 0
        for i in parse_ranges(a.range, len(paras)):
            p = paras[i - 1]
            total += len(p["t"])
            if total > 5000:
                print(f"   … 一度に見せるのは5,000字まで。 続きは --range {i}-")
                break
            seen.add(i)
            print(f"\n{'## ' if p['h'] else ''}p{i}{' [採用済]' if i in used else ''}{' [タグ一覧]' if p.get('tag') else ''} {p['t']}")
    s["seen"] = sorted(seen)
    save(st)


def cmd_pick(a):
    st = load(a.stem)
    s = src(st, a.src)
    as_ = pick_enum(a.as_, AS, AS_ALIAS, "役割(--as)")
    if s["status"] != "fetched":
        die(f"出所{L(s['id'])} は本文が無い")
    v = s["identity"]["verdict"]
    if v == "別作品の疑い":
        die("同定 = 別作品の疑い(題が頁に出てこない)。 この頁からは採れない → skip --why 別作品")
    if v == "要確認" and not s.get("same"):
        if not a.same:
            die("同定 = 要確認(題は在るが著者名が無い)。 同じ作品だと分かる語句を --same \"…\" で指す\n"
                "  条件: この頁と、こちらのデータ(あらすじ・キャッチ・巻説明・著者名)の両方に在る4字以上の語句。例: 主人公の氏名")
        ph = norm(a.same)
        if len(ph) < 4:
            die("--same は4字以上")
        if ph not in norm(raw_of(st, s["id"])):
            die("--same の語句がこの頁に無い(一字一句そのまま指す)")
        if ph not in own_text(st["card"]):
            die("--same の語句がこちらのデータに無い → 別の語句で(無ければこの頁は採らない)")
        s["same"] = a.same
        got = autopick_tags(st, s, paras_of(st, s["id"]))  # 同定が通ったので、タグ一覧は道具が採る
        if got:
            print(f"  ★タグ一覧 p{','.join(map(str, got))} は道具が採った(役割=タグ)")
        save(st)
    k = s["kind"]
    if s["origin"] != "auto" and s["id"] not in adopted(st, k) and len(adopted(st, k)) >= CAP["adopt"][k]:
        die(f"{k} の採用は {CAP['adopt'][k]}頁まで(既に 出所{','.join(L(i) for i in adopted(st, k))})")
    paras = paras_of(st, s["id"])
    used = {i for p in st["picks"] if p["src"] == s["id"] for i in p["paras"]}
    idxs = [i for i in parse_ranges(a.paras, len(paras)) if i not in used]
    if not idxs:
        die("指した段落は全部採用済み(タグ一覧は道具が採っている)")
    if any(paras[i - 1]["h"] for i in idxs):
        die("見出しは採れない(本文の段落番号だけを指す)")
    if len(idxs) > 12:  # 頁を丸ごと指させない(読んで、材料になる所だけ)
        die("一度に指せるのは12段落まで。 show --range で読んで、材料になる段落だけを指す")
    blind = [i for i in idxs if i not in set(s.get("seen") or [])]
    if blind:  # ★頭62字だけ見て指させない(v0.1 の試走で、全文を読まずに指した採用が断片になった)
        die(f"まだ全文を見ていない段落がある: p{','.join(map(str, blind))}\n"
            f"  → {ME} show {a.stem} {L(s['id'])} --range {min(blind)}-{max(blind)} で読んでから指す")
    p = add_pick(st, s, paras, idxs, as_)
    if not p:
        die(f"字数の上限(1頁 {cap_src(s)}字・全体 {CAP['chars_work']}字)に達している")
    s["skip"] = None
    save(st)
    print(f"採用#{p['id']} p{a.paras} → {as_}{'(ネタバレ印)' if p['spoiler'] else ''} {p['chars']}字{'(上限で切った)' if p['truncated'] else ''}"
          f" ・ この頁の残り {cap_src(s) - chars_src(st, s['id'])}字 ・ 全体の残り {CAP['chars_work'] - chars_all(st)}字")
    print(f"  採った文の頭:「{p['text'][:56]}…」  ← 違う段落だったら {ME} unpick {a.stem} {p['id']}")
    hint(st)


def cmd_unpick(a):
    st = load(a.stem)
    p = next((x for x in st["picks"] if x["id"] == int(a.pick)), None)
    if not p:
        die(f"採用#{a.pick} は無い")
    if p["auto"] or p.get("mech"):
        die("道具が採った分(Wikipedia の節・タグ一覧)は取り消さない。 頁ごと外すなら skip")
    st["picks"].remove(p)
    st["done_at"] = None
    save(st)
    print(f"採用#{p['id']} を取り消した(出所{L(p['src'])} p{','.join(map(str, p['paras']))})")
    hint(st)


def cmd_skip(a):
    st = load(a.stem)
    s = src(st, a.src)
    if s["origin"] == "auto":
        die("道具が自動で取った Wikipedia は skip しない")
    if s["status"] != "fetched":
        print(f"出所{L(s['id'])} は本文が無い({s['status']})ので判断は要らない。 何もしていない")
        hint(st)
        return
    if human_chars(st, s["id"]):
        die("この出所は採用済み(skip できない。外すなら先に unpick)")
    why = pick_enum(a.why, SKIP_WHY, None, "理由(--why)")
    st["picks"] = [p for p in st["picks"] if p["src"] != s["id"]]  # 頁を外すなら、道具が採ったタグ一覧も一緒に外す
    s["skip"] = why
    save(st)
    print(f"出所{L(s['id'])} {s['domain']}「{(s['title'] or '')[:30]}」を不採用 = {s['skip']}")
    hint(st)


def cmd_none(a):
    st = load(a.stem)
    k = pick_enum(a.kind, KINDS, KIND_ALIAS, "種別")
    if adopted(st, k):
        die(f"{k} は採用済みの頁がある(none は不要)")
    # ★開きもせずに「材料なし」と言わせない: 検索を1回はして、開ける結果のうち2頁(無ければ在るだけ)は試してから
    qs = [q for q in st["searches"] if q["kind"] == k]
    if not qs:
        die(f"{k} はまだ検索していない → {ME} search {a.stem} {k}")
    usable = {r["url"] for q in qs for r in q["results"]
              if not not_material(_site_gate.host_of(r["url"])) and _site_gate.host_of(r["url"]) != "ja.wikipedia.org"
              and not any(_site_gate.host_of(r["url"]).endswith(d) for d in _site_gate.DENY)}
    tried = sum(1 for s in st["sources"] if s["kind"] == k and s["origin"] != "auto")
    if tried < min(2, len(usable)):
        die(f"{k} は開ける結果が {len(usable)}件あるのに {tried}頁しか試していない → 少なくとも {min(2, len(usable))}頁は開いて判断してから none")
    room = n_fetch(st, k) < CAP["fetch"][k] and n_tried(st) < CAP["fetch_work"]
    if len(qs) < 2 and room:  # ★1回の検索であきらめさせない(v0.1 の試走で 公式 が検索1回のまま none になった)
        die(f"{k} は検索が1回だけ。 別の検索語でもう1回試してから none → {ME} search {a.stem} {k} --q 2")
    if pending(st):
        die("未判断の出所がある → 先に pick か skip")
    st["none"][k] = pick_enum(a.why, NONE_WHY, None, "理由(--why)")
    save(st)
    print(f"{k} = 材料なし({st['none'][k]})")
    hint(st)


def write_bundle(st):
    """材料の束(material.json / material.md)を state から書き出す。 → 束"""
    c, d = st["card"], wdir(st["stem"])
    used = {p["src"] for p in st["picks"]}
    bundle = {
        "stem": st["stem"], "version": st["version"], "bundle_version": VERSION, "model": st["model"], "made_at": st["done_at"],
        "card": {k: c[k] for k in ("slug", "title", "authors", "original_authors", "publisher", "imprint", "magazine",
                                   "year_started", "year_ended", "volumes", "demographic", "genres", "anime_adapted", "synopsis", "catch")},
        "anilist": {"entries": [{k: e[k] for k in ("id", "group", "format", "year", "popularity", "title", "genres")} | {"main": e["id"] in ani_main(st["anilist"])}
                                for e in st["anilist"]["entries"]],
                    "tags": anilist_merged(st["anilist"]), "skipped": st["anilist"]["skipped"]},
        "wikipedia": {"title": st["wiki"]["title"], "categories": st["wiki"]["categories"]},
        "sources": [{k: s[k] for k in ("id", "kind", "origin", "domain", "url", "title")} | {"identity": s["identity"]["verdict"], "same": s.get("same")}
                    for s in st["sources"] if s["id"] in used],
        "picks": [{"id": p["id"], "src": p["src"], "kind": src(st, p["src"])["kind"], "as": p["as"], "spoiler": p["spoiler"],
                   "auto": p["auto"], "text": p["text"]} for p in st["picks"]],
        "none": st["none"],
    }
    with open(os.path.join(d, "material.json"), "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=1)
    md = [f"# 材料: {c['title']} ({st['stem']})", f"道具 {st['version']} / 運転 {st['model']} / {st['done_at']}", "",
          f"著者 {'・'.join(c['authors'])} / 原作 {'・'.join(c['original_authors']) or '-'} / {c.get('publisher')} / {c.get('year_started')}〜 / 全{c['volumes']}巻",
          f"今のジャンル: {', '.join(c['genres'])}", "", "## AniList のタグ(機械。自分/小説/アニメ/他の漫画 の最高票。 小説・アニメは本筋のエントリだけ)"]
    for r in bundle["anilist"]["tags"]:
        md.append(f"- {r['name']} [{r['category']}] {r['self']}/{r['novel']}/{r['anime']}/{r['other']}"
                  + (" ネタバレ印" if r["spoiler"] else "") + (" 成人" if r["adult"] else "")
                  + (f" 〔本筋でないエントリの票 {r['weak']} は使わない〕" if r.get("weak", 0) > max(r["self"], r["novel"], r["anime"]) else ""))
    md += ["", "## Wikipedia のカテゴリ(機械)"] + [f"- {x}" for x in st["wiki"]["categories"]] + ["", "## 採用した文面"]
    for p in st["picks"]:
        s = src(st, p["src"])
        md += [f"### [{p['id']}] {s['kind']} / {p['as']}{' / ネタバレ印' if p['spoiler'] else ''}{' / 自動' if p['auto'] else ''} / 出所{L(s['id'])} {s['domain']}",
               p["text"], ""]
    with open(os.path.join(d, "material.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return bundle


def cmd_rebundle(a):
    """束だけ作り直す(票のまとめ方を直した時など)。 取り直さない・台帳に書かない・done の時刻も変えない。"""
    st = load(a.stem)
    if not st.get("done_at"):
        die("まだ done していない(束が無い)")
    b = write_bundle(st)
    weak = [e for e in b["anilist"]["entries"] if not e["main"] and e["group"] != "漫画"]
    print(f"束を作り直した: {st['card']['title']} / AniList タグ {len(b['anilist']['tags'])}種"
          + (" / 票を使わないエントリ: " + "、".join(f"{e['group']}{e.get('format') or ''}(登録者{e.get('popularity')})" for e in weak) if weak else ""))


def cmd_done(a):
    st = load(a.stem)
    lack = [k for k in KINDS if k not in st["none"] and not adopted(st, k)
            and not (k == "wiki" and any(p["auto"] for p in st["picks"]))]
    if lack:
        die(f"まだ決まっていない種別: {'・'.join(lack)} → 採用するか、 none <種別> --why で理由を残す")
    pend = [s["id"] for s in pending(st)]
    if pend:
        die(f"未判断の出所がある: {','.join(L(i) for i in pend)} → pick か skip")
    st["done_at"] = now()
    save(st)
    c, d = st["card"], wdir(st["stem"])
    bundle = write_bundle(st)
    by = {}
    for k in KINDS:
        ss = [s for s in st["sources"] if s["kind"] == k and s["origin"] != "auto"]
        by[k] = {"search": sum(1 for q in st["searches"] if q["kind"] == k), "fetch": n_fetch(st, k), "adopt": len(adopted(st, k)),
                 "chars": sum(p["chars"] for p in st["picks"] if src(st, p["src"])["kind"] == k),
                 "skip": sorted(s["skip"] for s in ss if s["skip"]), "refused": sorted({s["domain"] for s in ss if s["status"] == "refused"}),
                 "error": sum(1 for s in ss if s["status"] == "error"), "none": st["none"].get(k)}
    line = {"at": st["done_at"], "stem": st["stem"], "slug": c["slug"], "title": c["title"], "version": st["version"], "model": st["model"],
            "anilist_entries": len(st["anilist"]["entries"]), "anilist_tags": len(bundle["anilist"]["tags"]),
            "wikipedia": st["wiki"]["title"], "wikipedia_identity": st["wiki"]["identity"], "by_kind": by, "chars": chars_all(st),
            "sources": [{"id": s["id"], "kind": s["kind"], "origin": s["origin"], "domain": s["domain"], "url": s["url"], "status": s["status"],
                         "identity": (s["identity"] or {}).get("verdict"), "picked": chars_src(st, s["id"]), "skip": s["skip"], "sha1": s["sha1"]}
                        for s in st["sources"]]}
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"== 要素収集の報告 ({st['version']} / {st['model']}) ==\n作品: {c['title']} ({st['stem']})")
    print(f"AniList: 関連 {line['anilist_entries']}件 / タグ {line['anilist_tags']}種" + (f"({st['anilist']['note']})" if st["anilist"]["note"] else ""))
    print(f"Wikipedia: {('「%s」 同定 %s / カテゴリ %d件 / 自動採用 %d字' % (st['wiki']['title'], st['wiki']['identity'], len(st['wiki']['categories']), sum(p['chars'] for p in st['picks'] if p['auto']))) if st['wiki']['source'] else '記事なし'}")
    for k in KINDS:
        b = by[k]
        print(f"{k:<5}: 検索 {b['search']} 取得 {b['fetch']} 採用 {b['adopt']}({b['chars']}字)"
              + (f" 不採用={','.join(b['skip'])}" if b["skip"] else "") + (f" 取らない札={','.join(b['refused'])}" if b["refused"] else "")
              + (f" 取得失敗 {b['error']}" if b["error"] else "") + (f" none={b['none']}" if b["none"] else ""))
    print(f"材料 合計 {line['chars']}字(上限 {CAP['chars_work']}) → {os.path.relpath(os.path.join(d, 'material.md'), ROOT)}")
    print(f"台帳 1行追記 → {os.path.relpath(LEDGER, ROOT)}")


# ───────── 自動運転(★道具が Haiku を「土台なし」で1回ずつ呼ぶ。 会話として運転させない = 1作 約200万→数万トークン) ─────────
AUTO_MODEL = "claude-haiku-5-5"
WANT = {"wiki": 2, "公式": 1, "考察": 2, "ネタバレ": 1}  # 種別ごとの採用の目安(頁数)
LOOK = {
    "wiki": "アニヲタWiki などの百科の、この作品の記事と、主人公(主要人物)の記事。 作風・舞台・人物の性格や属性が書かれた頁",
    "公式": "出版社・掲載誌・アニメ公式サイト・電子書店の、この漫画そのものの紹介文(あらすじ)が載った頁",
    "考察": "この作品が何を描いているか(主題・魅力・作風)を、作品全体について論じている頁。 1話だけの感想より全体の考察",
    "ネタバレ": "中盤以降・結末までの展開をまとめた頁(全巻のあらすじ・最終回の解説)",
}
TRIAGE_SCHEMA = {"type": "object", "required": ["open"], "properties": {"open": {"type": "array", "items": {"type": "integer"}}}}
PICK_SCHEMA = {"type": "object", "required": ["skip", "same", "picks"], "properties": {
    "skip": {"type": "string", "enum": ["", "別作品", "薄い", "書誌や商品情報だけ", "重複"]},
    "same": {"type": "string"},
    "picks": {"type": "array", "items": {"type": "object", "required": ["paras", "as"], "properties": {
        "paras": {"type": "array", "items": {"type": "integer"}},
        "as": {"type": "string", "enum": ["物語", "作風", "人物", "主題", "展開"]}}}}}}


def card_text(c):
    return (f"題: {c['title']} / 著者: {'・'.join(c['authors']) or '-'} / 原作: {'・'.join(c['original_authors']) or '-'}"
            f" / 版元: {c.get('publisher') or '-'} {c.get('imprint') or ''} / 掲載誌: {c.get('magazine') or '-'}"
            f" / {c.get('year_started') or '?'}年〜 / 全{c['volumes']}巻\nあらすじ(こちらのデータ): {c['synopsis'] or c['catch'] or '(なし)'}")


def ask_model(st, prompt, schema, model):
    import _lean_claude
    try:
        ans, use = _lean_claude.ask(prompt, schema, model)
    except _lean_claude.LeanError as e:
        save(st)
        stop(f"モデルの呼び出しが失敗: {e}")
    u = st.setdefault("auto_use", {"calls": 0, "in": 0, "out": 0, "cost_usd": 0.0, "sec": 0.0})
    u["calls"] += 1
    u["in"] += use["in"]
    u["out"] += use["out"]
    u["sec"] = round(u["sec"] + use["sec"], 1)
    u["cost_usd"] = round(u["cost_usd"] + (use.get("cost_usd") or 0), 5)
    return ans


def triage(st, k, rec, model):
    """検索結果から開く頁を選ばせる(番号だけ返させる)。 開けない結果は見せる前に外す。"""
    used = {x["url"] for x in st["sources"]} | {x["final_url"] for x in st["sources"]}
    rows = [r for r in rec["results"] if r["url"] and not unusable(st, r["url"]) and r["url"] not in used
            and _site_gate.host_of(r["url"]) != "ja.wikipedia.org"]
    if not rows:
        return []
    prompt = "\n".join([
        "次の漫画について、検索結果のうち「開く価値のある頁」を番号で選ぶ。", "", "■ 作品", card_text(st["card"]), "",
        f"■ 探しているもの: {LOOK[k]}", "",
        "■ 決まり", "- 同じ題の別作品・続編・スピンオフ・ゲーム版・アニメだけの頁(漫画の話が無い)・グッズ・ニュース・通販の一覧・動画は選ばない",
        "- 上の作品カード(著者・版元・年・あらすじ)と食い違う頁は選ばない", "- 良い順に最大3件。 該当が無ければ空の配列", "",
        "■ 検索結果"] + [f"{r['n']}. [{_site_gate.host_of(r['url'])}] {r['title'][:70]} — {r['snippet'][:160]}" for r in rows]
        + ["", '出力: {"open": [番号, ...]}'])
    ans = ask_model(st, prompt, TRIAGE_SCHEMA, model)
    ok = {r["n"] for r in rows}
    return [n for n in dict.fromkeys(ans.get("open") or []) if n in ok][:3]


def judge_page(st, s, model, budget=5000):
    """取得した頁の段落を見せて、採る段落(番号と役割)を返させる。 道具が検査してから採用する。"""
    paras = paras_of(st, s["id"])
    lines, shown, used = [], set(), 0
    for i, p in enumerate(paras, 1):
        if p["h"]:
            lines.append(f"## {p['t'][:60]}")
        elif p.get("tag"):
            continue  # タグ一覧は道具が採る
        elif used < budget:
            lines.append(f"p{i} {p['t']}")
            shown.add(i)
            used += len(p["t"])
    if not shown:
        s["skip"] = "本文なし"
        return
    v = s["identity"]["verdict"]
    prompt = "\n".join([
        "次の漫画の資料として、この頁のどの段落が使えるかを番号で選ぶ。 文面は書かない(番号と役割だけ)。", "", "■ 作品", card_text(st["card"]), "",
        f"■ この頁: {s['domain']} 「{(s['title'] or '')[:60]}」 / 同定の機械検査 = {v}"
        + ("(題と著者名が頁に在る)" if v == "OK" else "(題は在るが著者名が無い)"), "",
        "■ 採る段落と役割", "- どんな話か(設定・主人公の境遇・舞台) → 物語", "- 作風・雰囲気・どんな読み味か → 作風",
        "- 主要人物の性格・関係・属性 → 人物", "- 何を描いているか(主題) → 主題", "- 中盤以降・結末の展開 → 展開",
        "■ 採らない段落", "発売日・巻数・価格 / スタッフ・声優・主題歌 / 売上・ランキング・受賞の羅列 / グッズ・イベントの告知 /",
        "書き手の自己紹介・前置き・近況 / コメント欄 / 別の作品の紹介 / 目次・メニュー。 迷ったら採らない。 全部で最大8段落",
        "■ skip(この頁を使わない時だけ)", "別作品 = 作品カードと違う作品の頁 / 薄い = 使える段落が無い / 書誌や商品情報だけ / 重複 = 既に採った内容と同じ",
        "■ same", ("同定が「要確認」なので必須: この頁と、上の作品カードの両方に一字一句で出てくる4字以上の語句(主人公の氏名など)。 無ければ skip=別作品"
                   if v != "OK" else "空文字でよい"), "",
        "■ 段落"] + lines + ["", '出力: {"skip": "", "same": "", "picks": [{"paras": [番号...], "as": "役割"}]}'])
    ans = ask_model(st, prompt, PICK_SCHEMA, model)
    s["seen"] = sorted(shown)
    if ans.get("skip"):
        st["picks"] = [p for p in st["picks"] if p["src"] != s["id"]]
        s["skip"] = ans["skip"]
        return
    if v == "別作品の疑い":
        s["skip"] = "別作品"
        return
    if v == "要確認":
        ph = norm(ans.get("same") or "")
        if len(ph) < 4 or ph not in norm(raw_of(st, s["id"])) or ph not in own_text(st["card"]):
            s["skip"], s["why"] = "その他", "同じ作品だと示す語句を道具が確かめられなかった"
            return
        s["same"] = ans["same"]
    autopick_tags(st, s, paras)
    k, n = s["kind"], 0
    if s["id"] not in adopted(st, k) and len(adopted(st, k)) >= CAP["adopt"][k]:
        s["skip"] = "重複"
        return
    got = {i for p in st["picks"] if p["src"] == s["id"] for i in p["paras"]}
    for pk in ans.get("picks") or []:
        idxs = [i for i in dict.fromkeys(pk.get("paras") or []) if isinstance(i, int) and i in shown and i not in got][:8 - n]
        if not idxs or pk.get("as") not in AS:
            continue
        if add_pick(st, s, paras, idxs, pk["as"]):
            got |= set(idxs)
            n += len(idxs)
    if not human_chars(st, s["id"]):
        st["picks"] = [p for p in st["picks"] if p["src"] != s["id"]]
        s["skip"] = "薄い"


def auto_none(st, k):
    ss = [x for x in st["sources"] if x["kind"] == k and x["origin"] != "auto"]
    if not any(q["kind"] == k and any(r["url"] and not unusable(st, r["url"]) for r in q["results"]) for q in st["searches"]):
        return "検索に出ない"
    if ss and all(x["skip"] == "別作品" for x in ss if x["status"] == "fetched") and any(x["status"] == "fetched" for x in ss):
        return "出たが別作品"
    if not any(x["status"] == "fetched" for x in ss):
        return "取得できない" if ss else "検索に出ない"
    return "見たが薄い"


def cmd_auto(a):
    global QUIET
    QUIET = True
    cmd_open(argparse.Namespace(stem=a.stem, model=a.model.replace("claude-", "") + "(auto)", fresh=a.fresh))
    st = load(a.stem)
    if st.get("done_at"):
        print("済(やり直すなら --fresh)")
        return
    for k in KINDS:
        if k in st["none"]:
            continue
        for s in [x for x in pending(st) if x["kind"] == k]:  # 中断からの再開: 取得済みで未判断の頁を先に片づける
            judge_page(st, s, a.model)
            save(st)
        while len(adopted(st, k)) < WANT[k]:
            ns = sum(1 for q in st["searches"] if q["kind"] == k)
            if ns >= 2 or n_fetch(st, k) >= CAP["fetch"][k] or n_tried(st) >= CAP["fetch_work"]:
                break
            rec = run_search(st, k, qi=ns + 1)
            nums = triage(st, k, rec, a.model)
            save(st)
            print(f"[{k}] 検索{ns + 1}「{rec['q'][:40]}」→ {len(rec['results'])}件 / 開く {nums}")
            for n in nums:
                if len(adopted(st, k)) >= WANT[k] or n_fetch(st, k) >= CAP["fetch"][k] or n_tried(st) >= CAP["fetch_work"]:
                    break
                r = next(x for x in rec["results"] if x["n"] == n)
                before = len(st["sources"])
                do_fetch(st, k, r["url"], "search", ref=f"{rec['id']}:{n}")
                save(st)
                if len(st["sources"]) > before and st["sources"][-1]["status"] == "fetched":
                    s = st["sources"][-1]
                    judge_page(st, s, a.model)
                    save(st)
                    print(f"   出所{L(s['id'])} {s['domain']} → " + (f"採用 {human_chars(st, s['id'])}字" if human_chars(st, s["id"]) else f"不採用={s['skip']}"))
        if not adopted(st, k) and not (k == "wiki" and any(p["auto"] for p in st["picks"])):
            st["none"][k] = auto_none(st, k)
            save(st)
    u = st.get("auto_use") or {}
    print(f"モデル呼び出し {u.get('calls', 0)}回 / 読み込み {u.get('in', 0)}・出力 {u.get('out', 0)} トークン / {u.get('sec', 0)}秒")
    cmd_done(argparse.Namespace(stem=a.stem))


def cmd_status(a):
    if a.stem:
        st = load(a.stem)
        show_card(st["card"])
        show_status(st)
        hint(st)
        return
    if not os.path.exists(LEDGER):
        print("台帳はまだ空")
        return
    with open(LEDGER, encoding="utf-8") as f:
        for ln in f.read().splitlines()[-30:]:
            r = json.loads(ln)
            print(f"{r['at']} {r['version']} {r['model']:<10} {r['chars']:>6}字 {r['stem']} {r['title'][:30]}")


def cmd_probe(a):
    st = load(a.stem)
    kinds = KINDS + ["計"]
    print("語 → 採用した材料に出る回数(種別ごと) / 取得した全文に出る回数")
    for w in [x.strip() for x in a.words.replace("、", ",").split(",") if x.strip()]:
        cnt = {k: 0 for k in kinds}
        for p in st["picks"]:
            n = p["text"].count(w)
            cnt[src(st, p["src"])["kind"]] += n
            cnt["計"] += n
        raw, where = 0, ""
        for s in st["sources"]:
            if s["status"] != "fetched":
                continue
            paras = paras_of(st, s["id"])
            for i, p in enumerate(paras, 1):
                n = p["t"].count(w)
                if n and not where:
                    where = f"初出=出所{L(s['id'])} p{i}"
                raw += n
        print(f"  {w:<10} 採用 {cnt['計']:>2} ({' '.join(f'{k}{cnt[k]}' for k in KINDS)}) / 全文 {raw:>3} {where}")


def main():
    ap = argparse.ArgumentParser(description="要素収集(材料集め)。 正本 = skill element-harvest")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("open"); p.add_argument("stem"); p.add_argument("--model", default="unknown"); p.add_argument("--fresh", action="store_true"); p.set_defaults(f=cmd_open)
    p = sp.add_parser("search"); p.add_argument("stem"); p.add_argument("kind"); p.add_argument("--q"); p.add_argument("--query"); p.set_defaults(f=cmd_search)
    p = sp.add_parser("fetch"); p.add_argument("stem"); p.add_argument("sid"); p.add_argument("nums"); p.set_defaults(f=cmd_fetch)
    p = sp.add_parser("fetch-url"); p.add_argument("stem"); p.add_argument("kind"); p.add_argument("url"); p.set_defaults(f=cmd_fetch_url)
    p = sp.add_parser("show"); p.add_argument("stem"); p.add_argument("src"); p.add_argument("--range"); p.add_argument("--from", dest="frm"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("pick"); p.add_argument("stem"); p.add_argument("src"); p.add_argument("paras"); p.add_argument("--as", dest="as_", required=True); p.add_argument("--same"); p.set_defaults(f=cmd_pick)
    p = sp.add_parser("unpick"); p.add_argument("stem"); p.add_argument("pick"); p.set_defaults(f=cmd_unpick)
    p = sp.add_parser("skip"); p.add_argument("stem"); p.add_argument("src"); p.add_argument("--why", required=True); p.set_defaults(f=cmd_skip)
    p = sp.add_parser("none"); p.add_argument("stem"); p.add_argument("kind"); p.add_argument("--why", required=True); p.set_defaults(f=cmd_none)
    p = sp.add_parser("done"); p.add_argument("stem"); p.set_defaults(f=cmd_done)
    p = sp.add_parser("rebundle"); p.add_argument("stem"); p.set_defaults(f=cmd_rebundle)
    p = sp.add_parser("status"); p.add_argument("stem", nargs="?"); p.set_defaults(f=cmd_status)
    p = sp.add_parser("probe"); p.add_argument("stem"); p.add_argument("words"); p.set_defaults(f=cmd_probe)
    p = sp.add_parser("auto"); p.add_argument("stem"); p.add_argument("--fresh", action="store_true")
    p.add_argument("--model", default=AUTO_MODEL); p.set_defaults(f=cmd_auto)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
