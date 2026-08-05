---
name: edition-overrides-key-is-public-slug
description: edition-overrides.jsonのキーは公開slug(slug-override後)。SRC stemで書くと死にキー=一度も適用されない(15件発掘・是正済)
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-05T02:31:14.494Z
---

# edition-overrides のキーは公開slug (= 2026-08-05 カムイ外伝で発覚)

**promoteは `_slug_override(slug)` 適用後の公開slugで edition-overrides.json を引く。** slug-override頁(SRC stem≠公開slug)の overrides を **SRC stemで書くと死にキー**になり、エラーも警告も出ず一度も適用されない。

**Why:** カムイ外伝(SRC=kamuigaiden/公開=kamui-gaiden)で、2026-07のper-case版手術(ビッグC+小学館文庫12+決定版11・楽天全確証)が死にキーで眠っていた。頁内容がoverridesと部分一致していたため「適用済み」に見えていた。全量監査で**死にキー15件**発掘: 真の死に7件(q-e-d/dr-slump/abashiri-ikka/sp-2000/c-minor/源氏egawa/reset)は是正で手術が実効化、8件は後日正キーで再手術済みの陳腐化複製(`_dead_*`へ退避)。

**How to apply:**
- overridesに書く前に **slug-overrides.yml でそのstemが公開slugに変わらないか確認**し、キーは必ず公開slug。
- 死にキー是正は「古い手術が現行頁を上書きする」回帰リスクを伴う(手塚タブ型)→ **before/after差分検品必須**。実測: q-e-d=v1喪失(真のv1 9784063336597 1998-12を復元)・あばしり=文庫幽霊巻v7喪失(復元)の2回帰。
- ★data/manga.v2 は **gitignore**(66k=git外)= 回帰時にgit HEADから頁は復元できない。復元源= .preview-data(subset)/stale索引の逆引き/種2/楽天。
- 再発防止候補(未実装): promoteが「どの頁にも一致しないoverridesキー」を警告する。

関連: [[edition-canonical-mechanism]] [[feedback-one-bug-means-a-class]]
