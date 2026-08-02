---
name: romcom-judge
description: ラブコメ判定して/続けて=romance∩comedy候補を材料ベースでromcom裁定(Sonnet安全設計・fail-closed・知識判定禁止)。ラブコメ適用して=yes分をOpus+がgenre-append.ymlへ適用。80年代ラブコメ6件問題の恒久是正
---

# ラブコメ判定 (= 2026-08-03 ユーザ設計。トリガー「ラブコメ判定して/続けて」/ 適用「ラブコメ適用して」)

## 背景 (= なぜやるか)

`romcom` は全DBで**143作しか無い**(80年代は6件)。注ぎ手(AniList/楽天/AI fill)が romance+comedy の
2キーに割って romcom を出力しない構造のため。候補集合 = **romance∩comedy 7,184作**。
うち紹介文に「ラブコメ」明記の**2,181件は自動YES済**(text-match)。残りをAIが材料ベースで裁定する。
同型の枯れキー(4-koma 93/gag 147/samurai 132/mahou-shoujo 217/war 194/yokai 257)への横展開は本柱の効果確認後。

## 役割分担 (= ユーザ裁定 2026-08-03「コストで困るかも。skill化して他にやらせたい」)

- **Sonnet**: worklist の材料(catch/synopsis/themes)だけを根拠に yes/no/unknown を裁定→台帳へ逐次保存。ここまで。
- **Opus4.8+**: `--apply`(genre-append.yml書込)と reflect。ai-judge yes の無作為~20件を目視してから適用。

## Sonnet手順 (=「ラブコメ判定して」「ラブコメ判定続けて」)

```
python scripts/_romcom-worklist.py            # 初回 or .cache消失時のみ(裁定済はskip=冪等)
python scripts/_romcom-batch.py --stats       # 進捗確認
python scripts/_romcom-batch.py --show 100    # 未裁定の先頭100件(★150だと出力が外部ファイル化して面倒。100推奨)
```
表示形式: `slug \t 年|対象|誌|themes \t 題 \t catch／synopsis`

各行を裁定して `{"slug":"yes|no|unknown", ...}` のJSONを `.cache/romcom-vNN.json` に書き:
```
python scripts/_romcom-batch.py --apply .cache/romcom-vNN.json
```
**3バッチ(~300件)ごとに** `git add data/seeds/romcom-judged.jsonl && git commit && git push`(逐次保存)。

### 裁定基準 (= ★材料に書いてあることだけが根拠。fail-closed)

- **yes** = 材料が「恋愛とコメディが主軸で絡む」ことを示す時だけ。証拠語彙の例:
  「ラブコメ」「コメディロマンス/ロマンティック・コメディ」「恋のドタバタ」「純愛コメディ」「恋愛コメディ」
  「胸きゅんコメディ」「〜との恋を描くコメディ」「恋と笑い」。
  設定型の証拠: 恋愛関係・求愛・同居/許嫁/幼なじみとの恋 を巡る騒動・勘違い・ドタバタが本筋。
- **no** = 材料が別の主軸を明示: シリアス恋愛(「切ない」「ドラマ」)、ギャグ主軸(恋は小道具)、
  スポーツ/バトル/ミステリー主軸(恋はサブ)、家族/群像コメディ、お色気コメディ(恋愛関係の発展が無い)、
  雑多な短編集。
- **unknown** = 材料が空('')・題名しか無い・上記どちらとも読めない。★迷ったら unknown。

### NEVER (= Sonnet安全設計)

- ★**知識判定禁止**: 「この題名は有名なラブコメのはず」等、材料に無い根拠で yes にしない
  (Gemini検品が幻覚で退役した教訓。知名作の知識判定は Opus+ が別途行う)。
- `scripts/_romcom-apply.py` を叩かない(適用=Opus+専権)。
- 台帳 `data/seeds/romcom-judged.jsonl` を手で編集しない(resumeの土台。追記はscript経由のみ)。
- 台帳・worklistの再発明禁止(既存scriptを使う)。

## Opus+手順 (=「ラブコメ適用して」)

1. `python scripts/_romcom-apply.py --dry` で件数確認 + ai-judge yes を無作為~20件目視(台帳とworklist突合)。
2. `python scripts/_romcom-apply.py --apply` → genre-append.yml へ純粋追加(冪等・source付き・quote済)。
3. 反映: 件数少なら `_reflect-targeted.py --only <slugs> --push`、数百件超なら**次の週次蒸留に乗せる**(安い)。
4. commit+push(genre-append.yml + romcom-judged.jsonl)。

## 関連

- seed結線: `_promote-bulk-v2.py` の `_GENRE_APPEND`(genre-append.yml union・フラグ不変) = 2026-07-31既設
- 台帳: `data/seeds/romcom-judged.jsonl`(git追跡・純粋追記) / worklist: `.cache/romcom-worklist.jsonl`(再生成可)
- 経緯記憶: [[romcom_backfill_state]] / ジャンル閉語彙: [[ai_genre_closed_vocabulary]]
