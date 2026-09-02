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
