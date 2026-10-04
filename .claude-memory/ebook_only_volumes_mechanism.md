---
name: ebook_only_volumes_mechanism
description: 【機構】電子書籍のみで出た巻を巻の並びの続きに「電子のみ」札で出す(案2・2026-10-04)。seed=ebook-only-volumes.yml、isbn13は持たない
metadata:
  type: project
---

2026-10-04 ユーザ裁定「案2」(無人島でエルフと共同生活@COMIC: 紙1〜8巻・9/10巻は電子のみで完結)。
選択肢は 1注記だけ / 2巻の並びの続きに札付き / 3電子版タブ / 4帯 で、**2** を採用。

- seed `data/seeds/ebook-only-volumes.yml`(キー=SRC slug)→ promote が**全edition操作の後・書影最終充填の前**に
  edition_type の先頭の版(刷タブにも)の末尾へ `ebook_only: true` の巻を足す。同番号が在れば足さない(紙が出たら自然に退く)。
- 巻の欄: `ebook_only`/`kobo_url`(lib/schema.ts)。`kindle_asin` は既存欄。isbn13 は**持たない**
  (電子に振られた番号=10巻 9784867947265 は楽天紙/NDLに無い。ISBN照合・消失監視を壊す)。
- 表示(components/VolumeCoverflow.tsx): サムネに青「電子」札 / 詳細に「📱 電子書籍のみ」+注記(Kobo書影の注意書きは出さない)/
  紙の店(楽天/Yahoo!/Amazon)を隠す / Kindle=/dp/ASIN・Kobo=商品ページへ直接。
- 完結は status-corrections(source=publisher-official)。索引は total_volumes=10・完結。
- ★1件目のみ手で seed 化。 他作品への展開(電子続巻の候補表 kobo-digital-continuation.tsv は7/30から空)は未着手=ユーザ裁定待ち。
関連 [[ebook_only_editions_out_of_scope]] [[version_tabs_stock_ebook]]

## 2026-10-04 調査: 同じ型(紙が止まり続巻が電子のみ)の広がり(調査のみ・未反映)
- 道具 `scripts/_kobo-dcont-harvest.py` を改良: `--scope stopped`(連載中に限らない=紙最終から12か月で日付判定が完結にするため ongoing だけだと本命を落とす)/
  「第N巻」を巻として読む(旧=無人島型を見逃す)/ 著者ゲート / 紙の巻数=max_edition_volumes。
- 対象(2巻以上・紙最終2012〜半年前・完結確定でない)= 20,543作・全件照会 約7.4時間(楽天Kobo 1.3秒/作)。
- 無作為300 → 電子のみの候補 9(3%)/ 単話の混入 5 → 全体推定 約600作(幅 300〜1,100)。 新しい順300 → 電子のみ3・電子先行9・単話5。
- ★副産物: 紙の続巻が出ているのに MANGAL 未掲載(ティアムーン12・千輝くん15・玉座と小夜啼鳥23(POD))= 別の型。
- 要確認の型: 電子だけ巻の割り方が違う(麻雀放浪記風雲篇 紙5→電子12)/ 単話は価格<400円 or 巻番号が飛ぶで判定。
- 表: docs/production-diagnostics/ebook-only-continuation-survey.tsv / 仕分け .cache/_dcont_classify.py・_dcont_sample.py。
- ★全件調査 完了(2026-10-05 07:2x・20,503作・約8h・中断0): 電子のみ(照合一致)398作/725巻・照合できず49・分巻の疑い223・単話206・
  電子先行20・紙は発売済(MANGAL未掲載)10。 表 docs/production-diagnostics/ebook-only-continuation.tsv(道具 _kobo-ebook-only-survey.py)。
  電子のみの最初の巻の年: 2026が81作(最近の分は後から紙が出る可能性=様子見)。 未掲載10作(SHIORI EXPERIENCE 23・無能なナナ15・凍牌ミナゴロシ篇10 等)は別の取りこぼし。
  採用は1件ずつ(紙の不在を NDL でも確かめる・長い題は楽天の題検索が外れる恐れ)。
