---
name: placeholder_gif_old_layer_kobo_route
description: "【機構・第1周完了 2026-09-11】旧作の仮書影(.gif)層をKobo電子で埋める。道具=_kobo-placeholder-fill.py(版ゲート+dhash装丁ゲート+Kobo側プレースホルダ検出)。芯1,381頁→2,473巻/393頁を反映済"
metadata: 
  node_type: memory
  type: project
  originSessionId: ac630d68-4de0-4259-a1f9-db37d14ed2a6
  modified: 2026-09-11T06:17:42.381Z
---

## 何が穴だったか

仮書影の周回(skill `placeholder-cover-refresh`)は **2019年以前を既定で除外**する。理由は正しい
(楽天**紙**を引き直しても旧作は `.gif` のまま)が、★**Kobo電子なら埋まる**という一段が繋がっていなかった。
この層は cover_url が**非null**なので、書影監査にもどこにも出てこない。
[[cover_harvest_plan]] は `cover_url=null` 層の計画で**別物**。

## 道具 = `scripts/_kobo-placeholder-fill.py`(照合ロジックは `_kobo-covers.py` から import)

```
--build-queue → --survey → --pairs → --selfcheck → --triage → --accept
```
- `--accept` は `data/seeds/cover-override.jsonl` へ純粋追加。却下は `data/seeds/kobo-placeholder-rejects.tsv`。
- 反映は `_reflect-targeted.py --only $(cat .cache/kobo-placeholder/accepted-slugs.txt)`。

### ★3つのゲート(どれも実データで発覚したものを封じた)

1. **版ゲート**(100億の男) — 巻番号だけで突き合わせると、同一頁に通常版と文庫版が同居する時に
   「文庫3巻へ通常版3巻の書影」を付ける = [[kobo_cover_wrong_for_old_print]] のゴルゴ文庫型。
   Koboがどの版を電子化したかは**巻数でしか判らない**ので、総巻数が一致する版にだけ充当する。
2. **装丁ゲート = dhash**(HELLSINGの目視を機械化) — 同頁の紙の実物巻とKoboの**同じ巻**を比較。
   ★閾値は実測較正: 同巻同装丁 **5〜14**(帯付きで14)/ 別巻 **20〜29** / 仮書影 **31** → `thresh=12`。
   帯付きはDIFF側に落ちて審査へ回るが**誤採用より安全**(無書影 ＞ 誤書影)。
3. **Kobo側プレースホルダ検出**(あかね噺 v24 が「JUMP COMICS DIGITALのロゴだけ」) —
   紙との距離比較では弾けるが**NOPAIR頁は素通り**するので、頁内だけで完結する
   `LOGO`(明るい画素85%以上)/ `TEMPLATE`(別巻なのに絵が同じ)を追加。
   ★TEMPLATEは **あずみ/拳児/SANCTUARY のような強い共通レイアウト作品で偽陽性**。
   紙と一致(MATCH)していれば TEMPLATE 旗は無効にする。LOGO は**巻単位**で外す(頁ごと捨てない)。

## 第1周の実測(2026-09-11)= 素の件数は仕事量ではない [[feedback_raw_count_is_not_worklist]]

| 段 | 残り |
|---|---|
| 仮 .gif 素の検出 | 9,412巻 / 3,037頁 |
| 芯(同頁に実物書影あり=比較元が取れる) | 1,381頁 |
| Koboに電子版が実在 | 512頁 / 2,616巻 |
| 版ゲートで留保 | −156版 / 652巻 |
| Kobo側プレースホルダ | −75頁(LOGO) / −6頁(TEMPLATE) |
| 装丁ゲートMATCH=自動確定 | 276頁 / 1,213巻 |
| 目視審査161頁 → 152頁採用 / 9頁却下 | |
| **反映済** | **393頁 / 2,473巻**(本番+preview、検算2,473/2,473) |

## 残り(次の周回)

- ★**頁内が全部 .gif = 1,627頁**は比較元が無いので queue 外(`--include-noanchor` で入る)。
  memory の既定方針どおり「頁内で装丁が統一されるか」で裁定する必要がある。
- 版ゲートで留保した **156版/652巻** — 文庫/新装など別版。Kobo側の版を特定できれば救える。
- ★**要確認1件**: `mobile-keisatsu-patlabor`(21巻) = 装丁不一致だが、**我々の紙書影
  (standard v11)のほうが別版の疑い**。上流を直せば21巻が救える [[feedback_cover_oddity_signal]]。

## 副産物の構造修正

`_promote-bulk-v2.py` の特装版pass が巻のISBNを 特装版→通常版 に差し替えてから凍結 `normal_cover`
を焼くため、**cover-override が参照されず黙って潰れていた**(汗と石鹸7巻)。差し替え後のISBNで
引き直すよう修正。範囲は355件中1件だったが値でなく経路を直した [[seed_silently_ineffective_class]]。
