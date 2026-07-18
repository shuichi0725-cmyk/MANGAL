---
name: anilist-link-quality
description: "【✅解消 2026-07-18】AniListリンク誤り(bardock型)=検証ゲートで全リンク裁定済(drop813/relink616/FAIL0)。歴史記録。現行機構は[[anilist_link_verification_plan]]"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-12 ユーザ実機発見(ドラゴンボール本編にBardock読切のあらすじ)→「測定だけ慎重に」で全数測定済み。
## ✅修正済み(2026-06-13 commit c092d880)
- **relink 568件**: relations(日本語native題)で「兄弟に完全一致」を見つけ本編へ付け替え(ONE PIECE→30013/ドラゴンボール→30042 等、正しいあらすじ復活)。`_relink-anilist-s3.py`→`s3-relink-map.json`。
- **drop 374件**: S1読切/S2巻数乖離/S4章数僅少 or 複数シグネチャ で relink先無し → enrich除外。`anilist-link-overrides.yml`(action:relink/drop)、enrich builderが読む。
- ★**S3単独のstripは不採用**(BLOOD+↔ブラッドプラス等ラテンvsカナ・記号違いで同一作を誤dropするため)。S3単独~3,497は温存(将来relations relinkで精緻化余地)。
- 仕組み: `_gen-anilist-link-overrides.py`(suspects+relink-map→override)/`_build-anilist-enrich-map.py`(relink優先・drop除外を適用)。次promoteで本番反映済み。

## 症状の構造
match-v14が**本編keyに同franchiseのスピンオフ/読切/番外編のAniList ID**を与える(bardock型)。1誤リンク→synopsis/英題/ジャンル/タグ/slugの4-5表示が汚染。slug層は長さガードで防御済(2026-06-11)だがリンク自体は誤ったまま。

## 測定結果(`_audit-anilist-link-quality.py`、S判定39,493中)
- 疑惑hit **3,967(10.0%)** → `.cache/anilist-link-suspects.tsv`
- S1 ONE_SHOT割当=99 / S2 巻数大乖離=202 / S4 章数僅少=215 / S3 romaji末尾過剰=3,607
- ★**あらすじ誤表示が実際に出ているのは3,238ページ**
- 確例: ドラゴンボール(59巻)→Bardock読切 / ドラえもん→藤子伝記 / ガンダムW→ENDLESS WALTZ / 電車男・ときめきトゥナイト・神のみ・ゴッドハンド輝 等、複数シグネチャ同時hit組は全部この型。
- ★S3単独(~3,300)には正当も混在(AniList romajiが副題込み正式長題=同一作)→ **「余分な末尾がうちの副題と一致するか」での精緻化が次の測定**。

## 修正方向(裁定済みの選択肢、実行はGO待ち)
- (a) 疑惑リンクを**剥がす**(安全・synopsis等も消える=誤情報より無い方が誠実)
- (b) dumpの**relations+popularityで同franchiseの本体IDに付け替え**(dump v3にrelationsあり=機械で確証付き再結線可能)
- ★どちらも**Pythonスクリプト化でClaudeトークンほぼゼロ**(ユーザのコスト懸念に対する答え)。機械裁定で割れない分だけHaiku/Sonnet副エージェント。
- 入力資産: `.cache/anilist-manga-dump-v3.jsonl.gz`(format/volumes/chapters/relations/popularity全部入り)+ match-v14-all.tsv + suspects.tsv。

関連: [[anilist_matching_state]][[merge_needs_external_proof]](逆パターン=AniListが別作を1 idに束ねる)[[display_data_polish_tasks]]
