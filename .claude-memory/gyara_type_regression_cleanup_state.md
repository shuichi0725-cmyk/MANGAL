---
name: gyara_type_regression_cleanup_state
description: 【進行中】ギャラ型(巻×発売日の大逆行=復刻接ぎ木)是正。トリガー「ギャラ型続けて」。残549版・済23頁
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-08-16T23:53:00.205Z
---

**トリガー「ギャラ型続けて」**で worksheet の次から再開する(モデル不問=Opus運転可)。

## 状態(2026-08-17 第4バッチ終了時点)
- 検出器 = `scripts/_audit-vol-date-regression.py`(月次サニティ登録済=CLAUDE.md参照)。flag **549版**(初回573→557→549)
- worklist = `docs/production-diagnostics/vol-date-regression.tsv`(逆行年数降順)
- 分類worksheet(30年+の85頁) = `docs/production-diagnostics/vol-date-regression-worksheet.tsv`(A_SPLIT_WORK?=28 / B_REPRINT_MIX=49 / C_INTERNAL_MIX=3。クラスタdump付き)
- **済23頁**: ギャラ(A型の型見本=2頁分離) + B型22
  - 第1バッチ: 大空のちかい/少年No.1/ビバ!バレーボール/朝日の恋人/トラジマのミーめ/チョッキン/爆笑戦士!SDガンダム
  - 第2バッチ: 少年の町ZF/薩摩義士伝/くたばれ!!涙くん/虹をよぶ拳/のら犬の丘/あかつき戦闘隊/デスハンター/セクサロイド/エル・アルコン-鷹-
  - 第3バッチ: 電人アロー/ボンボン/ガンドランダー
  - 第4バッチ: ケネディ騎士団/銭ゲバ/天才バカボンのおやじ
- **保留**: ピカドンくん(初版4冊がv0×4=巻番号不明) / **流れ星五十三次**(サンコミックスv5だけ1968-07-25でv1-4の1973から5年逆行。NDLに当該runが無く裁定不能=要追加調査) / **クイーンエメラルダス**(初版KC全4巻がMADBに無く、グランドコレクション/KPC/講談社漫画文庫/復刊ドットコムの4run混線=重い)

## レシピ(第1〜4バッチで確立)
1. worksheetから候補選定(n_editions の小さい単純run型から)→ 種2クラスタの巻明細dump
   = `python .cache/gyara/dumpvol.py <sid...>`(volumes は editions 経由で join。series/volumesに直接 imprint 列は無い)
2. 初版run(ISBN無時代)を **NDL SRU**(`scripts/_lookup.py --title --creator --live`・1.2秒/req厳守)で裏取り。
   ★`--title` だけだと NDL を叩かず楽天キャッシュ+楽天liveになる(それはそれで復刻runのISBN/版元の一次資料として有用)
3. **edition-canonical/*.yml**(キー=SRC slug!)で再構築: volumes=完備最古の初版run / 復刻・完全版・別社版は **extra_editions**(type+label+imprint+publisher)で別タブ化
4. changelog(edition-fix-changelog.jsonl)1行 → `_reflect-targeted.py --only <slugs>` → **status/year/publisher確認** → 検出器再走 → **preview cp+索引再構築** → commit/push

## 厳守(実踏済みの罠)
- **捏造しない**: 両ソースに無い巻は入れない。MADB単独の巻も消さない(NDL不在≠不存在。古い単行本はNDL未収録層が厚い=ボンボン/流れ星のサンコミックス)
- 1冊しか記録の無い版は**その1冊だけで版を立てる**(銭ゲバのSPコミックス/Magical comics)。欠落を埋めない
- release_dateは**必ず引用符**。canonical新設時はreflectの「消えたISBN/消えた版」警告を必ず検分(版名変更や移設なら正常)
- ★**文庫タブの混在は `suppress_types: [bunkobon]` + bunkobon の extra_editions で作り直す**(canonicalが自動で作り直すのは standard/aizoban だけ。銭ゲバ/バカボンで実踏)
- ★**work-level publisher は「最多巻の社」多数決**(canonical後に再導出)。初版タブより復刻タブの巻数が多いと社名が化ける
  → 温存タブの publisher が空だと更に化ける(ケネディ=若木書房になった)。suppressして publisher を明示すると直る
- 復刻で年が新しくなっても status は自動で completed にならないことがある → `status-corrections.yml`(キー=公開slug)へ根拠付き追加(ガンドランダー)
- **A型(別作品混在)はギャラ式**: 同_skeyのstub×2 + edition-overrides(公開slugキー)+ **`"anilist": false`**

## 残りの難所(後回しにした順)
- 手塚系5作(アポロの歌/ビッグX/キャプテンKen/白いパイロット/ロック冒険記)+ふしぎな少年=全集・文庫の多層
- 小池一夫劇画系(御用牙/首斬り朝/道中師/子連れ狼/ケイの凄春)=4〜6run+sid分裂
- A型28件(銭形平次=3社別コミカライズ/鉄腕アトム=9クラスタ33版/幻魔大戦=5クラスタ 等)
- C型3件(一平全集/沙漠の魔王/大和小伝=1 edition行内の年代混在=MADB行自体が混成)

関連: [[edition_canonical_mechanism]] [[edition_mix_same_author_ayako]] [[never_delete_because_broken]] [[merge_needs_external_proof]]
