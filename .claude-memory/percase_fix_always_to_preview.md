---
name: percase_fix_always_to_preview
description: per-case修正は直したら必ずテスト環境(preview)に上げてユーザに確認させる
metadata:
  type: feedback
---

**per-case で頁を直したら、その頁を必ず `.preview-data/manga/` に入れて push する。**
反映(`_reflect-targeted.py`)だけで終わらせない。

**Why**: 2026-08-08 ユーザ明示「なおしたらテストページにあげて確認させてね」。
本番 `data/manga.v2` に書いても**公開されるのは週次蒸留**なので、ユーザはそれまで結果を目で確認できない。
`_reflect-targeted.py` の preview 同期は **既に preview に在る頁しか上書きしない**(新規頁・未投入頁は
「preview同期0」となり静かに素通りする)ため、per-case で触った頁は明示コピーが要る。

**How to apply**:
1. `cp data/manga.v2/<stem>.yml .preview-data/manga/`(**ファイル名=SRC stem**。公開slugではない)
2. masters を触ったら `data/{magazines,genres,publishers,demographics,publisher-aliases}.yml` も
   `.preview-data/` へコピー(未同期だと enum backstop で preview ビルドが落ちる)
3. `python scripts/_build-list-index.py .preview-data/manga .preview-data`
4. `git add .preview-data && commit && push`
5. ★**push後15-20分待つ・追いpush禁止**([[preview_deploy_pitfalls]])。ユーザには待ち時間を伝える。
- drop した頁は preview からも消えていることを確認する(`--drop` は自動で消す)。

関連: [[reflect_protocol_fast]] [[drop_page_redirect_chain]] [[feedback_production_deploy_gate]]
