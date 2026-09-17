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

## ★変種(2026-09-15 週次で実踏): 源が git には在るのに worktree から消えている

「源が無い」だけでなく **git追跡済みの `data/manga/*.yml` が作業ツリーから削除された状態**(`git status` に
` D` 11件)で週次に入りかけた。中身は直近の頁分割で作った源(俺の空3分割・王様の仕立て屋2分割・
激マン2・騎士ガンダム系ほか)で、`data/seeds/source-pages/` にも無かった = **次のフルpromoteで頁ごと消える**
一歩手前。削除した犯人のscriptは特定できず(`.cache/srcstub-bak-*` は別件)。

- **復元は `git checkout -- data/manga/` 一発**(gitignore配下でも force-add 済みなら追跡されている)。
- ★**週次の入口で `git status --porcelain -- data/manga/ | grep '^ D'` を見る**のが安い防壁。
  0件でないなら中身を確かめてから進む(preflightには未実装=入れる価値あり)。

## ★2026-09-17 復元完了(400 → 4)+ 月次検出器#34を新設(ユーザGO)

- **源stub 396件を `data/seeds/source-pages/` に生成**(git追跡=恒久)。 `_skey` は
  **頁ISBNの種2逆引きの多数決**(1本目のISBNだけで決めない)。 400/400で逆引きできた。
- ★**同値確認が要る**(実証): `promote --only-file` で再生成し before/after を突合 →
  **384件 完全同値 / 12件 題名そのままで巻が純増**(源が消えて凍結していた頁の追いつき= 正常) /
  **★4件 題名が変わった**。 後者は `_skey` が**親シリーズ**を指し、**別の生きた頁と重複**する型:
  `kamakuramonogatari`『鎌倉ものがたり. 異界編』1巻 → 『鎌倉ものがたり』59巻
  (本番に `kamakura-monogatari` が別に実在)。 他 ajinopuroresu / arufuheim… / kurabetekemishite…。
  **この4件は復元を見送り before に戻した**(= per-case 裁定待ち。 種2に該当subシリーズが無い)。
- **key2slug.tsv に368件を追記**。 28件は **同じseries_keyが既に別slugへ登録済み**
  (= 改名後の新slug)で、足すと二重頁になるので見送り(`.cache/orphan-key2slug-skipped.txt`)。
- **月次サニティ #34 を新設** = `scripts/_audit-orphan-source-pages.py`。
  CLAUDE.md索引 / `docs/monthly-sanity-detectors.md` 本文 / `_monthly-distill.py` DETECTORS の
  3点に登録済み(`_check-sanity-registry.py` green)。 **再発は件数で見る**。
- before退避 = `.cache/orphan-v2-before/`(400件)。

★根因の確定: **400件中398件が `.cache/apply/key2slug.tsv` 未登録**だった
= 「src頁を作ったのにキー登録を忘れた」型 [[new_page_creation_srcpage_key2slug]]。
改名頁が74%(298/400)を占めるので、**改名でキーを張り替えた時に旧stemの登録が落ちる**のが主経路。

### ★残り4件も per-case で復元 → **源なし頁 0**(2026-09-17)

4件とも「**親/兄弟seriesのISBNを持つ分割頁**」で、素直な `_skey` では related-merge が兄弟を
巻き込み題も巻も化ける(kamakura-monogatari-makai-hen 1巻 → 『鎌倉ものがたり』59巻 = 既存頁と重複)。
→ **激マン!Z&グレート編と同じ型**で固定した:
  src stub に **`_title_force` / `_kana_force`** を置き、**`edition-overrides.json`(キー=公開slug)で
  editions を全置換**する。 これなら _skey が親を指していても中身は動かない。
対象 = ajinopuroresu 『味のプロレス. マニアック編』1巻 / alfheim-no-kishi-ballad-tsugumi-no-mori 11巻 /
kamakura-monogatari-makai-hen 1巻 / kurabete-kemishite 3巻(overrideは既存・題だけ固定)。
4件とも before と slug/title/ISBN集合/巻数/書影/説明が**完全同値**。

★**罠**: `_skey` を**手で書くと静かに失敗する**(全角チルダ「～」/括弧の字形違いで series が引けず、
`find_series` が None → 頁ごと skip = **`wrote 0` で終わりエラーにならない**)。
**DBの生値(`series_key`)をそのままコピーする**こと。 実際1回踏んだ。
