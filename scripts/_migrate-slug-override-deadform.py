# -*- coding: utf-8 -*-
"""slug-overrides.yml の「死に形」を promote が読む形へ移行する(2026-09-05 ユーザGO)。

背景: promote の `_slug_override` は `doc["overrides"]` 配下の **入れ子dict(slugキー付き)しか読まない**。
      トップレベルの平坦形 `old: new` は書いても永久に効かず、過去に裁定済みの slug 是正が
      静かに無効化されていた(実測 143件中 116件が旧slugのまま公開中)。
      発覚= ユーザ指摘「猫と紳士のティールーム = ティールームがヘボン」(2026-09-05)。

やること(--apply で実行。既定は dry-run):
  1. 平坦形を全部 `overrides:` 配下の {slug, reason, at} へ移行
  2. ★安全ゲート: 移行先slugが 既に公開中 / 他の移行先と重複 / SRCが存在しない → **その行は移行しない**
  3. 実際に公開slugが変わる頁について redirect を張る
     - data/slug-aliases.yml と public/_redirects に 旧slug→新slug
     - ★既に旧slugを指しているリダイレクトは**新slugへ張り替える**(チェーンを作らない)
  4. 反映対象の SRC stem を .cache/slug-migrate-stems.txt に出す(_reflect-targeted.py --only へ)

可逆: 変更前の3ファイルを .cache/slug-migrate-bak-<ts>/ に退避する。
"""
import argparse
import io
import json
import os
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

SOP = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
ALIAS = os.path.join(ROOT, "data", "slug-aliases.yml")
REDIR = os.path.join(ROOT, "public", "_redirects")
STEMS = os.path.join(ROOT, ".cache", "slug-migrate-stems.txt")
LF = chr(10)


