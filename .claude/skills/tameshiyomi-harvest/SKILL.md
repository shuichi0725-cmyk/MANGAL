---
name: tameshiyomi-harvest
description: 試し読み拾って=BookLiveの試し読みリンク(title_id)を魚で収集しseed化。判断はscript、AIは保留裁定のみ。Sonnet運転前提
---

# 試し読み拾って (= BookLive title_id 収集。2026-07-12 設計、同日★全巻展開を追加)

MANGALの「📖 試し読み」ボタン用に、BookLiveの作品ID(title_id)を集めて
`data/seeds/tameshiyomi-booklive.jsonl`(= シリーズ単位アンカー) と
`data/seeds/tameshiyomi-booklive-volumes.jsonl.gz`(= ★巻単位の実データ、ボタンが読むのはこっち) に貯める。
**収集だけがこのskillの仕事**(ボタンUI/中継/via_cd注入は別作業=このskillでは触らない)。

## ★全巻展開の発見 (= 2026-07-12、ユーザ「ドラゴンボールなら42巻分取らないとダメよ？」で判明)

BookLiveのtitle_idは**シリーズ/版単位**。product頁の`vol_no`パスやbviewerのcid末尾3桁を
変えるだけで**同一title_idのまま全巻に到達できる**(TinyFish検索は不要・HEADチェックのみで済む)。
実証済: `title_id/582763`(チェンソーマン)で`vol_no/001`→1巻、`/002`→2巻。
`bviewer cid=582763_001/_002`、`185409_001/_025`、`185407_100` 全部HEAD200。
帰結: **アンカー(シリーズ→title_id)さえ集めれば、巻ごとの追加検索は不要**。
`cid=f"{title_id}_{vol:03d}"` を `max(total_volumes, max_edition_volumes)` 分HEAD検証するだけ
(= `_tameshiyomi-harvest.py --expand`)。TinyFish検索が要るのは**新規シリーズのtitle_id発見時だけ**。

## 収集するのは title_id(+巻の実在HEAD確認)だけ (= 2026-07-13 ユーザ裁定)

**購入ページURLは収集しない**。試し読みビューアも購入ページも `title_id`+`巻番号` から決定的に生成できる:
- 試し読み: `booklive.jp/bviewer/s/?cid=<title_id>_<巻3桁>`
- 購入: `booklive.jp/product/index/title_id/<title_id>/vol_no/<巻3桁>`
アフィリエイトパラメータもURL生成時(ボタンUI実装側)に付ける。収集の仕事を勝手に増やさない。

## NEVER (最重要・全部実害防止)

- **title_idを推測や連番で作らない**。scriptの検索+検証を通ったものだけがseedに入る
  (= ただし全巻展開の`vol_no`/cid末尾3桁を変える手法は実証済みの例外、これは検索でなくHEAD検証)
- **保留の採用は証拠付きのみ**: `--accept` する前に、候補title_idのBookLive頁の題・著者が
  MANGAL頁と一致することをsnippet/fetchで自分の目で確認。曖昧なら保留のまま残す(残すのは正常)
- **seedを手で編集しない**(追記はscript経由のみ。壊すと全ボタンが死ぬ)
- TinyFishは**無料枠のみ**(Fetch/Search)。Agent/Browserは絶対に使わない(クレジット消費)
- 1回の**検索(--limit)**実行は100まで。それ以上は分割(TinyFish 150req/分制限)。
- 検索失敗/エラーで止まったら**そのまま再実行**(再開可能設計)。リトライ連打しない

## ★★ BookLiveアクセス規約 (= 2026-08-29 制定。規制を受けた事故の再発防止。最優先で守る)

**2026-08-29にBookLive!からアクセス規制を受けた。** 原因と再発防止を必ず頭に入れてから触ること。

### 何をやらかしたか(実測値)
2026-08-28に入れた「尾の自動再訪」が、最終配信巻より上の404を毎回「未チェック」に戻すため
**同じシリーズを永久に叩き直す無限ループ**になった。そこへ「BookLiveは大手CDNだからHEADは安全」
という**根拠のない思い込み**で入れた8並列・間隔なし(しかも実体はHEADでなくGET)が重なり、

| 指標 | 実測 |
|---|---|
| 送信回数(下限) | **2,778,133** |
| 単独最多 | meitantei-conan **383,708回**(1シリーズ・全110巻) |
| 命中率 | 先頭40万件=89〜90% → **以降231万件が連続0.0%** |
| 2026-08-29の新規リンク | **0件**(前日8/28も21件) |

= **得るものがゼロのまま数百万回叩いていた**。規制されて当然。

### 以後の規約(ゆるめる時はユーザ裁定を取る)
1. **直列のみ。並列は禁止**。最短間隔 2.0秒/リクエスト(NDLの1.3秒より保守的に)。
   `check_cid()` が強制する。BookLive宛の生 urlopen をその場で書かない。
2. **1実行1,500件まで**。超えたら正常終了して次回に回す。
3. **200/404以外は1件でも即中断**(429/403/5xx/timeout/接続断)。★台帳に書かない。
   = 「規制されている」を「試し読みが無い」と誤記録して**偽404を永久固定する**のが最悪の副作用。
   本体は exit 2 を返し、ループが**停止札**を置いて二度と起動しなくなる。
