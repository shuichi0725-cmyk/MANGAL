"""生MADB役割タグ → 著者補正seed(全series)。 種2不変overlay。 promoteが series_key→sid 解決で適用。
分類: artist/著(→authors) / original(→original_authors) / credit(→drop) / 未知(→既定author)。
  drop     = その作品で全タグが credit のみ の現著者(編/監修/訳/装丁/協力/企画bare/発売...)
  original = その作品で original のみ(=原作/原案/脚本/構成/キャラクター原案...)→ role=original_author
  add      = drop後に実在人物著者0 の救済(マスター実在・非entity・変種重複除外)
  ★ガード: drop後に実在著者もaddも無いなら drop撤回(現状維持)
"""
import os
import sqlite3, json, sys, re, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
db = sqlite3.connect(ROOT + "/.cache/db-v2.sqlite"); c = db.cursor()
roles = json.load(open(ROOT + "/.cache/madb-mid-roles.json", encoding="utf-8"))

ARTIST = {"著", "著者", "漫画", "まんが", "マンガ", "萬画", "劇画", "作画", "画", "絵", "え", "作", "さく",
          "画作", "コミック", "comic", "comics", "COMIC", "Comic", "コミカライズ", "イラスト",
          "illustration", "Illustration", "ILLUSTRATION", "art", "アート", "アーティスト"}
STORY = {"原作", "原案", "シナリオ", "脚本", "脚色", "構成", "ストーリー", "story", "STORY", "翻案",
         "ネーム", "原著", "原作者", "案", "文", "ライター", "戯作", "述", "設定",
         "キャラクター原案", "キャラクター原作"}
CREDIT = {"編", "編集", "編纂", "責任編集", "共同編集", "編著", "監修", "監訳", "翻訳", "訳", "装丁", "装幀",
          "装呟", "デザイン", "ブックデザイン", "カバーデザイン", "カバー", "カバーイラスト", "表紙", "本文",
          "ロゴ", "レイアウト", "写真", "カラー", "彩色", "取材", "協力", "企画", "制作", "製作", "校訂",
          "監督", "総監督", "演出", "プロデュース", "アートディレクション", "テクニカルアドバイザー",
          "アドバイザー", "指導", "メカニックデザイン", "キャラクターデザイン", "解説", "エッセイ", "語り",
          "選", "コンテ", "医療監修", "料理監修", "将棋監修", "発売", "頒布"}

def cls_part(p):
    p = p.strip()
    if not p:
        return None
    if p in ARTIST:
        return "artist"
    if p in STORY:
        return "story"
    if p in CREDIT:
        return "credit"
    for k, r in [("監修", "credit"), ("協力", "credit"), ("デザイン", "credit"), ("編集", "credit"),
                 ("監督", "credit"), ("イラスト", "artist"), ("作画", "artist"), ("漫画", "artist"),
                 ("原案", "story"), ("原作", "story"), ("構成", "story"), ("脚本", "story")]:
        if p.endswith(k):
            return r
    return None

def classify(tag):
    if tag == "":
        return "author"
    rs = set(filter(None, (cls_part(p) for p in re.split(r"[・/／、,＆&\+（）()\s　]+", tag))))
    if "artist" in rs:
        return "author"
    if "story" in rs:
        return "original"
    if "credit" in rs:
        return "credit"
    return "author"  # 未知 → 既定 author

def norm(s):
    return re.sub(r"[・･\s　,，.\-‐―]", "", s).lower()

ROLE_LABEL = [
    (("編集", "編纂", "責任編集", "共同編集", "編著", "編"), "編集"),
    (("監修", "監督", "総監督", "演出", "指導", "アドバイザー"), "監修"),
    (("翻訳", "監訳", "共訳", "訳"), "翻訳"),
    (("装丁", "装幀", "装呟", "カバー", "ブックデザイン", "デザイン", "ロゴ", "レイアウト", "本文", "表紙", "DTP"), "装丁・デザイン"),
    (("解説", "エッセイ", "語り", "述"), "解説"),
    (("企画",), "企画"),
    (("協力", "取材", "原案協力", "設定協力", "アシスタント"), "協力"),
    (("写真", "彩色", "カラー"), "写真・彩色"),
    (("制作", "製作", "プロデュース"), "制作"),
]

def display_role(tags):
    """credit名の生タグ集合 → 表示役割ラベル。"""
    joined = " ".join(tags)
    for parts, label in ROLE_LABEL:
        if any(p in joined for p in parts):
            return label
    return next((t for t in tags if t), "その他")

