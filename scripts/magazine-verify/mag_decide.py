"""連載誌の是正案を作る(読むだけ)。 自動で直せる組 = AUTO、 人が見る組 = REVIEW に分けて TSV に出す。
AUTO の条件(全部満たす時だけ):
  - 今の連載誌の掲載作品一覧に載っていない(=矛盾) か、 連載誌が空でジャンプ+の一覧に載る
  - 題+著者で載っている一覧がちょうど1誌
  - その行の開始年と頁の開始年が合う(頁の年が 開始年-1 〜 開始年+3。 行に年が無い一覧は年を見ない)
  - 行に移籍・並行連載の注記(← / 『SQ』 『最強』 等)が無い
"""
import json, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mag_audit2 as M

ROOT = M.ROOT
D = M.D
TARGET = {"wsj-list": "weekly-shonen-jump", "jump-plus": "shonen-jump-plus", "jump-sq": "jump-sq",
          "monthly-jump": "monthly-shonen-jump", "saikyo-jump": "saikyo-jump", "v-jump": "v-jump",
          "fresh-jump": "fresh-jump", "wsm-list": "weekly-shonen-magazine", "wss-list": "weekly-shonen-sunday",
          "champion-list": "champion"}
MANUAL_ARTS = {"wyj", "ultra-jump", "wsj-zokan"}   # 記事の中に別媒体(Web版・増刊)の表が混ざる = 人が見る
CHECKED = {"weekly-shonen-jump", "weekly-shonen-magazine", "weekly-shonen-sunday", "weekly-young-jump", "ultra-jump", "champion"}
MOVE_NOTE = re.compile(r"←|→|『(?:SQ|最強|VJ|GJ|YJ|WJ|LIVE|SQ\.19|ジャンプ|週刊|月刊|少年)[^』]*』|並行連載|移籍|より移|から移|スピンオフ|漫画化|外伝|番外編")
YEAR = re.compile(r"(19[5-9]\d|20[0-3]\d)(?=[.年/\-])")


def full_records():
    recs = {}
    for key in M.ARTICLES:
        p = D / f"{key}.wikitext"
        if p.exists():
            recs[key] = [(M.norm(M.clean(r)), M.clean(r).strip()) for r in M.records(p.read_text(encoding="utf-8"))]
    return recs


import yaml
MAG_PUB = {k: (v or {}).get("publisher", "") for k, v in yaml.safe_load(open(ROOT / "data" / "magazines.yml", encoding="utf-8")).items()}
MAG_PUB.update({"shonen-jump-plus": "shueisha", "jump-sq": "shueisha", "monthly-shonen-jump": "shueisha",
                "saikyo-jump": "shueisha", "v-jump": "shueisha", "fresh-jump": "shueisha"})


def main():
    idx = M.load_index()
    recs = full_records()
    blob = {k: "\x00".join(n for n, _ in v) for k, v in recs.items()}
    auto, review = [], []
    for r in idx:
        cur = r["magazine"]
        if cur and cur not in CHECKED:
            consider_other = True
        else:
            consider_other = False
        tks = M.title_keys(r["title"]); aks = {M.norm(a) for a in r["authors"] if len(M.norm(a)) >= 2}
        if not tks or not aks:
            continue
        hits = {}
        for k, v in recs.items():
            if not any(t in blob[k] for t in tks):
                continue
            ev = [raw for n, raw in v if any(t in n for t in tks) and any(a in n for a in aks)]
            if ev:
                hits[k] = ev
        if not hits:
            continue
        cur_art = next((k for k, m in TARGET.items() if m == cur), None)
        if cur == "weekly-young-jump":
            cur_art = "wyj"
        if cur == "ultra-jump":
            cur_art = "ultra-jump"
        if cur_art and cur_art in hits:
            continue                                   # 今の雑誌の一覧に載っている = そのまま
        if not cur and set(hits) != {"jump-plus"}:
            continue                                   # 空欄はジャンプ+だけ埋める(今回の範囲)
        if consider_other and "jump-plus" not in hits:
            continue                                   # 一覧の無い雑誌の頁は ジャンプ+ に当たる時だけ見る
        arts = sorted(hits)
        row = {"slug": r["slug"], "title": r["title"], "cur": cur or "(空)", "pub": r["publisher"], "authors": "・".join(r["authors"]),
               "year": r["year"], "vols": r["vols"], "arts": arts,
               "ev": " ‖ ".join(f"{k}: {hits[k][0][:150]}" for k in arts)}
        reason = []
        if len(arts) != 1:
            reason.append("複数誌")
        a = arts[0]
        if a in MANUAL_ARTS or a not in TARGET:
            reason.append(f"要確認の記事({a})")
        line = hits[a][0]
        ys = [int(y) for y in YEAR.findall(line)]
        if ys and r["year"]:
            y0 = min(ys)
            if not (y0 - 1 <= r["year"] <= y0 + 3):
                reason.append(f"年が合わない(頁{r['year']}/一覧{y0})")
        if MOVE_NOTE.search(line.split(r["title"][:2])[-1] if r["title"][:2] in line else line):
            reason.append("移籍/並行/派生の注記")
        if consider_other:
            reason.append(f"一覧の無い雑誌({cur})")
        # ★出版社の一致(2026-11-04): 雑誌の出版社と頁の出版社が違えば人が見る(他社の同名作・再録版の取り違え)
        to_pub = MAG_PUB.get(TARGET.get(a, ""), "")
        if to_pub and r["publisher"] and r["publisher"] != to_pub:
            reason.append(f"出版社が違う(頁{r['publisher']}/雑誌{to_pub})")
        row["to"] = TARGET.get(a, "")
        row["reason"] = " / ".join(reason)
        (review if reason else auto).append(row)
    cols = ["slug", "title", "cur", "to", "pub", "authors", "year", "vols", "reason", "ev"]
    for name, rows in (("auto", auto), ("review", review)):
        with open(D / f"decide-{name}.tsv", "w", encoding="utf-8") as f:
            f.write("\t".join(cols) + "\n")
            for x in sorted(rows, key=lambda x: (x["cur"], x.get("to", ""), x["slug"])):
                f.write("\t".join(str(x.get(c, "")).replace("\t", " ").replace("\n", " ") for c in cols) + "\n")
    print("AUTO", len(auto), Counter((x["cur"], x["to"]) for x in auto).most_common())
    print("REVIEW", len(review), Counter(x["cur"] for x in review).most_common())


if __name__ == "__main__":
    main()
