---
name: genre_from_rakuten_story_plan
description: 【✅実装完了 2026-06-17】楽天あらすじ→ジャンル/タグ。教師あり学習→信頼度較正→2パス救済→方法D直接パッチ。本番manga.v2に genre 6,638作/tag 7,395作 純粋追加。全記録=docs/genre-rakuten-learning.md
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

## ★実装完了(2026-06-17)= 全記録 `docs/genre-rakuten-learning.md`

5フェーズで実施し本番反映済([[genre_quality_improvement]]の中核):
- **①caption強化**=巻番号順に複数巻あらすじ連結(`corpus-v2.jsonl`)。
- **②信頼度較正**=held-out3000をhigh/medium/lowで再分類→ラベル別の適合率を測り**採用閾値**決定(信頼度で適合率が単調上昇=閾値運用有効)。採用=13ジャンル/26タグ。
- **③本番分類**=対象20,682作(provisional 8,793 ∪ theme tag未保有 20,660)をworkflow分類→閾値超だけseed化。
- **④2パス救済**=グレー帯を別エージェントが本文で厳格再判定。**isekai/gourmet 96%確証(truth-gap救出)・drama過付与58%棄却**。
- **⑤方法D**=`_genre_rakuten_apply_inplace.py`でseedを本番manga.v2のgenres/tags欄だけに純粋追加(promote通さず・他不変)。**genre 6,638作・tag 7,395作**。typecheck/test211緑。

### ★再利用できる重要知見
- **truth-gap**: 教師ラベル(AniList/Wiki)は不完全→測定Pは**下限値**。本文を読むLLMの方が正しい例が多い(isekai/gourmet/school/料理)。**2パス救済 or タグとのクロス確証**で真値を裏取りできる。
- **gag/romcom/samurai/4-koma は教師ゼロ**=この源で学習不可(AniList語彙がComedy/Romance/Historical/形式に吸収)。
- **具体ラベルは当たる/抽象は壊滅**: タグでも Food/Isekai/野球/BL/格闘技は高P、Philosophy/Tragedy/成長物語/癒し系は壊滅。
- **信頼度しきい値**で中精度ジャンル(comedy/action/sci-fi/horror)をhigh限定で安全採用できる。
- 成果物: seed=`data/seeds/genre-rakuten.yml`/`tag-rakuten.yml`(git追跡)、promoteにloader結線済(将来の全promoteでも同結果)。manga.v2はgit非追跡=seedから再反映可。
- 残: provisional ~2,149作は高精度ラベル取れずAI暫定のまま。tag救済(Phase④のタグ版)は未実施(genre優先で実施)。

---

## 当初方針(2026-06-16 確定、 以下は実施済の元計画)

## 狙い
本番 manga.v2 の **`genres_provisional:true`(=AI推定の低信頼)が 32,167件 / 48%**。ここを楽天あらすじ由来の高精度ジャンルで底上げする。

## なぜ楽天ストーリーか
- ⭐**誤マッチゼロ**: itemCaption は **ISBN紐付け**=その作品その巻に確実結合。AniList題名照合は約10%が疑わしいリンク([[anilist_link_quality]])で別作ジャンルが紛れるが、楽天経由は原理的に起きない。
- 内容ベース分類はメタデータ推測より当たる。
- 著作権OK: キャプションを**AI入力にして分類ラベルを出す**のは変換的利用(本文再掲しない)→安全。表示用にあらすじ本文を出すのは別問題(逐語NG・要約要)。

## ★順序 = 「いきなり振らず、まず学習」(ユーザ強調)
1. **教師コーパス抽出**: trusted(AniList genres+themes ∪ Wikipedia、できれば**2源一致**で高純度)が埋まっている作品 × 楽天ストーリー有り の **(あらすじ本文, 既知ジャンル/要素)ペア**。概算 trusted≈34,000のうちキャプション有り≈1.5〜2万件=校正に十分。
2. **学習+検証(held-out)**: train/testに分け、学習側で覚え→test側予測→**既知ジャンルを再現できたかでジャンル別 適合率/再現率を算出**。当たるジャンル/外すジャンルを数字で把握。
3. **振る(apply)**: provisional/未ラベル × ストーリー有り に、**精度が閾値以上のジャンルだけ**付与。`genres_rakuten` 印 + 多数決の一票。**trusted/手動は上書きしない**。

## 手段(どれか/ハイブリッド)
- A: **埋め込み+kNN/軽量分類器** — 推論LLM不要=安価・決定的・監査可(近傍の既知作を根拠提示)。多ラベル前提。
- B: **LLM few-shot** — ジャンル別代表ペアをin-context注入。既存fill workflow流用で着手速い。
- 推奨: 埋め込みkNNで近傍既知作を引き→それをfew-shot実例にLLM最終判定(根拠も残る)。

## 実測データ(2026-06-16)
- 楽天キャプション: 全246,228 ISBN中、分類に使える40字+が**44%(110,548)**、無キャプション54%。=**高精度・部分カバー**(precision高/recall中)源。作品単位カバーはもっと高い(1巻紹介文が厚い)。
- データ実体: `data/seeds/harvest/rakuten-isbn.jsonl.gz`(復元後 `.cache/rakuten-isbn.jsonl`)。

## 注意
- ラベルノイズ(AniList粗・Wiki雑音)→2源一致を高信頼教師に。
- クラス不均衡(war/mahou-shoujo等希少)→ジャンル別閾値で弱いジャンルは振らない。
- **クローズド32キー厳守**([[ai_genre_closed_vocabulary]]、新語禁止)。
- **タグ(要素)はジャンルより難**(AniListタグ=構造化英語語彙)。まずジャンル32キーで精度を出し、タグは後段。

着手時の最初の一手 = **step0: 教師コーパスの作品単位件数を確定**(trusted∩キャプション有り)。
