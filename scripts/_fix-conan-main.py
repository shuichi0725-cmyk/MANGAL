"""[修正・ログ付] 名探偵コナン本編の誤クラスタ是正(検証済の先行1件)。
症状: 本編(青山剛昌・全108巻)が従版slug meitantei-conan-2011 に入り、著者=太田勝(映画作画家)、無印slug消失。
修正:
  1. slug: meitantei-conan-2011 → meitantei-conan(無印=主版に復帰)
  2. 著者: authors=[青山剛昌(writer_artist)] / original_authors=[](本編は単独著)
  3. alias: meitantei-conan-2011 → meitantei-conan(旧URL 301)
  4. slug-overrides seed と change-log に来歴記録(detected_by, source, checks, undo)
適用層: data/manga(source) / data/manga.v2(出力) / .preview-data(テスト)
※非破壊・可逆(change-logのundoで元slug/著者に戻せる)。
"""
import os, json, yaml, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = "."
OLD, NEW = "meitantei-conan-2011", "meitantei-conan"
NOW = "2026-06-16"  # JST想定(Date不可のため固定)

LOG = "data/seeds/_change-log.jsonl"
OVR = "data/seeds/slug-overrides.yml"
ALI = "data/slug-aliases.yml"

changed_layers = []
for base in ("data/manga", "data/manga.v2", ".preview-data/manga"):
    old_p = os.path.join(base, OLD + ".yml")
    new_p = os.path.join(base, NEW + ".yml")
    if not os.path.exists(old_p):
        print(f"  skip(無): {old_p}")
        continue
    d = yaml.safe_load(open(old_p, encoding="utf-8")) or {}
    before_author = [a.get("name") for a in d.get("authors", [])]
    d["slug"] = NEW
    d["authors"] = [{"name": "青山剛昌", "role": "writer_artist", "kana": "アオヤマゴウショウ", "romaji": "aoyama goushou"}]
    d["original_authors"] = []
    with open(new_p, "w", encoding="utf-8") as w:
        yaml.safe_dump(d, w, allow_unicode=True, sort_keys=False, width=10000)
    if os.path.abspath(old_p) != os.path.abspath(new_p):
        os.remove(old_p)
    changed_layers.append(base)
    print(f"  fixed: {base}  slug {OLD}->{NEW} / author {before_author}->['青山剛昌']")

# alias 追記(純粋追加)
ali = {}
if os.path.exists(ALI):
    ali = yaml.safe_load(open(ALI, encoding="utf-8")) or {}
if ali.get(OLD) != NEW:
    ali[OLD] = NEW
    with open(ALI, "w", encoding="utf-8") as w:
        yaml.safe_dump(ali, w, allow_unicode=True, sort_keys=True, width=10000)
    print(f"  alias追加: {OLD} -> {NEW}")

# slug-overrides seed(恒久指示・promoteが将来読む用)
ovr = {}
if os.path.exists(OVR):
    ovr = yaml.safe_load(open(OVR, encoding="utf-8")) or {}
ovr.setdefault("overrides", {})
ovr["overrides"][OLD] = {"slug": NEW, "reason": "本編が従版slugに誤収容・無印復帰", "at": NOW}
with open(OVR, "w", encoding="utf-8") as w:
    yaml.safe_dump(ovr, w, allow_unicode=True, sort_keys=False, width=10000)
print(f"  slug-override記録: {OLD} -> {NEW}")

# change-log(追記専用JSONL・来歴)
entry = {
    "ts": NOW, "action": "slug_rename+author_fix", "target": NEW,
    "detected_by": "manual.user+slug-final-audit", "source": "slug-final-integrated.tsv / 表紙vision(青山剛昌)",
    "before": {"slug": OLD, "authors": ["太田勝"], "original_authors": ["青山剛昌", "窪田一裕"]},
    "after": {"slug": NEW, "authors": ["青山剛昌"], "original_authors": []},
    "checks": ["表紙4巻すべて青山剛昌表記", "qid:Q313945主版提案", "全108巻1994開始(本編)", "フィルムコミック混入なし"],
    "confidence": "high",
    "evidence": {"work_qid": "Q3853685", "anilist_id": 31061, "vols": 107, "missing_vol": 106},
    "undo": "slug-overrides.yml の該当行削除 + alias削除 + authorsを[太田勝]に戻す + ファイル名を-2011へ",
    "state": "applied", "layers": changed_layers,
    "note": "太田勝=映画フィルムコミック作画家の著者汚染。本編は青山剛昌単独。-2011は太田勝断片(2巻/2011)の年suffix痕跡。106巻欠けは別途種4補完候補。",
}
os.makedirs("data/seeds", exist_ok=True)
with open(LOG, "a", encoding="utf-8") as w:
    w.write(json.dumps(entry, ensure_ascii=False) + "\n")
print(f"  change-log追記: {LOG}")
print("done.")