4. **連続300件ヒット無しでも中断**(200で別頁を返す「静かな規制」の保険)。
5. **完了は掃引済み台帳(`.cache/tameshiyomi/expand-swept.jsonl`)で判定**。
   尾の再訪は「巻数nが増えた時」か「前回掃引から30日経った時」だけ。毎バッチ再訪しない。
6. **収穫ゼロが3バッチ続いたらループ停止**(無限ループの最終防波堤)。
7. アイドル運転は **1起動12バッチ・バッチ間300秒** が既定。

### 停止札 (= 規制中の再突入防止)
- `docs/production-diagnostics/BOOKLIVE-BLOCKED.md`(git追跡=別PCにも効く)
- `.cache/tameshiyomi/BLOCKED`(ローカル)
どちらかが在る間、`_idle-tameshiyomi-expand-loop.sh` は**起動を拒否**する。
**札を消してよいのはユーザが「復帰した」と言った時だけ**。自分で試し打ちして確かめない。
復帰手順は札の中身に書いてある(robots.txt確認 → `--expand-limit 1` を手で1回 → 札を消す)。

## 手順 (= この順で回す)

```
1. python scripts/_tameshiyomi-harvest.py --stats                   # 現在地(アンカー数/保留/全巻展開数)
2. python scripts/_tameshiyomi-harvest.py --limit 100               # 新規シリーズのtitle_id発見(検索。人気順)
3. python scripts/_tameshiyomi-harvest.py --expand --expand-limit N # ★アンカー済み全シリーズを全巻展開(検索不要・高速)
4. python scripts/_tameshiyomi-harvest.py --review                  # 保留一覧
5. (保留の裁定) 各行について:
   - 魚で `site:booklive.jp <題>` を検索し直し、候補title_idの頁題がMANGAL題と同一作品か確認
   - 確信が持てたものだけ: python scripts/_tameshiyomi-harvest.py --accept <slug>=<title_id>
   - 確信なし/BookLiveに無い作品 → 保留のまま放置(それが正しい)
   - accept後は忘れず3を再実行(新規acceptしたslugも全巻展開する)
6. commit+push:
   git add data/seeds/tameshiyomi-booklive.jsonl data/seeds/tameshiyomi-booklive-volumes.jsonl.gz docs/production-diagnostics/tameshiyomi-holds.tsv
   git commit -m "試し読みharvest: +N件(保留M)/全巻展開+K巻" && git push
```

## scriptが保証していること(理解用・いじらない)

- 対象選定=本番索引の人気順(popularity)上位から未収集・未保留のみ
- 採用ゲート=①題の正規化**完全一致**(部分一致は保留) ②著者姓がsnippetに存在
  ③ビューアURL(`bviewer/s/?cid=<id>_001`)の**HEAD 200実在検証**。3つ揃わないと自動採用しない
- 出力=jsonl純粋追加(証拠snippet・検証日付き)・保留=tsv。再実行で重複しない
- `--expand`=アンカー済み(title_id確定)シリーズについて、`data/manga-list-index.json`の
  `total_volumes`/`max_edition_volumes`を上限にcid各巻を**直列HEAD**検証、200のみ
  `tameshiyomi-booklive-volumes.jsonl.gz`に`{slug, volume, title_id, cid}`で純粋追加。
  既に検証済みの巻はskip(再開可能)。1シリーズ完了ごとに件数を表示。
  ★完了判定は掃引済み台帳(expand-swept.jsonl)。2026-08-29時点で**33,080シリーズ掃引済み・残36
  (=41リクエスト)**。この柱は実質もう枯れている = 復帰しても長時間回す仕事は無い

## 保留の典型と裁定のコツ

- **完全一致なし**: 表記ゆれ(ONE PIECE⇔ワンピース等)や巻数付き題。BookLive頁を魚でfetchして
  題+著者が一致すれば --accept。シリーズ違い(0巻/外伝)を本編と間違えないこと
- **複数候補**: 無印と新装版/カラー版が並ぶ。**無印(通常版)のtitle_id**を選ぶ
- **候補0**: BookLiveに無い(古書・成年など)。放置

## 報告形式

`アンカー合計X件(+今回N) / 保留Y件(うち今回裁定でZ件採用) / 全巻展開=W巻(V件シリーズ完了)`

## 関連

- 魚の使い方=skill tinyfish / ボタンUI・中継(/go)実装=別途(Claude本体の作業)
- 将来: シーモアはビューアURL規則が不透明なため、ASP提携後に別途設計

## ★デルタ恒常化 (= 2026-08-06 ユーザ指示「日々増える新作を取得」)

- queue は索引から毎回再算出+**latest_date降順**(新しい作品から拾う)。**popularity=0の足切りは廃止**
  (新作・マイナー作はpop0=旧ゲートだと永久に収集されなかった)。除外=収集済seed∪保留holds。
- 帰結: 日次/週次で新規頁が増えると**次バッチの先頭に自動で並ぶ**。特別なqueue再算出は不要=
  「試し読み拾って」を時々回すだけで新作が追随する。旧作のpop0層(~3万)も列の後方に入った=長期の被覆拡大。
- 表示側は data/tameshiyomi-map.json(`_gen-tameshiyomi-map.py`)がビルド時joinの正=週次の事前再生成で更新。
