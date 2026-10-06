---
name: canonical-isbn-sequence-renumber-trap
description: 【型・2026-10-07】8/17ギャラ型一括是正の「ISBN連番から巻番号を振り直す」は、古い巻が後年ムック化/再刊で後ろのISBN帯に入ると誤る(ボルト&ナット2巻を10巻に振っていた)。NDLのvol番号×楽天題で検算する
metadata:
  node_type: memory
  type: project
  originSessionId: 3694f556-496e-4196-90f0-578fafaf2df4
  modified: 2026-10-06T20:52:07.301Z
---

ボルト＆ナット(BOLTS AND NUTS!・田中むねよし・ネコ・パブリッシング)で実踏(ユーザ指示「ボルトアンドナット10巻の対応」)。

- 8/17 の canonical 注記「v2枠の 9784777001866(2004-08)は ISBN連番から v10 の実体」= **誤り**。
  NDL(作者束縛SRU・`dcndl:volume` つき20件)と楽天題「BOLTS AND NUTS!(vol.N)」の2ソースで確定:
  …1866 = **vol.2**(2004-08・Neko mook 686=初期巻の後年ムック化)/ …1040 = **vol.10**(2003-12)/ 旧「1巻」…5344 = **番外編**(1999-02)。
  vol.1 はティーポ1997年1月号増刊(ISBN無し=非掲載)、vol.3 は両ソースに無し。vol.19・20(2011・2013)が未掲載だった。
- 是正 = canonical 本体: 2巻復活 / 10巻=…1040 / 番外編は **4.5 + volume_label=番外編**([[half_volume_number_mechanism]]・画面は「番外編」表示)/ 19・20巻追加。記帳 edition-fix-changelog.jsonl。
- ★**なぜ連番が誤るか**: 初期巻が雑誌増刊で出て、後年ムック/再刊でISBNが付くと、**巻番号は小さいのにISBNは後ろの帯**に来る。
  連番+発売日だけで「間に入る巻」を決めると、別の巻の実体(ここでは…1040)を押しのけてしまう。**NDL の vol 番号が先、ISBN連番は補助**。
- 型の大きさ(同日検算): 「ISBN連番/採番」注記の canonical 352本・3,302巻を楽天題の巻番号と照合 → 食い違い86冊のうち
  全集/作品集/傑作選の**通し番号**(手塚治虫漫画全集（35）等=作品内の巻と違って正しい)を除くと **疑いは ルパン三世(lupin-iii)11冊のみ**
  (canonical 4〜14 vs 楽天（2）〜・中央公論社 4-12-4104xx)。水木しげる漫画大全集34冊は頁自体が大全集=大全集番号が正。**ルパン三世は未着手(ユーザ判断待ち)**。
関連: [[seed4_auto_wipe_accident]] [[wikipedia_bibliography_crosscheck]] [[feedback_one_bug_means_a_class]]
