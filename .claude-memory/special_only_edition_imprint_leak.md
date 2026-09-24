---
name: special_only_edition_imprint_leak
description: 【型・未対応・GO待ち】種2に「特装版ISBNだけの通常版edition」が別レーベルで在ると、特装版是正でISBNは通常版に差し替わるのにレーベルだけ残り、頁の通常版imprintが特装版レーベルになる(ちいかわ=講談社キャラクターズA)。種2で190 series
metadata:
  type: project
---

2026-09-24 ちいかわ per-case で発見。種2(db-v2)の series 53019 は standard edition が2本:
65660=ワイドKC(3,5,6,8巻) / 65661=講談社キャラクターズA(中身は1・2巻の**特装版ISBN**)。
promote の特装版是正(special-edition-fix*.yml)は special→normal に ISBN を置換して variant 併記するが、
**edition の imprint は特装版側のまま**残り、頁の通常版タブが「講談社 / 講談社キャラクターズA」と出る
(楽天/Wikipedia はどの巻も ワイドKC[モーニング])。imprint を per-page で上書きする seed は無い(edition-overrides は editions 丸ごとのみ)。

- 規模(09-24実測): 種2で「全ISBNが特装版の standard edition が、同series他版と別レーベル」= **190 series**。
  レーベル上位 プレミアムKC 56 / 講談社キャラクターズA 35 / IDコミックススペシャル 17 / KC magazine 16。
- 直し方の案: promote の同type版合流で imprint を決める時、特装版ISBNだけの版の imprint を候補から外す(多数決は通常版ISBNの版で)。
  コード変更=全頁に効くので GO 待ち。検算は ちいかわ(→ワイドKC)で。
- 同日 ちいかわは他の項目(ジャンル/分野/開始年/7・8巻日付/特装版5冊)だけ是正済み・imprint は未。
関連: [[imprint_label_leak]] [[special_edition_fix_state]]
