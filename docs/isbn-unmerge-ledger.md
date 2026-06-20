# ISBN誤共有 un-merge 監査台帳 (= 後追い用の人手可読ログ)

機械可読ログ = `data/seeds/unmerge-changelog.jsonl` / 本表 = その人手可読版。
**全操作は可逆** (= `.cache/*-bak-*` に before yml を退避、`dup-merge-alias.yml` で alias 逆引き)。
種2 sqlite は全工程で**不変**。日付 = JST 2026-06-20。

## 操作種別

| code | 意味 | 戻し方 |
|---|---|---|
| dedup/alias | 重複/別名ページを canonical へ統合・除去 | alias行削除 + backupから復元 |
| de-interleave | 共有ISBN束を真題著者で各作へ振分(両作生存) | backupから復元 |
| re-point | 誤ISBNを剥がし自前の真ISBNへ差替 | backupから復元 |
| strip→needs-content | 真ISBN不明で除去しqueue化 | backupから復元 |
| restore | needs-content等を真ISBNで復元 | backupから復元 |
| drop | 掲載対象外と裁定し除去のまま | (意図的除去) |

---

## ① series-dedup (commit `7a3eac20b`, bak `unmerge-bak-20260620-083428`)

| slug(drop) | → canonical | 根拠 |
|---|---|---|
| aporon-no-kanashimi 他6(eiyuu-herakuresu/higeki-no-ou-oidipusu/meikai-no-orufeusu/odeyusseusu-no-koukai/oryunposu-no-kamigami/toroi-no-mokuba) | manga-girishia-shinwa | マンガギリシア神話=8エントリ重複→1 |
| princess | idol-sousei-densetsu-princess | 美少女プリンセス重複 |

## ② de-interleave (commit `7a3eac20b`, 同bak)

| 群 | 振分(各作の巻数) | 根拠 |
|---|---|---|
| cue-2004 / cue | 村上3 / 花見沢1 | 種1/楽天の真題著者 |
| shinpika-mizuki-shigeru-den / watashi-ha-gegege | 各1 | 同上 |
| besuteia / ryuugetsushou | ベスティア / 流月抄3 | 同上 |
| akai-hitsuji-no-kokuin / hakushaku-cain / kafuka / wasure-rareta-juliet | 赤い羊1 / 伯爵カイン6 / カフカ=ISBN無→needs-content / 忘れジュリ1 | 同上 |

## ③ 誤側7件分岐 (commit `c43547b09`, bak `unmerge3-bak-20260620-103905`)

| slug | 操作 | before → after | 根拠 |
|---|---|---|---|
| kurotokage-2019 (森下裕美) | re-point | 講談社黒とかげISBN → 9784575945614(双葉社2019) | 種1[作画]森下裕美・slug年一致 |
| gift-2012 (塩森恵子) | re-point | 講談社GiftISBN → 9784575334906(双葉社2012) | 種1[著]塩森恵子・slug年一致 |
| hiyoko-brand (こばやしひよこ) | dedup/alias | → oku-sama-wa-joshikousei | 同著者+cm104題一致+愛蔵版13ISBN同一 |
| 24colors | strip→needs | 麻生歩COLORS ISBN剥がし | 別著者(千葉コズエ)・真ISBN無→queue |
| venus-2015 | strip→needs | 関口シュンISBN剥がし | 別著者(麻生歩)・真ISBN無→queue |
| gift-2006 | strip→needs | 秋本尚美ISBN剥がし | 別著者(ユキヲ)・真ISBN無→queue |
| fire-emblem-thracia-776-2000 | strip→needs | たかなぎ優名ISBN剥がし | 別著者(日野慎之助)・真ISBN無→queue |

## ④ 残存共有2件 (commit `f4c8c4230`, bak `unmerge4-bak-20260620-115946`)

| slug | 操作 | before → after | 根拠 |
|---|---|---|---|
| colors-2001 (啄木鳥しんき) | re-point | 麻生歩COLORS3ISBN → 啄木鳥4巻(9784757705128/707054/708846/711716,エンターブレイン) | vol4=楽天確認/vol1-3=ユーザ調査+ISBN連番。qid(麻生歩疑い)clear |
| gift-ichinose-2015 (一ノ瀬ゆま) | re-point | 秋本尚美Gift2ISBN → 一ノ瀬上中下3巻(9784344834798/839205/843585,幻冬舎) | 種1で[著]一ノ瀬確認。anilist106164等enrichは本人=保持 |

