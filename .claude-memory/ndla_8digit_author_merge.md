---
name: ndla-8digit-author-merge
description: "種2の作者表で別人が合体する型(NDL典拠IDを8桁で切って名寄せ)= 2026-10-20 ユーザGOで是正済み。promote が本のクレジットで分け直す(識別子は8桁のまま=全桁にすると新作の作者が空欄)"
metadata:
  node_type: memory
  type: project
  originSessionId: 4eb881fe-cc0f-412d-b718-0578babc3249
  modified: 2026-10-20T03:16:11.853Z
---

**型**: `scripts/_build-mangaka-madb.py` が metadata504 の `ma:ndla`(NDL典拠ID)を `re.search(r"(\d{8})")` で取り、`ndl:<8桁>` を mangaka の識別子にして**名寄せ**している。典拠IDは8桁(19,802人)と**9桁(27,127人)**があり、9桁の頭8桁が同じ人(=同時期に典拠登録された隣のID)が**1人に合体**する。例: 喜月かこ(001211922)→瞳ちご、さちも(001161075)→桜日梯子、nikuhen(034109169)→みつたに。★**原作+作画の2人が同時登録で隣のIDになり1人に潰れる**のが多い(サイコアゲンスト 原作平石六+作画景山愁 / 外科医エリーゼ 原作yuin+作画mini)。

**規模(2026-10-20)**: 衝突キー4,213 / 作者表の合体行3,168名 / series の結び19,575。

**是正(2026-10-20 ユーザ「1直したい」)**: ★識別子は**全桁にしない** = 種2の作者表は `ndl:<8桁>` で登録済み・populate は新しい作者行を足さない(qid が表に在る作者だけ結ぶ)ので、全桁にすると新作の作者が**空欄**になる。代わりに:
- `scripts/_gen-ndla-merged-groups.py` → `data/seeds/ndla-merged-groups.json`(合体行の名前 → 組の全員の名前。同名の別行が在る105名は外す)。月次 intake の **ndlagroups 段**(promote の前)
- promote `_split_ndla_merged`(get_authors → apply_author_corrections の直後・_apply_book_credit の前): 本のクレジット(metadata101-clean の schema:creator)に載る組の名前へ分け直す。2人載れば2人に、役割は巻書誌 `madb-role-credits` の[原作]過半数=原作欄 / [作画]過半数=artist、タグ無しは元の役割のまま。組の外の人は足さない・クレジットに誰も居なければ触らない
- 初回フルpromote: 作者欄が変わった頁 236(分け直し188・改名6・役割)。前回の「別人」リスト119頁中107頁が直った。残り10 = 同名の別行が在る名前(西野リュウ等)・クレジットに組の人が居ない・兎/兔の字違い
- 同時に見つけた既存の揺れ: `_role_credit_fix` が ISBN の set を順不同で数え、同数の原作表記/並びが再生成のたびに入れ替わっていた(40頁)→ sorted で固定

新規頁の `author-overrides.json`(2026-10-20 の13頁)はそのまま(頁単位の手の上書きが勝つ)。[[author_pollution_overlay_fix]] [[author_not_in_volumes_audit]] [[ndl_authority_homonym_state]] [[feedback_one_bug_means_a_class]]
