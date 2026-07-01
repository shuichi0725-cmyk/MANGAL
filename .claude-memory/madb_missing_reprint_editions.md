---
name: madb-missing-reprint-editions
description: 【測定済・将来パッケージ】MADBは完全版/新装版/愛蔵版級の再版シリーズをほぼ未収録(全DBで完全版11件/新装版12件)。版タブが通常版だけなのはこれが根因。補完=楽天タイトル検索で系列収穫→種4拡張
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-12 ユーザ実機指摘(ドラゴンボールに通常版しか無い)→測定で系統欠落と確定。

## 事実
- 種2 edition型分布: standard 173,154 / bunkobon 8,216 / deluxe 2,691 / aizoban 255 / wideban 182 / **shinsoban 12 / kanzenban 11**。
- ★DB完全版1巻ISBN(9784088734446)はMADB raw 660MBに**0回**=MADB自体が未収録。有名完全版(スラダン/ハガレン/寄生獣/北斗/幽白/ダイ)も種2に全滅。るろ剣のみ1件。
- 文庫はそこそこ収録(8,216)→ うる星3タブはMADBが偶々持っていたから。imprint「文庫」×type=standardの誤分類は0件(typing自体は健全)。
- ホーム社名義DB文庫15冊=本編merge済みで巻番号畳みに吸収(軽微・別問題)。

## 補完の方向(将来・道具は手元にある)
- ★**ユーザ指示(2026-06-12): 主要タイトルの完結作を対象に「NDLを回して」ドラゴンボール型の未掲載(完全版等の版シリーズ)を探す**。NDL SRU(by-title/by-creator)はインフラ実証済([[ndl_slug_fix_method]])で、書誌に完全版・愛蔵版の系列が載る。NDLで系列発見→ISBN確定、楽天で発売日/書影を肉付け、の2段が堅い。
- **楽天ブックスAPIのタイトル検索**(outOfStockFlag=1で絶版も出る・発売日/書影/ISBN付き)で「有名作品×版マーカー(完全版/新装版/愛蔵版/フルカラー)」の系列ISBNを収穫 → ★種4(volumes-supplement)を「版シリーズ丸ごと補完」に拡張 → separate_editions/版タブで表示。
- 認証・レート(1QPS)・キャッシュ機構は `_rakuten-fill-dates.py` のものを再利用可。
- 優先順位: 有名作(閲覧上位)から。完全版はアフィ単価も高い(1冊1,000円超)= 収益面でも優先度高。
- 関連: [[multi_edition_unification_pending]](版タブ設計=実装済) [[display_data_polish_tasks]](楽天収穫中) [[madb_cm104_frozen]]
