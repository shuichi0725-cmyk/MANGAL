---
name: angolmois-hakata-split
description: 【型・是正済 2026-10-07】アンゴルモア=種2の1つの版に元寇合戦記1-10と続編の博多編1-12が同じ巻番号で同居→同番号は古い方が勝ち博多編1-9が隠れていた。博多編を新頁に分離(13巻)
metadata:
  node_type: memory
  type: project
  originSessionId: 3694f556-496e-4196-90f0-578fafaf2df4
  modified: 2026-10-06T15:25:15.654Z
---

ユーザ裁定「分ける」+ ja.wikipedia『アンゴルモア 元寇合戦記』書誌情報(23冊)× 楽天ISBN照合(23冊すべて実在)× 種2。

- 真因: 種2 series 33438「アンゴルモア」の**単一 edition**に元寇合戦記1-10(2015-18)と博多編1-12(10欠・2019-26)が**同じ巻番号**で入っていた。
  頁生成は同番号を古い方で取るので、博多編1-9は隠れ、番号が被らない博多編11・12だけが「元寇合戦記の11・12巻」として出ていた
  (年も2015-2026に化けていた)。7/24全消しの復元判定で博多編13を「別シリーズ」と見て保留したのが入口。
- 是正(PoJ式 [[ousama_shitateya_4part_split]] と同じ): `edition-canonical/angorumoa.yml`(元寇合戦記10冊)/ 新頁
  `angorumoa-genkou-kassenki-hakata-hen` = `source-pages` stub(_skeyは親と同じ)+ canonical(13冊)+ edition-overrides(題/ヨミ/anilist:false/subtitle空)
  + status-corrections(ongoing)+ magazine-corrections(両頁 comic-walker。親の旧値 shonen-ace は誤り。初出サムライエースはマスター外)
  + genre-append(war=親と同じ)。記帳 unmerge-changelog.jsonl。
- ★Wikipedia の誤り2つ(楽天+種2で確定): 博多編4巻の発売日「2020年3月25日」→ 正 2021-03-25 / 4巻と5巻に同じISBN → 5巻=9784041119235。
  日付は「楽天と年月が一致すれば Wikipedia」([[wikipedia_release_date_is_authoritative]])。
- ★親頁の題は「アンゴルモア」のまま据え置き(正式は「アンゴルモア 元寇合戦記」)。題を変えるとフル promote が公開 slug を
  導き直して改名するおそれ([[full_promote_resolves_public_slug]])= slug 変更はユーザ確認事項なので触らなかった。
- 同日の他の裁定: 男一匹ガキ大将に「本宮ひろ志漫画大全集」001-008 を kanzenban タブで追加(ユーザ提示の s-manga は BOXセット
  ISBN 9784087938012=大全集001-008+特典000『天然まんが家』の予約受注生産。★BOX は巻として載せず単巻8冊を載せる)/
  sandman = THE SANDMAN 新訳(インターブックス)=アメコミで non-manga-drop(新訳3 series+旧訳2 series)・頁 drop・R2 prune 台帳へ。
関連: [[seed4_auto_wipe_accident]] [[oresora_4way_split]]
