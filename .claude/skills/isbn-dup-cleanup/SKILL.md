---
name: isbn-dup-cleanup
description: ISBNダブリの続き=本番ページ間の同ISBN重複を潰す(検出→層別→判定→適用→検証)。R1-R7(2026-07-07)で確立した正本
---

# ISBNダブリ潰し (= 同ISBNが複数ページに載る事故の解体)

トリガー語: 「ISBNダブリの続き」「ISBNダブリ潰して」。進行状態=memory [[isbn-dup-cleanup-state]]。

## NEVER (最重要)
- **機械判定は必ず全ログを目視してから適用**(毎回誤りが出る。R4は自動裁定を却下し手動表、R5はoverride6件)
- **部分重なりのdedupは固有巻が消える**(page-dedup=頁skipなので、drop側⊆canonical側 の包含を確認してから)
- **著者不一致ペアをdedupしない**(homonym防御。集合完全一致=同一物理本の時だけ例外)
- **canonical選定に注意**: 傑作選/セレクト/外伝/新装レーベル(CPC等)を本体より優先させない(あおぞら家族セレクト/ダイヤのA外伝の誤判定例)
- 巻の帰属判定は本籍sid題との**完全一致**で(substringはスピンオフ題⊃本編題ですり抜ける=西風の旅団事故)

## 手順
1. 検出: `python scripts/_audit-isbn-dup-pages.py`(~1分) → docs/production-diagnostics/isbn-dup-pages.tsv
2. 層別: `_isbn-dup-triage.py`(集合一致系) / `_isbn-dup-r5.py`(汎用判定器=基底題canonical+隠れ本+題系譜)
3. **判定基準**(クラスタごと):
   - **隠れ本あり**(メンバーsidの自ISBNがunionに無い=number-dedupが新版/続シリーズを隠している) → **分割**(merge-exceptions block)
   - **lossless家族**(隠れ本ゼロ×題系譜つながる×同著者) → **dedup**(page-dedup+alias301)
   - 両頁同題で本籍も曖昧 → per-case(外部確証: Wiki/NDL/楽天delta著者)
4. 適用: `_isbn-dup-apply.py`(auto.json→page-dedup+alias+_redirects+changelog) / blockはmerge-exceptions.ymlへ
5. 反映: `_reflect-targeted.py --only <生存stem> --drop <drop stem> --push`
6. 検証: 再監査で件数減 + 分割頁が自分の本だけ持つか + `.cache`のjournal的ログ確認

## 構造知識 (なぜ起きるか)
- DUP_PAGE の正体 = find_related のグループmergeが**メンバーsidごとに同じunion頁をN枚出力** + **number-dedup(最古優先)が新しい版/続シリーズを隠す**(タッチ完全版と同型)
- 種4 qid注入(作者QID)/本籍無しISBN → 種4 seed を疑う
- ゲーム同題群(VP/スターオーシャン/FE/X-MEN型)の解き方: Wikiのコミカライズ一覧×楽天delta著者×レーベル(エニックススーパーコミック劇場=アンソロ)で 正規コミカライズ各頁+アンソロ1頁(series-merge renumber) に再編。VP前例=2026-07-07
- 過去の一括dedup(2026-06の335件)にも誤りがある(VP土方本編が丸ごと消えていた)=canonicalの中身を疑ってよい

## 関連道具
- 個別調査: `python scripts/_isbn-dup-case.py <stem1,stem2,...>`(sid/本籍/楽天題の一覧)
- 照会: `python scripts/_lookup.py --isbn/--title [--live]`(必ずこれ経由=external-data-access)
- renumber統合: series-merge.yml merge_keys+renumber:true(代表巻は(sid,番号)単位=2026-07-07精緻化済)
