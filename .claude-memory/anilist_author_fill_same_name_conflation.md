---
name: anilist_author_fill_same_name_conflation
description: 著者が空の頁を AniList staff で埋める補完が、AniList の同名束ね(sora と 三月ソラ)で別人を入れる。是正= author-overrides.json(頁固定)
metadata:
  type: project
---
`_promote-bulk-v2.py` の「著者ゼロ→AniList補完」(`.cache/author-fill-map.json`、anilist_id→staff の日本語名)は、
種2の series_authors が空の頁だけに著者を入れる。AniList が**同名の別人を1人の staff に束ねている**と別人が入る。

実例(2026-10-31 ユーザ指摘「漫画家名はsoraが正しそう」): 『墜落JKと廃人教師』(白泉社 花とゆめ・全20巻)の作者は **sora** なのに
頁は **三月ソラ**(講談社の別人)。種2の series_key は `name:sora|…` で正しかった= 補完だけが誤り。
`data/seeds/identity-check.tsv` / `author-diff-real.tsv` に AUTHOR_MISMATCH として既に出ていた(=この2表は同型の発見に使える)。

**Why:** 補完は「空の時だけ」なので静かに入り、題・ISBNは正しいため他の検査に掛からない。

**How to apply:**
- 是正= `data/seeds/author-overrides.json` に slug で著者を固定(override が先に効き、補完は authors が空でないので走らない)。
  形式= 2スペースindent・CRLF・`_note` 付き。json.dump で並べ替えると全行差分になる→末尾追加で書く。ヨミが無ければ `author-yomi.yml` へ。
- 同型を探す= author-fill-map の同一名が複数 anilist_id に付いているもの × 頁の出版社が食い違うもの。
- 関連: [[author_qid_wrong_person]] [[ndla_8digit_author_merge]]
