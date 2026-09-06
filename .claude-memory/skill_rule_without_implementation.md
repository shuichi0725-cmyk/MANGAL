---
name: skill_rule_without_implementation
description: skill/CLAUDE.mdに「規定」があっても実装されているとは限らない。規定に頼る前にgrepで実体を確かめる
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 74b7cb9b-8792-4d9b-a5f5-6e0efb70e9e8
  modified: 2026-09-06T13:28:13.297Z
---

skill や CLAUDE.md に書いてある**運用規定が、実際にはコードのどこにも実装されていない**ことがある。
規定を読んで「ではこの型は処理済みだな」と判断すると、静かに取りこぼす。

**実例(2026-09-04 日次蒸留)**: skill daily-distill A2-2 に
「上下巻: ペア=1頁統合(上=v1,下=v2・題から上下除去) / 下巻単独=保留」と明記されていたが、
`grep -n "上下\|ジョウ\|ゲカン\|pair"` が生成器・分類器のどこにもヒットしなかった = **未実装**。
結果『ひみつー佐世保事件で妹を喪ったぼくの話ー』(新潮社バンチ・同日発売)が
上=new1b(1巻の新作) / 下=ex_mid(全巻回収不成立) に割れ、1作品が2経路へ散っていた。

**Why**: 規定は「そうすべき」を書いたもので「そうなっている」の保証ではない。
skillは人が読む手順書なので、実装より先に書かれる/実装が後で消える、のどちらも起こる。
規定を実装の証拠として扱うと、検査したつもりで検査していない状態になる。

**How to apply**:
- 規定に基づいて「この型は処理済み」と結論する前に、**その規定を実装しているコードをgrepで1回引く**。
  ヒット0なら未実装。ヒットしても、その関数が実際に呼ばれている経路かを確かめる。
- 未実装を見つけたら手作業で埋めず**scriptに焼いてから**進む([[feedback_efficiency_first]] と同じ理由=次回消える)。
- 逆に、実装を直したら skill 側の記述も更新して「規定だけが残る」状態を作らない。

## ★機構で封鎖した分 (2026-09-06)

同じ型が **月次サニティ**でも起きていた: CLAUDE.md の月次サニティ節に「月次=新規増加を見る」と
書いた検出器のうち **4本**(`_audit-subtitle-orphan-volume.py` = Sugar&Spice型で適用器まで在る /
`_furigana-audit.py` / `_anilist-verify-gate.py` / `_audit-seed1-lost.py`)が
`_monthly-distill.py` の `DETECTORS` に登録されておらず、**一度も回っていなかった**。

→ ★**`scripts/_check-sanity-registry.py`** を新設(節 ⇔ DETECTORS を突合。未登録/実体なしで exit 1。
`run sanity` の先頭で自動実行)。 回さない理由が在る検出器は script 内 `EXEMPT` に**理由つき**で書く。
以後「節に書いたのに回らない」は機械が鳴る = grep で確かめる手間が要らない。
DETECTORS は 25本(既定18 + heavy 7)。

★同日、 検出器カタログの**本文**を `docs/monthly-sanity-detectors.md` へ逃がした(CLAUDE.md の 39.7% = 17,404字を占めており毎セッション読む必要が無い)。 CLAUDE.md 側は**29行の索引表**。
番人はこれに合わせて **3点突合**(索引=CLAUDE.md ⇔ 本文=docs ⇔ DETECTORS)になった。
★**新しい型を足す時は 本文・索引・DETECTORS の3つを揃える**(揃わないと番人が exit 1 で鳴る)。

関連: [[daily_distill_hold_not_requeued]](簿に出るのに消化されない型) /
[[feedback_sanity_check_tool_warnings]](script出力を鵜呑みにしない) /
[[feedback_raw_count_is_not_worklist]](登録する時は行数を**芯**TSVに向ける)
