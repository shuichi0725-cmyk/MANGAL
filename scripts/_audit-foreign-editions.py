"""外国語版(scope外=日本出版でない)を ★複数証拠 で検出 → non-manga-drop.yml へ純粋追加。
[[mangal_inclusion_scope]]: 掲載=日本出版漫画(manhwa日本語版含む)。 外国語版書誌はdrop。

★複数証拠(ISBN単独のtypo誤判定を回避):
  ① latin題(漢字・かな無し=日本作でない強signal。 日本作は日本語題)
  ② シリーズの ★**全ISBNが非9784**(978-4=日本。 typoなら全巻一致しない=一貫foreign)
  ③ ★**複数巻**(2巻以上=typo説明不可)→ auto-drop安全
  単巻のみ非9784 = typo懸念 → ★report のみ(auto-dropしない)。

★既存filterの穴(2026-06-04判明): 旧scanは「EMPTYslug + 翻訳credit文字列」依存で、
  クリーンlatin題(Akira/Naruto外国版)を取りこぼした。 ISBN国コードが未使用だった。
  本scriptが恒久的に塞ぐ。 蒸留(intake)の promote 前に走らせる。

使い方: python scripts/_audit-foreign-editions.py [--apply]
  (無印=報告のみ / --apply=safe[複数巻]を non-manga-drop.yml へ純粋追加)
"""
import io
import sys
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
NM = ROOT / "data" / "seeds" / "non-manga-drop.yml"
LATIN = re.compile(r"^[\x00-\x7f｡-ﾟ\s]+$")
HAS_JP = re.compile(r"[ぁ-んァ-ヶ一-龠]")
CC = {"9780": "英米", "9781": "英", "9782": "仏", "9783": "独",
      "9785": "露", "9788": "西/伊/丁", "9789": "北欧/蘭/韓", "9791": "仏"}


def jst():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    apply = "--apply" in sys.argv
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    nt = io.open(NM, encoding="utf-8").read()

    rows = con.execute(
        "SELECT s.series_key, s.title, GROUP_CONCAT(v.isbn13) "
        "FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id "
        "WHERE v.isbn13!='' GROUP BY s.id").fetchall()
    safe, single = [], []
    for key, title, isbn_csv in rows:
        if not title or not LATIN.match(title) or HAS_JP.search(title) or len(title) <= 3:
            continue
        isbns = [i for i in (isbn_csv or "").split(",") if i]
        if not isbns or any(i.startswith("9784") for i in isbns):
            continue                                   # 日本版を1つでも含む=除外(誤dropリスク)
        rec = (key, title, isbns[0], len(isbns))
        (safe if len(isbns) >= 2 else single).append(rec)

    new_safe = [r for r in safe if r[0] not in nt]
    new_single = [r for r in single if r[0] not in nt]
    print(f"[{jst()}] 外国版監査(複数証拠=latin題∧全巻非9784):")
    print(f"  ★safe(複数巻=auto-drop可): 既存除き新規 {len(new_safe)} / 全 {len(safe)}")
    print(f"  単巻のみ(typo懸念=報告のみ): 新規 {len(new_single)} / 全 {len(single)}")
    for r in new_safe[:15]:
        print(f"     「{r[1][:30]}」 {r[3]}巻 {CC.get(r[2][:4], r[2][:4])} {r[2]}")

    if apply and new_safe:
        if not nt.endswith("\n"):
            nt += "\n"
        lines = []
        for key, title, isbn, n in new_safe:
            cc = CC.get(isbn[:4], isbn[:4])
            t = title[:30].replace('"', "")
            lines.append(f'  - series_key: "{key}"\n    reason: foreign_language_edition\n'
                         f'    note: "(蒸留)外国版({cc}・全{n}巻非9784・latin題): {t}"')
        io.open(NM, "w", encoding="utf-8").write(nt + "\n".join(lines) + "\n")
        import yaml
        d = yaml.safe_load(io.open(NM, encoding="utf-8").read())
        print(f"  ✓ --apply: {len(new_safe)}件 追加 / non-manga-drop total {len(d['non_manga'])} (YAML OK)")
    elif apply:
        print("  --apply: 新規safe無し(冪等)")
    else:
        print("  (報告のみ。 --apply で safe を non-manga-drop.yml へ純粋追加)")


if __name__ == "__main__":
    main()
