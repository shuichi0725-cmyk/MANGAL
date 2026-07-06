---
name: promote-empty-only-wipe-accident
description: "【戒め】promote --only \"\" (シェル変数空)がフルモード誤発動→全66k削除事故(2026-07-06)。ガード実装済み・復旧はフルpromoteで可能"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

2026-07-06、`python scripts/_promote-bulk-v2.py --only "$ST"` で **$STが空**(前段の生成コマンドがエラーでファイル未作成)のまま実行→ promoteが「--only無し=フルモード」と解釈→ **フルモードは開始時に data/manga.v2 の全ymlを削除する仕様** → 全66,900頁削除→10分timeoutでkillされ13kで中断。

**Why:** シェルで `VAR=$(cmd)` が失敗しても後続は空文字で走る。promoteのフル/targetedの分岐が「ONLY_SLUGSが空か」だけだったため、空引数がフル(destructive)に落ちた。

**How to apply:**
1. **ガード実装済み**: promoteは `--only` 指定で中身が空なら即abort(sys.exit 2)。剥がさない。
2. シェルで `$VAR` をdestructiveコマンドに渡す前は**必ず `[ -n "$VAR" ] &&` を付ける**(自分の書くワンライナーでも)。
3. 長時間コマンド(フルpromote等)をBashのtimeout付きで直接実行しない(kill=中途半端な削除状態)。run_in_background か PowerShell 背景で。
4. **復旧手順**(実証済み): manga.v2は種2+seedからの純粋な派生物。全seedがcommit済みなら `python scripts/_promote-bulk-v2.py`(フル~50-110分)で全成果込みで完全復元できる。本番R2・preview・seedは独立で無傷。復元後は本番索引+カレンダー再生成+スポット検証(当日修正した頁のmax巻)を行う。
5. 索引フル再生成のskip数の平常値=**~923**(genre other 920=[[display_data_polish_tasks]]の既知未解決+微量)。0でないからと慌てない、悪化検知は「923から増えたか」で見る。
