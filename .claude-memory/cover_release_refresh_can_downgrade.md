---
name: cover-release-refresh-can-downgrade
description: 発売後書影追従(_cover-release-refresh.py)は「頁と違えば書く」だけで劣化を止められなかった→2026-09-14に劣化ガードをscript側へ恒久実装済(負テスト済)。手検品はもう不要
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

## ★是正済み (2026-09-14 commit 70a1981f4)。手検品はもう要らない

ユーザ裁定「週次や見直し時に劣化しないように」を受けて、**script側に劣化ガードを恒久実装**した。

```python
elif RE_PLACEHOLDER.search(live) and cur:   # RE_PLACEHOLDER = r"/\d{13}\.gif"
    n_down += 1          # 頁に既に書影が在るなら、live が仮書影の時は**書かない**
```

- **止める**= 実書影(Kobo補完/実jpg) → 仮`.gif`。**通す**= 仮`.gif`→実jpg、版数上げ `_1_2`→`_1_3`、頁が空の時の充填
- ★**Kobo由来を一律保護にはしない**: 紙の実物が出たらそちらが正しい([[kobo_cover_wrong_for_old_print]] = Kobo電子は注意書き付きの代替)。実際 `watashi-ga-watashi-o-uru-wake` 10巻は `_1_2→_1_3` の正当な格上げだった
- 集計行に `★劣化ガードで不採用{n_down}` を出すので、効いた件数が毎回見える
- **負テスト済**: 2026-09-16発売の57巻で回して「不採用1」(jukebox 3巻のKobo実書影を防衛)・seed行数は不変を確認。修正前ならこの実行が `.gif` を書き込んでいた

**How to apply:**
- ★**もう手検品は不要**。そのまま回してよい(週次蒸留 step1 の `--days 45` も安全になった)
- 効いた件数が急増したら、楽天側で書影が大量に引っ込んだ signal = 中身を見る
- 関連: [[kobo_cover_wrong_for_old_print]] [[volume_add_includes_cover]] [[feedback_one_bug_means_a_class]] [[cover_harvest_plan]]
