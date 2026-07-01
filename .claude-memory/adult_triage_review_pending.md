---
name: adult-triage-review-pending
description: 成年判定の3分けレビューUI(ローカル・書影付)を本番DB後に作る残処理。4状態モデルでAniList未照合の罠を解く
metadata:
  type: project
---

**残処理(2026-06-01〜02、 ユーザ要望・本番DB完成後に詰める)**: 蒸留結果をアップする前に、 ★**成年判定を3分けして人が最終確定するレビュー仕組み**(ローカルネット=家のデバッグモード、 将来は**書影付**=Amazon API入れば)が欲しい。

**3分け** = 既存の2フラグ+geo出し分け([[adult_judgment_architecture]])と一致:
- **非成年** = adult_jp:no かつ adult_us:no
- **成年(日本)** = adult_jp:yes
- **米では成年(US-only)** = adult_jp:no かつ adult_us:yes

★**罠(ユーザ指摘)**: 「非成年」はAniListのisAdultを見ないと確定不能 → ★**4状態モデル**にする: `adult_us = yes / no / unknown(AniList未照合)`。 AniList照合済=確信を持って振れる / 未照合=「日本非成年・米不明」の**暫定** → ここだけ人がレビュー。

★**データ知見(ユーザのBL説は検証で否定)**: US-only成年1,985件(merge後ページ1,913)のAniListジャンルは Romance1268 / **Hentai581 / Ecchi441** / Drama569 が主で、 ★**BL/Yaoiは上位に無し**。 = 日米差は「露骨・きわどい異性愛(Hentai/Ecchi)」。 未照合作の likely-adult 予測にもこのgenreを使える。 リストは `us-only-adult.csv`(title/anilist_id/authors/genres/tags/page_key)を生成・ユーザに送付済。

**レビューUI設計案**: 3列(非成年/成年JP/米成年only)、 各列で★「要確認(未照合 or signal矛盾)」を上に浮かせ確信分は素通り、 書影スロット常設、 人の確定は★既存 `data/seeds/adult-overrides.yml`(override機構)に書き戻して蓄積。 = 「未照合かつ曖昧」だけ人手に絞る。 関連 [[adult_judgment_architecture]] [[madb_data_acquisition]]。
