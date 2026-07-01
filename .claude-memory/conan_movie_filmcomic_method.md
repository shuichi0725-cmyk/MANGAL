---
name: conan_movie_filmcomic_method
description: コナン劇場版の「漫画版(コミカライズ=keep)」と「フィルムコミック(=drop)」の判別方法。wiki生ソース(action=raw)+楽天seriesNameレーベル。同パターンの映画タイアップ仕分けに再利用可
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

コナン劇場版は同じ映画タイトルに **漫画版(コミカライズ)** と **フィルムコミック** が併存し、判別が要る(2026-06-16 全仕分け完了)。

**判別の決定軸 = 楽天 seriesName(レーベル名)+作画者**:
- **KEEP=コミカライズ**(描き起こし漫画): seriesName「少年サンデーコミックス(素)」+ 著者に **阿部ゆたか/丸伝次郎** / 商品説明に「漫画化」「コミカライズ」。巻は「○○2」等の番号付き。
- **DROP=フィルムコミック**(映画の画面流用本): seriesName「少年サンデーコミックス**〔ビジュアル(セレクション)〕**」「〜スペシャル」、題/説明に「**劇場版アニメコミック**」「フィルムコミック」。巻は「(上)(下)(完全版)」。
- **DROP=コンビニ廉価**: seriesName「**My First BIG**」。
- **DROP=総集編/セレクション**: 「○○セレクション」(キャラ別/テーマ別)「vs黒ずくめ PART1-4」=既刊エピソード寄せ集め。「挑戦状」=クイズ本。「推理ミス」(京都トリック研究会)=第三者考察本。「カラーイラスト全集」=画集。

**wiki調査の信頼手法**: WebFetch(小モデル抽出)は不安定。**`ja.wikipedia.org/w/index.php?title=...&action=raw` で生wikitext取得** → ISBN行を逐語抽出が確実(`scripts/_conan-wiki-raw.py`)。ただし wiki書籍欄は不完全(漆黒は漫画版を載せず)→ **最終確証は楽天の商品説明**。

**コミカライズ存在作 = 5本**(他は film のみ): 第1作 時計じかけ / 第3作 世紀末(全3巻) / 第5作 天国へのカウントダウン / 第7作 迷宮 / 第13作 漆黒(全3巻)。**+ recent映画(純黒/ハロウィン/緋色/黒鉄等)も「○○2」番号付きコミカライズ(阿部ゆたか/丸伝次郎)が存在**=keep。全コミカライズ巻はDB収録済(種4不要)。

**罠**: 同一コミカライズが表記揺れ(空白有無)+著者名key で複数sidに分裂([[series_fragmentation_rootcause]])→ series-merge.yml で統合。filmとcomicalizeはqidで別(film=作者qid Q313945 / comicalize=作品qid Q11657721 等)。混在ページは [[promote_merge_respects_drop]] の修正で解消。成果物=`docs/conan-decision-keep-drop.pdf`。
