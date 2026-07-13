#!/bin/bash
# アイドル運転の試し読み無限ループ(2026-07-14): バッチごとcommit+push=「やめて」でいつ殺しても損失≤1バッチ
# 自然停止: 対象枯れ / 連続エラー3
cd "$(dirname "$0")/.." || exit 1
i=1; fails=0
while :; do
  echo "=== $(date '+%m-%d %H:%M') idle-batch $i ==="
  if out=$(python scripts/_tameshiyomi-harvest.py --limit 100 2>&1); then
    fails=0
  else
    fails=$((fails+1))
  fi
  echo "$out" | tail -2
  if echo "$out" | grep -q "^対象 0 作"; then echo "queue空→終了"; break; fi
  git add data/seeds/tameshiyomi-booklive.jsonl docs/production-diagnostics/tameshiyomi-holds.tsv 2>/dev/null
  git commit -qm "試し読みharvest: idle $(date '+%m%d-%H%M')" 2>/dev/null && git push -q
  if [ $((i % 3)) -eq 0 ]; then
    python scripts/_tameshiyomi-harvest.py --expand --expand-limit 60 | tail -1
    git add data/seeds/tameshiyomi-booklive-volumes.jsonl 2>/dev/null
    git commit -qm "試し読みharvest: idle-expand $(date '+%m%d-%H%M')" 2>/dev/null && git push -q
  fi
  if [ "$fails" -ge 3 ]; then echo "連続エラー3→終了"; break; fi
  i=$((i+1))
done
echo "=== idle-tameshiyomi 終了 ==="
python scripts/_tameshiyomi-harvest.py --stats
