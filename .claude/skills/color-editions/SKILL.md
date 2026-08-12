---
name: color-editions
description: カラー版して/カラー版続けて=電子カラー版柱(Koboハーベスト→照合seed→頁ストリップ+一覧)。電子続巻して=紙が止まり電子だけ進む作品の検出。試し読み結線も本柱
---

# 電子カラー版柱 (= 2026-07-30 新設。トリガー「カラー版して」「カラー版続けて」「電子続巻して」)

電子書籍にしかない**カラー版**を収集し、作品頁に「🎨 電子カラー版 全N巻」ストリップと
一覧 `/color-manga` を出す柱。[[ebook_only_editions_out_of_scope]] の「将来柱」の実体化。

## ★表示は停止中 (= 2026-08-02 ユーザ要望「勝手につけられた。元にもどしたい」)

頁ストリップ/一覧の表示は `public/data/color-editions.json` を **{} に空化**して止めてある。
★**手順2(build)は public JSON を再生成する=走らせると表示が復活する**。収集(手順1/差分)は
いつ回してもよいが、**build以降はユーザの表示再開GOが出るまで走らせない**。

## パイプライン (= この順で回す)

```
1. python scripts/_kobo-color-harvest.py     # ★全量版(2026-08-03): {カラー版,フルカラー}×ジャンル再帰分割×多ソートunion(全上書き)
1b. python scripts/_kobo-color-harvest.py --delta   # 差分(新着だけ追記・数分)=アイドル運転の柱⑪
2. python scripts/_color-editions-build.py   # 束ね→本番照合→seed+public JSON+unmatched TSV ★表示復活=GO必須(上記)
3. python scripts/_color-tameshiyomi.py --limit 30   # BookLive title_id収集(③試し読み・resumable)
4. (3の後) 2を再実行 → JSON の b に結線
5. commit+push(テスト環境)。本番=機能蒸留 or 週次(public/data/color-editions.json + チャンク)
```

### 全量harvestの設計 (= 2026-08-03 ユーザ裁定「明らかに取得数が少ない。全部取得+アイドルで差分」)

- 旧: title=カラー版×101904×2ソートunion=窓上限~6,000 → 3,779冊で頭打ち。★「フルカラー」
  (「版」なし表記=TL/BL/単話系に多い)が検索語に無く丸ごと漏れていた。
- 新: キーワード{カラー版, フルカラー} × countが3,000超のスライスは子ジャンル(GenreSearch APIで
  動的取得・.cacheに永続)へ再帰分割 → 葉でも超える時は8ソートの窓union(±releaseDate/±itemPrice/
  sales/standard/reviewCount/reviewAverage)。dedup=itemNumber・_rate_gate直列・429backoff吸収。
- ★単話/分冊/合本のノイズ除去は**buildの仕事**(rawは全部持つ=[[acquire_all_obtainable_info]])。
- ★build側も2026-08-13に対称修正(ユーザ指摘「収集が少なすぎない?」): harvestは{カラー版,フルカラー}なのに
  buildの対象判定が「カラー版」substringのみ=**フルカラー(版なし)層4,705冊/511群を捨てていた**→FC_MARK解禁。
  照合fallback追加=①第N部トークン除去(ジョジョ6部型) ②部題のみ(ジョジョリオン型) ③中間ー読みー除去
  (To LOVEるダークネス型) ④第1〜5部→本題頁へ畳み込み+巻数合算(ジョジョ本編63巻型。N≤5限定=6部以降は別頁が正)。
  166→209作。残unmatched=大半が紙の無いwebtoon/TL系(正当)+SBR(頁題STEEL BALL RUNのカタカナ不一致)+ジョジョランズ(頁未作成)。

## データの居場所

| 何 | どこ |
|---|---|
| 生harvest | .cache/kobo-color-raw.jsonl (再引き直し可・git外) |
| 確定seed | data/seeds/color-editions.yml (build全置換生成) |
| 頁表示用 | public/data/color-editions.json = {slug:{v巻数,u楽天affURL,c表紙,t表示題,b=BookLive title_id}} |
| 試し読みseed | data/seeds/color-tameshiyomi.jsonl (**純粋追記のみ**・buildが読む) |
| 未照合queue | docs/production-diagnostics/color-editions-unmatched.tsv (AI裁定→照合改善) |
| 表示 | ★2026-08-12現行: components/ColorCorner.tsx(ホームのコーナー・全集直上) + app/color-manga(一覧)。両方とも書影タップ=**Kindle検索直行**(lib/kindleLink.ts。ASIN無しのためアプリ着地=PA-API解錠後に/dp直リンク化)。ColorEditionNote(頁ストリップ)は**マウント除去済み=停止中**(2026-08-02ユーザ裁定。再開はユーザGO) |

## 照合の鉄則 (= 同題decoy対策。巻抜けfill 2026-07-29 の教訓)

- 残差題完全一致(norm)+★**著者ゲート**(交差ゼロは採用しない→unmatched行き)
- 分冊版/単話/合本/セット/期間限定 はノイズ除外
- Kobo APIは1クエリ3,000件上限 → sort=±releaseDate の2パスunion(harvest実装済)
- レート1.3秒/req・Referer/Origin必須([[external_data_access]])

## 電子続巻(相方の柱・「電子続巻して」)

```
python scripts/_kobo-dcont-harvest.py --limit 50   # ongoing作をlatest降順に走査(resumable)
```
- Kobo最大巻>紙最大巻 → docs/production-diagnostics/kobo-digital-continuation.tsv に候補。
- ★**報告層のみ・自動seed化禁止**(Koboの採番は新装版でズレる。採用は個別裁定=だろう運転禁止)。
- 全ongoing走査は長時間=アイドル枠で回す。429/失敗=中断→同コマンド再実行で再開。

## 試し読み(③)の鉄則 (= tameshiyomi-harvest と同基準)

- 採用=結果題がカラー版display題とnorm完全一致 かつ bviewer HEAD200 のみ。曖昧=保留(.cache/color-tame-holds.tsv)
- TinyFishは無料枠のみ・1回100件まで。title_idの推測/連番生成は絶対禁止
- URL生成: 試し読み=booklive.jp/bviewer/s/?cid=<title_id>_001 / 購入=…/title_id/<id>/vol_no/001
