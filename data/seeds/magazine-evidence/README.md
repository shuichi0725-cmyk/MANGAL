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
| `wiki-article.jsonl` | 追記 | ja.wikipedia 作品記事の Infobox | 1頁ずつ |
| `manual.jsonl` | 追記 | 人が読んで決めたもの | 1頁ずつ |

- **一括型** = 1行目 `{"_meta": {source, checked_at, data_as_of, method, via}}`、 以降**調べた頁ごとに1行** `{"slug", "hits": [...]}`。
  `hits` が空 = 調べたが見つからず。 取り直すとファイルごと置き換える(前の版は git 履歴)。
- **追記型** = 1行 = 1回の確認 `{"slug", "hits", "at", "ref"}`。 同じ頁は最新の確認を使う。
- `hits` の1件 = `{"mag": 雑誌マスタのkey または "?誌名"(マスタに無い), "raw": ソースの誌名, "n": 回数/冊数, "ref": 抜粋}`。
- slug = 公開slug(`data/manga-list-index.json` の slug)。

## 守ること

- ★**失敗(429・瞬断・壊れた行)は書かない**。 書いてよい「見つからず」は、 手元の完全なデータを引いて無かった時か、 相手が正常に応答して空だった時だけ([[feedback_no_negative_record_on_failure]])。
- ★誌名 → key は `_magazine-ledger.py` の `resolve` を使う。 週刊/月刊・「+」を落として寄せない(2026-11-07: 旧 `wiki_mag_lib.canon` が 月刊少年チャンピオン→週刊少年チャンピオン、 少年ジャンプ+/月刊少年ジャンプ→週刊少年ジャンプ に寄せていた)。 1つの書き方が2誌に当たる別名は使わない。
- NDL は連載誌を持たない(2026-11-04 実測: MADB 内の NDL 由来 29,398 冊で初出 0)= ソースにしない。

## 取り直し

```
python scripts/_magazine-ledger.py sweep-madb      # MADB を新しいリリースで取り直した後(.cache/magazine-lists/madb-*.jsonl)
python scripts/_magazine-ledger.py sweep-rakuten   # 楽天キャッシュが新しくなった後
python scripts/_magazine-ledger.py build
```
