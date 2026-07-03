---
name: kiko_multiedition_mixing_heuristic
description: 奇子型(多版混在)の検出=ユーザ経験則「volume_label混在(数字+上/下)+発売日矛盾+書影一部欠け」。巻抜け1417中162作。NDLで版確定→edition-overrideで版分離が型
metadata: 
  node_type: memory
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

2026-06-30 ユーザ指示「効率でなく一つの作品事(per-case)調べて。本番前の最後の仕上げ」。

**★ユーザの経験則(コード化済 = _detect-volgap-mismatch.py / kiko検出)**: 怪しい作の3signal —
- ①**表記揺れ**: 巻が「1巻,2巻,下巻」のように数字と上/中/下/前/後が混在(volume_label)。
- ②**発売日矛盾**: 巻番号順で発売日が逆行(vol3が1968でvol1が1978等)。
- ③**書影一部欠け**: 一部の巻だけcover無。
3つ揃う = ★**同一作の複数版がconflate(奇子型)**。巻抜け1,417中 **162作**該当。例: サイボーグ009/カムイ伝/ドラえもん/ゴルゴ13/エロイカより愛をこめて/人間ども集まれ!。古典の多版作に集中。

**★is-this誤マッチ(別作混入)も併発**: 巻抜けの中に「欠け」でなく「別作の巻が混入」(ねこぱんち←キジトラ猫の小梅さんvol26-29/丹下左膳←手塚治虫漫画全集/空がすき←竹宮恵子作品集)。検出=各巻のISBN→実題名(harvest/楽天)が作品題と乖離(英↔カナ・ハイフン揺れは著者一致で除外)。

**★per-case是正の型(人間ども集まれ!で実証)**:
1. 全巻のnumber/volume_label/isbn/date/coverを展開。
2. ★**NDL title検索で全版を確定**(年×出版社×巻=版の権威。実業之日本社原版1968上下/講談社ホリデー新書1978/文藝春秋文春文庫1995上下/講談社漫画文庫2010)。
3. **edition-overrideで版ごとに分離**(同type複数版はlabelで区別=「文春文庫」「講談社漫画文庫」)。誤混入巻(別版/別作)を除去。ISBN無の古版は除去 or 最小edition。
4. 書影は楽天ISBN直引き(絶版は無し許容)。

**進め方**: 162作を**一個ずつ**(効率でなく)。誤マッチ(別作混入)は volume-exclude+正ページへ種4移設。多版混在は edition-override。durable seed。[[edition_mix_same_author_ayako]] [[multi_edition_unification_pending]] [[volgap_mostly_undermerge]]


## 2026-07-03 ドカベン型=複合Frankenstein(奇子型の上位種)と新機構2つ
- ★症状: 本編standardの「原版ISBN無し枠」にだけ文庫ISBN(1994-)や別作(プロ野球編0557帯)が滲む。原因は2層: ①種2ネイティブ汚染(51472に245冊) ②同qidスピンオフ(プロ野球編51477/スーパースターズ編51474)がclusterに吸われ番号衝突→本編が勝ち**スピンオフ全体が不可視化**(ページ不存在)。
- ★新機構: **merge-exceptions.yml**(対称series-idペアでfind_related block・promote結線済) + **series-keep.yml**(spinoff旧作dropからの救済・既存)。スピンオフ独立ページ化の定石=例外ペア+keep+種4gap fill+本編override浄化。
- ★slugは旧source棚卸し由来(promote旧source依存)→新独立ページのslugは data/manga/(旧69k)に既存の名がある(dokaben-super-sutaazuhen等)。--onlyで書けない時は旧sourceでslugを確認。
- 適用結果: 本編1-48(プレISBN37=正)+文庫31 / プロ野球編1-52 / スーパースターズ編1-45。
