---
name: merge-needs-external-proof
description: 【最重要・本番DB安全】同一anilist_idは「同一作」でない=AniListは別作品も1franchise-idに束ねる(ゲゲゲ8作→1id/クル4冊→1id)。mergeは外部確証(Wiki/cmoa/NDL/ISBN連番)がある時のみ、デフォルトは分離(別slug)
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★series統合(merge)の安全原則。 2026-06-03、 ゲゲゲの鬼太郎のWiki裏取りで「同一aid→即merge」の危険が判明し確立。

**★中核の誤り = 「同一anilist_id = 同一作」は偽**:
- ★AniListは ★**別々の作品を1つのfranchise-idに束ねる**。 実証2件:
  - ★**ゲゲゲの鬼太郎(id40499)**: 種2の10断片が全部このidだが、 ★Wiki裏取りで「スポーツ狂時代(週刊実話1978)/死神大戦記(学研1974)/その後の(別マ1970)/ねずみ男と(いんなあとりっぷ1973)/雪姫ちゃんと(少年ポピー1980)」= ★**1970〜80年に別雑誌で連載された別作品**。 AniListが誤って同居。
  - ★**ととある日のクル(id115578)**: 4冊が1id([[volume_split_merge]])。 こちらは cmoa が全4巻シリーズと示したので merge 正当=外部証拠あり。
- ★= ★**同一aidは「同じfranchise」止まり。 別作品も平気で同居**。 ★**同一aidを根拠にmergeしてはいけない**(本番DBで別作が1ページに統合=復旧困難な大惨事)。

**★非対称リスク(本番DB)**:
- ★**誤merge(別作を1ページ)= 致命的**(復旧困難)。 誤非merge(1シリーズが数ページ)= 軽微(後から統合可・URL生存)。
- → ★**デフォルト = 分離(各作品に固有slug=別ページ)**。 ★**mergeは外部確証がある時だけ**の例外操作。

**★mergeを許す「確証」(外部・種2非依存)**:
- ★Wikipedia(著名作の作品/巻構成。 ゲゲゲで威力実証=別作を見抜いた)。
- ★cmoa等書店の全巻リスト(クルで実証=全4巻シリーズ確定)。
- ★NDL著者典拠ID + 主題 + 巻番号([[ndl-clustering-design]])。
- ★ISBN/巻番号の連続(同一出版社の番号付き連番。 例=しょせん他人事 巻1-10・白泉社4592連番→merge済)。
- ★これら**いずれかが「同一刊行物」を積極的に証明**した群だけ統合。

**★種2(MADB)は統合根拠に使えない**(ユーザ指摘 2026-06-03):
- ★「ここまで繋がらなかった = 種2のデータ自体に欠陥」。 著者qid欠落(ゲゲゲ/ドラえもんがanthology誤分類[[author_roles_state]])、 cm104凍結([[madb_cm104_frozen]])、 著者+生title clustering の分裂([[series_fragmentation_rootcause]])。
- → ★**統合判定は種2でなく外部確証で**。 種2は候補出しまで。

**★AniList relations は使える(idのlumpと別)**:
- ダンプは全件 `relations`(PARENT/SEQUEL/SPIN_OFF/SIDE_STORY/ALTERNATIVE)を保持(新規fetch不要)。 ★**関係の種類**で「版違い(ALTERNATIVE)=merge寄り / 派生(SPIN_OFF/SIDE_STORY/PARENT)=別ページ」を判別する補助に使える(idの同一性より relations の type が情報)。

**★運用(slug衝突2,096群の解消)**:
- ★**デフォルト=各断片に固有slug**(over-collapseは「AniList romaji共有」が原因→**各作品の完全title(副題込)のkana/romaji**でslug生成し分離)。 衝突解消は原則「分離」。
- ★**merge は外部確証が取れた群だけ**(著名franchise=Wiki / 番号付きシリーズ=cmoa/連番ISBN)を curated に積む。 AniList照合55%・aid無675群は種2/Wiki/諦め(天井)。
- ★pipeline順 = drop → ★**確証merge** → slug(最終ページにだけ) → 残り別slug([[collision_slug_investigation]])。

関連: [[volume_split_merge]][[ndl_clustering_design]][[series_fragmentation_rootcause]][[anilist_matching_state]][[author_roles_state]]。
