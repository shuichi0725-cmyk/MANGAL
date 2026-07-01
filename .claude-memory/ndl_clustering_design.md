---
name: ndl-clustering-design
description: 分裂/版違い根治=NDL SRU(著者典拠ID+正規化主題)で再クラスタ。cm104凍結後の新刊も統一可。200群検証で94%統一・over-merge 0
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★series分裂([[series_fragmentation_rootcause]])と版違い統合([[multi_edition_unification_pending]])の根治設計。 ★**NDL書誌を権威軸に再クラスタ**(2026-06-03、 200群実測で確証)。

**背景=なぜMADBで解けないか**:
- ★cm104(マンガ単行本シリーズ=容器C-ID、 [[madb_cm104_frozen]])は2024-11凍結。 ★**凍結後の新刊は NDLサーチ自動取込**(`ma:dataPublisher: NDLサーチ`)で、 ★**schema:isPartOf(容器結線)を持たない孤立レコード**(title+volumeNumberのみ)。 = cm104/cm107どちらにも繋がらない。 cm107「マンガ作品」も新刊には結線無し(dead-end、 cm101証拠で確認)。
- = MADBネイティブ容器は旧作のみ。 新作はMADB側に grouping軸が無い。

**★解=NDL SRU APIの著者典拠ID**:
- `https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&query=isbn=XXX&recordSchema=dcndl` (要 html.unescape)。
- ★**著者典拠ID**: `dcterms:creator>foaf:Agent rdf:about="http://id.ndl.go.jp/auth/entity/NNN"` = ★**NDL authority=表記揺れ・凍結前後を越えて不変**。 ★**新刊(NDLサーチ由来)も旧巻と同じ典拠IDを持つ**(シャングリラ新旧で001361391,001231747一致=実証)。
- 同時に取れる: `dc:title`(主題+副題、 rdf:value が題本体)/ `dcndl:volume`(巻)/ `dcndl:edition`(エキスパンションパス等=版/おまけ識別)/ `dcndl:seriesTitle`(レーベル)。 ★**1照会で clustering+版+巻番号 が全部**。

**★clustering鍵(200群検証で確定)**:
- **主軸=正規化主題**(NFKC+小文字+ひら→カナ、 副題[「:」前]・中黒・括弧グロス[（エース）]・記号 吸収)。
- **補強=著者典拠ID集合**(あれば)/ 典拠空なら著者名。
- 統一条件 = ★**主題一致 ∧ (典拠overlap ∨ 典拠空)**(完全集合一致でなくoverlap=巻で著者数が違う鬼平型を吸収)。

**★検証実測**: 200群→relaxed統一188/200(94%)・over-merge 0。 ★**2000群(本検証)→ relaxed統一1891/2000(94%) / strict1825(91%) / over-merge候補10 / NDL未ヒット24 / 典拠ID可用97%**。 ★**over-merge候補10は精査の結果「真の誤統合0」**: 6件=NDLが種2の過分裂を正しく統合(頭文字D⇄イニシャルD/ZOMBIE‑LOAN⇄Zombieloan/代紋TAKE2/技巧貸与⇄スキルレンダー 等の表記違い=NDLが賢い)、 3件=続編/編(カードキャプターさくら+クリアカード編等=作品単位統合=MANGALで別ページ化は方針判断)、 1件=セレクション(drop候補)。 失敗91=典拠空(主題で救済可)+読みグロス正規化+★NDLが種2誤統合を正分離(トキワ荘≠アイヌ語辞典/西村京太郎傑作選=別編者)。 = ★**94%統一・無関係作の誤統合ゼロ・NDLは種2の過分裂も過統合も正す**=本番投入に足る堅牢性。

**★速度の現実(本実装の必須要件)**: per-ISBN SRU照会は~1秒/件(0.5s礼儀+通信)。 全34万巻=~95時間=非現実的。 → ★**対象を「容器なし新刊 + 分裂作」に絞る**(旧作はMADB isPartOfで統合可、 NDL照会不要)+ 遅延短縮/並列/NDL bulk。 cache=`.cache/ndl-sru-raw-cache.json`(検証で4136件蓄積済)。

**注意・限界**:
- ★NDL検索の引用符""完全一致は**UI専用、 OpenSearch/SRU APIでは無効**。 title検索は特徴的題のみ有効(「生存」等ありふれた題は25,591件で埋もれる)→ ★ISBN→SRUの per-volume照会が確実。
- 一部NDL古書誌は典拠ID欠落→主題+著者名fallback要。
- 副題は両義: 「:選集/外伝」=別物分離シグナル / 「:life」等=ノイズ揺れ → 主題は副題前で取る。
- 全DB(~34万巻)適用はNDL SRU大量照会→cache(`.cache/ndl-sru-raw-cache.json`)+礼儀(0.5s)+段階実行。 furigana audit と同パターン。

