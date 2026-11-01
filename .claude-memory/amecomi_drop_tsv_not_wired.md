---
name: amecomi_drop_tsv_not_wired
description: アメコミ等の非掲載は non-manga-drop.yml(series_key)へ書く。american-comics-drop.tsv/anthology-drop.tsv は promote が読まない=フルpromoteで頁が復活する
metadata:
  type: project
---

`data/seeds/american-comics-drop.tsv`(slug単位の台帳)は `_promote-bulk-v2.py` に結線されていない。promote が読む非掲載は
`non-manga-drop.yml` / `magazines-drop.yml` / `company-nonmanga-drop.json`(series_key単位)だけ。

**Why:** 2026-06-20 にアメコミとして外した garfield / x-men / x-men-1994 / x-men-1994-4 が、10/20 月次のフルpromoteで黙って復活し、
本番に出たまま Web材料の対象にも入っていた(2026-11-02 ユーザ指摘「消した漫画を収集しようとしてる」)。tsv冒頭に「昇格要(follow-up)」と書いたまま放置。

**How to apply:**
- 頁を非掲載にする時は、頁のISBN→種2(.cache/db-v2.sqlite)逆引きで series_key を全部出し、`non-manga-drop.yml` に追記(+ `nonmanga-drop-changelog.jsonl`)→ `_reflect-targeted.py --drop`。tsv だけに書いて終わりにしない。
- 2026-11-02 に上の4頁の17キーを昇格済み(sandman は 10/07 に昇格済み)。
- リダイレクトは `_gen-redirects.py` が行き先の消えた alias を自動で落とすので手直し不要。

関連: [[drop_page_redirect_chain]] [[scope_bd_translation_not_listed]]
