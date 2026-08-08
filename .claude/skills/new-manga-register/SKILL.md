---
name: new-manga-register
description: 新規追加/新刊入れて=新規マンガをテスト先行で登録(順番固定protocol・捏造/単巻先行の再発防止)
---

# 新規追加 / 新刊入れて

トリガー語: 「新規追加」「新刊入れて」「この漫画を載せて」等。
流れは**テスト先行が例外的に許される唯一のルート**: preview生成→ユーザ確認→GOで本番化。

## 順番固定 (= 2026-07-02 ユーザ裁定。CLAUDE.md「新規登録 protocol」)
1. **全巻回収が先** — 巻Nを発見したら title+creator で NDL全巻+楽天全巻(outOfStockFlag=1)を回収。**単巻先行登録は禁止**
2. **題の確定** — NDL題×楽天題を突合。不一致=調査、不明=ユーザ報告。**勝手命名は絶対禁止**。slugは確定題+確定ヨミから一度だけ生成
3. **ヨミの確定** — 題ヨミ=NDLタイトルヨミ。著者名+ヨミ=NDL典拠/楽天。不明=報告して待つ。役割(原作/作画)不明もデフォルトで埋めない
4. **一括登録** — 全巻+必須メタ(title/kana/romaji/authors/year/status/demographic/genre≥1)が揃ってから
5. **enrichは登録後** — 1巻基点でネタバレ無しのcatch/synopsis。genreはclosed vocabulary(master32キー、trusted無ければprovisionalマーク)。最終巻あらすじ丸写し禁止
6. **作れないものは作らない** — 埋められない項目=空+欠落表で報告。必須すら確定できない作品=登録保留リスト(載せない)

## 実装ルート
- 少数=daily/backward distill の worksheet フローに乗せる(_distill_daily / _distill_backward)
- 生成後: 検証(Zodミラー/slug衝突/日付pad) → preview投入(test-deploy skill) → ユーザ確認 → GO後に「反映して」で本番系列へ

## 索引ガードとの関係
authors/genres/year/kana 非空要求は「埋める圧力」になる→**埋めるな、保留にせよ**(チェック通過のための捏造が最悪)。

## ★0. 存在チェックは題でなくISBNで (2026-08-08 二重頁事故の恒久対策)
「全巻回収」の直後、**頁を作る前に**必ず:
```
python scripts/_exists.py --isbn <判明した全巻のISBNをカンマ区切りで全部>
```
`--title` は**完全一致**なので `どっきり!エンジェル` / `GREEN PARADISE` / `Xの歌声` のような
**感嘆符・中黒・ラテン/カタカナ・ギリシャ文字**の揺れで素通りし、**二重頁**を作る。
★ユーザ提供の1本だけで判断しない(提供ISBNは欠落巻であることが多く、当たらなくて当然)。
1件でも当たれば**新規登録ではなく既存頁の是正**に切り替える(種2駆動の既存頁を残し自作seedは撤去)。
登録後も **ISBN+正規化題で全数照合**して重複ゼロを確認する。[[existence_check_by_isbn_first]]

