---
name: gyara_type_regression_cleanup_state
description: 【進行中】ギャラ型(巻×発売日の大逆行=復刻接ぎ木)是正。トリガー「ギャラ型続けて」。B型は44/49完了、残はA型28・C型3・保留5
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-08-17T01:07:40.464Z
---

**トリガー「ギャラ型続けて」**で worksheet の次から再開する(モデル不問=Opus運転可)。

## 状態(2026-08-17 B型ほぼ完了)
- 検出器 = `scripts/_audit-vol-date-regression.py`(月次サニティ登録済)。flag **524版**(初回573→557→549→533→524)
- worklist = `docs/production-diagnostics/vol-date-regression.tsv` / 分類worksheet = `vol-date-regression-worksheet.tsv`(30年+の85頁: A_SPLIT_WORK?=28 / B_REPRINT_MIX=49 / C_INTERNAL_MIX=3)
- **B型 44/49 是正済**。是正した頁は edition-canonical/*.yml を見れば全部わかる(source: に根拠と手法)
- **次にやるのは A型28件 と C型3件**(下記「残りの難所」)

### B型の保留5件(理由つき・触るなら追加調査から)
- **流れ星五十三次** サンコミックスのv5だけ1968-07-25でv1-4の1973から5年逆行。NDLに当該runが無く裁定不能
- **ピカドンくん** 初版4冊がv0×4=巻番号不明
- **タンク・タンクロー** MADBの巻が全部v0=巻番号不明(ピカドンくんと同型)
- **クイーンエメラルダス** 初版の講談社コミックス全4巻がMADBに無く、グランドコレクション/KPC/漫画文庫/復刊ドットコムの4run混線
- **SWAN** 続編『ドイツ編』『モスクワ編』(平凡社)が同一頁に混在=A型判断が要る。初出はマーガレット・コミックス全21巻(集英社1977-81)

## レシピ(B型44件で確立)
1. worksheetから候補選定 → 種2クラスタの巻明細dump = `python .cache/gyara/dumpvol.py <sid...>`(volumesはeditions経由でjoin)
2. **NDL SRU**で裏取り = `python scripts/_lookup.py --title X --creator Y --live`(1.2秒/req厳守)。
   ★`--creator`を付けないとNDLを叩かず楽天キャッシュ+楽天liveになる(復刻runのISBN/版元にはこちらも有用)
3. **edition-canonical/*.yml**(キー=SRC slug)で再構築: volumes=**完備最古**run / 他runは全て extra_editions
4. changelog(edition-fix-changelog.jsonl)1行 → `_reflect-targeted.py --only <slugs>` → status/year/publisher確認 → 検出器再走 → preview cp+索引再構築 → commit/push

## 厳守(実踏済みの罠)
- **捏造しない**: 両ソースに無い巻は入れない。欠番は空けたまま。1冊しか記録の無い版はその1冊だけで立てる
- NDL不在≠不存在(1960-70年代の単行本はNDL未収録層が厚い)。MADB単独の巻も消さない
- release_dateは**必ず引用符**。reflectの「消えた版/巻」警告は必ず検分(版名変更・統合なら正常)
- ★**文庫タブの混在は canonical では直らない** → `suppress_types: [bunkobon]` + bunkobonのextra_editionsで作り直す(canonicalが自動で作り直すのは standard/aizoban だけ)
- ★**extra_editions は既存タブを消さない** → 種2側に同じ版が居ると**二重タブ**になる(black-angels で実踏)。extraを足す時は suppress_types をセットで考える
- ★**work-level publisher は「最多巻の社」多数決**(canonical後に再導出)。温存タブのpublisherが空だと化ける
- ★**版元が両ソースに無い版は `publisher: 不明`** と明示してよい(pub_key_of が解決せず publishers[] を汚さないことを確認済。快傑ハリマオの1960初出・首斬り朝の劇画キングシリーズで採用)
- ★**レーベル名が不明な主版は `canonical_label` と `canonical_imprint` を両方省略する**(promoteは canonical_imprint→canonical_label→既存imprint の順に代用するので、labelだけ書くとレーベル欄に「通常版」が出る)
- ★**古いvolume-excludeが版分離の邪魔をする**: 2026-07-04に一括登録された「激マン型混入」除外67件のうち、後から版分離した頁では復刻タブの巻を消すだけの副作用になる(小さなお茶会・black-angelsで実踏→解除済)。canonical新設時は該当ISBNがvolume-exclude入りしていないか見る
- 復刻で年が新しくなってもstatusは自動でcompletedにならないことがある → `status-corrections.yml`(キー=公開slug)
- **A型(別作品混在)はギャラ式**: 同_skeyのstub×2 + edition-overrides(公開slugキー)+ **`"anilist": false`**

## 残りの難所
- **A型28件**(別作品が同一頁に混在=頁分離が要る): 銭形平次=3社別コミカライズ / 鉄腕アトム=9クラスタ33版 / 幻魔大戦=5クラスタ 等
- **C型3件**(1 edition行内の年代混在=MADB行自体が混成): 一平全集 / 沙漠の魔王 / 大和小伝
- B型保留5件(上記)

関連: [[edition_canonical_mechanism]] [[edition_mix_same_author_ayako]] [[never_delete_because_broken]] [[merge_needs_external_proof]]
