---
name: gyara_type_regression_cleanup_state
description: 【進行中】ギャラ型(巻×発売日の大逆行=復刻接ぎ木)是正。トリガー「ギャラ型続けて」。残541頁中17済・30年+残り約70版
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-16T23:20:48.561Z
---

**トリガー「ギャラ型続けて」**で worksheet の次から再開する(モデル不問=Opus運転可)。

## 状態(2026-08-17時点)
- 検出器 = `scripts/_audit-vol-date-regression.py`(月次サニティ登録済=CLAUDE.md参照)。flag **557版**(初回573)
- worklist = `docs/production-diagnostics/vol-date-regression.tsv`(逆行年数降順)
- 分類worksheet(30年+の85頁) = `docs/production-diagnostics/vol-date-regression-worksheet.tsv`(A_SPLIT_WORK?=28 / B_REPRINT_MIX=49 / C_INTERNAL_MIX=3。クラスタdump付き)
- **済17頁**: ギャラ(A型の型見本=2頁分離) + B型16(第1バッチ: 大空のちかい/少年No.1/ビバ!バレーボール/朝日の恋人/トラジマのミーめ/チョッキン/爆笑戦士!SDガンダム、第2バッチ: 少年の町ZF/薩摩義士伝/くたばれ!!涙くん/虹をよぶ拳/のら犬の丘/あかつき戦闘隊/デスハンター/セクサロイド/エル・アルコン-鷹-)
- **保留**: ピカドンくん(初版4冊がv0×4=巻番号不明、要NDL個別調査)

## レシピ(第1・2バッチで確立)
1. worksheetから候補選定(単純な2〜3run型から)→ 種2クラスタの巻明細dump(sqlite .cache/db-v2.sqlite)
2. 初版run(ISBN無時代)を **NDL SRU**(`scripts/_lookup.py --title --creator --live`・1.2秒/req厳守)で裏取り、復刻runの版元/題は**楽天delta**(.cache/rakuten-isbn-delta.jsonl)から
3. **edition-canonical/*.yml**(キー=SRC slug!)で再構築: volumes=完備最古の初版run / 復刻・完全版・ワイド版は **extra_editions**(type: shinsoban/kanzenban/wideban+label+publisher+volume_label上下)で別タブ化。文庫等の既存タブは自動温存
4. changelog(edition-fix-changelog.jsonl)1行 → `_reflect-targeted.py --only <slugs>` → **status/year確認**(往年作がongoingなら status-corrections.yml へ根拠付き追加) → 検出器再走で件数減を確認 → **preview cp+索引再構築** → commit/push
- 是正例は data/seeds/edition-canonical/ の 2026-08-17 付け16本を見よ(source: に手法メモ)

## 厳守(実踏済みの罠)
- **捏造しない**: 両ソースに無い巻は入れない(のら犬の丘v4=欠番のまま)。MADB単独の巻も消さない(虹をよぶ拳6-7=保持)
- 一括同日日付=重版混入シグナル(デスハンターv1の1974-03-10→NDL初版1971に是正した型)
- 楽天キャッシュに初版全巻ISBNが眠っていることがある(爆笑戦士SDガンダム=MADB/NDL両方v1・v6欠→楽天で全8巻復元)
- release_dateは**必ず引用符**。canonical新設時はreflectが警告する「消えたISBN」を必ず検分(移設なら正常)
- **A型(別作品混在)はギャラ式**: 同_skeyのstub×2 + edition-overrides(公開slugキー)+ **`"anilist": false`**(2026-08-17新設=promoteのper頁enrich遮断。リメイク側にAniListを帰属させ原作側で遮断)

## 残りの難所(後回しにした順)
- 手塚系5作(アポロの歌/ビッグX/キャプテンKen/白いパイロット/ロック冒険記)=全集・文庫の多層
- 小池一夫劇画系(御用牙/首斬り朝/道中師/子連れ狼/ケイの凄春)=4〜6run+sid分裂
- A型28件(銭形平次=3社別コミカライズ/鉄腕アトム=9クラスタ33版/幻魔大戦=5クラスタ 等)
- C型3件(一平全集/沙漠の魔王/大和小伝=1 edition行内の年代混在=MADB行自体が混成)

関連: [[edition_canonical_mechanism]] [[edition_mix_same_author_ayako]] [[never_delete_because_broken]] [[merge_needs_external_proof]]
