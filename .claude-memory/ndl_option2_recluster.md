---
name: ndl-option2-recluster
description: NDL著者典拠+ISBN+読みで option2(原作+別作画)の巻レベル再クラスタ。DBの作画版混在をNDLが暴き是正。slug-recluster/volume-finalに確定
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

【2026-06-06 完了。 gap c-2 option2 の根本解決】★Web/エージェントでは見えない「作画版の巻混在(誤クラスタ)」を NDL が暴いた。

## 手法 = NDL ライブ by-ISBN 照会
- ★**bulk著者検索RDFは作画が空の記録が多い**(原作のみ表記)→ ★**我々DBの各巻ISBNを NDL SRU で個別照会**(`isbn="..."` recordSchema=dcndl)が確実。 全巻の作画・副題・読みが揃う。
- NDLは ★**著者典拠ID**(id.ndl.go.jp/auth/entity)+ ★**読み transcription**(カナ)を持つ → 作画姓を正確にローマ字化(カナ→ヘボン)+ 典拠IDでクラスタ。 XMLはHTMLエスケープ注意(html.unescape)。
- 原作=全巻共通creatorで除外、 残り(作画)で巻をグルーピング。 副題(別ゲーム/別題)はtitleで分離。
- ツール: `scripts/_ndl-recluster.py`(典拠ID指定で再クラスタ) / ライブ一括は `.cache/ndl-option2-fetch.json` にキャッシュ。

## 成果(option2 全10群 → 31ページ)
- `data/seeds/slug-recluster-candidates.tsv`(ページ単位: base/作画/slug/年/巻数/ISBN) + `data/seeds/slug-volume-final.tsv`(★**ISBN→final_slug** 145巻、 ISBN二重割当0=本番適用元)。
- ★**DBの混在を是正**: 仕掛人藤枝梅安=さいとう版に武村版5巻が混入→分離 / 魔界転生=4作混在(臣新蔵・石川賢+夢の跡・聖者の行進) / ★**zeruda=1 slugに11ゲームが潰れていた**(時のオカリナ/トライフォース/ムジュラ等にゲーム別分離) / dai-toshokan=本編+副題2 / little-busters4版/metroid2版/aidoru2版。
- ★**option2誤判定の訂正**: manga-hyakunin-isshu / mangaban-sekai-no-rekishi / turn-a-gundam(矢立肇=サンライズ集合PN)= 実は単一作 → merge。
- B修正4件: arabesuku-dai-1-bu/2-bu、 accel-world入替(4コマpun=akucheru-warudo・過剰統合解除)、 soul-eater-not是正(本編→soul-eater[base新設])。

## 残(適用フェーズ・GO後)
- ★**本番ビルドに巻レベル再クラスタを配線**: 種2の混在シリーズを `slug-volume-final.tsv`(ISBN→slug)で巻別ページに再分割(promote、 [[ndl_clustering_design]]と同系)。 統合TSVでは該当27エントリを `c2_recluster` 化済(巻別N版)。
- 微レビュー: zeruda `yume-o-miru-shima`(を→o、 規約wo) / little-busters本編=高木が無印(option2厳密なら-takagi)。
