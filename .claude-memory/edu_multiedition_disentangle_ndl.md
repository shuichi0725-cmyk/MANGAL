---
name: edu_multiedition_disentangle_ndl
description: 教育系学習まんがの年代版混入(Frankenstein)是正法=ISBN発行コード×NDL発行年で年代版分離→NDLで全巻補完→楽天ISBN直引きで書影。集英社日本の歴史で実証
metadata: 
  node_type: memory
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

2026-06-29。教育系学習まんがは**同シリーズが何度も版を重ね(年代版)**、promoteが巻番号ごとにISBNを1つ選ぶ際に**年代を区別せず混ぜる**→vol1-20に別年版のISBNが寄せ集まりFrankenstein化(1巻=2016年/2巻=1982年…)。

**是正法(集英社 日本の歴史で実証)**:
1. ★**ISBN発行コード `isbn[6:10]`** が年代版を識別(集英社の場合: 2440/2500=1982・1950/1951/2441=1992・2390=1998・7461=2007漫画版・2391=2016・2392=2021)。コード=事実境界。
2. ★**NDL SRU title検索で全巻取得**(楽天でなくNDL先=[[ndl_volume_completion_better_than_rakuten]]。古版/絶版もNDLにある)。NDLの`dcterms:issued`発行年でコード→年代を確定(コード番号だけでは年代不明)。
3. 発行年で年代版editionにグループ(`edition.label`="日本の歴史 2016年版"等、type=standard/bunkobon)。urusei多版モデルのタブ。
4. ★**別シリーズ除外**: 「人物日本の歴史」(code2520)等は title 検索に紛れる→title/codeで除外。
5. NDLで各年代版の欠巻補完→**書影は楽天ISBN直引き**(largeImageUrl・noimage除外)。
6. 重複ページ(同jumbleが著者別に2ページ=笠原/井上)は1ページに統合、著者=監修(児玉幸多)。

**実装**: scripts/_investigate-nihonshi → _disentangle-nihonshi(コード分離) → _complete-nihonshi-ndl(NDL全巻) → _rebuild-nihonshi-final(統合・補完・書影)。結果=2016版/2021版/1982版が[1-20/18]完全。

**残**: ①preview のみ=本番durabilityは種4 or option2(promote側で発行コード版分離を恒久実装=全多版作に効く本丸)未了。②他教育系(世界の歴史等)も同jumbleの可能性大=同法で展開可。[[multi_edition_unification_pending]] [[overmerge_sweep_conclusion]]
