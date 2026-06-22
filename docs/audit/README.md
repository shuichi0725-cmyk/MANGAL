# 巻 出力サニティ監査 (本番 yml = data/manga.v2)

生成器: `scripts/_audit-volume-output.py`（read-only）。本番 yml を直接読み、promote の
merge/dedup が**出力側に作った穴**を検出する。種2 sqlite を読む `_audit-volume-numbering.py`
では原理的に見えなかった層（菜の #1 欠落型）を補完する。

## 全量結果 (2026-06-22 / 66,357作品 / 69,588edition)

| 型 | 件数 | RECOVERABLE | SOURCE_GAP |
|---|---|---|---|
| **MISSING_VOL1** (#1欠落) | 629 | **143** | 486 |
| **GAP** (中抜け) | 656 | **80** | — |
| **PUBLISHER_MIX** (別社混入) | 1,928 | — | — |
| **DATE_DISORDER** (発売日逆行) | 485 | — | — |

- **RECOVERABLE** = 欠番がソース(種2)に存在する = promote が落とした = **機械的に復元可能**（復元候補ISBN付き）。最優先。
- **SOURCE_GAP** = ソースにも無い = 真の取りこぼし = 種4補完の領域（MADB未収録）。
- TSV の `recover_isbn` 列 = 復元候補ISBN（多数派出版者線を優先＝本物の版）。

## 各 TSV

- `audit-vol-output-missing1.tsv` — #1欠落（RECOVERABLE 先頭ソート）
- `audit-vol-output-gap.tsv` — 中抜け欠番
- `audit-vol-output-pubmix.tsv` — 1版内ISBN出版者記号混在（少数派巻数降順）
- `audit-vol-output-datedisorder.tsv` — 巻番号順の発売日逆行（逆行年数降順）

## 注意（誤検出の傾向）

- **DATE_DISORDER / PUBLISHER_MIX の大型案件は多くが「別社の復刻版が1つの standard 版に畳まれた」
  多版統合(multi-edition)問題**（例: 鬼平犯科帳=文藝春秋＋リイド社、サザエさん=姉妹社＋…）。
  これは「混入除去」でなく**版を分離**して直すべき（[[multi_edition_unification_pending]]）。
- 古典の全集・復刻(大全集等)は番号が非時系列なことがあり DATE_DISORDER が出るが正常な場合あり。
  → いずれも**自動修正せず人手裁定**。本監査は surfacing 専用。

## 菜(sai) = 試金石

3型すべてで捕捉: MISSING_VOL1(欠[1]・RECOVERABLE・復元=`9784063193824`講談社本物) /
PUBLISHER_MIX(講談社9＋別社2) / DATE_DISORDER(30.7年逆行)。ground-truth=菜12巻/ふたたび3巻(別作)。
