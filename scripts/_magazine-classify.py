"""雑誌候補の一次仕分け = 同名衝突群を 雑誌/アンソロ/別作品/古典 に分類。

★判別軸: 雑誌・アンソロジーは「各レコードが複数著者の号(高 turnover)」。
  別作品(ラブレター×13)・古典翻案(西遊記)は「各レコード単独著者」。
  avg authors/record と turnover で分離。 既存 ANTHOLOGY drop 該当も判定。
出力: .cache/magazine-candidates.tsv(レビュー用)。 ※自動 drop はしない。
"""
import sqlite3, sys, re, unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(".cache/db-v2.sqlite")

# 既存 promote の抜粋本/アンソロ drop 語(=既に drop されるもの)
ALREADY_DROP = re.compile(r"アンソロジー|セレクション|傑作選|傑作集|総集編|名作集|名作選|"
                          r"ほんとにあった|本当にあった|現代コミック|怪談|傑作|ベスト|オムニバス|"
                          r"日本の歴史|公式|ガイド|ファンブック|画集|大全|大百科")
# 雑誌っぽい語(参考シグナル)
MAG_WORD = re.compile(r"GUSH|mania|on\s?BLUE|Canna|Comic|コミック誌|月刊|週刊|隔月|季刊|増刊|別冊|"
                      r"MAGAZINE|マガジン|EX$|DX|スペシャル|SP$", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龯]", "", unicodedata.normalize("NFKC", s or "").lower())


def main():
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    c = con.cursor()
    aname = {mid: nm for mid, nm in c.execute("SELECT id, name FROM mangaka")}
    sa = defaultdict(set)
    for sid, mid, role in c.execute("SELECT series_id, mangaka_id, role FROM series_authors"):
        sa[sid].add(mid)
    sub = {}; ystart = {}
    for sid, t, st, ys in c.execute("SELECT id, title, subtitle, year_started FROM series"):
        sub[sid] = (t, st, ys)
    vlbl = defaultdict(bool); years = defaultdict(list)
    for sid, vl, rd in c.execute("SELECT e.series_id, v.volume_label, v.release_date FROM editions e JOIN volumes v ON v.edition_id=e.id"):
        if vl: vlbl[sid] = True
        if rd and len(rd) >= 4 and rd[:4].isdigit(): years[sid].append(int(rd[:4]))
    con.close()

    bytitle = defaultdict(list)
    for sid, (t, st, ys) in sub.items():
        bytitle[norm(t)].append(sid)

    cands = []
    for nt, sids in bytitle.items():
        if len(sids) < 3:
            continue
        if any(sub[s][1] for s in sids) or any(vlbl[s] for s in sids):
            continue   # subtitle/巻番 有 → 雑誌でない(別処理)
        authsets = [sa.get(s, set()) for s in sids]
        if any(not a for a in authsets):
            continue
        union = set().union(*authsets); common = set.intersection(*authsets)
        if not (union and len(common) <= len(union) * 0.2 and len(union) >= 4):
            continue
        title = sub[sids[0]][0]
        avg_auth = sum(len(a) for a in authsets) / len(sids)
        allyears = sorted(y for s in sids for y in years.get(s, []))
        span = (allyears[-1] - allyears[0]) if allyears else 0
        # 分類: ★distinct著者≥20 = 真のアンソロ誌(古典翻案は最大~15)。 高信頼。
        if len(union) >= 20:
            cat = "MAGAZINE_HIGH"              # ★高信頼=雑誌/アンソロ誌(自動drop候補)
        elif ALREADY_DROP.search(title):
            cat = "anthology_dropped"          # 既存ルールで drop 済
        elif avg_auth >= 1.6:
            cat = "review_small"               # 小規模・要目視(BL誌等 vs 古典/foreign)
        else:
            cat = "different_works"            # 単独著者=別作品/古典(keep)
        cands.append((cat, title, len(sids), round(avg_auth, 1), len(union), span,
                      bool(MAG_WORD.search(title))))

    order = {"MAGAZINE_HIGH": 0, "review_small": 1, "anthology_dropped": 2, "different_works": 3}
    cands.sort(key=lambda x: (order[x[0]], -x[4]))
    from collections import Counter
    cnt = Counter(x[0] for x in cands)
    print(f"候補群: {len(cands)}")
    for k in ("MAGAZINE_HIGH", "review_small", "anthology_dropped", "different_works"):
        print(f"  {k}: {cnt[k]}")
    with open(".cache/magazine-candidates.tsv", "w", encoding="utf-8") as f:
        f.write("category\ttitle\trecords\tavg_authors\tdistinct_authors\tyear_span\tmag_word\n")
        for cat, t, n, av, u, sp, mw in cands:
            f.write(f"{cat}\t{t}\t{n}\t{av}\t{u}\t{sp}\t{mw}\n")
    print("wrote .cache/magazine-candidates.tsv")
    print("\n=== ★MAGAZINE_HIGH(distinct著者≥20=高信頼drop)全件 ===")
    for cat, t, n, av, u, sp, mw in cands:
        if cat == "MAGAZINE_HIGH":
            print(f"  [{n}記録 著者{u}] {t[:40]}")


if __name__ == "__main__":
    main()
