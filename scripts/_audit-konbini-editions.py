# -*- coding: utf-8 -*-
"""コンビニ廉価/抜粋レーベルの版を検出し、機械的に落とせるものだけ仕分ける (2026-08-30 新設)。

きっかけ: ユーザ「ハレンチ学園の一番上はコンビニだと思う」→ KPC『ドキドキ校内編/ワクワク校外編』366円 =
  講談社プラチナコミックスのテーマ別抜粋本だった。方針メモの掲載除外優先度は
  ①成年誌 ②**コンビニ本** ③纏められないもの。

★**レーベル名だけで決めつけない**。過去の掃引で「imprint一律dropは不可(オリジナルが実在)」と
  結論が出ている([[konbini_reprint_sweep]] 148drop/16hold)。本検出器も
  **楽天の 判型(size)・価格・叢書名** を証拠として併記し、人が裁けるようにする。

■ 判定リストの根拠(2026-08-30 実測)
  HIGH に入れたもの = 楽天の判型が「コミック」・価格が300〜850円・叢書名がコンビニ廉価線と一致。
  ★EXCLUDE に落としたもの(=当初コンビニと誤判定していた):
    - ぶんか社コミック文庫 …… 判型**文庫**(49/49)・価格中央**880円** = 通常の文庫レーベル。コンビニ本ではない
    - 青林堂オンデマンド ……… オンデマンド出版(絶版復刻)。コンビニ流通ではない
    - 山岸凉子/酒井美羽/高橋葉介 等の「作家名+セレクション」…… 1100〜1320円の作家別選集
    - デュオ(・)セレクション系 … 判型**新書**のBLレーベル
  ★「セレクション」という語だけで拾うと上のような正規レーベルを巻き込む。必ず証拠列を見ること。

■ 自動dropしてよい条件 (3つすべて。作品が消えないことを機械で保証する)
  ① imprint が HIGH に一致
  ② **同じ頁に他の版が残る**
  ③ その版の巻数が主版より少ない(= 抜粋・一部再録)

出力: docs/production-diagnostics/konbini-triage.tsv
  bucket A=自動drop可 / B=高確度だが巻数が主版以上(全巻再録の疑い・要確認) /
         C=単独版(落とすと作品が消える。[[never_delete_because_broken]]) / D=レーベル要判定 /
         E=裁定済み(候補に当たるがコンビニではないと確認済。SETTLED に根拠あり)

  python scripts/_audit-konbini-editions.py
"""
import collections, io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
RAK = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "konbini-triage.tsv")

# ★コンビニ廉価/抜粋であることがレーベル名だけで確定するもの(証拠は上のdocstring)
HIGH = re.compile(
    r'^(KPC|KPC ?mini|講談社プラチナコミックス|プラチナS・girlセレクション|'
    r'Shueisha ?home ?remix|集英社ホームリミックス|Birz ?comics ?remix|'
    r'(食)?Akita ?top ?comics( ?wide)?|秋田トップコミックス|'
    r'ジャンプ[ 　]?(・)?コミック(ス)?[ 　]?(・)?セレクション|ジャンプC・セレクション.*|'
    r'ヤングジャンプ・コミックスセレクション|My ?First ?BIG.*|マイファーストビッグ.*)$', re.I)
# ★裁定済み = 候補には当たるが**コンビニ廉価本ではない**と証拠つきで確認したもの(2026-08-30)。
#   再掲すると毎回同じ調査をやり直すことになるので、根拠を添えてここに固定する。
SETTLED = {
    "ぶんか社コミック文庫": "判型=文庫(28/28)・価格中央869円。ぶんか社の通常の文庫レーベル",
    "青林堂オンデマンド": "オンデマンド出版(絶版の受注生産復刻)。コンビニ流通ではない",
    "山岸凉子スペシャルセレクション": "1320円・潮出版社 希望コミックス。作家別の作品集で廉価本ではない",
    "秋田コミックスセレクト": "★1984年刊・641〜748円・叢書=秋田コミックス・セレクト。"
                       "『恐怖新聞(1)〜(5)』と通し番号が振られた大判再刊で、"
                       "コンビニ廉価本(90年代後半〜)より前の版。抜粋ではない",
    "デュオセレクション": "判型=新書・619円。BL系の新書レーベル",
    "デュオ・セレクション": "判型=新書・641円。同上",
    "デュオ・セレクション・オリジナル": "判型=新書・660円。同上",
    "バンブーコミックス 潤恋オトナセレクション": "770円・竹書房の通常レーベル",
    "ワイド版高橋葉介ベストセレクション": "1100円のワイド判作品集。同頁の他版も1巻のみで落とすと作品が消える",
}
# 候補として拾うが HIGH でないもの(=人が裁く)。ここに当たらないレーベルは最初から見ない
CAND = re.compile(
    r'コンビニ|my ?first ?big|マイファーストビッグ|platinum|プラチナ|remix|リミックス|廉価|'
    r'セレクション|オンデマンド|top ?comics|トップコミックス|kpc|蔵出し|'
    r'ぶんか社コミック文庫|秋田コミックス(セレクト|スペシャル)', re.I)


