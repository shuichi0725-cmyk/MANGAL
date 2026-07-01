---
name: ai-genre-closed-vocabulary
description: 蒸留でAIがジャンル付与する時はmaster32キーから文言を選ぶだけ(新語禁止)+低信頼マーク。表はdata/genres.yml=正本
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

蒸留で **AI がジャンルを付与する時は、 master 32 キーの中から「文言を持ってくる」だけ**。新語の創作・英語混入・表記揺れは禁止。該当が無ければ未付与でよい(`other` 行きより未付与を優先)。AI 由来は必ず `genres_provisional: true` で低信頼マーク(後から「AI 推定」と判別できるように)。

**Why:** AI が drama/comedy/romance を過剰付与し二系統が並存した反省([[genre_quality_improvement]])。closed vocabulary に縛れば表記揺れ・英語混入・タクソノミー膨張を機械的に防げる。trusted(AniList genres+themes ∪ Wikipedia ∪ 手動)を主、AI は trusted が空の時だけの fallback=裏取り役。

**How to apply:**
- 正本テーブル = `data/genres.yml`(32 キー、変更時はここが基準。CLAUDE.md の表も同期更新)。
- AI fallback 時のみ master キーから選定 → `genres_provisional: true` を立てる。
- backstop: `lib/loadData.ts` が master 外キーを reject(build で弾く)。
- ★スポーツは野球/サッカー以外を増やさない。★タクソノミー新規キー追加はユーザ裁定マター(AI は選ぶだけ)。

master 32 キー(key=表示名): action=アクション adventure=冒険 fantasy=ファンタジー sci-fi=SF mystery=ミステリー horror=ホラー gag=ギャグ comedy=コメディ romcom=ラブコメ romance=恋愛 drama=ドラマ slice-of-life=日常 school=学園 sports=スポーツ baseball=野球 soccer=サッカー historical=歴史 samurai=時代劇 mecha=メカ yokai=妖怪 gourmet=グルメ 4-koma=4コマ漫画 essay=エッセイ漫画 isekai=異世界 bl=ボーイズラブ suspense=サスペンス music=音楽 supernatural=超常 ecchi=お色気 mind-game=頭脳戦 mahou-shoujo=魔法少女 war=戦争

詳細ページの「ジャンル/要素」分離 = [[clustering_unit_is_series]] 系の表示設計と別。要素欄は AniList タグの和訳(`data/seeds/tag-i18n.yml`)で、ジャンル(master)とは別物。
