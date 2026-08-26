---
name: orphan-source-pages-restored
description: 源なしmanga.v2頁258件を復元(2026-08-26週次で発覚)。promoteは元頁駆動=源が消えると次のフルpromoteで頁消失する構造
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-26T12:14:00.640Z
---

2026-08-26の週次finalizeで「索引に居るのに未生成」1頁(tougarashi-dragon-no-shin=数値ペンネーム359のint化)を調査中に、**data/manga(源)にもpreorder-pagesにも存在しないmanga.v2頁が258件**あると判明。月次1.2.19のtorikoboshi頁化94件の源が全て消えていた+過去分の残り。promoteは元頁駆動([[orphan_series_promote_is_srcpage_driven]])なので、**源なし頁は次のフルpromote(月次)で黙って消える**ところだった。

**Why:** data/mangaはgitignore(再生成物扱い)なので消えても履歴が無い。genpagesの源がいつ消えたかは未特定(頁化→preview確認→renameの流れのどこか)。数値ペンネームはYAML安全弁が無いとintで書かれ、Zodがname:stringを要求してビルドskip=「検索に出るのに404」になる。

**How to apply:**
- 復元手法(実証済み): manga.v2から最小源(slug/title/_skey/kana/romaji/authors/year/status/demographic)を再構成。_skey=頁ISBNで種2逆引き(257/258解決)。種2外の自己完結頁(魔界転生=canonical供給)は**合成_skey『name:著者|name:題』**(オーフェン式)。復元後promote --onlyで**同値確認**(完全一致を実証)
- 著者名は必ず `str()`+quote(数値ペンネーム359/296型)
- 月次サニティ候補: 「源なしmanga.v2頁」数の監視(v2 − data/manga − preorder-pages)。増えたら頁化フローの源永続化漏れ
- 関連: [[orphan_series_promote_is_srcpage_driven]] [[seed4_auto_wipe_accident]]
