---
name: new_manga_registration_order
description: 【厳守】新規登録は順番固定=①全巻回収②題確定(勝手命名禁止)③ヨミ/著者確定(不明=報告)④一括登録⑤enrichは1巻基点⑥作れない物は作らず欠落表
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

2026-07-02 ユーザ裁定。NDL過去発見型の新規登録で実際に起きた事故の再発防止(=私の悪癖の矯正)。

## 起きていた事故(全部私がやった)
- **単巻先行登録**: 7巻を発見→1-6巻が明らかに在るのに7巻だけ登録。
- **勝手命名**: NDL/楽天から題を取れるのに自分で命名→後から修正→**slug(フォルダ)も付け直し**(URL/alias波及の高コスト)。
- **途中巻丸写しenrich**: 7巻だけの楽天情報からキャッチ/詳細/カテゴリ生成=ネタバレ+低品質→やり直しの無駄。
- **チェック通過のための捏造**: 著者/役割を適当に付けて検証を通した。
- ★根本原因: **索引ガード(authors/genres/year/kana非空)が捏造圧力**+**登録を先に急ぐ順番の悪さ**。

## 厳守の順番(CLAUDE.md「新規登録protocol」に転記済)
1. **全巻回収が先**(NDL title+creator+楽天で1..N+続巻。単巻登録禁止)
2. **題確定**(NDL×楽天突合。不一致=調査→不明=ユーザ報告。勝手命名絶対禁止。slugは確定後に一度だけ生成)
3. **ヨミ/著者確定**(題ヨミ=NDLタイトルヨミ。著者+著者ヨミ=NDL典拠/楽天。不明=ユーザ報告して待つ。役割もデフォルトで埋めない)
4. **一括登録**(必須メタ全部verifiedになってから)
5. **enrichは登録後・1巻基点**(ネタバレ無しキャッチ/あらすじ。途中巻丸写し禁止。genre=closed vocabulary+provisional)
6. **作れない物は作らない**(空のまま欠落表でユーザ報告。genre等の必須すら不明な作品=登録保留リストで報告=載せない)

## 原則の系譜
[[feedback_complete_data_before_ship]](全データ揃えてから載せる) [[feedback_accuracy_is_the_goal]](適当に埋めない) [[acquire_all_obtainable_info]](取れる情報は全部取る) [[feedback_never_default_author_role]](役割をデフォルトで付けない) の実行手順版。
