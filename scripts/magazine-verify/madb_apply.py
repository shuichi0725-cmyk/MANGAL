"""連載誌の MADB 是正を seed に書く(本番頁はまだ触らない = 後で _reflect-targeted --only-file)。 2026-11-04 ユーザ裁定:
  1(返事なし=案のまま) 段階 A・B・D を直す / C(MADBのみ弱)は見送り
  2「たして」 マスタに無い誌のうち 10頁以上の誌を足す   3「たてて」 増刊は親誌に寄せず別の誌として立てる
入力 = docs/production-diagnostics/magazine-verify-2026-11-04.tsv(mag_verify_report.py が作る)
書く = data/magazines.yml と .preview-data/magazines.yml(末尾追記)/ data/seeds/magazine-corrections.yml(末尾追記・既存キー不変)/
       data/seeds/magazine-fix-changelog.jsonl / .cache/magazine-lists/stems-madb.txt / .cache/magazine-fix-bak-<日時>/(manga.v2 の退避)
usage: python scripts/magazine-verify/madb_apply.py            # 試走(件数だけ)
       python scripts/magazine-verify/madb_apply.py --write    # 書く
"""
import csv, datetime, json, os, re, shutil, sys
from collections import Counter
from pathlib import Path
import yaml

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from wiki_mag_lib import canon
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
TSV = ROOT / "docs" / "production-diagnostics" / "magazine-verify-2026-11-04.tsv"
TODAY = "2026-11-04"
APPLY_TIERS = ("A", "B", "D")          # C は見送り / E は今の値で正しい

# 足す誌(10頁以上 + 名前を挙げた増刊)。 key: (誌名, 出版社key, 読者層, 照合に使う誌名の別表記...)
NEW_MAGS = {
    "weekly-comic-bunch": ("週刊コミックバンチ", "shinchosha", "seinen", "週刊コミックバンチ", "コミックバンチ"),
    "chuchu": ("ChuChu", "shogakukan", "shoujo", "ちゅちゅ", "ChuChu"),
    "monthly-shonen-rival": ("月刊少年ライバル", "kodansha", "shounen", "月刊少年ライバル"),
    "corocoro-comic": ("月刊コロコロコミック", "shogakukan", "kodomo", "月刊コロコロコミック", "コロコロコミック"),
    "monthly-shonen-sirius": ("月刊少年シリウス", "kodansha", "shounen", "月刊少年シリウス"),
    "princess-gold": ("プリンセスGOLD", "akita", "shoujo", "プリンセスGOLD", "プリンセスゴールド"),
    "gessan": ("ゲッサン", "shogakukan", "shounen", "ゲッサン"),
    "monthly-princess": ("月刊プリンセス", "akita", "shoujo", "月刊プリンセス", "プリンセス"),
    "lala-dx": ("LaLa DX", "hakusensha", "shoujo", "LaLa DX", "ララDX", "LaLaDX"),
    "gundam-ace": ("ガンダムエース", "kadokawa", "shounen", "ガンダムエース", "月刊ガンダムエース"),
    "magazine-special": ("マガジンSPECIAL", "kodansha", "shounen", "マガジンSPECIAL", "マガジンスペシャル"),
    "ciao-deluxe": ("ちゃおデラックス", "shogakukan", "shoujo", "ちゃおデラックス", "ちゃおDX"),
    "the-hana-to-yume": ("ザ花とゆめ", "hakusensha", "shoujo", "ザ花とゆめ", "ザ・花とゆめ"),
    "bessatsu-hana-to-yume": ("別冊花とゆめ", "hakusensha", "shoujo", "別冊花とゆめ"),
    "grand-jump-premium": ("グランドジャンプPREMIUM", "shueisha", "seinen", "グランドジャンプPREMIUM"),
    "cookie": ("Cookie", "shueisha", "shoujo", "Cookie", "クッキー", "CooKie"),
    "the-margaret": ("ザ マーガレット", "shueisha", "shoujo", "ザ マーガレット", "ザ・マーガレット", "ザマーガレット"),
    "deluxe-margaret": ("デラックスマーガレット", "shueisha", "shoujo", "デラックスマーガレット"),
    "corocoro-ichiban": ("コロコロイチバン!", "shogakukan", "kodomo", "コロコロイチバン!", "コロコロイチバン"),
    "garo": ("月刊漫画ガロ", "seirindo", "seinen", "月刊漫画ガロ", "ガロ"),
    "club-sunday": ("クラブサンデー", "shogakukan", "shounen", "クラブサンデー"),
    "bessatsu-friend": ("別冊フレンド", "kodansha", "shoujo", "別冊フレンド"),
    "nakayoshi-lovely": ("なかよしラブリー", "kodansha", "shoujo", "なかよしラブリー"),
    "bessatsu-corocoro-comic": ("別冊コロコロコミック", "shogakukan", "kodomo", "別冊コロコロコミック"),
    "jump-sq-19": ("ジャンプSQ.19", "shueisha", "shounen", "ジャンプSQ.19"),
}
# 既存キーへ寄せる別表記(Wikipedia では同じ誌の記事 = 週刊少年サンデー超 → 週刊少年サンデーS へリダイレクト)
EXTRA_ALIAS = {"週刊少年サンデー超": "shonen-sunday-super", "週刊少年サンデー超増刊": "shonen-sunday-super"}
# ★「親誌+増刊」だけの名前は親誌に寄せない(ユーザ裁定3「増刊は別の誌」)。 誌名そのものが増刊表記の誌(サンデーS 等)は除く
PURE_ZOUKAN = re.compile(r"^(Sho-Comi|少女コミック|週刊少年サンデー|週刊少年マガジン|週刊少年ジャンプ|週刊少年チャンピオン|なかよし|りぼん|ちゃお|"
                         r"マーガレット|別冊マーガレット|花とゆめ|LaLa|ララ|月刊少年マガジン|月刊少年ガンガン|少年ガンガン)(増刊|増刊号)$")

