"""根拠台帳(data/seeds/magazine-evidence)から連載誌を埋める/直す(2026-11-07 ユーザ「順番はまかせる」)。

  python scripts/magazine-verify/ledger_apply.py plan    # 計画 docs/production-diagnostics/magazine-ledger-apply-2026-11-07.tsv(読むだけ)
  python scripts/magazine-verify/ledger_apply.py apply   # magazine-corrections.yml へ(新しい頁は末尾追記・誤り6頁は書き換え)+ changelog + 反映用 stem 一覧

★本番を変えるのは「強い根拠が1誌にそろい、 出版社も合う」頁だけ。 次は変えずに HOLD(表に理由):
  強い根拠が2誌以上(移籍・増刊・読切) / マスタに無い誌の根拠もある / 根拠が Wiki一覧だけ(当たり方が粗い) / 楽天説明が別の誌 /
  誌の出版社と頁の出版社が合わない / 今の誌も記載にある(移籍先・出張掲載) / 既に人や前回の是正が上書きした頁(BUGFIX の6頁を除く)
"""
import datetime, importlib.util, json, os, re, shutil, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("ml", os.path.join(ROOT, "scripts", "_magazine-ledger.py"))
ML = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ML)
import yaml

TODAY = datetime.date.today().isoformat()
PLAN = os.path.join(ROOT, "docs", "production-diagnostics", f"magazine-ledger-apply-{TODAY}.tsv")
PLAN_JSON = os.path.join(ROOT, ".cache", "magazine-lists", f"ledger-apply-{TODAY}.json")
CORR = os.path.join(ROOT, "data", "seeds", "magazine-corrections.yml")
LOG = os.path.join(ROOT, "data", "seeds", "magazine-fix-changelog.jsonl")
STEMS = os.path.join(ROOT, ".cache", "magazine-lists", f"stems-ledger-{TODAY}.txt")

# 11/4 の照合関数(wiki_mag_lib.canon)の取り違えで誤って上書きした頁 → 正しい誌(2026-11-07 ユーザ了承「順番はまかせる」)
BUGFIX = {
    "drop": ("monthly-shonen-champion", "初出「月刊少年チャンピオン」(MADB 初出欄13冊・ja.wikipedia)を canon が週刊に寄せていた"),
    "gokuman": ("monthly-shonen-champion", "初出「月刊少年チャンピオン」(MADB・ja.wikipedia)を canon が週刊に寄せていた"),
    "hakaijuu": ("monthly-shonen-champion", "初出「月刊少年チャンピオン」(MADB・ja.wikipedia)を canon が週刊に寄せていた"),
    "katteni-takahashi-hiroshi": ("monthly-shonen-champion", "初出「月刊少年チャンピオン」(MADB)を canon が週刊に寄せていた"),
    "worst-gaiden": ("monthly-shonen-champion", "初出「月刊少年チャンピオン」200904～07(MADB)を canon が週刊に寄せていた"),
    "asa-ga-mata-kuru-kara": ("bessatsu-hana-to-yume", "初出「花とゆめプラス」20050425、「別冊花とゆめ」200710,201002(MADB)。 canon が花とゆめプラス→花とゆめ に寄せていた。"
                                                       "花とゆめプラスは増刊でマスタに無い = 続きの別冊花とゆめ"),
}

# 出版社の同じ系列(誌の社と単行本の社が別名義でも同じ会社グループ)
GROUPS = [
    {"kadokawa", "ascii-media-works", "enterbrain", "fujimi-shobo", "mediafactory", "kadokawa-game-linkage", "kadokawa-shoten"},
    {"shogakukan", "shogakukan-creative"},
    {"shueisha", "home-sha"},
    {"gakken", "gakken-2"},
]


def same_pub(a, b):
    if not a or not b or a == b:
        return True
    return any(a in g and b in g for g in GROUPS)


