---
name: author_kana_fill_state
description: 著者フリガナ完埋め=完了(2026-06-11)。Web裏取り全30バッチ済→author-yomi.ymlに1,676件純粋追加(35,679キー)。unresolved 372はauthor-yomi-unresolved.jsonに保留。反映は次回promote
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★**著者フリガナ完埋め(2026-06-10〜11)= seed反映まで完了**(commit 352c737a)。

**結果**:
1. AI一括生成2,161名(`.cache/kana-fill-results.json`: high 1,281 / low 880 / 団体134)
2. low 880全員のWeb裏取り(30バッチ、NDL/電書店/出版社/Wiki): **confirmed 328 / corrected 180 / unresolved 372**。訂正率~20%=Web裏取り必須の再実証。batch15-30結果=`.cache/kana-verify-out/batch-NN.json`、batch1-14=`.cache/kana-verify-results-1.json`
3. ★**author-yomi.yml に 1,676件 純粋追加**(34,003→35,679キー)= AI高確信1,191 + Web確認504 − 既存重複19 − role汚染3。`applied=1676, missing=0, overwrites=0` 機械確認済。適用器=`scripts/_apply-kana-verified.py`(dry-run→--apply、.new検証→置換)
4. ★**unresolved 372 = `data/seeds/author-yomi-unresolved.json`**(git追跡)に保留。name/ai_kana/note/verify_source付き。★**ユーザ自身が手動調査中**(2026-06-11、AI調査コスト高のため。名前リストを50名×7+22の8txtで渡し済)。★戻ってきたら「名前→読み」を**純粋追加**(形式は何でも受ける、`scripts/_apply-kana-verified.py`と同様に overwrites=0 機械確認、部分追加OK)。AI側から再調査しない
5. role文字列混入名(「Yoshi原作者」等3件)=author overlay側の課題としてskip

**残**: 本番反映は次回promote(enrich_authorがauthor-yomi.ymlを読む)。それまで本番kanaカバー率は旧値のまま。

関連: [[author_data_map]][[method_ai_generate_plus_webverify]][[author_kana_index_and_mobile_filter]]
