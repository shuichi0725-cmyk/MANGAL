---
name: slug-cluster-fix-and-changelog
description: 主版slug消失バグ(従版に本編収容・著者汚染)を37作修正済。来歴ログ機構(_change-log.jsonl/slug-overrides.yml)。promote未読込=恒久化未了
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

2026-06-16 修正。**症状**: 本編(主版)の無印slugが消え、本編が従版slug(年/副題suffix)に収容される＋著者汚染。
発端=名探偵コナン本編が `meitantei-conan-2011`(著者=太田勝=映画フィルムコミック作画家)に入り無印消失。

**根本原因**: slug生成(slug-final-integrated.tsv・qid基準で「本編=無印」と正しく提案)と、本番promoteのクラスタリング(著者基準)が**食い違い**。著者キーに映画作画家(太田勝/阿部ゆたか等)が紛れ→別クラスタ化→無印が生成されず従版slugに本編が入った。[[author_pollution_overlay_fix]][[clustering_unit_is_series]]

**scope**: slug-final提案=無印なのに本番で無印消失=**60作**(コナン175/江戸前の旬130/JIN/超電磁砲/蜘蛛/デビルマン/ポケスペ等)。

**修正済(37作・可逆・全層)**:
- コナン: -2011→無印 `meitantei-conan`・著者 太田勝→青山剛昌単独。
- Type A 36作: 「題完全一致の本番ファイルが1つ＋無印slug空」のみ自動rename(`scripts/_fix-cluster-slugs.py`)。
- 適用層: data/manga(source)/data/manga.v2/.preview-data。sansedai-stockの旧slug参照も是正。

**来歴ログ機構(今回新設・git追跡)**:
- `data/seeds/_change-log.jsonl` = 追記専用1行1変更。ts/action/target/detected_by/source/before/after/checks/confidence/**undo**/state。保険・巻き戻し用。
- `data/seeds/slug-overrides.yml` = {旧slug: {slug:新, reason, at}} 恒久指示。
- `data/slug-aliases.yml` = 旧→新301。
- ★スクリプト: `_fix-conan-main.py`(コナン)/`_fix-cluster-slugs.py`(--apply。dry-run既定)。

**恒久化(2026-06-16 ②実施)**: ★**promote(_promote-bulk-v2.py L1697付近)が slug-overrides.yml を読むよう実装済**(`_slug_override()`・py_compile確認)=再promoteで-2011等が再発しない。著者は補正機構がoriginal→author昇格不可のため、**コナンは src `_skey` を汚染fragment(name:太田勝|名探偵コナン/2巻)→綺麗な本編(qid:Q313945|名探偵コナン/sid40529/175巻/青山剛昌)へ再指定**で恒久化。★残課題: data/manga(_skey格納)はgitignore=再生成で消える恐れ(完全git永続化は未)。★コナンは次promoteで巻数107→175=重複版のdedup要確認。

**①完了(2026-06-16・flag23作決着)**: rename9(jin/bara-monogatari/black-jack-kuroi-ishi/cashmere/dai-chouhen-doraemon/deep-impact/inma-no-ikenie/kibun-wa-hardboiled/ten-yori-takaku→無印)+ no_action14(bakudan/en/fetish/kujira/kyou-kara-hitman-special/majo/message/nippon-no-rekishi/pocket-monster-special[Type B本編不在]/refrain/seasons/spring/tenchi-muyou/yuuwaku=同名別作集合で無印作らずが正)。全件 _change-log に記録。③検証=meitantei-conan.html 著者青山剛昌・旧-2011消滅・deploy success。

**スクリプト**: _fix-conan-main.py / _fix-cluster-slugs.py / _resolve-flags.py / _inspect-flags.py。

**関連調査**: 名探偵コナン フィルムコミック/漫画版 混線(`docs/conan-investigation.pdf`)。Wikipedia映画記事のISBN×我々のISBNで漫画版(keep)/フィルムコミック(drop)を権威確定(5映画100%一致)。映画フランチャイズ全般に横展開可。[[madb_volume_misnumber_fix]]
