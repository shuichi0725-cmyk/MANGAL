"""語彙外の語の裁定(data/element-harvest/new-words-proposal.tsv の「案」)を語彙へ書く。 2026-10-28 ユーザ「裁定は終わりにする」
(裁定ページで変えた語は0 = 全部 案どおり)。

  出す → 和名は wamei-tags.yml allow / JA_DRAFT の訳語なら英名も tag-i18n.yml に
  訳   → tag-i18n.yml に 英名: {ja: 案の語}
  寄せる → 英名は tag-i18n.yml(ja=寄せ先)/ 和名は wamei-tags.yml alias
  隠す → rulings.yml word_rulings に hide_common(表に出さず隠して持つ)。 英名は訳を足さない(サイトの表示にも出ないまま)
  外す → 和名は wamei-tags.yml exclude(allow に在れば抜く)。 英名は何もしない(訳が無い = 出ない)
★tag-i18n / wamei-tags はサイトの表示全体に効く(見直しの外の頁にも)。 書く前に3つを退避。

  python scripts/_apply-new-words-ruling.py [--go "<発話>"]
"""
import argparse, csv, datetime, importlib.util, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import yaml

TSV = os.path.join(ROOT, "data", "element-harvest", "new-words-proposal.tsv")
TI = os.path.join(ROOT, "data", "seeds", "tag-i18n.yml")
WM = os.path.join(ROOT, "data", "seeds", "wamei-tags.yml")
RU = os.path.join(ROOT, "data", "element-harvest", "rulings.yml")


def is_en(w):
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 '\-/&.]*", w)) and w not in ("SM", "DV", "SNS", "VTuber")


def q(s):
    return '"' + s.replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--go", default=""); a = ap.parse_args()
    sp = importlib.util.spec_from_file_location("ea", os.path.join(ROOT, "scripts", "_element-assign.py"))
    ea = importlib.util.module_from_spec(sp); sp.loader.exec_module(ea)
    draft_rev = {v: k for k, v in ea.JA_DRAFT.items()}
    rows = list(csv.DictReader(open(TSV, encoding="utf-8-sig"), delimiter="\t"))
    ti = (yaml.safe_load(open(TI, encoding="utf-8")) or {}).get("tags") or {}
    wm = yaml.safe_load(open(WM, encoding="utf-8")) or {}
    allow, alias, exclude = list(wm.get("allow") or []), dict(wm.get("alias") or {}), list(wm.get("exclude") or [])
    ti_add, al_add, ex_add, hide, allow_add, allow_del = {}, {}, [], [], [], []
    for r in rows:
        w, v, t = r["語"], r["案"], r["案の語"]
        if v == "出す":
            if w in draft_rev and draft_rev[w] not in ti:
                ti_add[draft_rev[w]] = w
            if w not in allow:
                allow_add.append(w)
        elif v == "訳":
            if w not in ti:
                ti_add[w] = t
        elif v == "寄せる":
            if is_en(w) or w == "VTuber":
                if w not in ti:
                    ti_add[w] = t
            elif w not in alias:
                al_add[w] = t
        elif v == "隠す":
            hide.append(w)
        elif v == "外す" and not is_en(w):
            if w not in exclude:
                ex_add.append(w)
            if w in allow:
                allow_del.append(w)
    # 寄せ先・訳語が表に出る語か(書いた後の語彙で)
    disp = set(ea.load_vocab()["display"]) | set(allow_add) | set(ti_add.values())
    lost = sorted({t for t in list(al_add.values()) + list(ti_add.values()) if t not in disp})
    print(f"tag-i18n に足す {len(ti_add)} / wamei allow +{len(allow_add)} -{len(allow_del)} / alias +{len(al_add)} / exclude +{len(ex_add)} / 隠す(hide_common) {len(hide)}")
    print("  tag-i18n:", " / ".join(f"{k}→{v}" for k, v in ti_add.items()))
    print("  alias:", " / ".join(f"{k}→{v}" for k, v in al_add.items()))
    print("  exclude:", "・".join(ex_add), "/ allowから抜く:", "・".join(allow_del) or "なし")
    print("  寄せ先・訳語のうち表に出ない語(hide_common など):", "・".join(lost) or "なし")
    if not a.go:
        print("(試運転・何も書かない)")
        return
    bak = os.path.join(ROOT, ".cache", f"new-words-ruling-bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    os.makedirs(bak, exist_ok=True)
    for p in (TI, WM, RU):
        shutil.copyfile(p, os.path.join(bak, os.path.basename(p)))
    today = datetime.date.today().isoformat()
    # tag-i18n: tags: が最後の節 = 末尾に足す
    s = open(TI, encoding="utf-8").read().rstrip("\n") + "\n"
    s += f"  # ── 語彙外の語の裁定({today}・ユーザ「裁定は終わりにする」= 案どおり)──\n"
    for k, v in ti_add.items():
        s += f"  {(q(k) + ':').ljust(30)} {{ja: {v}, genre: \"\"}}\n"
    open(TI, "w", encoding="utf-8", newline="\n").write(s)
    # wamei: 節ごとに末尾へ差し込む(コメントを壊さないよう文字列で)
    s = open(WM, encoding="utf-8").read()
    lines = s.split("\n")

    def sec_end(name):
        i = next(i for i, l in enumerate(lines) if l.startswith(name + ":"))
        j = i + 1
        while j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("#") or not lines[j].strip()):
            j += 1
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1
        return j
    note = f"  # 語彙外の語の裁定 {today}(案どおり)"
    for name, new in (("allow", [f"  - {q(w)}" for w in allow_add]), ("alias", [f"  {q(k)}: {q(v)}" for k, v in al_add.items()]),
                      ("exclude", [f"  - {q(w)}" for w in ex_add])):
        if new:
            j = sec_end(name)
            lines[j:j] = [note] + new
    s = "\n".join(lines)
    for w in allow_del:
        s = s.replace(f"\n  - {q(w)}\n", "\n", 1)
    open(WM, "w", encoding="utf-8", newline="\n").write(s)
    # rulings: word_rulings に hide_common を1件
    s = open(RU, encoding="utf-8").read()
    ent = (f"  - kind: hide_common\n    words: [{', '.join(q(w) for w in hide)}]\n    at: \"{today}\"\n"
           f"    quote: {q(a.go.strip())}\n    note: \"語彙外の語の裁定(new-words-proposal.tsv の案=隠す・裁定ページで変更0)\"\n")
    i = s.index("word_rulings:")
    j = s.find("\n", i) + 1
    # word_rulings の最後の項目の後ろ(次の最上位キーの前)
    m = re.search(r"\n(?=[A-Za-z_]+:)", s[j:])
    k = j + m.start() + 1 if m else len(s)
    s = s[:k].rstrip("\n") + "\n" + ent + s[k:]
    open(RU, "w", encoding="utf-8", newline="\n").write(s)
    for p in (TI, WM, RU):
        yaml.safe_load(open(p, encoding="utf-8"))  # 壊れていないか
    print(f"書いた / 退避 {os.path.relpath(bak, ROOT)}")


if __name__ == "__main__":
    main()