def read_lines(p):
    s = io.open(p, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in s else LF
    return s.replace(eol, LF).split(LF), eol


def write_lines(p, lines, eol):
    io.open(p, "w", encoding="utf-8", newline="").write(LF.join(lines).replace(LF, eol))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    doc = yaml.safe_load(io.open(SOP, encoding="utf-8")) or {}
    live = {k: v for k, v in (doc.get("overrides") or {}).items()
            if isinstance(v, dict) and v.get("slug")}
    flat = {k: v for k, v in doc.items() if k != "overrides" and isinstance(v, str) and v}
    flat.update({k: v for k, v in (doc.get("overrides") or {}).items() if isinstance(v, str) and v})

    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    published = {r[F["slug"]] for r in idx["d"]}
    live_targets = {v["slug"] for v in live.values()}

    move, hold = {}, []
    seen_target = {}
    for old, new in sorted(flat.items()):
        src = os.path.join(ROOT, "data", "manga", old + ".yml")
        if not os.path.exists(src):
            hold.append((old, new, "SRC(data/manga/<key>.yml)が無い=このキーでは引かれない"))
            continue
        if new in published and new not in flat:          # 別頁が既にその公開slugを使っている
            hold.append((old, new, "移行先slugが既に公開中(%s)" % new))
            continue
        if new in live_targets:
            hold.append((old, new, "移行先slugを既存overrideが使用中"))
            continue
        if new in seen_target:
            hold.append((old, new, "移行先slugが %s と重複" % seen_target[new]))
            continue
        seen_target[new] = old
        move[old] = new

    # ★連鎖/入れ替えは丸ごと保留(2026-09-05): 移行先slugが**別の平坦形のキー**でもある場合、
    #   両方が同時に移行できないと片側だけ適用され「良いslugが空くだけ」になる。
    #   実例: happy-4010->happy(SRC無で保留) と happy->happy-hama-1994(移行可) の対。
    #   さらに旧slugが別頁の公開slugとして生き返る形なので redirect も張れない。両方外す。
    _targets = set(flat.values())
    _chain = [o for o, n in move.items() if o in _targets or n in flat]
    for o in _chain:
        hold.append((o, move[o], "入れ替え/連鎖の一部(このslug自体が別エントリの移行先)=両方揃わないので保留"))
        del move[o]

    changing = {o: n for o, n in move.items() if o in published}   # 実際に公開slugが変わる頁
    print("平坦形(死に形) %d件 → 移行 %d / 保留 %d" % (len(flat), len(move), len(hold)))
    print("  うち公開slugが実際に変わる頁: %d" % len(changing))
    for o, n, why in hold:
        print("  [保留] %-46s -> %-40s %s" % (o, n, why))
    if not a.apply:
        print(LF + "(dry-run。適用は --apply)")
        return

    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(ROOT, ".cache", "slug-migrate-bak-" + ts)
    os.makedirs(bak, exist_ok=True)
    for p in (SOP, ALIAS, REDIR):
        io.open(os.path.join(bak, os.path.basename(p)), "w", encoding="utf-8", newline="").write(
            io.open(p, encoding="utf-8", newline="").read())
    print("backup: " + bak)

    # ---- 1. slug-overrides.yml を書き換え(平坦形を除去 → overrides配下へ入れ子で追加) ----
    lines, eol = read_lines(SOP)
    flatkeys = set(flat)
    out = []
    for l in lines:
        if l and not l.startswith(" ") and ":" in l and l.split(":", 1)[0] in flatkeys:
            continue                                    # トップレベル平坦形を落とす
        if l.startswith("  ") and not l.startswith("    ") and l.rstrip().endswith(":") is False \
           and ":" in l and l.strip().split(":", 1)[0] in flatkeys:
            continue                                    # overrides配下のstr形も落とす
        out.append(l)
    oi = [i for i, l in enumerate(out) if l == "overrides:"][0]
    blk = []
    for old in sorted(move):
        blk += ["  %s:" % old,
                "    at: '2026-09-05'",
                "    reason: 平坦形(promoteが読まない死に形)で書かれていた既裁定のslug是正を、効く入れ子形へ移行(ユーザGO 2026-09-05)",
                "    slug: %s" % move[old]]
    out[oi + 1:oi + 1] = blk
    write_lines(SOP, out, eol)
    chk = yaml.safe_load(io.open(SOP, encoding="utf-8")) or {}
    n_live = sum(1 for v in (chk.get("overrides") or {}).values() if isinstance(v, dict) and v.get("slug"))
    n_dead = sum(1 for k, v in chk.items() if k != "overrides" and isinstance(v, str))
    n_dead += sum(1 for v in (chk.get("overrides") or {}).values() if not (isinstance(v, dict) and v.get("slug")))
    print("slug-overrides.yml: 効く形 %d件 / 残る死に形 %d件" % (n_live, n_dead))

    # ---- 2. redirect(既存チェーンの張り替え + 新規追加) ----
    al, aeol = read_lines(ALIAS)
    repointed = 0
    for i, l in enumerate(al):
        if ":" in l and not l.startswith("#"):
            k, v = l.split(":", 1)
            if v.strip() in changing:                   # 旧slugを指していたaliasを新slugへ
                al[i] = "%s: %s" % (k, changing[v.strip()])
                repointed += 1
    have = {l.split(":", 1)[0] for l in al if ":" in l and not l.startswith("#")}
    while al and al[-1] == "":
        al.pop()
    added = 0
    for o, n in sorted(changing.items()):
        if o not in have:
            al.append("%s: %s" % (o, n))
            added += 1
    al.append("")
    write_lines(ALIAS, al, aeol)
    print("slug-aliases.yml: 張り替え %d / 追加 %d" % (repointed, added))

    rd, reol = read_lines(REDIR)
    rp = 0
    for i, l in enumerate(rd):
        parts = l.split()
        if len(parts) >= 2 and parts[1].startswith("/manga/"):
            tgt = parts[1][len("/manga/"):]
            if tgt in changing:
                rd[i] = "%s /manga/%s 301" % (parts[0], changing[tgt])
                rp += 1
    havep = {l.split()[0] for l in rd if l.strip() and not l.startswith("#")}
    while rd and rd[-1] == "":
        rd.pop()
    ad = 0
    for o, n in sorted(changing.items()):
        if ("/manga/" + o) not in havep:
            rd.append("/manga/%s /manga/%s 301" % (o, n))
            ad += 1
    rd.append("")
    write_lines(REDIR, rd, reol)
    print("_redirects: 張り替え %d / 追加 %d" % (rp, ad))

    # ★掲載外(non-manga-drop)の頁は promote が出力しないので反映対象から外す(2026-09-05)。
    #   入れると _reflect-targeted.py の検証ゲートが「promote後にファイル無し」で止まる。
    #   override の記録自体は残す(将来 drop が解けたら効く)。
    _dropped = set()
    _ndp = os.path.join(ROOT, "data", "seeds", "non-manga-drop.yml")
    if os.path.exists(_ndp):
        _txt = io.open(_ndp, encoding="utf-8").read()
        _dropped = {m for m in move if ("[slug=%s]" % m) in _txt}
    _stems = [m for m in sorted(move) if m not in _dropped and os.path.exists(
        os.path.join(ROOT, "data", "manga.v2", m + ".yml"))]
    io.open(STEMS, "w", encoding="utf-8").write(LF.join(_stems) + LF)
    print("反映対象 %d stem (掲載外 %d 除外) → %s" % (len(_stems), len(move) - len(_stems), STEMS))


if __name__ == "__main__":
    main()