**★データ入手経路(2026-06-03 探索で確定)**:
- ★**NDL API(SRU/OpenSearch)= レート制限あり**。 ★具体値非公表だが「同時リクエスト制限 + 継続大量アクセスでIP遮断」(本セッションの検証4000件で**HTTP 429**を踏んだ)。 ★**商用(MANGAL=アフィリエイト)はAPI利用申請が必要**。 = ★**大規模API乱打は不可**、 対象限定+低速のみ。
- ★`ndlsearch.ndl.go.jp/` = **統合検索**(全国の連携図書館+CiNii等=ノイズ大、 うる星500件にmook/CD混在)。 ★`ndlsearch.ndl.go.jp/bib` = **全国書誌データ**(標準書誌=クリーン、 MARC/DC-NDL DL可)。
- ★**本命bulk = 全国書誌のOAI-PMHハーベスト**: `https://ndlsearch.ndl.go.jp/api/oaipmh`(verb=ListRecords&metadataPrefix=dcndl&from/until[full datetime])。 ★set無で日付範囲、 各レコードのsetSpecで `iss-ndl-opac`(全国書誌)/book/open/jpro を判別。 ~291件/日、 ★**earliestDatestamp=2022-10-01**(=★凍結後の新刊を完全カバー=本命対象)、 ★**オープンデータ・API遮断回避**。 ★ListSets: **B00156=NDL全国書誌情報 / B00155=新着**(但しB-setは日付harvestと相性悪く、 set無+日付+setSpec判別が正解)。
- ★**未確認(次回・レート回復後)**: OAIの dcndl 直列化に著者典拠リンク(auth/entity)が入るか(SRUでは確認済、 OAIは format差で未確認→**dcndl_v3要確認**)。 新着は「完成版(~1ヶ月後)」で典拠付与の可能性→完成版datestamp狙い。
- ★Web NDL Authorities bulk(id.ndl.go.jp/information/download)=著作典拠は**古典文学914件のみ・漫画無**、 個人名典拠も無し=漫画に**使えない**。
- ★うる星実測: NDL(189 ISBN)>種2(171)だが、 NDL-onlyの大半は非漫画(グラフィック=フィルムコミック12/mook/CD/ファンブック/研究本)。 = **古作はMADB完全、 NDL広域passはノイズ増**。 NDLが効くのは**新刊(凍結後)+分裂+疑い取りこぼし**。

**★★試走で判明した重要なcourse-correction(2026-06-03、 OAI 1週間+1日試走)**:
- ★**OAI bulkハーベストは本命にならない(dead-end)**: ① ★**OAI feedのdcndl/dcndl_v3に著者典拠(auth/entity)が0%=入っていない**(SRUには在るのに!=典拠は ★**SRU per-ISBNでしか取れない**)。 ② ★**全国書誌(iss-ndl-opac)の漫画が極端に希薄(NDC726=2件/日)**=NDL標準書誌は漫画をほぼ目録化せず(漫画は別経路=jpro出版情報等の可能性)。 ③ OAI batch=200/req(実測確定)。 → ★scripts/_harvest-ndl-oai.py は当初想定では使えない(典拠が来ない)。
- ★**(B)dry-runの決定的発見**: 検証2000分裂群の ★**91%(1823)が既存AUTO merge(著者集合)で既に統合済**、 NDL純増は51のみ(大半アメコミarc副題/セレクション=疑問符)。 = ★**全件NDL再クラスタは不要・無駄**。
- ★**= 現実的スコープ(最終)**: ★**NDLの出番は最小限**。 ①巻番号/版は **MADB schema:position/volumeNumber(patch済[[madb_volume_misnumber_fix]])で足りる(NDL不要)**。 ②分裂はAUTO mergeが9割解決。 ③NDL(SRU per-ISBN 典拠)が要るのは ★**残9%のAUTO漏れ + 凍結後新刊の小集合(数百〜低千件)だけ**を低速照会(+商用API利用申請)。 ④検証用SRU cache 4000+件(`.cache/ndl-sru-raw-cache.json`)は再利用可。
- ★教訓: MADB(種2)+ AUTO merge + MADB native fields が想像以上に強い。 NDLは「凍結後新刊」と「AUTO漏れ」のピンポイント補完に絞るべき。
- ★**AUTO漏れの実数(種2実測)= 164群/~2,175巻のみ**(凍結後新刊19,700巻の大半は既存シリーズに繋がりclustering不要)。 = SRU照会は実質数千件・~1時間で足りる(340kでない)。
- ★**AUTO漏れ164群のローカル改善 = 112件統合適用済(commit e9e9f76、 NDL不要)**: strict-norm(整形のみ=全角半角/中黒/空白吸収、 ★副題/続編[:re/第N部/arc]は保持→除外)で同一題 + ★qid整合(union内非None著者qid同一→同名別著者/別作品を除外)+ UNION整合。 116→qid整合で112。 検証=釣りバカ日誌(113+15+10→132)/咲(別qid物を正分離)等。 ★危険な誤merge(東京喰種:re/X-MEN arc/別qid)を構造的に回避。 残52群(HOLD48=続編副題+qid不整合等)はNDL or 個別。

関連: [[madb_native_series_structure]][[madb_volume_misnumber_fix]][[furigana_ndl_audit]]。
