---
name: role_credit_original_author_fix
description: 【機構】巻書誌の[原作]クレジットで原作者抜けを埋め、[作画]で役割を直す(ゴブリンスレイヤー型・2026-10-04)。条件・除外・読みの宿題
metadata:
  type: project
---

発端(2026-10-04 ユーザ): ゴブリンスレイヤー本編/外伝だけ原作 蝸牛くもが抜け、外伝の作画が「原作・作画」。
- **原因**: 頁の著者は種2のシリーズ台帳(主sidの series_authors・cm104凍結)だけから作る。MADB巻書誌(生 metadata101)は
  全巻に `[作画]黒瀬浩介` `[原作]蝸牛くも` と役割付きで持つが、promote は表示名寄せ(`_apply_book_credit`=人を足さない)にしか使っていなかった。
  AniList著者補完は著者0人の頁だけ。
- **機構**: `scripts/_gen-madb-role-credits.py` → `data/seeds/madb-role-credits.json.gz`({isbn: {o:[原作], a:[作画系]} | 0})。
  ★月次でMADB取込後に再生成(生 metadata101.json が要る)。promote の build_yml で `_role_credit_fix`(著者override より前=手が勝つ):
  ①原作者欄が空の頁だけ、過半数の巻(クレジットの在る巻が分母)に[原作]で載る名前を足す。会社名/製作委員会も入れる(ユーザ裁定)。
  除外 = 既存著者と同一人物の疑い(畳み込み一致・部分一致・DB別名)/ 名前に [ / 監修 ほか 協力 不詳 不明 /
  カタカナ候補で著者欄に姓名連結ローマ字(GrahamLynne)が居る頁(翻訳物の二重)。
  ②原作者が居る頁で writer_artist が過半数の巻で作画系タグのみ → artist。
- 事前調査: 候補1,872行のうち 原作者欄が既にある頁は表記揺れ二重(桑澤/桑沢)・MADB誤記(山田宏→山口宏)が多い=触らない。
  ★DB mangaka.alt_names に別人混入(中津功介=古場みすみ等)= `_apply_book_credit` の改名にも使われる別リスク(未着手)。
- 反映(2026-10-04): 模擬計算 2,262頁(原作+1,568行・1,148人 / 役割→作画 1,027人)+読み追加の945頁 = 2,934頁を targeted 反映
  (500頁×6・バックアップ .cache/role-credit-fix-bak-<ts>/・表 docs/production-diagnostics/role-credit-fix.tsv)。
- 読み: `scripts/_resolve-author-yomi.py`(MADB504のja-hrkt→NDL典拠)で423人を author-yomi.yml へ純粋追加(末尾追記・既存不変)。
  ★宿題: 漢字始まりの個人名 約120人(.cache/role-fix-yomi-ndl-books.json)は NDL が429/timeoutで未取得 →
  回復後に `_lookup.ndl_live_retry`(作法どおり)で ISBN書誌の creators/creators_kana(件数一致時のみ対応付け)から引く。
関連 [[author_data_map]] [[madb_cm104_frozen]] [[author_roles_state]] [[ndl_access_rate_method]]
- ★**ユーザ指示(2026-10-04)「120人は引き直す。覚えておいて」** = NDL回復後に必ず実施(対象 .cache/role-fix-yomi-ndl-books.json = name→ISBN)。
  author-yomi.yml へ末尾追記 → 該当頁を targeted 反映。
- revisions(リヴィジョンズ)の原作 = S・F・S で正(ユーザが Wikipedia で確認)。旧 茗荷屋甚六(AniList由来)は誤り。
