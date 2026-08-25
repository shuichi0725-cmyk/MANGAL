---
name: seed4-auto-wipe-accident
description: 月次1.2.19が種4-auto(日次続巻台帳916巻)を全消し→883巻が本番から消失。復元済み・種4-autoは蓄積資産=再生成禁止
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-25T16:10:10.364Z
---

2026-08-21の月次蒸留1.2.19が `data/seeds/volumes-supplement-auto.yml`(日次蒸留の続巻台帳)を**全消し**(916巻)。うち**種2未収録の883巻が本番から黙って消失**(異種族レビュアーズ12巻等806頁)。2026-08-26に週次前preflightの**ISBN消失監視**(`_audit-isbn-loss.py`)が検知→git履歴(8d02dbf88~1)から914巻を復元し806頁再生成で解消。

**Why:** 種4-autoは「派生seed(再生成可能)」ではなく**蓄積資産**(日次の楽天予約zokkanの唯一の記録)。月次のintakeが派生seed再生成と一緒に扱うと消える。消失は誰にも見えない=監視だけが頼り。

**How to apply:** (★2026-08-26 GO実装で全部機械化済み)
- 封鎖4層: ①_register-seed4-ndl.py=merge書込(縮小abort/backup/空入力保持) ②intake末尾isbnloss stage ③preflight seed4_auto_volumes減少FAIL ④clean鮮度ガード(Phase0+intake)
- 汎用番人: _check-seeds.py(parse死/台帳減少/種4フィールド)=intake先頭stage+reflectゲート結線済
- 完了判定: _monthly-postflight.py(週次側はfinalizeがprune実証+purge+snapshot自動)
- 月次で種4-autoを全消し/再生成しない。retireは「ISBNが種2に実在する巻だけ」個別除去
- 大きな蒸留後は `python scripts/_audit-isbn-loss.py` で理由なし消失0を確認(preflightに組込済)
- 同事故の副産物として発見した型: ①**number=0の1巻が続巻到着で不可視化**(promoteの「number=0はnumbered巻があればskip」規則。泣かせたくて/エロゲ世界=種4巻1で復元) ②**スペシャルプライスパック(廉価再録)が主枠を奪う**(猫と竜=volume-exclude) ③続巻が著者名違いの別クラスタに落ちる(アラフォー賢者15-18=[[series_fragmentation_rootcause]])
- 関連: [[intake_manifest_ledger_live]] [[never_delete_because_broken]]
