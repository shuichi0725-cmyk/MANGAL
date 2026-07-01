---
name: acquire-all-obtainable-info
description: 取得できる権威情報は全部取得して活用する(最小限で済ませない)。蒸留時の furigana 取りこぼしの反省
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

ユーザ指示(2026-06-26): 「**取得出来る情報は全部取得して活用してほしい**」。蒸留時に楽天/NDLのフリガナを確認せず、MADBの字別読み(悪夢→アクユメ等)をそのまま使ったのが slug 誤りの根因だった、という反省から。

**Why:** 権威データ(楽天/NDL/AniList)は MADB の機械読みや AI 推測より正確。各ソースは1フィールドでなく**多数のフィールドを持つ**のに、必要最小限だけ取って残りを捨てると、後で「あの情報あったのに使ってなかった」事故になる(= furigana 取りこぼし=今回)。

**How to apply:**
- ★各ソースから**取れるフィールドを全部抜く**:
  - **楽天 item**: title/titleKana / subTitle/subTitleKana / seriesName/seriesNameKana / **author/authorKana** / publisher / price / salesDate / itemcaption / 書影URL。
  - **NDL opensearch(ISBN)**: dcndl:titleTranscription(題ヨミ) / volumeTranscription(巻ヨミ) / creator+typnative(著者+ヨミ) / seriesTitle / publicationName(掲載誌)。
  - **NDL SRU(discovery dcndl)**: dcterms:creator>foaf:Agent の **rdf:about=著者典拠ID(`id.ndl.go.jp/auth/entity/...`)** = ★同名異人を一意分離できる唯一の鍵。★**事故例(2026-06-27判明)**: `_ndl-discovery.py`(2024/2025新刊取得)はSRU応答に**典拠IDが在ったのに foaf:name(名前文字列)だけ拾って典拠IDを保存しなかった** = 作者の人物同定に紐づけ損ねた(=「NDLから取得したが作者データに紐づけてない」状態)。捨てたのでなく**抜き忘れ**。SRUなので再照会で拾い直せる。新規作者271(`docs/ndl-new-authors-2024-2025.tsv`)の同名異人分離に効く。
  - **AniList**: english/romaji/synonyms/genres/tags/staff(roles)/dates/coverImage。
- ★抜いた情報を**実際に使う**: 題ヨミ→slug/表示フリガナ、**著者ヨミ→author-yomi.yml(未解決372の充足/検証)**、副題ヨミ→副題読み、掲載誌→magazine、価格/発売日→版情報。
- ★**2ソース合意**で精度担保([[furigana_ndl_audit]])。楽天も単独ではノイズ(titleKana=`0`/ISBN別版)があるので NDL/MADB と突合。
- 蒸留(月次)では**最初の harvest 時点で全フィールドを保存**(後から再 fetch しない設計)。[[madb_data_acquisition]] [[rakuten_cover_data_asset]]

★★**再発(2026-06-28、 ユーザ激怒): 「読み方を楽天やndlから持ってこないでフォルダ作ったの？前もやってそこが改善してないのが問題」**。NDL発見作のページ生成(`_pageify-ndl316-preview.py`)で、 **NDL kana(title_kana)が手元に在るのに slug を `pykakasi(漢字title)` で生成** → 君の名は→`kunnomeiha`(君=クン/名=メイ/は=ハ の音読み誤読)等 **142/214が誤り**。
- ★**鉄則: slug は必ず「読み(kana)」をローマ字化して作る。 漢字を pykakasi に読ませない**(漢字→読みは多義で機械が外す)。`make_slug(title, kana)`: Latin題/数字題は元綴り温存(GROUNDLESS/50婚→keep)、 純日本語題は **kana の Hepburn**。
- 是正: kana基点で102 slug rename(着ぐるみ→kigurumi/義弟→otouto/は→wa/君→kimi)。生成器も make_slug() 化。
- 教訓: このmemoryが在っても**新しい生成器で同じ手抜き(漢字pykakasi)を再発**させた。新規にslug/フリガナを作る箇所では毎回「kanaは在るか? それを使ったか?」を自問する。

関連: 楽天harvest=`.cache/rakuten-isbn.jsonl`(item に各Kana有)、NDL=`_furigana-audit.py` の `ndl_yomi`。slug修正で furigana を楽天475+NDL426で権威化したのが初適用。
