---
name: cover_transparent_gif_dark_bg
description: 【型・是正済】書影が黒い斑点で汚れて見える正体は「楽天の .gif 書影が透過付きRGBA PNGで返る」+ MANGALのダーク背景。楽天(白背景)では正常に見えるので上流を疑うと外す。対策=書影imgに bg-white
metadata: 
  node_type: memory
  type: project
  originSessionId: dfe047c5-43e6-4938-9211-aad55086f7bb
  modified: 2026-09-02T07:44:54.306Z
---

## 症状

MANGAL の書影に**黒い斑点ノイズ**が乗る(めぞん一刻1巻で2026-09-02にユーザ発見)。
**楽天の商品ページでは同じ画像が正常に見える**ため「楽天の画像が悪い」と誤診しやすい。

## 真因(実測で確定)

- 本番 `cover_url` には **`.gif`** で終わる楽天サムネイルURLが在る
  (例 `https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/4518/9784091804518.gif?_ex=200x200`)。
- そのURLは楽天のサムネイルサーバが **`Content-Type: image/png` の RGBA PNG** に変換して返す。
- めぞん一刻1巻は **12.7% のピクセルが非不透明**(2.9%が完全透明)。
- 楽天のページは**白背景**なので透けても白=正常に見える。MANGALは**ダーク背景**なので
  透過部分から背景色が透けて**黒い斑点**になる。
- 検算 = 同じPNGを白地に合成すると正常、ダーク地(#18181b)に合成するとスクショと同じ斑点が再現した。

## 規模(2026-09-02実測)

- 本番 `data/manga.v2` の `.gif` 書影 = **9,473 URL / 11,205 巻 / 3,983 頁**。
- 300件無作為標本で **7.7% が透明付き** = **約700〜900巻**。
- 該当ISBNは **978409(小学館)の旧作**に集中(ビッグコミックス系)。

## 対策(適用済 = commit bc36609d0)

**書影の img を必ず白地の上に置く**(`bg-white`)。不透明画像には影響しない。
CoverImage / CoverLightbox / ArtBookCard / DailyFeatureCorner(2箇所) / ShinkanRow /
TokushuClient(2箇所) / adult-triage に適用。
★データ側の差し替えは**不可**(`_1_2.jpg` `_1_5.jpg` 等の非透過variantは該当ISBNで404)。

## 今後の書影が増えた時 (= ユーザ質問 2026-09-02)

- **データ側は無対策でよい**。bg-white は**描画側**の対策なので、今後 `.gif` だろうが透過PNGだろうが
  どんな書影URLが増えても自動で効く。cover_url を選ぶ側(promote の `_cover_for` / covers.jsonl.gz)は
  一切触らなくてよい = 恒久策。
- **残っていた唯一の穴 = 新しいコンポーネントで bg-white を書き忘れる**。
  → ★番人 `lib/coverBackdrop.test.ts` を追加(commit c1a528381)。`components/**`・`app/**` の
  `<img>`/`<Image>` を全部数え上げ、`bg-white` が無ければ落とす。書影でない画像は
  タグ内か直前行に **`not-a-cover`** と書いて明示除外する(現状の除外=AiReviewSectionのアバター1件)。
  `npx vitest run` に乗るので deploy-cloudflare / 機能蒸留 / 週次 の前検査で自動的に効く。

## 反映経路(重要)

- **preview** = `components/**` が deploy-preview.yml の trigger に入っているので **push で自動反映**(15-20分)。
- **本番の漫画66k頁 = 週次蒸留でしか届かない**。機能蒸留は `manga/**` をPUTせず、
  チャンクもcontent-hash名なので旧漫画頁は旧チャンクを読み続ける。

関連: [[feedback_cover_oddity_signal]] [[rakuten_cover_data_asset]] [[placeholder_cover_refresh]] [[feedback_one_bug_means_a_class]]
