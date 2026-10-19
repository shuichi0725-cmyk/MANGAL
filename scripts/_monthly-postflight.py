# -*- coding: utf-8 -*-
"""月次蒸留 postflight = ★成功判定の機械化 (2026-08-26 新設。Phase0と対になる完了側)。

旧: skillの「成功判定」は全部AIの自己申告(散文)=忘れると死ぬ。以後この script の
exit 0 + 出力数値の引用が完了主張の条件(弱モデル耐性=_monthly-phase0.py と同思想)。

検査(FAILが1つでも exit 1 = 完了していない):
  1. seed lint (_check-seeds.py: parse死/台帳減少/種4フィールド)
  2. manga.v2 頁数 ≥ 66,000 (激減=事故)
  3. ISBN消失監視 (_audit-isbn-loss.py: 理由なし消失0)
  4. 種4-auto台帳 ≥ baseline (全消し/誤退役)
  5. publisher (unknown) ≤ baseline (clean差し替え漏れの下流症状)
  6. solo-truncated: 頁化した月(genpages-last.json が14日以内)は新規頁の途中巻断片=0
  7. 他言語名の出所: 作品QID/言語別ラベル(Wikidata)が enrich map の後に取り直されている

  python scripts/_monthly-postflight.py
"""
import glob
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
fails = []


def ok(msg):
    print(f"  OK   {msg}")


def fail(msg, hint=""):
    fails.append(msg)
    print(f"  FAIL {msg}")
    if hint:
        print(f"       → {hint}")


def check_other_names_sources() -> None:
    """intake の workqid/worklabels 段(--soft)が enrich map の後に取り直したか(2026-10-19 他言語名の月次組込)。
    QLever 不通で素通りした月は新作に Wikidata の他言語名(中国語・韓国語ほか)が付かないまま = ここで止める。"""
    c = os.path.join(ROOT, ".cache")
    em, wq, wl = (os.path.join(c, n) for n in ("anilist-enrich-map.json", "work-qid-map.json", "work-labels.json"))
    hint = ("QLever 不通で取り直せなかった。直ったら python scripts/intake.py --run --stages workqid,worklabels"
            " → 頁へは次の promote で入る(急ぐ時だけ _apply-other-names.py --apply)")
    missing = [os.path.basename(p) for p in (em, wq, wl) if not os.path.exists(p)]
    if missing:
        fail(f"他言語名の出所が無い: {', '.join(missing)}", hint)
        return
    if os.path.getmtime(wq) < os.path.getmtime(em) or os.path.getmtime(wl) < os.path.getmtime(wq):
        fail("他言語名の出所が古い(作品QID/言語別ラベルが enrich map の後に取り直されていない)", hint)
        return
    qmap = json.load(io.open(wq, encoding="utf-8"))
    labels = json.load(io.open(wl, encoding="utf-8"))
    qids = {v["qid"] for v in qmap.values() if v and v.get("qid")}
    lack = qids - set(labels)
    if lack:
        fail(f"言語別ラベル未取得の作品QID {len(lack):,} 件", hint)
        return
    ok(f"他言語名の出所 = 作品QID {len(qids):,} / ラベル {sum(len(v) for v in labels.values()):,} (enrich map の後に取り直し済)")


