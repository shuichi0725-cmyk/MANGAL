---
name: feedback_no_negative_record_on_failure
description: 【戒め・全外部照会共通】失敗(瞬断/5xx/timeout/連続429)を「無い」に変換して台帳に書かない。書いてよい否定は200で空だけ。連続429は即exit 2。検査法=except Exceptionの直後に台帳書込/done追加/結果行が続くか
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 91943095-ce24-473b-aee4-acbf1493c653
  modified: 2026-09-02T08:36:27.505Z
---

# 失敗→否定記録の禁止 (= BookLive事故 2026-08-29 の核心。2026-09-02 に非BookLive柱へ全適用)

**規則**
- 外部照会(楽天/NDL/wiki/TinyFish/AniList/BookLive)の**失敗を「無い」に変換して台帳・done集合・結果行に書かない**。
  書いてよい否定は **HTTP 200 で空**(楽天Items空・wiki missing・NDL 0件・BookLive 404)だけ。
- 連続429(`_lookup.Throttled` / `_booklive.Blocked`)= **即 exit 2**(次の手すきで同コマンド再開)。瞬断= **記帳せずskip**(次回再照会)。
- live予算(--live N)で**照会しなかった**対象も記帳しない(④完結判定で100件超が未照会のまま「nocaption」固定されていた型)。

**Why**: 規制されるほど偽の「無い」が増え、二度と再チェックされない(BookLiveで231万行、完結判定で3,799行を巻き戻した)。
「分からない時は書かずに止まる」が正しい。

**How to apply**
- 検査は目grepでなく2点だけ見る: ① `except Exception` の直後に **台帳書込/done追加/結果行書出** が続くか
  ② `Throttled`(NDLは `HTTPError.code==429`)を汎用exceptより**先に**個別で受けているか。
  BookLive経由scriptはヘルパ関数経由も推移的に追うAST検査(scratchpadで書き捨て)で「Blocked/CapReached握り潰しゼロ」を確認した。
- 新しい柱を足す時も同じ2点を通す(skill idle-run「失敗→否定記録の禁止」節が実装側の正本)。
- 過去に焼かれた偽陰性は **backup付きで巻き戻し**て再照会に回す(区別できないなら正当分も含めて全件)。

関連: [[booklive_access_incident]] [[feedback_agent_fanout_token_cost]] [[ndl_access_rate_method]] [[rakuten_long_job_needs_retry]]
