# slug新規則(6/10裁定)全面適用 レビュー資料

作成 2026-06-11。 ★**候補確定・未適用**(本番 promote はユーザGO後)。
規則: ①長音保持(mahouka-koukou) ②助詞を=o ③敬称ハイフン ④カタカナ外来語=英綴り資産。

## 今日やったこと

1. **生成器実装**: `_slug_rules.py` 新設(token_roman = 長音保持/ヲ=o/定着固有名詞)。 v1/v2/assemble/num-fix が共用。
2. **全再生成**: v1→v2→override(latinmix日本語run 186件再レンダ・英綴り検証資産は不変)→assemble。
3. **検証済資産の繋ぎ直し**(`_rekey-slug-assets.py`): c2裁定552行(rep列\x1f区切り)/recluster/volume-final。 rep(series_key)経由の機械再キー=裁定・証拠は不変。
4. **衝突層再導出**: triage再計算(衝突base 2,005→**1,632** = 長音保持の自然解消373)、c-1 option1(1,229群)、c-2 suffix(718行)。
5. **統合TSV恒久生成器**(`_integrate-slugs.py`): 全8layer + NDL fix継承(67件+手動3件)。 旧/tmp一回限り生成から脱却。
6. **apply-prep一本化**: 統合TSV単一ソース化(旧構造では NDL fix 層が適用入力に流れなかった)。

## 変更規模(対 6/06 統合TSV、全76,435 key)

| 区分 | 件数 | 率 |
|---|---|---|
| 不変 | 47,742 | 62% |
| ★長音保持による変更 | 22,919 | 30% |
| ★を=o | 428 | 0.6% |
| その他(複合・suffix再編・fix) | 838 | 1.1% |
| (旧キー形式で照合不能=参考外) | 4,508 | 6% |

- 最終ページ数 **71,874** / ページslug **71,796**(drop52+recluster26除く)
- ★**一意性: 不正重複 0 / recluster交差 0** / junk・空slug 0
- tokyo定着綴り適用: proposed に tokyo を含む 305件

## 既知例の検証

| 作品 | slug | 判定 |
|---|---|---|
| 鬼滅の刃 | kimetsu-no-yaiba | ✓不変 |
| 魔法科高校の劣等生 | mahouka-koukou-no-rettousei(-2018) | ✓規則①どおり(suffixは多作画化衝突由来) |
| からかい上手の高木さん | karakai-jouzu-no-takagi-san | ✓規則①③ |
| 星を継ぐもの | hoshi-o-tsugu-mono | ✓規則② |
| 東京喰種 | tokyo-guuru | ✓定着綴り例外+① |
| 宇宙戦艦ヤマト2199 | uchuu-senkan-yamato-2199 | ✓NDL fix を新規則で継承 |
| ベルセルク / ONE PIECE | berserk / one-piece | ✓英綴り資産不変 |

長音サンプル: aibou-ni-doku / kidou-senshi-z-gandamu / kongou / maajan-hourouki-2020 / medetaku-sourou / shoujo / boukensha。

## ★レビュー判断点(GO前にユーザ確認)

1. **定着固有名詞リスト**(規則①の例外、token単位): 現在 `toukyou/tookyoo→tokyo, kyouto→kyoto, oosaka→osaka, koube→kobe` の4語のみ。 追加・削除の希望があれば指定(後からの変更=再生成のみで安い)。
2. **幽☆遊☆白書 = `yuuyuu-hakusho`**: 分かち書きが「ユウユウ」1語のため `yuu-yuu` に割れない。 CLAUDE.md の理想は `yu-yu-hakusho`(AniList圏)。 →(a)現状容認 (b)個別fix行で `yu-yu-hakusho` (c)`yuu-yuu-hakusho`。
3. **裁定なし衝突 161群**(`.cache/c2-unverdicted-new.tsv`): 機械suffix(-年)で全てURL一意=安全。 ただし mahouka(-2018)/devilman/hunter-hunter 等の有名どころは「merge か suffix か」の curatorial 裁定をすると綺麗。 → 適用後に別途 Web裁定スイープ可(ブロッカーではない)。

## 適用手順(GO後)

1. `_slug-apply-build.py` → data/manga 合成ソース(slug=フォルダ名確定)
2. `python scripts/intake.py --run` 系 promote(~20分、 series_key駆動配線済み)
3. volume-final の REVIEW_APPLYTIME 141行(本番旧ページ名参照)を本番slug対応表で解決
4. 旧slug→新slug alias表 + `_redirects` 生成(page-dedup/dedup既存167行と統合)
5. spot check(既知例+ランダム50)+ `_audit-preproduction.py` 再実行で衝突0確認

## 関連ファイル

- 生成器: `scripts/_slug_rules.py` `_slug-gen-v1/v2.py` `_slug-assemble.py` `_slug-num-fix.py`
- 再キー/統合: `scripts/_rekey-slug-assets.py` `scripts/_integrate-slugs.py`
- 成果物: `data/seeds/slug-final-integrated.tsv`(76,435行・全layer済) / `.cache/apply/*`
- fix層: `data/seeds/slug-fix-candidates.tsv`(NDL確証67+手動7、key-based・再生成耐性)
