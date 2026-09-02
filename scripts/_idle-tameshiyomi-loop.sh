#!/bin/bash
# ★退役(2026-09-02): 旧アイドル運転の試し読みアンカー無限ループ。
#   対象は2026-07-15に枯れ、かつ本体は `while :` 無限 + 停止札チェック無し + 日次上限(CapReached=exit 0)で
#   空回りし続ける構造だった(リクエストは出ないが止まらない)。誤起動防止のため本体を撤去し即終了にする。
#   現行の柱①は scripts/_idle-tameshiyomi-expand-loop.sh(停止札/収穫ゼロ停止/MAX_BATCH/exit 2で札設置)。
#   アンカー収集(--limit 100)は週次step1が1回だけ回す。
echo "退役済み: 旧アンカー無限ループは起動しない。柱①は _idle-tameshiyomi-expand-loop.sh / アンカー収集は週次step1。"
exit 1
