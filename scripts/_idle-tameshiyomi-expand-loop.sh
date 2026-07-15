#!/bin/bash
# アイドル運転のexpand消化ループ(2026-07-15): アンカー収集は枯れた(13,949作)が、全巻展開は1,089シリーズ
# しか済んでいない=積み残し~1.2万シリーズをバッチごとcommit+pushで消化する。
# 「やめて」でいつ殺しても損失≤1バッチ。自然停止=展開対象0 / 連続エラー3。判断不要=Sonnet運転前提。
cd "$(dirname "$0")/.." || exit 1
i=1; fails=0
while :; do
  echo "=== $(date '+%m-%d %H:%M') expand-batch $i ==="
  if out=$(python scripts/_tameshiyomi-harvest.py --expand --expand-limit 60 2>&1); then
    fails=0
  else
    fails=$((fails+1))
  fi
  echo "$out" | tail -2
  if echo "$out" | grep -q "展開対象 0 "; then echo "expand queue空→終了"; break; fi
  git add data/seeds/tameshiyomi-booklive-volumes.jsonl 2>/dev/null
  git commit -qm "試し読みexpand: idle $(date '+%m%d-%H%M')" 2>/dev/null && git push -q
  if [ "$fails" -ge 3 ]; then echo "連続エラー3→終了"; break; fi
  i=$((i+1))
done
echo "=== idle-expand 終了 ==="
python scripts/_tameshiyomi-harvest.py --stats
