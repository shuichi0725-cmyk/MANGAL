---
name: full-promote-resolves-public-slug
description: 【型】フルpromoteは公開slugを再導出するので、手で直したslugの頁が黙って改名される。索引を焼き直すまで気づけない
metadata:
  type: project
---

**2026-09-22 週次で実踏**: 前週の本番と索引を突き合わせたら **23頁のslugが変わっていた**。
犯人は 2026-09-21 08:30台に走った**フル promote**(`find data/manga.v2 -newermt` で69,137ファイルが同時刻=フル走査の指紋)。

**機構**: promote は公開slugを**その場で再導出**する。過去に手で直した slug は、生成器が出す正規形と
ズレていることがあるので、フルpromoteのたびに正規形へ引き戻される。
今回の23頁は「されたされた」型([[slug_duplicated_token_sareta_type]])の是正差だった:
- 手の是正 = **切り詰め後**の文字列から重複トークンを削る → 短いまま
- 生成器 = **切り詰め前**に重複を削るので、空いた枠に末尾トークンが1つ入る → 1トークン長い

**なぜ気づけないか**: targeted反映は索引を `--update/--remove` で部分更新するため、
**フルpromoteで起きた改名は索引に反映されない**。次にフル `list-index` を焼いた時に初めて差が出る
(= 週次の手順1)。本番は旧slugのままなので、その週の prune で旧HTMLが消えて404になる。

**検出**: 前回フル週次の `data/manga-list-index.json` を `git show <marker>:` で出し、
**題をキーに** slug を突き合わせる(slugキーでは改名が「消滅+新規」に見える)。
★同題の別作品が居るので、旧slugが今週も実在する行は除外すること(でないと偽の改名になる)。

**処置**: 旧slug→新slug を `data/slug-aliases.yml` に追記するだけでよい。
`_gen-redirects.py` が**連鎖を平坦化**するので、旧slugを指していた既存aliasも自動で新slugへ1ホップになる
(今回はこれで preflight の「死に転送23件」が同時に消えた)。旧URLは301で生き残る。

**判断**: 生成器の正規形に寄せる(= aliasを張って受け入れる)方が収束する。
slugを固定して生成器と戦うと毎フルpromoteで再発する。ただし**公開済みslugのrenameはユーザ確認が要る**ので、
必ず一覧にして報告する。[[slug_rename_kills_slugkeyed_seed]] [[pubslug_src_stem_generator_trap]]
