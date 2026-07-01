---
name: volnum_remaining_merge_collection
description: 【残務】巻番号クリーンアップの残=S2_HAS21(分裂要merge)+COLLECTION19(傑作集)。慎重merge/人手判断マター。data/seeds/volnum-remaining-tasks.tsv
metadata: 
  node_type: memory
  type: project
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

巻番号クリーンアップ(A/B/C群=単巻誤番号・offset・gap)の**残務**。自動で安全に直せる分(是正62巻+補完770巻)は適用済。残るは慎重判断マターの**40件**:

## ① S2_HAS = 21件（分裂＝要merge）
種2には欠け巻があるのにDBページは一部しか持たない＝**promoteで別ページに分裂**した作品。単純補完でなく**merge/re-cluster**が要る。
- 例: 花恋 DB[6,7] 種2[1-7](他巻が別ページ) / Kanon DB[2,8] 種2[1,2] / コヨーテ DB[2,3,4] 種2[1-4]。
- ★[[merge_needs_external_proof]][[feedback_dont_repeat_regrouping_error]]＝誤merge厳禁。分裂先ページを特定し多数決+人手確認+可逆で。

## ② COLLECTION = 19件（傑作集/作品集/全集/名作選集）
複数の別題が傑作集容器でmergeされている。**傑作集＝それ自体1作品(N巻・副題付き)**として扱う原則（[[clustering_unit_is_series]]・ユーザ裁定）。別作mergeも傑作選アツメもしない。
- 例: 山本鈴美香作品集 / 山岸涼子全集 / わたなべまさこミステリー名作選集 / 諸星大二郎短編集成 / めざせ漫画家!受賞作品集 / なかよしオリジナル版作品集。
- 楽天で「○○傑作集/作品集（N）」collection名検索すれば巻構造は取れる(副題は表紙/NDL)。但し**深追い不要**(ニッチ・人手で十分)。

## リスト・証拠
- **`data/seeds/volnum-remaining-tasks.tsv`**(group/class/slug/title/db/種2or collection)＝全40件。
- 元証拠: `ndl-classify-B.tsv`/`ndl-classify-C.tsv`/`true-single-final.tsv`。
- 据置(触らない): CONT493(続編/シーズン正当)+NDL_NONE364(NDL照合不可)。

## 進め方(ユーザ指示あれば)
S2_HASは分裂先特定→merge、COLLECTIONは傑作集1作品化、どちらも**慎重・可逆・人手確認**。急がない。
