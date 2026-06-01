"""雑誌 drop リスト(cm105 雑誌マスター準拠・権威版)を生成。

★cm105(MADB マンガ雑誌マスター 5,753誌)に題が一致する 種2 series = 雑誌。
  ヒューリスティック(著者disjoint)は西遊記/ラブレター等を誤爆したが、
  cm105 は公式マスターなので誤爆ゼロ。 ただし:
  - ガード: cm105一致でも「単一著者+巻番号」= 実漫画の可能性(ZERO=松本大洋/ARIA=天野こずえ)
    → 除外して保護
  - cm105 が変種名で漏らす確定雑誌(GUSH maniaEX/on BLUE 等)は curated 追加
出力: data/seeds/magazines-drop.yml(series_key 単位。 promote が drop)。 種2/種3 不変。
"""
import json, sys, re, unicodedata, sqlite3
from collections import defaultdict
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding="utf-8")
CM105 = Path(".cache/madb/metadata105.json")
DB = Path(".cache/db-v2.sqlite")
OUT = Path("data/seeds/magazines-drop.yml")

# cm105 が変種名で漏らす確定雑誌(種2 title の正規化で curated 追加)
CURATED_EXTRA = {"gushmaniaex", "onblue", "ごうがいonblue2ndseason", "ルチルsweet"}


def norm(s):
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龯]", "", unicodedata.normalize("NFKC", s or "").lower())


def main():
    g = json.loads(CM105.read_text(encoding="utf-8")).get("@graph", [])
    mag = set()
    for rec in g:
        nm = rec.get("schema:name") or rec.get("rdfs:label")
        titles = [nm] if isinstance(nm, str) else ([x for x in nm if isinstance(x, str)] if isinstance(nm, list) else [])
        for t in titles:
            base = re.split(r"増刊|別冊|共同編集|（|\(", t)[0]
            for x in (t, base):
                n = norm(x)
                if len(n) >= 2:
                    mag.add(n)
    print(f"cm105 雑誌正規化名: {len(mag):,}", file=sys.stderr)

    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    aname = {mid: nm for mid, nm in con.execute("SELECT id, name FROM mangaka")}
    sa = defaultdict(set)
    for sid, mid in con.execute("SELECT series_id, mangaka_id FROM series_authors"):
        sa[sid].add(mid)
    vlbl = defaultdict(bool)
    for sid, vl in con.execute("SELECT e.series_id, v.volume_label FROM editions e JOIN volumes v ON v.edition_id=e.id"):
        if vl:
            vlbl[sid] = True
    rows = con.execute("SELECT id, series_key, title FROM series").fetchall()
    con.close()

    drops = []; protected = 0
    for sid, key, title in rows:
        n = norm(title)
        is_mag = n in mag or n in CURATED_EXTRA
        if not is_mag:
            continue
        na = len(sa.get(sid, set()))
        # ★強ガード: cm105一致でも 著者1-2人 = 実漫画(原作+作画含む)の可能性 → 保護。
        #   drop は 著者0(無著者mook)or 3人以上(明確なアンソロ誌)のみ。 curated は通す。
        if n not in CURATED_EXTRA and 1 <= na <= 2:
            protected += 1
            continue
        drops.append({"series_key": key, "title": title,
                      "source": "cm105-curated" if n in CURATED_EXTRA else "cm105"})

    drops.sort(key=lambda x: x["title"])
    header = (
        "# 雑誌 drop リスト(cm105 雑誌マスター準拠)— 自動生成 _gen-magazine-drop-cm105.py\n"
        "# MANGAL は単行本=作品のDB。 雑誌(mook含む)は cm105(MADBマンガ雑誌マスター)で\n"
        "# 確実に識別して drop。 ★ガード: cm105一致でも単一著者+巻番号=実漫画(ZERO/ARIA等)は保護。\n"
        "# 種2/種3 不変・promote の表示制御のみ・series_key 単位。\n"
    )
    with OUT.open("w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump({"magazines": drops}, f, allow_unicode=True, sort_keys=False, width=10**9)
    print(f"★雑誌drop(series_key): {len(drops):,}  / 実漫画として保護: {protected}")
    print(f"  wrote {OUT}")
    print("\n=== drop サンプル20 ===")
    for d in drops[:20]:
        print(f"  {d['title'][:30]}")


if __name__ == "__main__":
    main()
