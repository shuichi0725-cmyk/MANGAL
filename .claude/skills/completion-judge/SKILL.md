---
name: completion-judge
description: 完結判定して=連載中頁の最新巻captionから完結明示を拾う(Sonnet安全設計・fail-closed)。完結適用して=候補をOpus+が再判定しstatus-corrections適用(週次前)。チェンソーマン24巻型の取りこぼし防止
---

# 完結判定 (= 2026-07-16 ユーザ設計。トリガー「完結判定して」/ 適用「完結適用して」)

連載中(status!=completed)の頁は、最終巻が出ても気づけない(キャッチ/ジャンル等が揃っていると
その巻のcaptionを読まない)。出版社は最終巻の紹介文に「堂々完結!!」等を書く慣行があるので、
**最新巻のcaptionだけ読んで完結明示を拾う**。適用seedは既存の `status-corrections.yml`(promote結線済)。

## 役割分担 (= ユーザ裁定)
- **Sonnet**: 判定キュー生成→worksheet記入(明示文言のみtrue)→--collectで候補TSVへ。ここまで。
- **Opus4.8+(週次蒸留の前)**: 候補TSVを改めて判定→`--apply`→reflect。**適用はSonnetがやらない**。

## Sonnet手順 (=「完結判定して」)
```
python scripts/_completion-judge.py --queue            # 日次: 新刊巻が付いた頁だけ(caption無しは翌日再試行)
python scripts/_completion-judge.py --backlog --limit 300   # backlog: 連載中全頁スイープ(resume自動・caption無しは記帳=一回きり)
```
→ `.cache/completion/worksheet.jsonl` のTODOを記入:
- `completed: true` = captionに**完結の明示文言**がある時だけ。`quote` に該当文をそのまま引用(必須)。
  例: 「堂々完結!!」「ついに完結!」「最終巻!」「最終回」「感動の大団円」「完結巻」
- `completed: false` = それ以外全部(fail-closed)。★偽陽性の型:
  「最終章突入!」「クライマックス!」= 継続中 / 「第一部完」= 部の完結 / 「アニメ完結」= 作品は継続 /
  「完結記念」(既刊完結セットの宣伝) / 「完結間近」。迷ったらfalse+noteに理由。
```
python scripts/_completion-judge.py --collect          # true行→docs/production-diagnostics/completion-candidates.tsv
git add data/seeds/completion-judged.jsonl docs/production-diagnostics/completion-candidates.tsv && git commit && git push
```
- backlogは `--limit 300` ずつ回して commit+push(逐次保存・冪等=アイドル運転の柱④)。
- 429で自然停止(進捗保存済)。液晶の前の判断は「引用があるか」だけ=Sonnet安全。

## Opus+手順 (=「完結適用して」・週次蒸留の前に)
1. `completion-candidates.tsv` の各行を再判定(quoteが本当に作品完結か。シリーズ改題継続/分冊版に注意)
2. OKな行: `python scripts/_completion-judge.py --apply --slugs a,b`(または全承認なら `--all`)
   → `status-corrections.yml` へ純粋追加(status=completed + year_ended=最終巻年)
3. `python scripts/_reflect-targeted.py --only <touched> --push`
4. NGな行はTSVから手で消す(judgedレジャーには記帳済=再浮上しない)

## NEVER
- Sonnetは `--apply` を叩かない(適用=Opus+専権。ユーザ設計)
- quoteの捏造禁止(captionに無い文でtrueにしない)。曖昧=false
- 判定済みレジャー(`data/seeds/completion-judged.jsonl`)を手で編集しない(resumeの土台)

## 関連
- seed結線: `_promote-bulk-v2.py` の `_STATUS_CORR`(status-corrections.yml) = 2026-07-09既設
- 新刊巻の供給源: skill daily-distill(zokkan) / `_backward-apply-existing-vols.py`(a-touched)
- アイドル運転: skill idle-run の柱④(backlogスイープ)
