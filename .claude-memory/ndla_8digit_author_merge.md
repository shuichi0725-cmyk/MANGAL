---
name: ndla-8digit-author-merge
description: "⏳種2の作者表で別人が合体する型(NDL典拠IDを8桁で切って名寄せ)= 4,215組・公開頁≥113が別人の作者名。直し方は要GO(2026-10-20発見)"
metadata:
  node_type: memory
  type: project
  originSessionId: 4eb881fe-cc0f-412d-b718-0578babc3249
  modified: 2026-10-19T21:40:19.959Z
---

**型**: `scripts/_build-mangaka-madb.py` が metadata504 の `ma:ndla`(NDL典拠ID)を `re.search(r"(\d{8})")` で取り、`ndl:<8桁>` を mangaka の識別子にして**名寄せ**している。典拠IDは8桁(19,802人)と**9桁(27,127人)**があり、9桁の頭8桁が同じ人(=同時期に典拠登録された隣のID)が**1人に合体**する。例: 喜月かこ(001211922)→瞳ちご、さちも(001161075)→桜日梯子、nikuhen(034109169)→みつたに。

**規模(2026-10-20 実測・read-only)**: 衝突4,215組・巻き込まれ10,389人 / 合体した mangaka 行3,274 / それを作者表に持つ series 20,102 / うち series_key の作者が合体相手=作者表が別人 7,234。**公開頁で作者欄が別人だけ ≥113頁**(題一致の見積もり84 ∪ #9 author-not-in-volumes で合体が原因33。例: サイコアゲンスト=景山愁→平石六、外科医エリーゼ=mini→yuin、1日外出録ハンチョウ、銀魂3年Z組銀八先生)。promote の `get_authors` が series_authors をそのまま出すため。MADB 生データ(101の dcterms:creator C-id → 504 rdfs:label)と series_key は正しい=壊れているのはこちらの名寄せだけ。

**毎月再発**: populate が mangaka.csv(この道具の出力)で新 series の作者を結ぶので、新刊の作者も化ける(1.2.21 の#13芯36件中10件が別人)。新規頁は当面 `author-overrides.json` で当てる(2026-10-20 に12頁)。

**直し方の案(未着手・要GO)**: ①道具を全桁 `entity/(\d+)` に直す ②既存は種2を書き換えず、既存 overlay `data/seeds/author-role-corrections.yml`(series_key 単位・promote の `apply_author_corrections` が get_authors 直後に当てる)に「合体 mangaka を MADB の C-id ラベルで置き換える」補正を生成器で足す → 該当頁だけ targeted 反映。種2の mangaka/series_authors を作り直す案は INSERT-only 原則に反するので取らない。[[author_pollution_overlay_fix]] [[author_not_in_volumes_audit]] [[ndl_authority_homonym_state]] [[feedback_one_bug_means_a_class]]
