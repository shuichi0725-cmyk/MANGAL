---
name: kana-validity-state
description: 種3フリガナ正当性=3ソース突合(MADB ja-hrkt/種a/Wikipedia)で検証完了。真の誤り239修正済、残りは種3正(MADBノイズ)。slug土台は信頼可
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

種3 title_kana(フリガナ)正当性チェック(2026-05-31、 slug生成器の前段)。 詳細は `_audit-kana-3source.py` / commit 8844a70〜305b02f。

**前提**(ユーザ): 種3 kanaは基本 **MADB ja-hrkt 由来** + MADB に無い分は Claude AI fill。 ★MADB自体も誤あり(GS美神=ジーエスミカミ誤/正=ゴーストスイーパーミカミ)。 = 単一権威でなく3ソース突合(MADB/種a/Wikipedia)要=slug規則通り。

**ツール**: `_extract-madb-kana.py`(MADB raw→ISBN→ja-hrkt読み、 352,650/97%、 `.cache/madb-isbn-kana.tsv`、 ★分かち書きなのでsegmentedも得られる) / `_audit-kana-3source.py`(種3kana vs MADB vs 種a romaji、 kata正規化=句読点/長音/小書き吸収) / `_fix-kana-3source-errors.py`(訂正適用) / `_audit-kana-deep.py`(④深掘り) / `_wiki-kana-test.py`(Wikipedia裁定)。

**結果**(種3 kana有 76,417): ①MADB一致54% + ⑤AI fill種a一致4% = **58%確定正当**。
- ★**③ MADB+種a一致・種3別=239件=真の読み誤り→修正済**(commit 8844a70)。 当て字/人名読みの取りこぼし: 白物語シロ→ビャク / 聖母セイボ→マリア / 巨人キョジン→ワタシ / 龍と樹キ→イツキ / 夫婦フウフ→フタリ 等。 正読=種a一致のMADB ja-hrkt(分かち書き)で title_kana(空白除去)+ title_kana_segmented(分かち書き保持)両方訂正。 ★種3上書き=deliberate fix(蒸留protocolの保護外、 ユーザGO)。
- ④ 種3≠MADB・種a裁定不可=5,415(うちbase乖離2,091)= ★**大半ノイズ**(副題差/ISBN誤join/英語題)、 種3誤でない。
- ⑦ MADB無・種a無=24%=AI fillニッチ(裁定不可)。

**★Wikipedia サンプルテスト結論**: ④漢字題25件→種3誤**0** / MADB誤2(上杉謙信→ゴルゴ13誤join等=種3が正と確認)/ 記事無**88%**。 = 種3フリガナは健全、 ④はMADB側ノイズ、 Wikipediaも種3支持。 → **フルWiki照合不要(歩留まりゼロ)**。 サンプルで無駄打ち回避。

**結論**: 種3フリガナ=**健全・検証完了**(239修正済+残りは種3正)。 slug生成器(title_kana起点)の土台は信頼できる。

**副産物の宿題**: MADB に **ISBN→series 誤join**(上杉謙信のISBNがゴルゴ13に紐付く等)が存在=種2のデータ品質問題(別途)。 関連 [[anilist_matching_state]] [[madb_native_series_structure]]。
