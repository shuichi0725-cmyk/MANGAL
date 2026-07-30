---
name: synopsis-audit
description: あらすじ検品して/あらすじ検品続けて=synopsis-ja.json(3.9万件)の「別作品の内容」型を機械flag→AI裁定→是正。スワップはペアで直す。Opus運転前提
---

# あらすじ検品 (= 2026-07-30 新設。トリガー「あらすじ検品して」「あらすじ検品続けて」)

synopsis-ja.json(anilistキー・39,591件)に**別作品のあらすじが入っている**型を掃引する。
発見の型見本: ばけもの夜話づくし(105592)⇔凪のお暇(105614)の**相互スワップ**(生成batch内の対交換。
AniListリンクは正しいのにseed本文が別作品) + レッツ&ゴーMAX(48828)の事実誤り(前日譚→実は続編)。

## NEVER (全部実害由来)

- ★**訂正は必ず `synopsis-ja.json`(該当aidキー)へ** — `synopsis-slug-ja.json` に書いても頁に出ない
  (promoteはanilist側が先に埋め、slug側は「空の時だけ」fallback。Opusが一度この罠を踏んだ 2026-07-30)
- ★**スワップはペアで直す** — 1件見つけたら「その文が実際に指す作品」(swap_hint列が推定)側の
  seedも必ず確認する。相手も誤っているのが常
- **seedを手で編集しない** — 訂正は `--fix`(backup+changelog内蔵)経由のみ
- **推測で書かない** — 訂正文は `--show` のcaption素材/catchから書く。素材が無い作品は
  `--verdict <aid> hold` で保留(裁けないものを捏造で埋めない [[feedback-accuracy-is-the-goal]])
- 要約は60-120字・ネタバレ無し・最終巻あらすじの丸写し禁止(synopsis-ja本来の規格)
- fixしたら**その頁のslugをメモし、セッション末にまとめて reflect**(1件ずつreflectしない)

## 手順

```
0. 前提(初回 or 索引大変更後のみ・~10分): python scripts/_synopsis-audit.py --build
1. 検出:                                  python scripts/_synopsis-audit.py --scan
   → docs/production-diagnostics/synopsis-audit.tsv (score昇順=怪しい順。裁定済みは自動除外)
2. 裁定ループ(上から。1回のセッションで20-40件目安):
   a. python scripts/_synopsis-audit.py --show <aid>   # synopsis vs catch/caption素材を並べる
   b. 判定:
      - 別作品の内容 → swap_hint の相手頁も --show で確認(相互スワップか確認)
        → 訂正文をcaption素材から書き .cache/synfix-<aid>.txt へ →
        python scripts/_synopsis-audit.py --fix <aid> --text-file .cache/synfix-<aid>.txt
        (相手側も同様に fix。両方の verdict を fixed で記録)
      - 内容は同一作品で妥当 → python scripts/_synopsis-audit.py --verdict <aid> ok --note "..."
      - 素材不足で裁けない → --verdict <aid> hold --note "..."
3. 反映: fixしたslugを列挙して
   python scripts/_reflect-targeted.py --only <slug,...> --push -m "あらすじ検品: N件是正"
4. 報告: 検品N件(fixed/ok/hold内訳)+スワップ発見ペア+累計。台帳=synopsis-audit-verdicts.jsonl
```

## スコアの読み方(scan列)

- score = synopsisの内容語(漢字2+/カナ2+連)が同頁の独立証拠(title+catch+巻caption)に出る割合。
  **0.00=ほぼ確実に別作品** / 0.12未満をflag(それ以上は正常扱いで対象外)
- swap_hint = synopsisの語が題名に多く一致する別頁(=本文が本当に指していそうな作品)。空=推定不能
- ★偽陽性の型: 抽象的な短文synopsis(固有名詞ゼロ)/caption素材が乏しい作品 — ok/holdで台帳に落とす
- 裁定台帳(verdicts.jsonl)が resume の実体。scanは何度でも再実行可(裁定済みを除外して出す)

## 関連

- 訂正の実害記録=[[enrich-7k-resume-state]](2026-07-30続報) / 素材照会=skill external-data-access
- 頁反映=skill reflect-targeted / 同型の月次サニティ化は未着手(全量一巡後に検討)