ENTITY = re.compile(r"企画|プロ$|プロダクション|スタジオ|製作委員会|委員会|編集部|ルーム|新企画社|開発室"
                    r"|プロジェクト|PROJECT|社$|室$|出版部|出版局|出版社|編集局|刊行会|刊行委員会"
                    r"|基金|財団|協会|学会|研究所|研究会|事務局|連盟|機構|センター|資料館|博物館"
                    r"|新聞社|放送局|出版$|書籍部|事業部|制作部|製作部")

master = {}
master_norm = {}
for name, qid in c.execute("SELECT name, qid FROM mangaka"):
    master[name] = qid
    master_norm.setdefault(norm(name), name)

def resolve(nm):
    if nm in master:
        return nm
    return master_norm.get(norm(nm))

# series_id -> volume madb_book_ids
ser_mids = collections.defaultdict(list)
for mid, sid in c.execute("SELECT v.madb_book_id, e.series_id FROM volumes v "
                          "JOIN editions e ON v.edition_id=e.id WHERE v.madb_book_id IS NOT NULL"):
    ser_mids[sid].append(mid)

entries = []
st = collections.Counter()
for sid, mids in ser_mids.items():
    info = c.execute("SELECT series_key FROM series WHERE id=?", (sid,)).fetchone()
    if not info:
        continue
    skey = info[0]
    madb = [r[0] for r in c.execute(
        "SELECT m.name FROM series_authors sa JOIN mangaka m ON sa.mangaka_id=m.id WHERE sa.series_id=?", (sid,)).fetchall()]
    if not madb:
        continue
    name_cls = collections.defaultdict(set)
    name_tags = collections.defaultdict(set)
    name_raw = {}
    for mid in mids:
        for nm, tag, _ in roles.get(mid, []):
            k = norm(nm)
            name_cls[k].add(classify(tag))
            name_tags[k].add(tag)
            name_raw.setdefault(k, nm)
    if not name_cls:
        continue
    drop, orig = [], []
    for m in madb:
        cs = name_cls.get(norm(m))
        if not cs:
            continue
        if "author" in cs:
            continue                      # 作画/著 → authors のまま
        if "original" in cs:
            orig.append(m)                # 原作系(credit兼ねても原作優先)
        elif cs == {"credit"}:
            drop.append(m)
    # ★original-empty ガード: 原作化で authors(作画者)が0になるなら routing しない
    #   (= 単独creatorは原作タグでも実質著者。 機動戦士ガンダム→富野 型)
    artist_kept = [m for m in madb if m not in drop and m not in orig]
    if not artist_kept:
        orig = []
    keep_real = [m for m in madb if m not in drop and not ENTITY.search(m)]
    # 救済(drop後に実在人物著者0)
    add = []
    if not keep_real:
        def vnorm(s):
            return re.sub(r"(プロダクション|プロジェクト|プロ)$", "", norm(s))
        seen = {vnorm(m) for m in madb if m not in drop}
        madb_norm = {norm(m) for m in madb}
        for k, cs in name_cls.items():
            if ("author" in cs) and k not in madb_norm:
                canon = resolve(name_raw[k])
                if canon and canon not in add and canon not in madb and not ENTITY.search(canon) and vnorm(canon) not in seen:
                    add.append(canon); seen.add(vnorm(canon))
    # ガード
    if not keep_real and not add and drop:
        st["guard"] += 1
        drop = []
    # credits = dropした非著者を役割付きで保持(著者欄から除外+表示用)
    credits = [{"name": m, "role": display_role(name_tags[norm(m)])} for m in drop]
    if not (credits or orig or add):
        continue
    e = {"series_key": skey}
    if credits:
        e["credits"] = credits; st["drop_series"] += 1; st["drops"] += len(credits)
    if orig:
        e["original"] = orig; st["orig_series"] += 1; st["origs"] += len(orig)
    if add:
        e["add"] = add; st["add_series"] += 1; st["adds"] += len(add)
    entries.append(e)

OUT = ROOT + "/data/seeds/author-role-corrections.yml"
with open(OUT, "w", encoding="utf-8") as f:
    f.write("schema_version: 2\n")
    f.write("generator: _gen-author-role-corrections.py 生MADB役割タグ分類 全series\n")
    f.write("note: 種2不変overlay。 credits=非著者role(著者欄除外+表示用) / original=原作系をoriginal_authorsへ / add=救済著者\n")
    f.write("corrections:\n")
    for e in entries:
        f.write("  - series_key: %s\n" % json.dumps(e["series_key"], ensure_ascii=False))
        if "credits" in e:
            f.write("    credits: [%s]\n" % ", ".join(json.dumps(cc, ensure_ascii=False) for cc in e["credits"]))
        for fld in ("original", "add"):
            if fld in e:
                f.write("    %s: [%s]\n" % (fld, ", ".join(json.dumps(x, ensure_ascii=False) for x in e[fld])))
print("補正entry:", len(entries), dict(st))
print("出力:", OUT)
