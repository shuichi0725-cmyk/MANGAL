---
name: synopsis-ja-seed
description: synopsis和訳=git追跡seed(data/seeds/synopsis-ja.json)。高価なAI生成物だけ永続化、他enrichは再join。蒸留で純粋追加
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

AniList英descの**AI日本語要約あらすじ**(60-120字、逐語訳でなく言い換え=著作権配慮)の永続化方式。

**確定 (2026-06-02)**: ★`.cache/synopsis-ja-map.json`(gitignore=消える)から **`data/seeds/synopsis-ja.json`(git追跡seed)** へ移行。 key=**anilist_id**(作品単位、series_keyでない)、 {aid(str): ja} の単純map。 `_apply-synopsis.py`(MAP path) と `_promote-bulk-v2.py`(L1280付近 _syn_path) 両方の読込先を切替済。

**設計判断**: ★**synopsisだけが「高価なAI生成物」**=種3と同格でgit永続化。 他enrich(synonyms/genres/tags/anilist_id/QID)は **dump+matchから毎promoteタダで再join**するので**git非永続**(=再生成可能なものは焼かない原則)。 ★種3本体には**焼き込まない**理由3つ=①key違い(series_keyでbakeするとmatch変更時に別作品へ貼付く)②種3不変・promote-join設計を壊す③33MB巨大編集のモバイルfreeze回避([[feedback_mobile_render_freeze_largefile_edit]])。 ユーザ承認済(「synopsisだけgit seed化・独立ファイル・anilist_id key」)。

**蒸留での扱い(純粋追加only)**: enrich更新→未訳delta抽出(synopsis-ja.json未存在 かつ AniList desc有)→ `.cache/syn-batches/batch-NNN.json`(100件/batch)→ ★**分散workflow**で各batch AI要約→ `.cache/syn-out/batch-NNN.json`書出(中断耐性)→ merge→ `_apply-synopsis.py`で純粋追加(新規N/上書き0確認)→ ★**commit+push**。 本番反映は**全DB promote時**にmanga.v2へ焼く(seed commitだけでは本番に出ない)。

**実数 (2026-06-02時点)**: 移行時 29,364件。 ★追加中=非成人6,602(workflow `synopsis-translate`、batch-001..066)。 成人2,969は `.cache/synopsis-adult-deferred.json` に退避(露骨描写は中立化して後日同seedへ)。 desc無8,759は翻訳不可。 母数=enrich未訳18,332のうちdesc有9,571。

関連: [[anilist_matching_state]](enrich/match-v14)、 [[project_architecture_seeds]](種pyramid)、 CLAUDE.md「synopsis和訳=git追跡seed」節。
