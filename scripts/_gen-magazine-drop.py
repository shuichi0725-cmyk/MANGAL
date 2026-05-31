"""雑誌/アンソロ誌 drop リスト(data/seeds/magazines-drop.yml)を生成。

MAGAZINE_HIGH(distinct著者≥20)を基に、 明確な誤検出(海外コミック/古典/学習)は
confirmed:false で目視待ちに。 promote は confirmed:true のみ drop。
※種2/種3 不変。 promote 段の表示制御のみ。
"""
import sqlite3, sys, re, unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(".cache/db-v2.sqlite")
OUT = Path("data/seeds/magazines-drop.yml")

# ★誤検出(雑誌でない=keep)= confirmed:false にする
NOT_MAGAZINE = {
    "ソニック・ザ・ヘッジホッグ",          # 海外コミック(Archie Sonic)
    "ロミオ",                          # 古典/別作品の疑い
    "怪談",                            # 特定作品の疑い
    "漫画版世界の歴史",                  # 学習漫画(雑誌でない)
    "誰にも言えない(秘)",               # 不明
    "誰にも言えない",
    "まんがタイムきららカリノ",          # きらら系=要確認
    "ブラック・ジャックALIVE",          # トリビュート=要確認(keepかも)
    "原水爆漫画コレクション",            # 要確認
}


def norm(s):
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龯]", "", unicodedata.normalize("NFKC", s or "").lower())


def main():
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    c = con.cursor()
    sa = defaultdict(set)
    for sid, mid in c.execute("SELECT series_id, mangaka_id FROM series_authors"):
        sa[sid].add(mid)
    sub = {};
    for sid, t, st in c.execute("SELECT id, title, subtitle FROM series"):
        sub[sid] = (t, st)
    vlbl = defaultdict(bool)
    for sid, vl in c.execute("SELECT e.series_id, v.volume_label FROM editions e JOIN volumes v ON v.edition_id=e.id"):
        if vl: vlbl[sid] = True
    con.close()

    bytitle = defaultdict(list)
    for sid, (t, st) in sub.items():
        bytitle[norm(t)].append(sid)

    entries = []
    for nt, sids in bytitle.items():
        if len(sids) < 3:
            continue
        if any(sub[s][1] for s in sids) or any(vlbl[s] for s in sids):
            continue
        authsets = [sa.get(s, set()) for s in sids]
        if any(not a for a in authsets):
            continue
        union = set().union(*authsets); common = set.intersection(*authsets)
        if not (union and len(common) <= len(union) * 0.2 and len(union) >= 20):
            continue
        title = sub[sids[0]][0]
        entries.append((title, len(sids), len(union)))

    import yaml
    entries.sort(key=lambda x: -x[2])
    mags = []
    n_true = n_false = 0
    for title, recs, auth in entries:
        conf = title not in NOT_MAGAZINE
        n_true += conf; n_false += (not conf)
        mags.append({"title": title, "confirmed": conf, "records": recs, "authors": auth})
    header = (
        "# 雑誌/アンソロ誌 drop リスト — 自動生成(_gen-magazine-drop.py)+ 手動確認。\n"
        "# MANGAL は単行本=漫画作品のDB。 雑誌(掲載媒体)・実話/怖い話mook・\n"
        "# トリビュートアンソロは作品でないため drop。 distinct著者≥20 が一次抽出。\n"
        "# ★promote は confirmed:true のみ drop。 false は目視確認待ち(誤検出疑い)。\n"
        "# 種2/種3 不変・表示制御のみ・可逆。\n"
    )
    with OUT.open("w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump({"magazines": mags}, f, allow_unicode=True, sort_keys=False, width=10**9)
    print(f"wrote {OUT}")
    print(f"  総 {len(entries)} 件 / confirmed:true {n_true} / false(要確認) {n_false}")


if __name__ == "__main__":
    main()
