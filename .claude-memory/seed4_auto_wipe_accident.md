---
name: seed4-auto-wipe-accident
description: 月次が種4-auto(日次続巻台帳)を全消し=2回。8/21(1.2.19)分は復元済だが★7/24(1.2.18)分2,691件は復元対象外で225件が今も未復元(2026-10-06発見)。種4-autoは蓄積資産=再生成禁止
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-10-06T15:25:18.968Z
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

## ★2026-10-06 発見: 同じ全消しが **7/24(月次1.2.18・commit 1e107d9a4)にも起きていた**=未復元

mangaseek の発売日一覧との突き合わせ([[competitor_mangaseek_teardown]])で 9/17 発売の続巻が19冊抜けていたのを辿って発見。
- 1e107d9a4 で種4-auto が **30,058行→6行(`volumes: []`)**。削除 2,691 ISBN・追加 0。ヘッダの「db-v2再build時は再生成」がそのまま走った。
- 8/26 の復元は **8d02dbf88~1(=8/21直前)** から = 7/27〜8/21 に溜まった分だけ。**7/24 に消えた分は対象外**だった。
  `_audit-isbn-loss.py` も基準線が8/26以降なので、それより前の消失は見えない。
- 2026-10-06 時点の内訳(ISBN索引を --build し直して照合): 頁に戻った 2,440(MADB取込・8/4巻抜け充填・9/24保留見直し等の別経路)/
  種2に在るが頁に出ない 21 / 種4に在る 5 / ★**どこにも無い 225**(seedには changelog・completion-judged 等の**記録だけ**が残る)。
  225の内訳: 既存頁で**巻番号ごと欠け・発売済 55**(無職転生25・これは経費で落ちません!17・鬼役26・はるかリセット26・銀牙伝説レクイエム12 を頁で直接確認)/
  頁が特定できない発売済 119(**112が 7/11 の stale-backfill = title_display 空**で題照合できない。series_keys で頁に当てる必要)/
  未発売・日付なし 21 / 頁に同番号が別ISBNで在る 30(特装版等=実害小。シャンフロ27・花野井くん19 はこれ)。
- ★再取得されない理由 = 日次の楽天予約は「前回から増えたISBN」しか分類しない([[daily_distill_hold_not_requeued]])ので、
  7月に一度拾った巻は二度と拾われない。巻抜け監査は**途中の欠け**しか見ないので、**最新巻(末尾)の欠け**は誰も検出しない。
- 再算出の仕方: `git show 1e107d9a4 -- data/seeds/volumes-supplement-auto.yml` の削除行 × 現在の `.cache/isbn-page-index.json`(先に `_exists.py --build`)× 種2 `volumes.isbn13` × `data/seeds` 全文。
- ★**2026-10-06 GO→復元済み**(`scripts/_restore-seed4-wipe-0724.py --plan/--apply`・判定表 `docs/production-diagnostics/seed4-restore-0724.tsv`):
  225件 → 復元74冊/71頁(日次続巻と同じ検問+楽天ISBN照合=題が頁題で**始まる**・著者・巻番号・漫画ジャンル・**楽天題でも特装版判定**)+仮書影50冊を実物に。
  保留139の大半(約110)は「同巻番号が別ISBNで既に頁に在る」= 7/11 stale-backfill の古い巻はその後別経路で埋まっていた(実害なし)。
  ★検問を締めた実例: ねこぱんち頁に「お江戸/おとなのねこぱんち」(別シリーズ)7冊=題を「含む」判定ですり抜けた / 傷モノの花嫁12・アイマス5 = 古い記録に題が無く特装版検問をすり抜けた /
  アンゴルモア博多編13 = 頁が元寇合戦記1-10+博多編11-12の版混在(**頁の分離が未着手**)。
  個別: マンガ法律の抜け穴4/9/10/11・学研まんが世界の歴史9(楽天分類が漫画外でも同じ頁の他巻は掲載済み)・ねぇ、ぴよちゃん11(ねえ/ねぇ)・canonical本体へ ざこ検4/完全版 飛ぶ教室3。
  ★2026-10-07 ユーザ裁定で処理済み: 本宮ひろ志漫画大全集1-8=男一匹ガキ大将に kanzenban タブ / sandman=アメコミで drop / アンゴルモア=博多編を別頁に分離([[angolmois_hakata_split]])。
  **残**: bolt-and-nut 10(canonicalは別ISBN …1866 で確定済み=要調査なら per-case)。
  以後の監視 = 月次サニティ#36 `_audit-harvested-not-on-page.py`(確認済み簿 data/seeds/harvested-not-on-page-ack.jsonl)。
