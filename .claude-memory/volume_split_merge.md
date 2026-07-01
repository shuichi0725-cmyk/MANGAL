---
name: volume-split-merge
description: 巻割れ統合=cm104凍結orphanを著者+題でmerge→発売日順renumber。種12照合で漏れ巻回収・だろう運転回避が鉄則
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★cm104凍結=シリーズ構造なしの orphan(個別題の0巻/extra本)を「1作の多巻ページ」に統合する仕組み (= 2026-06確定)。

**機構**:
- `data/seeds/series-merge.yml` の entry に ★**`renumber: true`** を付ける(merge_keys=series_key群)。 promoteの `get_renumber_sids` が解決。
- `_promote-bulk-v2.py` の `get_editions_with_volumes` 冒頭に ★**renumber早期パス**: 当該群の全巻を ★**1冊(=1 source series_id)につき代表1巻**(最古release→最小ISBN)選択 → **発売日順に 1..N 連番付与** → 1 standard edition で返す。
- ★**per-sid代表が肝**(per-ISBNだと別版[通常版+文庫版]を別巻に数え過剰=anataで8巻bug)。 by_num collapse(全#0が1巻に潰れる)も回避。
- renumber しない群(番号付き本編+arc=choushoujo、 多版=kyuuso)は flag無しで既存logic。

**★検証の鉄則(だろう運転は損害大)**:
- ★**Wikipedia/ISBN/Wikidata で「1作品か別作品か」を確証**してからmerge。 DB signal(同qid/同レーベル/連番)だけで判断しない。 例: ★galaxy-angel-parody は DB上1作に見えたが、 Amazon著者15名+Yahoo「アンソロジー」表記で ★**パロディアンソロジー(掲載対象外)→drop** と判明(merge誤りを回避)。 ViVid LIFE Advance=独立4コマ(画像確認)→merge厳禁。
- ★**種1/種2照合を必ず**: 「欠落巻」と思っても ★**種2に在る(merge群に未linkなだけ)**ことが多い → ★**種4でなくmerge群に追加**。 同qid+語幹で完全照合(slug非衝突で抽出漏れる)。 例: hanitarou 13→だって～を種2から回収→正準14巻(Wiki一致)。 ★実際 種4登録は1件も不要だった。
- qid=作者([[shu2_qid_is_author]])なので「同qid=同作者」止まり、 同一作品の証明には題/刊行/外部照合が要る。

**実績(10群merge)**: hanitarou(14)/oji-marshmallow(5)/dai-mahou-touge(4)/neko-mukashi(4)/neko-monster(3)/anata(4)/toaru(4)/mayonaka(3)=renumber、 choushoujo(6+5)/kyuuso=非renumber。 promote --only で各実地確認済。

関連: [[madb_cm104_frozen]](シリーズ構造なしの根因)、 [[non_manga_drop_cleanup]](掲載対象外drop)、 CLAUDE.md「掲載対象 scope」。
