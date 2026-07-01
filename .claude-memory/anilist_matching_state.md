---
name: anilist-matching-state
description: "種a(AniList)↔種3 照合の現状。v9が本命matcher、staff/year/vol使用済、マッチ率~44%。title正規化強化で+1,305"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

種a = AniList manga dump (`.cache/anilist-manga-dump.jsonl.gz`, **101,590件**, 全JP原産)。 fields: title(romaji/english/native)/synonyms/genres/tags/**volumes(57%保有)**/startDate/**staff(100%)**/relations/isAdult/format。

**本命 matcher = `scripts/_audit-match-v9.py`**(v6→v9 の最新)。 既に多信号: title 4ch + 種2著者 + **staff** + year + volume + greedy 1:1競合解決 + 短編集除外。 threshold 130/150/180。 出力 `.cache/match-v9-all.tsv`(76,435行=全種3 + verdict/score/a_id)。 ※`_audit-en-vs-anilist.py` は別の旧 en比較audit、 本番matcherではない。

**マッチ率 (2026-05-30 強化後)**: matched **34,013 / 76,435 (~44%)**(S180高信頼 30,617)。 NO_MATCH 36,874。

**C改善 (commit e77a385)**: NO_MATCH 38,535 調査 → 1,802件は native title が AniList に完全一致なのに未マッチ = v9 の `title_norm`/`kata_norm` がダッシュ(‐ U+2010)/アポストロフィ(’)/全角記号(！＠／)を吸収できず。 `strip_punct()`(Unicode P*カテゴリ+長音/波線 全除去、 merge側 clean()と同軸)追加 → matched +1,305 net / S180 +3,151 / 完全退行 1件のみ(無頼男、 他496は1:1再割当)。

**★夜間調査 (2026-05-31, 詳細レポート=`docs/anilist-match-slug-investigation.md`, commit 514be1d〜b20b4dc)**: マッチ率+slug精度を調査専念(実データ不変)。 主要数値:
- **A: S180実FP率 0.1〜0.3%(安全)**。 最危険R1=21件精査で真FPは2〜4件のみ、 大半は偽MISMATCH(romaji↔カナ/異体字/翻訳者混入)。 → S180はproductionizationに使える。 ツール `_audit-s180-fp.py`。
- **B: 著者経由recallで +6,659件回収可能**(NO_MATCH3,815 / **DISPLACED2,622=81%!** / REJECT222)。 改良=romaji↔カナ橋渡し+翻訳者role除外。 DISPLACED81%は1:1greedyが勝てるマッチを落としてた裏付け→実装容易で確実。 マッチ率44.5%→~52%目標(精度保持)。 ツール `_audit-recall-authorroute.py`。
- **C: slug新規則(title_kana起点ヘボン)未実装と判明**(現makeSlug=display→wanakanaで漢字破綻)。 ★カタカナ主体10,930の48%(5,299件)が種aで英語綴り取得可=slug是正の最大レバー(aama→Armor型)。 衝突4,523群/10,648件(同名異作=要-姓+年suffix / imprintラベルからの生成バグ)。 ツール `_slug-prototype-audit.py`。
- **D: 種a再dump(v3)**=popularity(100%)/description(87%)/meanScore追加が高価値→`_anilist-dump-v3.py`で `anilist-manga-dump-v3.jsonl.gz` に全件取得(既存dump保持)。 chapters/externalLinks/charactersは低価値。
- **推奨優先順**: ①anilist_id結線(S180×30,617、 en同手法で即可) ②著者正規化改良+DISPLACED回収(Tier1格上げ) ③slug生成器新規実装(要slug規則裁定・GO) ④synonyms/genres ⑤popularity tie-break。 朝イチ判断3点はレポート末尾。

**★matcher イテレーション v9→v13 (2026-05-31, commit f16dc27〜23f2173, レポート `docs/anilist-match-slug-investigation.md`)**: ユーザ承認で v9 を反復改良(全て .cache のみ・種3/種2/本番不変)。
- **v10** = 著者正規化(romaji↔カナ橋渡し Boichi↔ボウイチ / 翻訳者role除外 / NFKC)+ 著者経由第2候補(ch E)+ DISPLACED N:1回収。 recall +4,719(44.5%→50.7%)だが変種過マッチ。
- **v11** = popularity 本編選択。 但しpop弱く変種解決50%。 ★気づき: 「本編=高pop」は誤前提。
- **v12** = exact題優先(非exact派生版を-50降格)。 **接地正解79%**。
- **v13** = v12 + CSafeLoader化(種3 load ~15分→~2分)+ grounded demote。 v12と同値=**収束**。
- ★**データ接地評価が鍵**(`_audit-diff-grounded.py`): popでなく**種3の年/巻/著者一致**で正解判定。 v9↔v10差分156の明確勝者136件で各版精度 = v9:63% / v10:36% / **v12:79% / v13:78%** / 加算merged:63%。 接地で v9 の既存誤マッチ50件(Free!=ハイスピード小説誤 等)も判明。
- **★最終 best = v14**(`_merge-v14-best.py` = v9 と v13 の各マッチを grounded(種3の年/巻/著者一致)で比較し高い方採用、 同点v9優先)。 = **退行0 + contested精度89%(v12/v13の79%超)+ ACCEPT+5,480(44.5%→51.6%)**。 v9採用33,685/v13改善取込5,808。 マッチ率/精度/退行0 の全部入り。 出力 `.cache/match-v14-all.tsv`。
- 本番化(要GO・未実施): **v14 を ①anilist_id結線の入力**に(退行0なので安全)。 残 contested ~14件+真曖昧20件は `.cache/diff-grounded.tsv` で人手(少数)。 matcher改善は v14 で完了(以降は per-case人手領域)。
- 反復ツール: `_audit-match-v{10-13}.py` / `_audit-match-verify.py <ver>` / `_audit-diff-grounded.py`(年/巻/著者で真の正解判定) / `_merge-v9-v10-additive.py` / `_merge-v14-best.py`。

