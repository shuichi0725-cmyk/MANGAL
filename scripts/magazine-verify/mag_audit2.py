"""連載誌の突合 v2(汎用): Wikipedia 記事の「1行(表なら1行分)」に 題名 と 著者名 が並んで出るかで、
本番の各頁がどの雑誌の掲載作品一覧に載っているかを判定する。 読むだけ(本番に書かない)。

出力: .cache/magazine-lists/membership.json  = {slug: {記事key: [根拠の行(短縮)]}}
"""
import json, re, sys, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / ".cache" / "magazine-lists"

# 記事key → (本番の雑誌key, 記事ファイル)。 本番に雑誌keyが無いものは None(=新設候補)
ARTICLES = {
    "wsj-list": "weekly-shonen-jump",
    "jump-plus": "shonen-jump-plus",
    "jump-sq": "jump-sq",
    "monthly-jump": "monthly-shonen-jump",
    "v-jump": "v-jump",
    "saikyo-jump": "saikyo-jump",
    "wyj": "weekly-young-jump",
    "ultra-jump": "ultra-jump",
    "wsj-zokan": "wsj-zokan",
    "fresh-jump": "fresh-jump",
    "champion-list": "champion",
    "wsm-list": "weekly-shonen-magazine",
    "wss-list": "weekly-shonen-sunday",
}

TRASH = re.compile(r"[\s・･!！?？。、,，.．:：;；\"'“”‘’「」『』()（）\[\]［］〜~\-‐－—―=＝/／★☆♪♡♥❤＋+×&＆]")


def norm(s: str) -> str:
    return TRASH.sub("", unicodedata.normalize("NFKC", s or "").lower())


def clean(s: str) -> str:
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{Display none\|[^{}]*\}\}", "", s)
    s = re.sub(r"\{\{(?:Small|small|nowrap|Nowrap)\|([^{}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{[Rr]uby\|([^|{}]*)\|[^{}]*\}\}", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    # [[A|B]] → 「A B」(記事名と表示の両方を残す)
    s = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\1 \2", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return s


def records(wt: str):
    out = []
    for chunk in re.split(r"\n\|-[^\n]*", wt):
        lines = chunk.split("\n")
        if any(ln.startswith("|") and not ln.startswith("|}") and not ln.startswith("{|") for ln in lines):
            # 表の1行分(セルが複数行にまたがる表も1つにまとめる)。 箇条書きが混ざる時は別に拾う
            out.append(" ".join(ln for ln in lines if ln.startswith("|") or ln.startswith("!")))
            out += [ln for ln in lines if ln.startswith("*") or ln.startswith("#") or ln.startswith(":")]
        else:
            out += [ln for ln in lines if ln.strip()]
    return out


def title_keys(title: str):
    keys = {norm(title)}
    keys.add(norm(re.sub(r"[(（][^)）]*[)）]", "", title)))  # 怪物(けもの)事変 → 怪物事変
    keys.add(norm(re.split(r"[ 　]+[-‐－〜~]", title)[0]))  # 副題を落とした形
    return {k for k in keys if len(k) >= 2}


def load_index():
    d = json.loads((ROOT / "data" / "manga-list-index.json").read_text(encoding="utf-8"))
    f = d["f"]; I = {k: i for i, k in enumerate(f)}
    def names(v):
        return [str(x).split("\t")[0] if not isinstance(x, dict) else x.get("name", "") for x in (v or [])]
    return [{"slug": r[I["slug"]], "title": r[I["title"]], "magazine": r[I["magazine"]] or "", "publisher": r[I["publisher"]] or "",
             "authors": [a for a in names(r[I["authors"]]) + names(r[I["original_authors"]]) if a],
             "year": r[I["year_started"]] or 0, "vols": r[I["max_edition_volumes"]] or 0} for r in d["d"]]


def main():
    idx = load_index()
    recs = {}
    for key in ARTICLES:
        p = D / f"{key}.wikitext"
        if p.exists():
            recs[key] = [(norm(clean(r)), clean(r).strip()) for r in records(p.read_text(encoding="utf-8"))]
    # 題の索引: 記事ごとに norm 文字列を1本につなげて先に部分一致で候補を絞る(速度)
    blob = {k: "\x00".join(n for n, _ in v) for k, v in recs.items()}
    member = defaultdict(dict)
    for r in idx:
        tks = title_keys(r["title"])
        aks = {norm(a) for a in r["authors"] if len(norm(a)) >= 2}
        if not tks or not aks:
            continue
        for k, v in recs.items():
            if not any(t in blob[k] for t in tks):
                continue
            ev = [raw[:160] for n, raw in v if any(t in n for t in tks) and any(a in n for a in aks)]
            if ev:
                member[r["slug"]][k] = ev[:2]
    json.dump(member, open(D / "membership.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("頁数", len(idx), "/ どれかの一覧に題+著者で載る頁", len(member))
    from collections import Counter
    print(Counter(k for m in member.values() for k in m).most_common())


if __name__ == "__main__":
    main()