def main() -> None:
    os.chdir(ROOT)
    # 1. seed lint
    r = subprocess.run([PY, "scripts/_check-seeds.py"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode == 0:
        ok("seed lint (parse/台帳減少/種4フィールド)")
    else:
        fail("seed lint NG", (r.stdout or "").strip().splitlines()[-1] if r.stdout else "")

    # 2. manga.v2 頁数
    n = len(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")))
    if n >= 66_000:
        ok(f"manga.v2 = {n:,} 頁 (≥66k)")
    else:
        fail(f"manga.v2 = {n:,} 頁 < 66,000 (激減=promote事故疑い)")

    # 3. ISBN消失
    r = subprocess.run([PY, "scripts/_audit-isbn-loss.py"], capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "").strip().splitlines()
    if r.returncode == 0:
        ok(f"ISBN消失監視 ({out[0] if out else 'ok'})")
    else:
        fail("ISBN消失: 理由なし消失あり(実在する巻を黙って消した疑い)",
             "docs/production-diagnostics/isbn-loss.tsv を1件ずつ裁定(復活 or 台帳に理由)")

    # 4/5. baseline 比較
    bp = os.path.join(ROOT, "data", "seeds", "preflight-baselines.json")
    base = json.load(io.open(bp, encoding="utf-8")) if os.path.exists(bp) else {}
    import yaml
    try:
        s4 = len((yaml.safe_load(io.open(os.path.join(ROOT, "data", "seeds",
                  "volumes-supplement-auto.yml"), encoding="utf-8")) or {}).get("volumes") or [])
    except Exception:
        s4 = -1
    b4 = base.get("seed4_auto_volumes")
    if s4 < 0:
        fail("種4-auto が読めない(parse死)")
    elif b4 is not None and s4 < b4:
        fail(f"種4-auto台帳が減少 {b4} → {s4} (全消し/誤退役の疑い)")
    else:
        ok(f"種4-auto = {s4} 巻 (基準 {b4})")

    unk = 0
    for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        for ln in open(f, encoding="utf-8"):
            if ln.startswith("publisher:"):
                if "(unknown)" in ln:
                    unk += 1
                break
    bu = base.get("publisher_unknown")
    if bu is not None and unk > bu:
        fail(f"publisher (unknown) 増加 {bu} → {unk}", "cleanの正規パス差し替え漏れを疑う(月次skill罠)")
    else:
        ok(f"publisher (unknown) = {unk} (基準 {bu})")

    # 5b. マーカー整合 (phase2 が両方書く。食い違い=途中失敗の痕跡)
    import re as _re
    mk_p = os.path.join(ROOT, ".cache", "madb-last-release.txt")
    st_p = os.path.join(ROOT, "data", "madb-intake-state.yml")
    mk = open(mk_p, encoding="utf-8").read().strip() if os.path.exists(mk_p) else None
    _m = _re.search(r'^\s*release_tag:\s*"?([0-9][0-9.]*)"?', io.open(st_p, encoding="utf-8").read(), _re.M) if os.path.exists(st_p) else None
    st = _m.group(1) if _m else None
    if mk and st and mk == st:
        ok(f"取込マーカー整合 {mk} (.cache = data/madb-intake-state.yml)")
    else:
        fail(f"取込マーカー不一致 .cache={mk} / intake-state.yml={st}", "phase2 が途中で止まった? 台帳 data/madb-distill-ledger.jsonl で正を確認")

    # 5c. 源なし manga.v2 頁 (情報のみ。promote は元頁駆動=源が無い頁は次のフルpromoteで黙って消える
    #     [[orphan_source_pages_restored]]。2026-09-02 時点の既知 2 件から増えたら頁化フローの源永続化漏れ)
    _v2 = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))}
    _src = set()
    for _d in ("data/manga", "data/seeds/source-pages", "data/seeds/preorder-pages"):
        _src |= {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(ROOT, _d, "*.yml"))}
    _orph = sorted(_v2 - _src)
    print(f"  INFO 源なし manga.v2 頁 = {len(_orph)} (既知2: shikakenin-fujieda-baian-saitou / tales-of-the-abyss-rei。増加=源永続化漏れ)"
          + (f": {', '.join(_orph[:8])}" if _orph else ""))

    # 6. solo-truncated (頁化した月のみブロッキング)
    r = subprocess.run([PY, "scripts/_audit-solo-truncated.py"], capture_output=True, text=True, encoding="utf-8")
    tsv = os.path.join(ROOT, "docs", "production-diagnostics", "solo-truncated.tsv")
    tsv_slugs = set()
    if os.path.exists(tsv):
        for i, ln in enumerate(io.open(tsv, encoding="utf-8")):
            if i and ln.strip():
                parts = ln.split("\t")
                if len(parts) > 1:
                    tsv_slugs.add(parts[1])
    gp = os.path.join(ROOT, ".cache", "torikoboshi", "genpages-last.json")
    if os.path.exists(gp) and time.time() - os.path.getmtime(gp) < 14 * 86400:
        made = set((json.load(io.open(gp, encoding="utf-8")) or {}).get("made") or [])
        hit = sorted(made & tsv_slugs)
        if hit:
            fail(f"新規頁に途中巻断片 {len(hit)} 頁: {', '.join(hit[:6])}",
             "skill monthly-distill 6b の裁定に戻る(彼岸島型/分裂/コンビニ断片)")
        else:
            ok(f"新規頁の途中巻断片 0 (頁化 {len(made)} 頁 / 全体flag {len(tsv_slugs)})")
    else:
        ok(f"solo-truncated 全体flag {len(tsv_slugs)} (今月は頁化なし=情報のみ)")

    # 7. 他言語名の出所の鮮度
    check_other_names_sources()

    print(f"\n結果: FAIL {len(fails)}")
    if fails:
        print("★月次蒸留は完了していない。上のFAILを直す(成功判定=このscriptの exit 0)。")
        sys.exit(1)
    print("→ postflight全通過。skillの報告に上の数値を引用して完了主張してよい。")


if __name__ == "__main__":
    main()