**残改善余地**:
- NO_MATCH 36,874 のうち **23,304件は著者名が AniList staff に存在**(著者経由でさらに照合可能性)、 13,429件は title/著者とも AniList になし(元々未収録)。
- **productionization 第一弾 = en-fill 完了 (2026-05-30, commit ba44a8a + 本番 edc10dd)**: option1。 `scripts/_apply-en-fills-surgical.py` で v9 の **verdict=S180 かつ 種3側 en 空 かつ AniList english 有** の **2,820件**に公式英題を `alternative_titles.en` へ**純粋追加**(s3_en空のみ=上書き無し)。 ★33MB保護ファイルへ **surgical 行挿入**(既存行不変、 diff=+5639/-0、 CSafeLoader parse OK・76,435件不変)。 en充足 40,992→**43,812**。 折返しキー(': '含む超長subtitle)2件は surgical不可で除外=別途。 S150/S130/S100 の316件は第二弾保留。 本番42→6ページが英題獲得(Yashahime/Mermaid Saga等)。 → **alternative_titles.en だけは AniList結線済**。
- **productionization 完了 (2026-05-31, commit 3c412d4/f00604f)**: anilist_id / synonyms / genres_anilist / tags を本番に投入。 ★種3に書かず **promote-join 方式**(adult_us と同じ): `_build-anilist-enrich-map.py`(match-v14 + dump → `.cache/anilist-enrich-map.json`、 39,493件、 synonyms 23,793[latin/CJK過半]/genres 37,781/tags 28,234[案2 filter: Demographic/Theme≥60/Cast・Setting≥70])→ `_promote-bulk-v2.py` が join し本番yml に出力(main series_key優先、 merge fallback)。 種3不変・match-v14更新で常に最新。 intake の enrich stage に統合。 検証: 42サンプル35ページ enrich、 ao-ashi=id107279/synonyms/genres[Sports]/tags[Seinen]。
- AniList **volumes** = STEP4 で活用済 (commit 6e8f35a): `_audit-trailing-gaps.py` が v9高信頼(S180)マッチで AniList volumes > 種2最大巻(merge group横断+種4込み)を末尾取込もれ検出。 候補1,150(欠け1巻716/FINISHED 1,133)。 ただしNDLも最新刊未収録(チェンソーマンNDL max=23)で今はISBN裏取り不可+AniList巻計数ノイズ(part1/2合算)あり → 種4未登録、 `data/seeds/volumes-trailing.yml` で追跡(NDL/MADB更新後に再訪)。
- genres/tags/isAdult も補強候補。

**★強正規化×著者ゲート 回収 (2026-06-02, commit直近)**: 4時間枠の多角調査(著者/役割揺らぎ軸)で判明=★未マッチの主因は**title正規化の弱さ**(著者groundingは堅牢: 種2著者+60/-40・key+40、 正規化が空白/記号/NFKC/romaji↔カナ/ひら↔カナ/姓名順/★alt_names筆名1,835/非著者role除外を吸収、 ★同名異作=中華一番[真鍋vs小川]/ガンダム[富野vs岡崎]を正しく弾く)。 ★未マッチページ**13,004件がtitle+著者両方一致**なのに漏れ(遊・戯・王vs遊☆戯☆王、銀河鉄道999vs９９９、コナン特別編の空白、三四郎²vs2、ACTⅡvsII、❤♥/☆★/全角)。 旧字(髙↔高)は6件のみ=著者揺らぎは小。 ★`_match-recover-norm.py`=3ゲート(①title強正規化[NFKC全角統一+全記号/空白/上付き/ローマ数字除去]でnative exact ②**著者overlap必須**=安全弁 ③1:1衝突保守skip+既存不可侵)で**12,375生成→enrich 39,493→51,158(+11,665)**。 スポット15件全正確。 `match-recovery.tsv`をenrich builderが追加読み。 本番42不変・全DB時に波及(synopsis/カテゴリ/著者/QID)。 ★残: 名探偵コナン本編はAniList 31061が劇場版に誤割当済で「不可侵」により未回収=既存誤マッチの別問題。 synopsis拡大は新規11,665のdescription再翻訳が次の道。

関連: [[series_fragmentation_rootcause]](merge側も clean()正規化に統一)、 [[shu3_kana_two_forms]]、 [[madb_data_acquisition]]。
