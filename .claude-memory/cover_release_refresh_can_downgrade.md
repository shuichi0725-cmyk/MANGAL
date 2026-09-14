---
name: cover-release-refresh-can-downgrade
description: 発売後書影追従(_cover-release-refresh.py)は「頁と違えば書く」だけなので、楽天が仮.gifを返すとKobo補完/実物書影を上書きして劣化させる。週次蒸留が毎回--days 45で回すので恒常リスク
metadata: 
  node_type: memory
  type: project
  originSessionId: 4cce8a9c-a5ff-4f2c-a19f-a21245d006b2
  modified: 2026-09-14T12:46:00.127Z
---

`scripts/_cover-release-refresh.py` の書き込み条件は **`live != 頁の現在値` だけ**(noimage除外のみ)。「liveの方が良い」は一切検査しない。そのため楽天がそのISBNに**仮書影(文字だけ `.gif`)を返す状態**だと、既に入っている良い書影を `.gif` で上書きする。

★**2026-09-14 実測**(9月発売885巻を `--from 2026-09-01 --to 2026-09-30` で一巡): 書込500件のうち **3件が劣化**だった。
- `jukebox` 3巻(9784065445686) / `kyuuketsu-bar-e-youkoso` 4巻(9784592165705) = 頁は**Kobo電子で補完した実書影**、live楽天(紙)は `.gif` → 上書きされるところだった
- もう1件は 実jpg → `.gif` の素の劣化
commit前に検品して3件とも除外。逆に `watashi-ga-watashi-o-uru-wake` 10巻の `_1_2.jpg → _1_3.jpg` は**正当な格上げ**なので戻した(= 保護を「Kobo由来なら一律除外」にすると取りこぼす)。

**Why:** 週次蒸留 step1 がこのscriptを `--days 45` で**毎回**回す。つまり Kobo補完([[placeholder_gif_old_layer_kobo_route]])や巻抜けfillで入れた書影は、楽天紙が仮のままのISBNだと**週次のたびに `.gif` へ戻されうる**。seedは後勝ちなので、劣化行が最後に来た時点で頁が負ける。過去分のseedを全走査した実測では劣化上書きは0件だったので、被害はまだ出ていない(今回が初出)。

**How to apply:**
- このscriptを回したら **commit前に追記行を検品**する。落とす条件 = ①新URLが `/{ISBN}.gif` か noimage(= 仮書影は決して改善ではない) ②`reason` に Kobo補完/巻抜けfill/小説混入是正 を持つISBNへの上書き。**残す**のは `_N_N.jpg → _N_N.jpg` の版数上げ
- 行数を先に控える(`wc -l data/seeds/cover-override.jsonl`)→ 実行 → 差分行だけ判定 → ファイルを書き戻す、が実行手順
- 恒久策の候補(未適用・要GO): script側に「新URLが `.gif`/noimage なら書かない」ガードを入れる。1行で済むが週次の共有ツールなのでユーザ裁定マター
- 関連: [[kobo_cover_wrong_for_old_print]] [[volume_add_includes_cover]] [[feedback_one_bug_means_a_class]] [[cover_harvest_plan]]