def plan():
    pages = ML.load_pages()
    stem2slug, _ = ML.page_files()
    slug2stem = {}
    for st, sl in stem2slug.items():
        slug2stem.setdefault(sl, st)
    corr = yaml.safe_load(open(CORR, encoding="utf-8"))["corrections"]
    src = {k: ML.read_source(k) for k, _, _ in ML.SOURCES}
    MAG = ML.MAG
    rows, c = [], Counter()
    for slug, p in sorted(pages.items()):
        E = ML.evidence_of(slug, src)
        cur, pub = p["mag"], p["pub"]
        cands = [k for k in E["strong"] if not k.startswith("?")]
        q = [k for k in E["strong"] if k.startswith("?")]
        if slug in BUGFIX:
            k, why = BUGFIX[slug]
            rows.append({"action": "BUGFIX", "slug": slug, "stem": slug2stem.get(slug, slug), "title": p["title"], "pub": pub,
                         "cur": cur, "new": k, "sources": "manual", "why": why, "ev": why})
            c["BUGFIX"] += 1
            continue
        if not cands or (cur and cur in cands and len(cands) == 1):
            continue
        r = {"slug": slug, "stem": slug2stem.get(slug, slug), "title": p["title"], "pub": pub, "cur": cur}
        hold = ""
        if slug in corr:
            hold = "既に上書き済みの頁(人・前回の是正)"
        elif len(cands) > 1 or q:
            hold = "強い根拠が割れる(" + "、".join(ML.magname(k) for k in list(E["strong"])) + ")"
        else:
            k = cands[0]
            r["new"] = k
            srcs = E["by_src"][k]
            r["sources"] = "+".join(srcs)
            if srcs == ["wiki-list"]:
                hold = "根拠が Wiki一覧だけ"
            elif E["weak"] and k not in E["weak"]:
                hold = "楽天説明は別の誌(" + "、".join(ML.magname(x) for x in E["weak"]) + ")"
            elif not same_pub(MAG[k].get("publisher") or "", pub):
                hold = f"出版社が合わない(誌={MAG[k].get('publisher')} / 頁={pub})"
            elif cur and cur in E["secondary"]:
                hold = "今の誌も記載にある(移籍先・出張掲載・増刊)"
            elif cur and cur in E["weak"]:
                hold = "楽天説明は今の誌"
        if not cur and not cands:
            continue
        if hold:
            r.update(action="HOLD", why=hold)
        else:
            r["action"] = "FILL" if not cur else "FIX"
            cols = {ML.SOURCES[i][0]: ML.SOURCES[i][1] for i in range(len(ML.SOURCES))}
            r["ev"] = " / ".join(f"{cols[s]}: {E['cells'][cols[s]]}" for s in r["sources"].split("+"))
        r.setdefault("new", "")
        rows.append(r)
        c[r["action"]] += 1
    json.dump(rows, open(PLAN_JSON, "w", encoding="utf-8"), ensure_ascii=False)
    with open(PLAN, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 根拠台帳からの連載誌の是正計画 {TODAY}(scripts/magazine-verify/ledger_apply.py)。 FILL=空欄を埋める / FIX=直す / BUGFIX=11/4 の誤り / HOLD=変えない\n")
        cols = ["action", "slug", "title", "pub", "cur", "new", "sources", "why", "ev"]
        f.write("\t".join(["action", "slug", "漫画名", "出版社", "今の連載誌", "新しい連載誌", "根拠のソース", "保留の理由", "根拠"]) + "\n")
        order = {"BUGFIX": 0, "FIX": 1, "FILL": 2, "HOLD": 3}
        for r in sorted(rows, key=lambda x: (order[x["action"]], x["slug"])):
            vals = [r.get(k, "") for k in cols]
            vals[4], vals[5] = ML.magname(vals[4]), ML.magname(vals[5])
            f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in vals) + "\n")
    print("計画:", dict(c))
    print("HOLD の理由:", Counter(r["why"].split("(")[0] for r in rows if r["action"] == "HOLD").most_common())
    print("FIX の多い取り違え:", Counter((ML.magname(r["cur"]), ML.magname(r["new"])) for r in rows if r["action"] == "FIX").most_common(12))
    print("→", os.path.relpath(PLAN, ROOT))


