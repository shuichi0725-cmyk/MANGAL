# production-diagnostics 台帳の共通形 (= reason列方式。2026-08-20 制定)

ギャラ型是正(`gyara-anomalies.tsv`)で有効だった「**なぜ自動で触らなかったかを機械が書き残す**」形を
他の監査台帳へ横展開するための規約。残務が件数でなく**型**で見えるようになる。

## 形

- 台帳は **TSV**(CSV禁止 = ユーザ明示)。1行 = 1判定単位(頁/版/著者ペア等、台帳ごとに固定)。
- **最終列に `reason`** を持つ。値は3種:
  - **空** = 新規・未裁定(検出されたが誰も見ていない)
  - **`保留: <理由>`** / **`正史: <根拠>=許容`** / **`<型ラベル>: <説明>`** = 触らない判断とその根拠。
    可能なら裁定日 `(YYYY-MM-DD裁定)` を末尾に付ける
  - **`済(YYYY-MM-DD): <処置>`** = 是正済み。どの機構で直したか(seed名/scriptなど)を書く
- **検出器は再実行時に旧TSVの reason を引き継ぐ**(キー列join。台帳ごとにキーを固定:
  例 vol-date-regression = slug+edition / author-not-in-volumes = slug+著者名)。
  再走で裁定が消えない = 台帳が「残す判断」の一次ソースになる。
- 既存の**先頭の分類列**(excerpt-subtitle の `分類`、deluxe-label-split の `class` 等)は
  「検出器の機械分類」でありそのまま残す。reason は「**人/AIの裁定**」で別物。両方あってよい。

## 適用済み

| 台帳 | キー | 適用日 |
|---|---|---|
| gyara-anomalies.tsv | slug+edition | 2026-08-17(発祥) |
| vol-date-regression.tsv | slug+edition | 2026-08-20(検出器が引き継ぎ対応済) |
| author-not-in-volumes.tsv | slug+巻書誌に無い著者 | 2026-08-20(検出器が引き継ぎ対応済) |

## 未適用(次に触る時に同じ形へ)

excerpt-subtitle.tsv / edition-mix.tsv / deluxe-label-split.tsv / cover-dup.tsv ほか。
一気に書き換えない(各検出器の再走コストが高い)。**その台帳を次に触る機会に**
①検出器へ reason 引き継ぎを足す ②既裁定分に `済(日付)`/`保留:` を書く、の2点だけやる。
