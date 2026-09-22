---
name: build-routes-need-node-options
description: 【型・封鎖済】next build を起こす経路は3つ。NODE_OPTIONS=--max-old-space-size=12288 が無い経路は code:134 でOOM死する
metadata:
  type: project
---

V8の既定ヒープ(~4GB)ではMANGALのコンパイル段が落ちる。症状 = `Next.js build worker exited with code: 134`
(ログが数KBしか出ないので原因が見えにくい)。**12288MB 指定で通る**(搭載31GB・ワーカー実測6.5GB)。

**build を起こす経路は3つある。新しい経路を足したら必ず入れる**:
1. 週次蒸留 … `.cache/_wkbuild.ps1` の `$env:NODE_OPTIONS`
2. 機能蒸留 … `scripts/_deploy-feature.py`(`benv.setdefault`)
3. 差分反映 … `scripts/_deploy-differential.py` ← ★**ここだけ抜けていた**(2026-09-22 実踏で是正)

1と2に在って3に無い、という形だったので **grep で3経路を突き合わせる**のが早い:
`grep -n "NODE_OPTIONS\|max-old-space" scripts/_deploy-*.py .cache/_wkbuild.ps1`
