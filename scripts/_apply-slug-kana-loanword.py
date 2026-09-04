# -*- coding: utf-8 -*-
"""カタカナ外来語のヘボン転写slugを英語綴りへ是正する(CLEAR層のみ・2026-09-05 ユーザGO)。

入力: docs/production-diagnostics/slug-kana-loanword.tsv の DEVICE_DIFF_CLEAR 行
      (= 装置案の英語をカナのローマ字へ逆置換すると現公開slugに戻る=差は外来語の綴りだけ、
        かつ カタカナ連が辞書語で丸ごと覆える、かつ 日本語側のハイフン構造が不変)

★機械ゲートを通っても**意味で誤る**ものが在るので、EXCLUDE に理由付きで列挙して外す。
  2026-09-05 の実査で見つけた3型:
    超人ロック系      親頁が choujin-locke。rock にすると同一シリーズが2綴りに割れる
    鍵師ロック        主人公は金庫を開ける錠前師=ロックは lock(rock ではない)
    アウト・ロー      ヨミ アウトロー(outlaw)。out-roo は語を割った壊れた案

処理(--apply): slug-overrides.yml へ入れ子形で追記 → slug-aliases.yml に 旧→新 を追記
              → _gen-redirects.py で public/_redirects と .cache/redirects.json を再生成
              → 反映対象stemを .cache/slug-loanword-stems.txt へ
可逆: 変更前を .cache/slug-loanword-bak-<ts>/ に退避。
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

TSV = os.path.join(ROOT, "docs", "production-diagnostics", "slug-kana-loanword.tsv")
SOP = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
ALIAS = os.path.join(ROOT, "data", "slug-aliases.yml")
STEMS = os.path.join(ROOT, ".cache", "slug-loanword-stems.txt")
LF = chr(10)

EXCLUDE = {
    "kagishi-rokku": "鍵師ロック=主人公は金庫を開ける錠前師(六田錠二)。ロックは lock であって rock ではない",
    "autoroo": "アウト・ロー(ヨミ=アウトロー/outlaw)。out-roo は語を割った壊れた案",
}
EXCLUDE_PREFIX = {
    "choujin-rokku": "超人ロック系は親頁が choujin-locke(聖悠紀)。rock にすると同一シリーズが2綴りに割れる",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rows = []
    for i, l in enumerate(io.open(TSV, encoding="utf-8").read().split(LF)):
        if i == 0 or not l.strip():
            continue
        p = l.split("\t")
        if len(p) >= 4 and p[0] == "DEVICE_DIFF_CLEAR":
            rows.append((p[1], p[2], p[3]))

    doc = yaml.safe_load(io.open(SOP, encoding="utf-8")) or {}
    ov = doc.get("overrides") or {}
    live_targets = {v["slug"] for v in ov.values() if isinstance(v, dict) and v.get("slug")}
    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    published = {r[F["slug"]] for r in idx["d"]}

    # ★pub -> SRC stem の逆引き(2026-09-05): TSVのキーは公開slug、overrideのキーは SRC stem。
    #   一度 override で改名済みの頁は data/manga/<公開slug>.yml が無いので逆引きが要る
    #   ([[pubslug_src_stem_generator_trap]])。見つかったら**既存 override の slug を更新**する。
    pub2stem = {v["slug"]: k for k, v in ov.items() if isinstance(v, dict) and v.get("slug")}

    move, update, hold, seen, alias_pairs = {}, {}, [], {}, {}
    for pub, cand, title in rows:
        why = None
        if pub in EXCLUDE:
            why = EXCLUDE[pub]
        for pre, r in EXCLUDE_PREFIX.items():
            if pub.startswith(pre):
                why = r
        key = pub if os.path.exists(os.path.join(ROOT, "data", "manga", pub + ".yml")) else None
        is_update = False
        if not why and key is None:
            st = pub2stem.get(pub)
            if st and os.path.exists(os.path.join(ROOT, "data", "manga", st + ".yml")):
                key, is_update = st, True          # 既存overrideの値を更新する
            elif os.path.exists(os.path.join(ROOT, "data", "seeds", "preorder-pages", pub + ".yml")):
                why = "preorder-pages 由来(SRCが data/manga に無い)=別ルートで直す"
            else:
                why = "SRC(data/manga/<slug>.yml)が無く override 逆引きでも見つからない"
        if not why and key in ov and not is_update:
            why = "既に override が在る(二重指定)"
        if not why and cand in published:
            why = "移行先slugが既に公開中"
        if not why and cand in live_targets:
            why = "移行先slugを既存overrideが使用中"
        if not why and cand in seen:
            why = "移行先slugが %s と重複" % seen[cand]
        if why:
            hold.append((pub, cand, title, why))
            continue
        seen[cand] = pub
        (update if is_update else move)[key] = cand
        alias_pairs[pub] = cand      # ★301のキーは**現公開slug**(SRC stemではない)

    print("CLEAR %d行 → 新規 %d / 既存override更新 %d / 除外 %d"
          % (len(rows), len(move), len(update), len(hold)))
    for p, c, t, w in hold:
        print("  [除外] %-42s -> %-34s %s" % (p, c, w))
    if not a.apply:
        print(LF + "(dry-run。適用は --apply)")
        return

    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(ROOT, ".cache", "slug-loanword-bak-" + ts)
    os.makedirs(bak, exist_ok=True)
    for p in (SOP, ALIAS):
        io.open(os.path.join(bak, os.path.basename(p)), "w", encoding="utf-8", newline="").write(
            io.open(p, encoding="utf-8", newline="").read())
    print("backup: " + bak)

    s = io.open(SOP, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in s else LF
    lines = s.replace(eol, LF).split(LF)
    oi = [i for i, l in enumerate(lines) if l == "overrides:"][0]
    blk = []
    for old in sorted(move):
        blk += ["  %s:" % old,
                "    at: '2026-09-05'",
                "    reason: カタカナ外来語のヘボン転写を英語綴りへ(CLEAR層=逆置換で現slugに戻る+カタカナ連が辞書で全被覆+日本語側のハイフン不変。ユーザGO 2026-09-05)",
                "    slug: %s" % move[old]]
    lines[oi + 1:oi + 1] = blk
    if update:
        # ★既存 override の slug 行だけを差し替える(キー行の直後ブロック内の "    slug: " を探す)
        for k, c in update.items():
            ki = [i for i, l in enumerate(lines) if l == "  %s:" % k]
            if not ki:
                print("  !! 既存override行が見つからない: %s" % k)
                continue
            i = ki[0] + 1
            while i < len(lines) and lines[i].startswith("    "):
                if lines[i].startswith("    slug:"):
                    lines[i] = "    slug: %s" % c
                    break
                i += 1
    io.open(SOP, "w", encoding="utf-8", newline="").write(LF.join(lines).replace(LF, eol))
    chk = yaml.safe_load(io.open(SOP, encoding="utf-8")) or {}
    print("slug-overrides.yml: 効く形 %d件" % sum(
        1 for v in (chk.get("overrides") or {}).values() if isinstance(v, dict) and v.get("slug")))

    s2 = io.open(ALIAS, encoding="utf-8", newline="").read()
    eol2 = "\r\n" if "\r\n" in s2 else LF
    al = s2.replace(eol2, LF).split(LF)
    have = {l.split(":", 1)[0].strip() for l in al if ":" in l and not l.strip().startswith("#")}
    while al and al[-1] == "":
        al.pop()
    n = 0
    _all = dict(move)
    _all.update({k: v for k, v in update.items()})
    for o, c in sorted(alias_pairs.items()):
        if o not in have:
            al.append("%s: %s" % (o, c))
            n += 1
    al.append("")
    io.open(ALIAS, "w", encoding="utf-8", newline="").write(LF.join(al).replace(LF, eol2))
    print("slug-aliases.yml: 追加 %d" % n)

    r = subprocess.run([sys.executable, "scripts/_gen-redirects.py"], cwd=ROOT)
    if r.returncode != 0:
        sys.exit("abort: _gen-redirects.py 失敗")

    io.open(STEMS, "w", encoding="utf-8").write(LF.join(sorted(_all)) + LF)
    print("反映対象 %d stem → %s" % (len(_all), STEMS))


if __name__ == "__main__":
    main()
