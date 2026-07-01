---
name: audit_volume_output_detector
description: 巻欠落/日付矛盾を本番yml側で検出する新監査。種2を見る旧監査では捕まらないpromote出力の穴を洗う
metadata: 
  node_type: memory
  type: project
  originSessionId: 40083ab0-9577-4733-a97e-7da2fd5bd20a
---

`scripts/_audit-volume-output.py`(read-only)= 巻の出力サニティ監査。★**本番 yml(data/manga.v2)を直接読む**のが肝。

**なぜ作ったか**: 旧 `_audit-volume-numbering.py` は種2 sqlite(ソース)を読むため、promote の merge/dedup が**出力側に作った穴**を原理的に検出できなかった(菜の #1 欠落型)。ソースは1-12完全でも出力で#1が消える事故を捕まえる層が無かった。

**検出4型**(edition単位・flag only): MISSING_VOL1(#1欠落・何度でも確実検出) / GAP(中抜け) / PUBLISHER_MIX(1版内ISBN出版者記号混在=別社混入) / DATE_DISORDER(巻番号順の発売日逆行=日付矛盾)。種2突合で **RECOVERABLE**(ソースに在る=promote落とし=機械復元可・復元候補ISBN付)か **SOURCE_GAP**(真の取りこぼし=種4)を判定。`jp_pub_prefix`=978-4登録グループ長ルールで出版者記号を正確抽出(大手の固定長誤分割回避)。

**全量結果(2026-06-22/66,357作品)**: MISSING_VOL1=629(RECOVERABLE143/SOURCE_GAP486)・GAP=656(RECOVERABLE80)・PUBLISHER_MIX=1,928・DATE_DISORDER=485。結果は `docs/audit/`(TSV4本+README)に git 永続化。

**菜(sai)の根因**(試金石): 同一作が3クラスタに分裂(qid:Q1399083講談社12巻 / 別社2025復刻9784768 / 菜〜ふたたび〜=続編別作3巻)→ auto-merge が1 standard版に畳む(版キー=type単位の既知バグ [[multi_edition_unification_pending]])→ ①dedup_key=`(release_date or "9999-99",...)` で**日付無しの本物#4/#6が日付付き別社に負け化け** ②6/18 T3混入除去が#1の双葉社誤ISBNを除去も**本物#1を埋め戻さず**空に。

**直し方の方針**: 大型の DATE_DISORDER/PUBLISHER_MIX は多くが「別社復刻が1 standard版に畳まれた」多版統合問題=除去でなく**版分離**で直す。全集/復刻は非時系列で DATE_DISORDER 誤検出あり=人手裁定。RECOVERABLE(計223)が最優先・機械復元候補。自動修正はせず surfacing 専用。

**実施済の恒久修正(2026-06-22・本番は再promoteまで不変)**:
1. **promote dedup是正** = `_dedup_key`を「最古日付優先」→「多数派出版者線(`_jp_pub_prefix`=978-4登録グループ長で正確抽出)最優先→最古日付→最小ISBN」。別社混入が日付で勝つ穴を封鎖。ドライラン(`_dryrun-dedup-fix.py`)で787頁/2,732巻変化=PUB_SWAP1,329/RESTORE1,244/OTHER159(全て同一社内刷違い=退行なし)を確認。
2. **NDL発売日バックフィル** = `_ndl-date-backfill.py`で release_date欠落のJP巻5,252件をNDL SRU照会→`data/seeds/release-date-supplement.jsonl`(2,939件取得)。promoteが`get_release_date_supplement()`で None時のみ上書き(`_eff_date`)。種2不変。
3. 検証: 菜が全12巻・講談社原本・完全時系列(1993-04→1998-09)に是正(import実行で確認)。#1復活+別社#4#6排除+#2#3が2008復刻→1993原本。
**残**: ①Kobo完走後に再promote→本番反映→`_audit-volume-output.py`再走で件数減少確認 ②多版統合(鬼平型)の版分離 ③SOURCE_GAP486=種4 ④NDL無2,333は楽天発売日で補助(Kobo後)。
