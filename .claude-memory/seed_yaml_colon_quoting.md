---
name: seed-yaml-colon-quoting
description: "seedへの機械追記で「: 」を含む値は必ずquote(2026-07-27に同一ミス4連発)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: db595250-4c34-4603-b151-4b5dbb1db69e
  modified: 2026-07-27T06:06:40.557Z
---

YAML seed(volumes-supplement / volume-exclude / edition-canonical 等)へ文字列を機械追記する時、値に「: 」(コロン+空白)や引用符・カンマが含まれると未quoteでパース破損する。

**Why:** 2026-07-27の1セッションで同じミスを4回踏んだ(note内「監査: 」×2、canonical source内、種4 note内)。★壊れたseedのままreflectが走ると**promoteが例外を握りつぶして注入なしで頁を再生成**し、silentなデータ欠落になる(ロザリオ13-14巻で実害一歩手前)。series_keyのsub:部分にカンマ/コロンを含む実例あり(ネオ・キャット)。

**How to apply:** 機械生成の文字列値は一律 `'...'`(内部の'は''に)でquoteする。追記後は必ず `yaml.safe_load` 検証→**それからreflect**。src頁の`_skey:`行をregexで拾う時は複数行折返しに注意(種2から引き直すのが正)。
