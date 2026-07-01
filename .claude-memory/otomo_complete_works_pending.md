---
name: otomo-complete-works-pending
description: OTOMO THE COMPLETE WORKS(大友克洋全集)はMADB未収録、資料が揃い次第 種4 で補完登録する残タスク
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

**残タスク(ユーザ明示・2026-06-01)**: OTOMO THE COMPLETE WORKS(大友克洋全集)を 種4(`data/seeds/volumes-supplement.yml`)で補完登録する。 ユーザが**資料を揃え中**、 揃ったら着手。 忘れないこと。

**確認済の状況(種2 = MADB release 1.2.16)**:
- ★OTOMO THE COMPLETE WORKS / 大友克洋全集 は **MADB 未収録**(取込もれ)。 2023年刊行開始の最新企画でMADBが未カタログ化。
- 大友関連の全集系 imprint は旧「大友克洋作品集」(ショート・ピースに付与)のみ。
- ★**判定シグナル**: 種2の AKIRA は 通常版6巻(KCデラックス)/ 総天然色6巻 / アニメコミック5巻 / 海外版27巻 のみ。 **8巻の AKIRA が現れたら全集収録の可能性が高い**(全集版AKIRAは別の巻割)。 現状8巻AKIRAは無い=全集未収録の裏付け。

**着手時の方針**:
- MADBの全集の扱い(手塚治虫漫画全集/石ノ森萬画大全集)に倣い、 ★各収録作を**個別ページ**として扱い、 全集名を imprint に。 全集を1ページに束ねない。
- 種4 形式に従い、 各巻の確定ISBN13・発売日・publisher・edition_type・収録作の series_keys 紐付けを Amazon/NDL/講談社公式で裏取りして登録([[project_architecture_seeds]] の種4 protocol、 CLAUDE.md「種4」節)。
- 種2 sqlite は不変、 audit+本番yml生成時に補完反映。
