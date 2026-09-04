---
name: bash_tool_heredoc_quote_pitfall
description: "【作業メモ】Claude CodeのBashツールで本文にシングルクォートを含むheredoc(python - <<'PY')が「unexpected EOF while looking for matching `''」で落ちる。回避=Writeでscratchpadにスクリプトを書いてから実行"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 91943095-ce24-473b-aee4-acbf1493c653
  modified: 2026-09-02T03:57:10.293Z
---

# Bashツールのheredoc+シングルクォート落とし穴 (2026-09-02 実踏)

`python - <<'PY' ... PY` の本文に `r['slug']` のようなシングルクォートが入ると、
Bashツールが `bash: -c: line 90: unexpected EOF while looking for matching ''` で
**1行も実行せず**落ちる(Git Bash on Windows / bypass permissions)。原因は未特定(ツール側のラップと推定)。

**回避(確立)**: 複数行のPython/シェルスクリプトは **Write ツールで scratchpad に書き、
`python "$S/xxx.py"` で実行**する。Bashコマンド本文にはシングルクォートを入れない。
`PYTHONIOENCODING=utf-8` を付けないと日本語printが文字化けする(実害なし・見た目)。

あわせて: repo の .py は **CRLF/LF が混在**(`_lookup.py`/`_completion-judge.py` はCRLF、
`_material-harvest.py` はLF)。機械置換は改行を正規化してから照合し、元の改行で書き戻す。

関連: [[feedback_agent_fanout_token_cost]](同じ見直しをサブエージェント無しで済ませた回)

追記 2026-09-02(夜): **バックスラッシュも化ける**。heredoc本文の `.replace('\\','/')` が実行時に
`unterminated string literal` になった(ツール側ラップで `\\` が `\` に潰れる)。シングルクォートと同じく
**Writeでscratchpadに書いて実行**が正解。関連: [[process_kill_commandline_self_match]]

- ★**ログ/生成物の読み出しで UnicodeEncodeError**(2026-09-02 2回踏んだ): `python -c "print(open(log,"rb").read().decode(...))"` は stdout が cp932 のままだと `\uFFFD`(replace文字)や絵文字で落ちる。**必ず `sys.stdout.reconfigure(encoding="utf-8")` か `export PYTHONIOENCODING=utf-8`** を先に付け、bytes は `decode("utf-8","replace")` で読む(reflect/promote のログは utf-8 と cp932 が混在)。

- ★**引数の `/` が `C:/Program Files/Git/` に化ける**(2026-09-04 実害): Git Bash(MSYS)は
  スラッシュで始まる引数をWindowsパスへ自動変換する。 `python scripts/_indexnow.py --urls /,/about` が
  **トップページでなく `https://mangal-db.com/C:/Program Files/Git/` を検索エンジンに送っていた**
  (ログの sample で発覚)。 回避= `MSYS_NO_PATHCONV=1` を付ける / PowerShell で叩く /
  `python -c` から関数を直接呼ぶ。 ★根治は**受け手側で形を検査**すること
  (`_indexnow.sanitize_urls` = パス以外[空白・`:`・`\`・`//`]を送信の一点で破棄)。
