# 連載誌の根拠台帳 (magazine-evidence)

頁ごとに「どこで調べて・何が出たか・いつ」を貯める台帳。 2026-11-07 新設。
目的 = **「まだ調べていない」と「調べたが見つからなかった」を分ける**(本番ではどちらも同じ空欄に見える)。

- 連載誌の**値**の正本は今まで通り 種3 + `data/seeds/magazine-corrections.yml`(promote が読む)。 この台帳は**根拠**の正本で、 本番には何も書かない。
- 一覧表は写し = `docs/production-diagnostics/magazine-ledger.tsv`(全頁)/ `magazine-ledger-summary.tsv`(誌×状態の集計)。
  `python scripts/_magazine-ledger.py build` で毎回作り直す(約20秒)。 **表を手で直さない**。

## ファイル

| ファイル | 型 | ソース | 調べた範囲 |
|---|---|---|---|
| `madb-shoshutsu.jsonl` | 一括 | MADB 単行本の初出欄(cm101) | MADB に巻が1冊でも在る頁(★2020年以降の巻は NDL 由来で初出欄が無い) |
| `madb-mokuji.jsonl` | 一括 | MADB 雑誌目次(cm106×metadata108×cm102) | 全頁(★目次が在るのは約40誌・昭和〜2010年代) |
| `rakuten-caption.jsonl` | 一括 | 楽天 itemCaption の「〜で連載」 | 巻が1冊でも楽天キャッシュに在る頁。 ★弱い根拠 |
| `wiki-list.jsonl` | 追記 | ja.wikipedia 雑誌の掲載作品一覧(13記事) | 当たった頁だけ記録(当たらなかった頁は未調査扱い) |
| `wiki-article.jsonl` | 追記 | ja.wikipedia 作品記事の Infobox | 全頁(2026-11-07: 本文ダンプ 11/1 版で照合) |
| `manual.jsonl` | 追記 | 人が読んで決めたもの | 1頁ずつ |

- **一括型** = 1行目 `{"_meta": {source, checked_at, data_as_of, method, via}}`、 以降**調べた頁ごとに1行** `{"slug", "hits": [...]}`。
  `hits` が空 = 調べたが見つからず。 取り直すとファイルごと置き換える(前の版は git 履歴)。
- **追記型** = 1行 = 1回の確認 `{"slug", "hits", "at", "ref"}`。 同じ頁の確認は**重ねて合わせる**(後の「なし」で前の「あり」を消さない = 別の記事・別の方法のことがある)。 確認日は一番新しい日。
- `hits` の1件 = `{"mag": 雑誌マスタのkey または "?誌名"(マスタに無い), "raw": ソースの誌名, "n": 回数/冊数, "ref": 抜粋}`。
- slug = 公開slug(`data/manga-list-index.json` の slug)。

## 守ること

- ★**失敗(429・瞬断・壊れた行)は書かない**。 書いてよい「見つからず」は、 手元の完全なデータを引いて無かった時か、 相手が正常に応答して空だった時だけ([[feedback_no_negative_record_on_failure]])。
- ★誌名 → key は `_magazine-ledger.py` の `resolve` を使う。 週刊/月刊・「+」を落として寄せない(2026-11-07: 旧 `wiki_mag_lib.canon` が 月刊少年チャンピオン→週刊少年チャンピオン、 少年ジャンプ+/月刊少年ジャンプ→週刊少年ジャンプ に寄せていた)。 1つの書き方が2誌に当たる別名は使わない。
- NDL は連載誌を持たない(2026-11-04 実測: MADB 内の NDL 由来 29,398 冊で初出 0)= ソースにしない。

## Wikipedia 作品記事の判定(2026-11-07)

- 欄の選び方 = 欄の題が頁の題と合う + **作画者**(作者/作画/漫画/著者)が合う欄。 原作者だけ合う欄は採らない(別の漫画版)。 QID でつながった記事で欄が1つなら作者照合なし。
  掲載誌が複数(移籍)の時は先頭 = 初出誌だけを強い根拠に数え、 2つ目以降は `"sub": true`。
- 記事の探し方 = 題・表記ゆれ・「(漫画)」・転送(リダイレクト)・Infobox の題からの逆引き。
- `ref` が「漫画の記事なし(本文ダンプ)」= 上のどの探し方でも、 漫画の Infobox を持つ記事が本文ダンプ(11/1 版・漫画記事 11,467 本)に無かった。
  ★**題名が大きく違う記事は拾えていない**(= 「無い」と言い切れるのは題で引ける範囲だけ)。
- ★API(api.php)は 10件ずつ・3秒間隔でも **15回ほどで 429**(11/4・11/7 とも)。 大量に見る時は本文ダンプ
  (`.cache/jawiki-dump/jawiki-latest-pages-articles-multistream.xml.bz2` 4.9GB・毎月1日ごろ更新)を落として `sweep-wiki-dump`。
  抜き出し(漫画記事+転送)は約30分で `.cache/jawiki-dump/manga-articles.jsonl` / `redirects.tsv` に残る。

## 取り直し

```
python scripts/_magazine-ledger.py sweep-madb      # MADB を新しいリリースで取り直した後(.cache/magazine-lists/madb-*.jsonl)
python scripts/_magazine-ledger.py sweep-rakuten   # 楽天キャッシュが新しくなった後
python scripts/_magazine-ledger.py sweep-wiki-dump # Wikipedia 本文ダンプを新しくした後(同じ記事の判定は2回しない)
python scripts/_magazine-ledger.py build
```