def apply():
    rows = json.load(open(PLAN_JSON, encoding="utf-8"))
    go = [r for r in rows if r["action"] in ("FILL", "FIX", "BUGFIX")]
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(ROOT, ".cache", f"magazine-fix-bak-{ts}")
    os.makedirs(bak, exist_ok=True)
    shutil.copy2(CORR, bak)
    txt = open(CORR, encoding="utf-8").read()
    corr = yaml.safe_load(txt)["corrections"]
    # ① 誤り6頁 = 既存キーの magazine 行だけ書き換え(evidence に経緯を足す)
    for r in [x for x in go if x["action"] == "BUGFIX"]:
        s = r["slug"]
        m = re.search(r"(?m)^  " + re.escape(s) + r":\n((?:    .*\n)+)", txt)
        if not m:
            sys.exit(f"★{s} の既存の上書きが見つからない = 中止")
        old_block = m.group(1)
        old_mag = re.search(r"(?m)^    magazine: (.+)$", old_block).group(1).strip()
        new_block = re.sub(r"(?m)^    magazine: .+$", f"    magazine: {r['new']}", old_block)
        new_block = re.sub(r"(?m)^    source: .+$", "    source: manual", new_block)
        new_block = re.sub(r"(?m)^    added_at: .+$", f"    added_at: '{TODAY}'", new_block)
        new_block += "    fixed_note: " + json.dumps(f"2026-11-07 直し: {old_mag}→{r['new']}。 {r['why']}", ensure_ascii=False) + "\n"
        txt = txt[:m.start(1)] + new_block + txt[m.end(1):]
        r["cur"] = old_mag
    # ② 新しい頁 = 末尾追記(既存キーは触らない)
    entries = {}
    for r in [x for x in go if x["action"] in ("FILL", "FIX")]:
        if r["slug"] in corr:
            sys.exit(f"★{r['slug']} は既に上書きがある = 計画が古い。 plan からやり直す")
        ev = re.sub(r"\s+", " ", r["ev"])[:300] + f"。旧値 {r['cur'] or '空'}(種3のAI埋め)"
        entries[r["slug"]] = {"magazine": r["new"], "source": "ledger:" + r["sources"], "evidence": ev, "added_at": TODAY}
    dumped = yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=10000)
    dumped = "\n".join(("  " + ln) if ln else ln for ln in dumped.splitlines())
    txt = txt + ("" if txt.endswith("\n") else "\n") \
        + "  # ★2026-11-07 根拠台帳(data/seeds/magazine-evidence)からの是正(ユーザ「順番はまかせる」)。 強い根拠が1誌にそろい出版社も合う頁だけ。\n" \
        + f"  #   計画表 = docs/production-diagnostics/magazine-ledger-apply-{TODAY}.tsv(HOLD は理由つきで残す)\n" + dumped + "\n"
    chk = yaml.safe_load(txt)["corrections"]
    bad = [s for s, v in chk.items() if v["magazine"] not in ML.MAG]
    if bad:
        sys.exit(f"★マスタに無い誌を書こうとした {bad[:5]} = 中止")
    open(CORR, "w", encoding="utf-8", newline="\n").write(txt)
    at = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8", newline="\n") as f:
        for r in go:
            f.write(json.dumps({"op": "magazine-correct", "slug": r["slug"], "title": r["title"], "before": r["cur"] or None, "after": r["new"],
                                "evidence": (entries.get(r["slug"]) or {}).get("evidence") or r["why"], "tier": "ledger-" + r["action"].lower(),
                                "at": at, "via": "magazine-corrections.yml → _reflect-targeted --only-file",
                                "reversible": f"magazine-corrections.yml を退避 {os.path.relpath(bak, ROOT)} から戻して再反映"}, ensure_ascii=False) + "\n")
    open(STEMS, "w", encoding="utf-8", newline="\n").write("\n".join(sorted({r["stem"] for r in go})) + "\n")
    print(f"書いた: 新規 {len(entries):,} / 誤り直し {sum(1 for r in go if r['action'] == 'BUGFIX')} / 反映する頁 {len({r['stem'] for r in go}):,}")
    print(f"  退避 {os.path.relpath(bak, ROOT)} / stems {os.path.relpath(STEMS, ROOT)}")


if __name__ == "__main__":
    {"plan": plan, "apply": apply}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
