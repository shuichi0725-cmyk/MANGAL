"""衝突(同名)群を「真の別作品」vs「merge失敗(分裂)」に三分類する包括監査。

はたらく魔王さま例: 同一作品が 作画029(qidなし)/ qid断片(著者なし)/ 原作名義 に
分裂 = クラスタキー非交差で非merge。 これを全衝突群で検出。

同一(正規化)title の群について、 各 member の (qid有無/著者/巻数/年) を見て:
  - frag_strong = qid-only断片(qid有・著者name無・小巻)と 著者断片 が混在(=同作分裂濃厚)
  - frag_maybe  = 同title で qid/著者パターン混在 or 小巻stub併存
  - diff_likely = 複数が独立して substantial(別著者・各5巻+)= 真の別作品候補
出力 .cache/frag-audit.tsv + 集計。 ※調査のみ、 変更なし。
"""
import sqlite3, sys, re, csv
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(".cache/db-v2.sqlite")


def norm_title(t):
    return re.sub(r"[\s　・！!？?、。「」『』〜~ー\-—–:：/／.,＆&]+", "", (t or "")).lower()


def parse_key(sk):
    qids = [p[4:] for p in sk.split("|") if p.startswith("qid:")]
    names = [p[5:] for p in sk.split("|") if p.startswith("name:")]
    author = names[0] if len(names) >= 2 else ""
    return (qids[0] if qids else ""), author


def main():
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    rows = con.execute("""SELECT s.series_key, s.title, s.subtitle, s.qid, s.adult_score,
        COUNT(v.id), MIN(substr(v.release_date,1,4))
        FROM series s LEFT JOIN editions e ON e.series_id=s.id
        LEFT JOIN volumes v ON v.edition_id=e.id GROUP BY s.id""").fetchall()
    con.close()

    groups = defaultdict(list)
    for sk, title, subt, qid, adult, vols, fy in rows:
        # サブタイトル無し(本編)同士の衝突に注目。 subt 有は別アーク/版なので除外集計
        if subt:
            continue
        groups[norm_title(title)].append({
            "key": sk, "title": title, "qid": qid or "",
            "author": parse_key(sk)[1], "vols": vols or 0,
            "year": fy or "", "adult": adult})

    cat = {"frag_strong": [], "frag_maybe": [], "diff_likely": [], "edition_dup": []}
    for nt, ms in groups.items():
        if len(ms) < 2:
            continue
        n_qid_stub = sum(1 for m in ms if m["qid"] and not m["author"] and m["vols"] <= 3)
        n_author = sum(1 for m in ms if m["author"])
        n_subst = sum(1 for m in ms if m["vols"] >= 5)
        authors = {m["author"] for m in ms if m["author"]}
        big = max(m["vols"] for m in ms)
        small_stubs = sum(1 for m in ms if m["vols"] <= 2)
        if n_qid_stub >= 1 and n_author >= 1:
            cat["frag_strong"].append((nt, ms))
        elif n_subst >= 2 and len(authors) >= 2:
            cat["diff_likely"].append((nt, ms))
        elif big >= 5 and small_stubs >= 1:
            cat["frag_maybe"].append((nt, ms))
        else:
            cat["edition_dup"].append((nt, ms))

    tot_groups = sum(len(v) for v in cat.values())
    print(f"=== サブ無し同名衝突群: {tot_groups:,} ===")
    for k in ("frag_strong", "frag_maybe", "diff_likely", "edition_dup"):
        g = cat[k]
        ent = sum(len(ms) for _, ms in g)
        print(f"  {k:<12}: {len(g):,} 群 / {ent:,} entry")
    frag_ent = sum(len(ms) for _, ms in cat["frag_strong"] + cat["frag_maybe"])
    print(f"\n★merge失敗濃厚(strong+maybe): {frag_ent:,} entry が統合されるべき重複")

    with open(".cache/frag-audit.tsv", "w", encoding="utf-8") as f:
        f.write("category\ttitle\tmembers\tdetail\n")
        for k in ("frag_strong", "frag_maybe", "diff_likely", "edition_dup"):
            for nt, ms in cat[k]:
                det = " || ".join(f"{m['title'][:14]}[{'qid' if m['qid'] else '著'+m['author'][:6]}|v{m['vols']}|{m['year']}]" for m in ms)
                f.write(f"{k}\t{ms[0]['title']}\t{len(ms)}\t{det}\n")
    print("wrote .cache/frag-audit.tsv")

    print("\n=== frag_strong サンプル12(同作分裂濃厚)===")
    for nt, ms in cat["frag_strong"][:12]:
        det = " | ".join(f"{'qid:'+m['qid'][:9] if m['qid'] else '著:'+m['author'][:8]}(v{m['vols']},{m['year']})" for m in ms)
        print(f"  {ms[0]['title'][:24]:<24} {det}")
    print("\n=== diff_likely サンプル8(真の別作品候補)===")
    for nt, ms in cat["diff_likely"][:8]:
        det = " | ".join(f"{m['author'][:8]}(v{m['vols']},{m['year']})" for m in ms)
        print(f"  {ms[0]['title'][:24]:<24} {det}")


if __name__ == "__main__":
    main()
