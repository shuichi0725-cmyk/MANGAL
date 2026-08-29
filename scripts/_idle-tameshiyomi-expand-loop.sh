#!/bin/bash
# 試し読みexpandのアイドル運転ループ。
#
# ★2026-08-29 全面改訂 (BookLive規制事故の是正)
#   事故: 2026-08-28に入れた「尾の自動再訪」が最終配信巻より上の404を毎回未チェック扱いに
#   戻すため、同じシリーズを永久に叩き直す無限ループになった。8並列GETで止まらず走り続け、
#   60シリーズに **231万リクエスト**(名探偵コナン単独38万回)。命中率は途中から0%のままで、
#   得られた新リンクは0件。結果 BookLive に規制された。
#
#   以後このループが守ること:
#     ① 停止札 (.cache/tameshiyomi/BLOCKED) が在る間は**起動しない**
#     ② 1バッチ = 少数シリーズ。バッチ間は BATCH_SLEEP 秒あける
#     ③ 収穫ゼロが ZERO_STOP 回続いたら停止 (無限ループの最終防波堤)
#     ④ 本体が exit 2 (=200/404以外の応答を検知) を返したら **即停止して停止札を置く**
#     ⑤ 1日の実行バッチ数を MAX_BATCH で頭打ちにする
#   レート(直列2秒/件・1実行1500件上限)は本体 scripts/_tameshiyomi-harvest.py 側の規約。
cd "$(dirname "$0")/.." || exit 1

BLOCK_FLAG=".cache/tameshiyomi/BLOCKED"
# ★git追跡側の札(別PC・別セッションにも効かせる。.cacheはgitignoreで同期しないため)
BLOCK_FLAG_REPO="docs/production-diagnostics/BOOKLIVE-BLOCKED.md"
BATCH_SLEEP=${BATCH_SLEEP:-300}     # バッチ間の休み(秒)
ZERO_STOP=${ZERO_STOP:-3}           # 収穫ゼロが続いたら止める回数
MAX_BATCH=${MAX_BATCH:-12}          # 1回の起動で回す最大バッチ数
EXPAND_LIMIT=${EXPAND_LIMIT:-10}    # 1バッチのシリーズ数

for f in "$BLOCK_FLAG_REPO" "$BLOCK_FLAG"; do
  [ -f "$f" ] || continue
  echo "停止札あり($f) = BookLive規制中。起動しない。"
  echo "--- 札の中身 ---"; cat "$f"
  echo "解除はユーザ裁定で: rm $BLOCK_FLAG_REPO .cache/tameshiyomi/BLOCKED"
  exit 1
done

i=1; zero=0; fails=0
while [ "$i" -le "$MAX_BATCH" ]; do
  echo "=== $(date '+%m-%d %H:%M') expand-batch $i/$MAX_BATCH ==="
  out=$(python scripts/_tameshiyomi-harvest.py --expand --expand-limit "$EXPAND_LIMIT" 2>&1)
  rc=$?
  echo "$out" | tail -3
  if [ "$rc" -eq 2 ]; then
    { echo "at: $(date '+%Y-%m-%d %H:%M')"
      echo "reason: 本体が200/404以外の応答を検知して中断(exit 2)"
      echo "$out" | tail -5
    } | tee "$BLOCK_FLAG" > "$BLOCK_FLAG_REPO"
    echo "★BookLiveから異常応答 → 停止札を置いて終了。ユーザに報告すること。"
    exit 2
  fi
  if [ "$rc" -ne 0 ]; then
    fails=$((fails+1))
    [ "$fails" -ge 3 ] && { echo "連続エラー3 → 終了"; break; }
  else
    fails=0
  fi

  if echo "$out" | grep -q "展開対象 0 "; then echo "expand queue空 → 終了"; break; fi

  # ★収穫ゼロの連続で止める(無限ループの最終防波堤)
  if echo "$out" | grep -qE "展開完了 \+0巻|展開中断 \+0巻"; then
    zero=$((zero+1))
    echo "  (収穫0 が $zero/$ZERO_STOP 回)"
    [ "$zero" -ge "$ZERO_STOP" ] && { echo "収穫ゼロが $ZERO_STOP 回続いた → 終了"; break; }
  else
    zero=0
  fi

  git add data/seeds/tameshiyomi-booklive-volumes.jsonl.gz 2>/dev/null
  git commit -qm "試し読みexpand: idle $(date '+%m%d-%H%M')" -- data/seeds/tameshiyomi-booklive-volumes.jsonl.gz 2>/dev/null && git push -q  # ★pathspec限定=他セッションのstage巻き込み防止(2026-07-19実害)

  i=$((i+1))
  [ "$i" -le "$MAX_BATCH" ] && sleep "$BATCH_SLEEP"
done
echo "=== idle-expand 終了 ==="
python scripts/_tameshiyomi-harvest.py --stats
