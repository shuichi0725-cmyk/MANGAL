---
name: repo-is-public-github
description: 【前提】github.com/shuichi0725-cmyk/MANGAL は public リポジトリ。コミットする前に「公開してよいか」を判断する。認証情報は .gitignore 済みで漏れていない(確認済み)
metadata: 
  node_type: memory
  type: project
  originSessionId: b13171da-074b-4da8-a8b5-905f74606a97
  modified: 2026-09-04T11:05:44.443Z
---

**`https://github.com/shuichi0725-cmyk/MANGAL` は public**(2026-09-04 匿名GETで確認: HTTP 200 / API `"private": false`)。
push した瞬間に世界に公開され、**git履歴からは消せない**前提で扱う。

## 確認済み(2026-09-04)

- `.gitignore` に `.env` と `.env*.local` があり、追跡されているのは値が空の `.env.example` のみ。
  **R2 / 楽天 / PA-API の認証情報は git に入っていない**。
- IndexNow の鍵 `public/efa08a89….txt` は公開リポジトリに在るが、これは**仕様上どのみち公開必須**のファイル
  (ユーザ裁定「おいて問題ない」2026-09-04)。詳細は [[indexnow_self_submit]]。

## How to apply

- ★**鍵・トークン・URL署名の類をコミットする前に、まず public かどうかを確認する**。
  今回、私は確認より先に鍵を commit & push し、ユーザが設置の可否を判断する前に既成事実にした(手順ミス)。
  **判断を仰ぐ材料を出す段階では、まだ push しない**。
- 新しい秘密を扱う時は `.env.local`(gitignore済)に置き、ビルド時に生成物へ流し込む形にする。
- 生成物 `out/` と `public/` は**そのまま本番で配信される**ので、ここに置いたものは全部公開物。

関連: [[feedback_production_deploy_gate]] [[hosting_worker_r2_architecture]]
