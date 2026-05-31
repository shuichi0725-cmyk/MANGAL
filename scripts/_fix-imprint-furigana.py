"""#2b imprint furigana バグ修正案生成 = display 題からフリガナ再生成。

対象 = title_kana がレーベル名(Daito comics 等)で、 display が実題の 152 件。
display を kakasi で読み(カタカナ)化 → title_kana(連結)/ title_kana_segmented
(トークン space 区切り)を再生成。 ★種3 上書き= deliberate fix なので、
まず .cache/imprint-furigana-fix.tsv に出力(レビュー)→ --apply で surgical 置換。
"""
import pickle, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi
_kks = pykakasi.kakasi()
PKL = Path(".cache/seed3-promote.pkl")

# kana 側のレーベル signal
IMP = re.compile(r"シリーズ$|コミックス|comics|セレクション|selection|アンソロジー|レーベル|デジタルコミック|ベストセレクション|公式アンソロ", re.I)
# display 側にレーベル/抜粋本語があれば= title自体がそれ = 対象外(正当 or drop見込)
TITLE_IMPRINT = re.compile(r"シリーズ|コミックス|comics|セレクション|selection|アンソロジー|anthology|レーベル|傑作選|傑作集|総集編|公式|ガイド|ファンブック|画集|原画集|大全|大百科|official", re.I)


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def regen_furigana(title):
    """display 題 → (連結カナ, 分かち書きカナ)。 kakasi トークンで segment。"""
    items = _kks.convert(title)
    toks = []
    for it in items:
        kana = it.get("kana") or ""
        # 記号のみ token は捨てる
        if re.search(r"[ぁ-ヿ一-鿿A-Za-z0-9]", it.get("orig", "")):
            if kana:
                toks.append(kana)
    seg = " ".join(toks)
    joined = "".join(toks)
    return joined, seg


def main():
    d = pickle.load(PKL.open("rb"))
    fixes = []
    for e in d.values():
        kana = e.get("title_kana") or ""
        if not IMP.search(kana):
            continue
        t = base_title(e["key"])
        if TITLE_IMPRINT.search(t):
            continue   # title 自体にレーベル/抜粋本語 = 正当 or drop見込 = 対象外
        joined, seg = regen_furigana(t)
        # 真のバグ = 再生成読みが旧kana(レーベル)と実質的に異なる
        if joined and re.sub(r"\W", "", joined) != re.sub(r"\W", "", kana):
            fixes.append((e["key"], t, kana, joined, seg))

    with open(".cache/imprint-furigana-fix.tsv", "w", encoding="utf-8") as f:
        f.write("key\ttitle\told_kana\tnew_kana\tnew_seg\n")
        for k, t, ok, nk, ns in fixes:
            f.write(f"{k}\t{t}\t{ok}\t{nk}\t{ns}\n")
    print(f"修正対象: {len(fixes)} 件 → .cache/imprint-furigana-fix.tsv")
    print("\n=== サンプル20(display / 旧kana=レーベル / 新kana)===")
    for k, t, ok, nk, ns in fixes[:20]:
        print(f"  {t[:24]:<24} 旧[{ok[:18]}] → 新[{nk[:26]}]")

    if "--apply" in sys.argv or "--new" in sys.argv:
        apply_fixes(fixes, commit="--apply" in sys.argv)


def yaml_scalar(v):
    import yaml
    line = yaml.safe_dump({"_": v}, allow_unicode=True, default_flow_style=False, width=10**9)
    return line.split(":", 1)[1].strip()


def apply_fixes(fixes, commit):
    YML = Path("data/seeds/series-supplement-v2.yml")
    fixmap = {f[0]: (f[3], f[4]) for f in fixes}
    lines = YML.read_text(encoding="utf-8").splitlines(keepends=True)
    KEY = re.compile(r"^  - key: (.*)$")
    out = []; cur = None; applied = 0
    for line in lines:
        m = KEY.match(line)
        if m:
            cur = m.group(1).rstrip("\n")
            if len(cur) >= 2 and cur[0] in "\"'" and cur[-1] == cur[0]:
                inner = cur[1:-1]
                cur = inner.replace('\\"', '"') if cur[0] == '"' else inner
            out.append(line); continue
        if cur in fixmap:
            nk, ns = fixmap[cur]
            sm = re.match(r"^(\s+)title_kana:\s", line)
            if sm:
                out.append(f"{sm.group(1)}title_kana: {yaml_scalar(nk)}\n"); applied += 1; continue
            sm = re.match(r"^(\s+)title_kana_segmented:\s", line)
            if sm:
                out.append(f"{sm.group(1)}title_kana_segmented: {yaml_scalar(ns)}\n"); continue
        out.append(line)
    dest = YML if commit else YML.with_suffix(".yml.new")
    dest.write_text("".join(out), encoding="utf-8")
    print(f"applied title_kana 置換: {applied} / 対象 {len(fixmap)} → {dest.name}")


if __name__ == "__main__":
    main()
