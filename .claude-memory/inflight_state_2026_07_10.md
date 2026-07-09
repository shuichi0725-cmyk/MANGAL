---
name: inflight_state_2026_07_10
description: 2026-07-10時点の進行中状態(mangazenkan/cmoa資産・週次待ち・残タスク)
metadata:
  type: project
---

2026-07-10クリア時点の進行中状態。

- **週次蒸留待ち**: preorder-pages **52件**(28+12+6+回収6の一部) + 完結是正344(status-corrections.yml) + 巻補完25作120巻+7巻/5作 + あしたのジョー4版再構築。次の「週次蒸留して」で全部本番公開。
- **テスト環境**: 17頁(①続巻11+巻抜け5作+回収ドラフト6=明日もいい日本編/スピンオフ/無自覚聖女/百雌繚乱/不貞の子/異世界サモナー)。回収分は確認→「本番化して」待ち。
- **mangazenkan資産**: `.cache/mangazenkan-完結.jsonl`=**8,778完結作**(page166で終端・題/巻数/著者/出版社)。ページ送り上限で全33,987の一部。[[feedback_accuracy_is_the_goal]]
- **完結漏れ残タスク**: 安全ゲート外の**2023-26最新巻626件**(キン肉マン型偽陽性多・要Wiki検証) + **不明134**(Wiki無)。検証済み493→344適用済/偽陽性9除外。
- **巻取りこぼし残**: NDL不一致22作(華夜叉/サライ=古典変則) + mangazenkan差1の141件(ノイズ多)。
- **cmoa**: 38/50バッチ(760作)で停止・`resumeFromRunId`で再開可(掲載誌ソース)。ヒット率~52%。
- **Cloudflare**: `.env`にCLOUDFLARE_API_TOKEN(Analytics Read)。「アクセス解析して」で日別レポート可。
- ★**D:ドライブ=.cacheのsymlink先**。切断すると全部消えたように見える(実体は無事)。ユーザがE:へバックアップ作成。
- 保留hold場所: `.cache/preorders/scope-out-hold/`(アンソロ号4件) `.cache/preorders/drafts-dropped/`(ゴルゴ13vsCIA=drop裁定)。