def main():
    eds = collections.defaultdict(list)
    with io.open(FLAT, encoding="utf-8") as f:
        h = next(f).rstrip("\n").split("\t")
        I = {k: h.index(k) for k in h}
        for l in f:
            c = l.rstrip("\n").split("\t")
            if c[I["is_version"]] == "1" or not c[I["number"]].isdigit():
                continue
            eds[(c[I["slug"]], c[I["ed_idx"]])].append(c)

    cands = {k: v for k, v in eds.items()
             if CAND.search((v[0][I["ed_imprint"]] or "") + " " + (v[0][I["ed_label"]] or ""))}
    want = {c[I["isbn13"]] for v in cands.values() for c in v if c[I["isbn13"]]}
    info = {}
    with io.open(RAK, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            i = str(o.get("isbn") or "")
            if i in want and i not in info:
                it = o.get("item") or {}
                info[i] = (it.get("itemPrice") or 0, it.get("size") or "", it.get("seriesName") or "")

    rows = []
    for (slug, ei), vs in sorted(cands.items()):
        imp = (vs[0][I["ed_imprint"]] or "").strip()
        others = [k for k in eds if k[0] == slug and k[1] != ei]
        omax = max((len(eds[k]) for k in others), default=0)
        isbns = [c[I["isbn13"]] for c in vs if c[I["isbn13"]]]
        pr = sorted(info[i][0] for i in isbns if i in info and info[i][0])
        med = pr[len(pr) // 2] if pr else 0
        sz = collections.Counter(info[i][1] for i in isbns if i in info and info[i][1])
        ser = collections.Counter(info[i][2] for i in isbns if i in info and info[i][2])
        hi = bool(HIGH.match(imp))
        if not others:
            b = "C_単独版(消すと作品が消える)"      # ★安全側の事実を最優先で表示する
        elif imp in SETTLED:
            b = "E_裁定済み(コンビニではない)"
        elif hi and len(vs) < omax:
            b = "A_自動drop可(高確度×他版あり×主版より少ない)"
        elif hi:
            b = "B_高確度だが巻数が主版以上(要確認)"
        else:
            b = "D_レーベルが要判定"
        rows.append((b, imp, vs[0][I["ed_label"]], slug, vs[0][I["title"]], len(vs), omax, med,
                     sum(1 for c in vs if c[I["has_cover"]] == "1"),
                     ",".join(k for k, _ in sz.most_common(2)),
                     ",".join(k for k, _ in ser.most_common(1)),
                     ";".join(isbns[:3])))
    rows.sort()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("bucket\timprint\tlabel\tslug\ttitle\t巻数\t同頁の最大他版巻数\t価格中央値\t書影数\t判型\t楽天叢書名\tISBN\n")
        for r in rows:
            f.write("\t".join(str(c) for c in r) + "\n")
    print("コンビニ候補の版: %d → %s" % (len(rows), os.path.relpath(OUT, ROOT)))
    for k, v in sorted(collections.Counter(r[0] for r in rows).items()):
        print("  %-46s %d" % (k, v))
    print("\n--- D(要判定)のレーベル分布。判型と価格が判断材料 ---")
    d = [r for r in rows if r[0].startswith("D_")]
    for imp, n in collections.Counter(r[1] for r in d).most_common():
        s = [r for r in d if r[1] == imp]
        print("  %3d  %-28s 価格中央%-6s 判型%s" % (n, imp[:26],
              (sorted(x[7] for x in s if x[7]) or ["?"])[len([x for x in s if x[7]]) // 2],
              collections.Counter(x[9] for x in s if x[9]).most_common(1)))


if __name__ == "__main__":
    main()