CANON2KEY = {}
for k, v in NEW_MAGS.items():
    for n in v[3:]:
        CANON2KEY[canon(n)] = k
for n, k in EXTRA_ALIAS.items():
    CANON2KEY[canon(n)] = k


def target_of(prop, mags):
    if not prop:
        return ""
    if prop in mags:
        return prop
    if prop.startswith("?"):
        return CANON2KEY.get(prop[1:]) or CANON2KEY.get(canon(prop[1:])) or ""
    return ""


def stem_of(slug, rev):
    if (ROOT / "data" / "manga.v2" / f"{slug}.yml").exists():
        return slug
    for k in rev.get(slug, []):
        if (ROOT / "data" / "manga.v2" / f"{k}.yml").exists():
            return k
    return None


def main(write):
    mags = yaml.safe_load(open(ROOT / "data" / "magazines.yml", encoding="utf-8"))
    rows = [r for r in csv.DictReader((ln for ln in open(TSV, encoding="utf-8") if not ln.startswith("#")), delimiter="\t")]
    existing = yaml.safe_load(open(ROOT / "data" / "seeds" / "magazine-corrections.yml", encoding="utf-8"))["corrections"]
    plan, skip = {}, Counter()
    for r in rows:
        t = r["段階"][0]
        if t not in APPLY_TIERS:
            skip[f"段階{t}"] += 1; continue
        if t in "AB" and PURE_ZOUKAN.match(r["MADB誌名"] or ""):
            skip["親誌+増刊(寄せない)"] += 1; continue
        tgt = target_of(r["提案"], {**mags, **{k: 1 for k in NEW_MAGS}})
        if not tgt:
            skip["マスタに無い誌のまま" if r["提案"] else "空のまま"] += 1; continue
        if tgt == r["今の連載誌"]:
            skip["今と同じ"] += 1; continue
        if r["slug"] in existing:
            skip["既存seedあり(触らない)"] += 1; continue
        plan[r["slug"]] = {"title": r["title"], "old": r["今の連載誌"], "new": tgt, "tier": r["段階"], "why": r["理由"],
                           "wiki": r["Wikipedia"], "madb": r["MADB"], "rakuten": r["楽天"]}
    ov = yaml.safe_load(open(ROOT / "data" / "seeds" / "slug-overrides.yml", encoding="utf-8"))["overrides"]
    rev = {}
    for k, v in ov.items():
        if isinstance(v, dict) and v.get("slug"):
            rev.setdefault(v["slug"], []).append(k)
    stems, missing = {}, []
    for s in plan:
        st = stem_of(s, rev)
        if st: stems[s] = st
        else: missing.append(s)
    for s in missing:
        plan.pop(s)
    used_new = sorted({p["new"] for p in plan.values() if p["new"] in NEW_MAGS})
    print("適用", len(plan), "頁 / 見送り", dict(skip), "/ stem不明", missing)
    print("  段階別", dict(Counter(p["tier"][0] for p in plan.values())), "/ 埋める", sum(1 for p in plan.values() if not p["old"]),
          "直す", sum(1 for p in plan.values() if p["old"]))
    print("  新しい誌", len(used_new), "誌:", {k: sum(1 for p in plan.values() if p["new"] == k) for k in used_new})
    print("  変化の上位", Counter((p["old"] or "空", p["new"]) for p in plan.values()).most_common(15))
    if not write:
        return
    # 0) 退避
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = ROOT / ".cache" / f"magazine-fix-bak-{ts}"; bak.mkdir(parents=True)
    for st in set(stems.values()):
        shutil.copy2(ROOT / "data" / "manga.v2" / f"{st}.yml", bak / f"{st}.yml")
    # 1) 雑誌マスタ(data と .preview-data の両方・末尾追記・既存不変)
    block = ("\n# ★2026-11-04 連載誌の MADB 是正で追加(ユーザ裁定「2たして。3たてて」= 10頁以上の誌を足す・増刊は別の誌)。\n"
             "#   根拠= MADB 雑誌掲載履歴(cm106+目次108+各号102)/単行本の初出欄 × ja.wikipedia 作品記事。 読者層= ja.wikipedia の誌の分類。\n")
    for k in used_new:
        name, pub, demo = NEW_MAGS[k][:3]
        block += f"{k}:\n  name: {name}\n  publisher: {pub}\n  demographic: {demo}\n"
    for p in (ROOT / "data" / "magazines.yml", ROOT / ".preview-data" / "magazines.yml"):
        txt = p.read_text(encoding="utf-8")
        cur = yaml.safe_load(txt)
        if any(k in cur for k in used_new):
            sys.exit(f"★既にキーが在る: {p} {[k for k in used_new if k in cur]}")
        p.write_text(txt + ("" if txt.endswith("\n") else "\n") + block, encoding="utf-8")
        yaml.safe_load(p.read_text(encoding="utf-8"))
    # 2) magazine-corrections.yml(末尾追記)
    entries = {}
    for s, p in sorted(plan.items()):
        src = {"A": "madb+wiki-verified", "B": "madb", "D": "manual"}[p["tier"][0]]
        ev = f"MADB(1.2.21) {p['madb'][:150]}"
        if p["wiki"]:
            ev += f" / ja.wikipedia{p['wiki'][:120]}"
        if p["rakuten"]:
            ev += f" / 楽天説明 {p['rakuten'][:60]}"
        if p["why"]:
            ev += f"。{p['why']}"
        ev += f"。旧値 {p['old'] or '空'}(種3のAI埋め)"
        entries[s] = {"magazine": p["new"], "source": src, "evidence": re.sub(r"\s+", " ", ev), "added_at": TODAY}
    dumped = yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=10000)
    dumped = "\n".join(("  " + ln) if ln else ln for ln in dumped.splitlines())
    cp = ROOT / "data" / "seeds" / "magazine-corrections.yml"
    txt = cp.read_text(encoding="utf-8")
    cp.write_text(txt + ("" if txt.endswith("\n") else "\n")
                  + "  # ★2026-11-04 連載誌の MADB 是正(ユーザ「調べて」→「2たして。3たてて」)。 MADB 雑誌掲載履歴・単行本の初出欄 × ja.wikipedia 作品記事。\n"
                  + "  #   段階 A=根拠2つ一致 / B=MADBのみ(1巻の初出欄 or 目次10回以上8割) / D=人が読んで裁定。 表= docs/production-diagnostics/magazine-verify-2026-11-04.tsv\n"
                  + dumped + "\n", encoding="utf-8")
    yaml.safe_load(cp.read_text(encoding="utf-8"))
    # 3) changelog
    at = datetime.datetime.now().isoformat(timespec="seconds")
    with open(ROOT / "data" / "seeds" / "magazine-fix-changelog.jsonl", "a", encoding="utf-8") as f:
        for s, p in sorted(plan.items()):
            f.write(json.dumps({"op": "magazine-correct", "slug": s, "title": p["title"], "before": p["old"] or None, "after": p["new"],
                                "evidence": entries[s]["evidence"], "tier": p["tier"], "at": at,
                                "via": "magazine-corrections.yml → _reflect-targeted --only-file",
                                "reversible": f"magazine-corrections.yml の当該キーを消して再反映(退避 {bak.name})"}, ensure_ascii=False) + "\n")
    (ROOT / ".cache" / "magazine-lists" / "stems-madb.txt").write_text("\n".join(sorted(set(stems.values()))) + "\n", encoding="utf-8", newline="\n")
    json.dump({s: {"stem": stems[s], **p} for s, p in plan.items()},
              open(ROOT / ".cache" / "magazine-lists" / "madb-apply-plan.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("書いた: 雑誌マスタ +", len(used_new), "/ corrections +", len(entries), "/ stems", len(set(stems.values())), "/ 退避", bak)


if __name__ == "__main__":
    main("--write" in sys.argv)
