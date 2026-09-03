---
name: subtitle-orphan-volume-split-sugar-spice
description: 【型・検出器未着手】Sugar&Spice型=巻題(副題)を題としてMADBが単独登録→種2で別sid(0巻/extra)に分裂→本編頁から巻が欠ける。楽天subTitle「親題+巻番号」が機械信号
metadata: 
  node_type: memory
  type: project
  originSessionId: f8fa63b4-3ce7-45e1-b2ab-f3f4fbab02f4
  modified: 2026-09-03T03:26:56.366Z
---

**型 (2026-09-03 ユーザ発見 sugar-spice)**: 各巻に固有の巻題を持つシリーズ(Sugar & Spice=全巻ジャズ標準曲題)で、MADBが
17/19/20巻を巻題「Somethin' stupid」「Rose & beast」「Over the rainbow」を**題として**別MADB-IDで登録し、
種2のクラスタキー(著者+題)がそれを別sid(number=0/1, is_extra=1)に落とした。本編sid(1-16,18)と結線されず、
頁は「17巻欠け+18巻で終わり」に見えた(完結・全20巻なのに)。

**なぜ既存監査が拾えないか**: 孤児sidは単巻・未頁化なので `_audit-solo-truncated.py`(vol1不在の孤立**頁**)の
対象外。巻抜け仮想は 1-16,18 の内側(17)しか見えず、末尾の19/20は「無い」ことが分からない。

**機械信号(検出器候補・未着手)**: 楽天キャッシュの `subTitle`(or title末尾)が「<既存頁の題> <数字>」を名乗るのに
そのISBNが本番page-indexに無く、同著者に当該題の頁が在る。楽天1パス走査で算出可(cf. `_audit-excerpt-subtitle.py`
の裏返し)。実例の楽天値: title「Somethin' Stupid」subTitle「Suger ＆ Spice 17」(楽天側の綴り誤りあり=正規化要)。

**是正の型**: 種4(volumes-supplement.yml)で本編 series_key に結線(種2不変)。renumber merge(series-merge.yml)でも
可だが、群に複数題があると全巻に title_display(=クラスタ題)が付く副作用があるので、本編が番号付きで揃っている
場合は種4が軽い。★種4の title_display は現行promoteでは頁に**出ない**(qid照合の名前集合にしか使われない。
hardboiled-daddy でも同じ)= 巻題を表示したければ promote 側の結線が要る(未実装・要裁定)。

**同時発見**: 4巻の日付逆行(MADB/NDL=2008-05 は後刷り奥付。楽天 2006-04 + Amazon 2006-04-17 の2源で
release-date-override)。笠倉のNDL納本は後刷りが混じる=この出版社の日付逆行は同型を疑う。

**How to apply**: 「完結してるのに巻が足りない」報告で末尾巻が無い時は、まず楽天/NDLで作者束縛検索して
全巻数を確定し、欠け巻ISBNを db-v2 で引く(別sidに眠っていれば種4で結線、無ければ真の取込もれ)。
検出器化はユーザ裁定待ち。[[volume_split_merge]] [[series_fragmentation_rootcause]] [[feedback_one_bug_means_a_class]]
