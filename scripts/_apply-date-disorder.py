"""発売日逆行 是正の適用 (= dry-run と同一ロジック + 安全ゲート)。

方針 (= 慎重):
- net-improving slug のみ (inv_after < inv_before)。regressor/構造混在は触らない。
- 各巻の新日付 = 主版(最多巻カバーpublisher)内の最古printing。現状より前のみ。
- ★ISBN-key可能(=manga.v2標準版にその巻のisbn13有)な変更だけ採用 → durable override seed化。
- ★per-slug 再ゲート: ISBN部分集合だけ適用しても なお逆行が減る slug のみ実行(部分適用で
  逆に増えるならその slug 丸ごとskip)。
- 二層 同時更新で整合: (a) data/seeds/release-date-override.jsonl (promote durable),
  (b) data/manga.v2 標準版の release_date を直接更新(即時可視)。両方 可逆(.cache backup + changelog)。

usage:
  python _apply-date-disorder.py            # preview (変更なし)
  python _apply-date-disorder.py --apply     # 実適用
"""
import sys, os, pickle, json, shutil, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
ROOT = L.ROOT
APPLY = "--apply" in sys.argv
AT = "2026-06-27"

OVERRIDE_SEED = f"{ROOT}/data/seeds/release-date-override.jsonl"
CHANGELOG = f"{ROOT}/data/seeds/date-disorder-changelog.jsonl"
BACKUP_DIR = f"{ROOT}/.cache/date-disorder-bak-{AT}"


def std_edition(d):
    return next((e for e in (d.get("editions") or []) if e.get("type") == "standard"), None)


def main():
    bundle = pickle.load(open(f"{ROOT}/.cache/rakuten-focus-index.pkl", "rb"))
    index = bundle["index"]; s2b = bundle["slug_to_bases"]
    import csv
    slugs = [r["slug"] for r in csv.DictReader(open(f"{ROOT}/docs/volume-date-disorder.tsv", encoding="utf-8"), delimiter="\t")]

    override_lines = []
    changelog_lines = []
    file_edits = {}  # slug -> {vol: new_date}
    stat = {"slug_apply": 0, "slug_skip_regress": 0, "slug_no_change": 0, "vol_change": 0,
            "vol_skip_noisbn": 0}

    for sl in slugs:
        p = f"{ROOT}/data/manga.v2/{sl}.yml"
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(open(p, encoding="utf-8"))
        if not d:
            continue
        bases = s2b.get(sl, {L.norm(d.get("title"))})
        ed = std_edition(d)
        if not ed:
            continue
        vols = [(v.get("number"), L.parse_prod_date(v.get("release_date")), str(v.get("release_date") or ""), v.get("isbn13"))
                for v in (ed.get("volumes") or []) if v.get("number")]
        vols.sort(key=lambda x: x[0])
        if len(vols) < 5:
            continue
        inv_before = L.inversions([(n, dt) for n, dt, _, _ in vols])
        _, chosen = L.primary_publisher(index, bases, [n for n, _, _, _ in vols])

        # ISBN-keyable subset の変更案を作る
        proposed = {}   # vol -> (new_date_str, new_tuple, rk_isbn, cur_str, prod_isbn)
        for n, dt, curstr, prod_isbn in vols:
            rec = chosen.get(n)
            if rec is None:
                continue
            old = rec["date"]
            if not (old and (dt is None or old < dt)):
                continue  # 前でない→変更しない
            if not prod_isbn:
                stat["vol_skip_noisbn"] += 1
                continue  # ISBN-None はスキップ(durable化不可)
            proposed[n] = (L.date_str(old, day=True), old, rec["isbn"], curstr, prod_isbn)

        if not proposed:
            stat["slug_no_change"] += 1
            continue
        # 部分適用後の逆行をシミュレート(安全ゲート)
        new_seq = [(n, (proposed[n][1] if n in proposed else dt)) for n, dt, _, _ in vols]
        inv_after = L.inversions(new_seq)
        if inv_after >= inv_before:
            stat["slug_skip_regress"] += 1
            continue  # 部分適用では改善しない→丸ごとskip

        # 採用
        stat["slug_apply"] += 1
        file_edits[sl] = {}
        for n, (nd, _t, rk_isbn, curstr, prod_isbn) in proposed.items():
            stat["vol_change"] += 1
            file_edits[sl][n] = nd
            override_lines.append({"isbn13": prod_isbn, "date": nd, "slug": sl, "vol": n,
                                   "reason": "date-disorder", "src_isbn": rk_isbn, "at": AT})
            changelog_lines.append({"slug": sl, "vol": n, "op": "release_date_normalize",
                                    "isbn13": prod_isbn, "before": curstr, "after": nd,
                                    "at": AT, "reversible": True})

    print(f"{'APPLY' if APPLY else 'PREVIEW'}: net-improve適用 {stat['slug_apply']} slug / "
          f"部分適用で非改善skip {stat['slug_skip_regress']} / 変更無 {stat['slug_no_change']}")
    print(f"  変更巻 {stat['vol_change']} / ISBN-Noneスキップ {stat['vol_skip_noisbn']}")

    if not APPLY:
        print("\n(preview。 --apply で適用)")
        # サンプル
        for ln in changelog_lines[:12]:
            print(f"  {ln['slug'][:28]:28} v{ln['vol']:>3} {ln['before']:>10} -> {ln['after']}")
        return

    # ---- 適用 (surgical: 対象isbn13の release_date 行のみ差し替え。全文再dumpしない) ----
    import re
    os.makedirs(BACKUP_DIR, exist_ok=True)
    # isbn13 -> new_date map をファイル単位で
    isbn_new = {ln["isbn13"]: ln["date"] for ln in override_lines}
    edited = 0; line_changed = 0
    re_isbn = re.compile(r"^\s*isbn13:\s*(.+?)\s*$")
    re_rd = re.compile(r"^(\s*)release_date:\s*.*$")
    for sl, vmap in file_edits.items():
        p = f"{ROOT}/data/manga.v2/{sl}.yml"
        targets = {}  # isbn13 -> new for this file (確認用)
        d = yaml.safe_load(open(p, encoding="utf-8"))
        ed = std_edition(d)
        for v in (ed.get("volumes") or []):
            if v.get("number") in vmap and v.get("isbn13"):
                targets[str(v["isbn13"])] = vmap[v["number"]]
        if not targets:
            continue
        shutil.copy2(p, f"{BACKUP_DIR}/{sl}.yml")  # 可逆backup
        lines = open(p, encoding="utf-8").read().split("\n")
        cur_isbn = None
        out = []
        for line in lines:
            mi = re_isbn.match(line)
            if mi:
                val = mi.group(1).strip().strip("'\"")
                cur_isbn = val if val not in ("null", "~", "") else None
                out.append(line); continue
            mr = re_rd.match(line)
            if mr and cur_isbn in targets:
                out.append(f"{mr.group(1)}release_date: '{targets[cur_isbn]}'")
                line_changed += 1
                cur_isbn = None  # 1巻1回
                continue
            out.append(line)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        edited += 1
    # seed + changelog (純粋追加)
    with open(OVERRIDE_SEED, "a", encoding="utf-8") as f:
        for ln in override_lines:
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        for ln in changelog_lines:
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")
    print(f"\n適用完了: manga.v2 {edited}ファイル / release_date行 {line_changed}本 差替 / "
          f"override seed +{len(override_lines)} / backup={BACKUP_DIR}")
    if line_changed != len(override_lines):
        print(f"  ⚠ 差替本数 {line_changed} ≠ override {len(override_lines)} (一部行未検出=要確認)")


if __name__ == "__main__":
    main()
