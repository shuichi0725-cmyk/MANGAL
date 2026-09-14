---
name: orphan-source-pages-restored
description: 源なしmanga.v2頁=次のフルpromoteで黙って消える構造。2026-08-26に258件復元、2026-09-14に再び414件を実測(未着手・GO待ち)
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-09-14T00:00:00.000Z
---

2026-08-26の週次finalizeで「索引に居るのに未生成」1頁(tougarashi-dragon-no-shin=数値ペンネーム359のint化)を調査中に、**data/manga(源)にもpreorder-pagesにも存在しないmanga.v2頁が258件**あると判明。月次1.2.19のtorikoboshi頁化94件の源が全て消えていた+過去分の残り。promoteは元頁駆動([[orphan_series_promote_is_srcpage_driven]])なので、**源なし頁は次のフルpromote(月次)で黙って消える**ところだった。

★**2026-09-14 の日次蒸留で再実測 = 414件**(manga.v2 69,238 − data/manga − source-pages 340 − preorder-pages 2,049)。一覧= `.cache/orphan-source-pages-2026-09-14.txt`。**未着手**(414頁の一括復元は大規模変更=ユーザGO待ち)。この日は per-case で1件だけ復元した(orenoshoukanmahougaokashii-… = 種4で続巻を足しても `promote --only` が対象外にして出なかったので源stubを作った)。

**Why:** data/mangaはgitignore(再生成物扱い)なので消えても履歴が無い。promoteの頁producerは**2つだけ**(①`data/manga/*.yml` + `data/seeds/source-pages/*.yml` の src ループ ②`data/seeds/preorder-pages/*.yml`)で、フル時は先頭で `OUT_DIR/*.yml` を全削除してから作り直す=どちらにも源が無い頁は再生成されない。実装で確認済み(`_promote-bulk-v2.py` の `if not ONLY_SLUGS:` unlink ループ / OUT_DIR書き込みは2箇所のみ・art-booksは別DIR)。数値ペンネームはYAML安全弁が無いとintで書かれ、Zodがname:stringを要求してビルドskip=「検索に出るのに404」になる。

**How to apply:**
- 源stubは**最小形でよい**(実例 `data/seeds/source-pages/2-hearts.yml`): `slug` / `title` / `title_kana` / `_skey` / `_note_origin`。残りはpromoteが種2+seedから埋める
- 復元手法(実証済み): manga.v2から最小源を再構成。_skey=頁ISBNで種2逆引き(257/258解決)。種2外の自己完結頁(魔界転生=canonical供給)は**合成_skey『name:著者|name:題』**(オーフェン式)。復元後promote --onlyで**同値確認**
- 著者名は必ず `str()`+quote(数値ペンネーム359/296型)
- ★**症状から辿る入口**: 「種4に巻を足して反映したのに頁に出ない」/「書影seedに実物が在るのに頁が仮.gifのまま(cover-override-unreflectedに残り続ける)」= まずこの型を疑う。見分け= `promote --only <stem>` が **total: 0 / wrote 0** を返す(2026-09-14に9月書影で3頁実踏: andaaaidoru, ashiyayamanoteodougugeihinkan-komikku, deyueru-masutaazu-aizouban)(`ls data/manga/<stem>.yml data/seeds/source-pages/<stem>.yml`)
- 月次サニティ候補: 「源なしmanga.v2頁」数の監視(v2 − data/manga − source-pages − preorder-pages)。増えたら頁化フローの源永続化漏れ
- 関連: [[orphan_series_promote_is_srcpage_driven]] [[seed4_auto_wipe_accident]] [[new_page_creation_srcpage_key2slug]]