※訂正: gift-2009(山田J太)/gift-2002(中村かなこ)は汚染なしと判明(resolve-masterが古snapshot)。詳細=`unmerge4-residual-flag.tsv`

## ⑤ needs-content 5件裁定 (commit `e26392225`/`13e0da4fc`, bak `unmerge5-bak-20260620-121144`)

| slug | 操作 | 真の作品 / 正ISBN | 根拠 |
|---|---|---|---|
| 24colors | restore | 24Colors〜初恋のパレット/千葉コズエ / 9784091316073(小学館2008) | NDL+AniList35686(正マッチ=enrich保持) |
| venus-2015 | restore | ヴィーナス:禁じられた危険なキス/麻生歩 / 9784776739586(宙出版2015) | NDL・slug年一致 |
| fire-emblem-thracia-776-2000 | restore | FEトラキア776/日野慎之助 / 9784757700321(エンターブレイン2000) | NDL(たかなぎ版と別作)・誤AniList35619 clear |
| kafuka | alias | → hakushaku-cain | AniList30885=伯爵カインシリーズ全5巻の一編 |
| gift-2006 | **drop(成年)** | Gift/東山翔(官能2007) | AniList55445=別著者の成年作。ユーザ裁定でドロップ確定 |

詳細裁定=`unmerge-needs-content-resolved.tsv`

---

## A: 同一ISBN複数作品(T3核心) — 分析のみ (commit `48ea274b7`, **未適用**)

- Phase1分類(676slug): CLEAN_owner296 / ALL_WRONG164 / UNKNOWN_only162(多くno_yml=既処理) / MIXED_deinterleave41 / WRONG_plus_unknown13
- Phase2(誤claim側 live218): **REPOINT41 / DEINTERLEAVE41 / STRIP・ALIAS136**
- Phase3 re-point proposal=dry-run。★自動番号付けにノイズ多数(mahouka-2025=53巻過収集等)→**bulk適用は危険、小バッチ人手vetting要**
- artifacts: `shared-isbn-classified.tsv` / `shared-isbn-actions.tsv` / `shared-isbn-repoint-proposal.tsv`
- **次の適用はこの表に追記してから実施** (= 段1:単巻16 → 段2:複数巻25 → 段3:strip/alias136 → 段4:deinterleave41)

### A 適用ログ (= ここに段ごと追記していく)

**★重要(2026-06-20)**: resolve-master.tsv は **6/18-19 の t3-fix/torichigae/special-edition 修正より前の古snapshot**。
統合台帳 operations.jsonl で「既処理か」を必ず確認 → 怪しければ実 yml を見る、で**済み作業の上書きを回避**。
(例: samurai-soldier は台帳上 t3-fix 済=現在 山本隆一郎の正26巻。stale proposal の「26→1」を信じれば正巻を破壊していた)

| 段 | 日付 | slug | 操作 | before→after | 根拠 | bak |
|---|---|---|---|---|---|---|
| 1 | 06-20 | eden-sakurazawa-2014 | strip誤著者巻 | 岡田俊平のエデン除去 → 桜沢エリカ1巻 | 種1著者照合 | sharedisbn-step1-bak-20260620-143120 |
| 1 | 06-20 | snow | strip誤著者巻 | 藤谷コマキのスノウ除去 → 吉田優希1巻 | 種1著者照合 | 同上 |
| 1 | 06-20 | stand-up | strip誤著者巻 | 白虎丸のSTAND UP!2除去 → 板垣雅也2巻 | 種1/楽天著者照合 | 同上 |
| 1 | 06-20 | zero-matsumoto | strip誤著者巻 | 冬目景のZERO除去 → 松本大洋3巻 | 楽天著者照合 | 同上 |

**段1の保留**: reset(高橋ユキ標準+山本まゆり文庫の2著者混在+enrich疑義) / comic-higashino-keigo-mystery-2014(アンソロ) / tenyoritakaku(全巻別著者=要re-point) / koi-shita…(matcher誤判定=実は本人作) → 個別精査へ。
**段1で既処理判明(台帳ガード)**: blazblue/box-1991/face/face-2019/kirara-hiramatsu-1987/nito-monogatari/samurai-soldier/work-in (= t3-fix/torichigae/special-edition で6/18-19に修正済)。
**次**: 段1残(未スキャンの全REPOINT/STRIP母集団)は **resolve-master でなく台帳+実DB** で現状確認してから。
