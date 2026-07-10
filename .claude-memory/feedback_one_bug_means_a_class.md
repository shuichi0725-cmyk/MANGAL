---
name: feedback-one-bug-means-a-class
description: 【方針】1件のバグ=型の代表と疑う。署名化→全DB掃引→検出器script化→月次サニティ登録、まで一続きの作業
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7b577e00-f57a-4227-841a-32fbd1f45c6c
---

ユーザ確認済みの働き方(2026-07-10)。「あなたは同型を探してくれるが他のAIには無理か?」への答えとして明文化。

**Why:** 本DBの欠陥は単発でなくパイプライン起因の系統(サスケ型年版誤分解17頁/坊っちゃん型ヨミ取り違え/互い違い版分裂3頁/FF型seed未登録復活…全て1件の指摘から型で回収)。1件直しで止まると同型が生き残り、ユーザが1個ずつ見つける羽目になる。

**How to apply:**
1. per-case修正が終わったら「これは型か?」を必ず自問。型なら**機械検出できる署名**に落とす(偽陽性を殺す条件込み: 例「版が巻を互い違いに持ち合い合体で連続」)
2. 全DB掃引(66k走査は監査目的なら可)→ヒットを**全件目視**してから適用(機械判定の盲信禁止=ミナミの帝王/金瓶梅誤投入の実害2回)
3. 署名は使い捨てず **検出器script化**(`scripts/_audit-*.py`)+ CLAUDE.md月次サニティ節へ登録=以後どのモデルでも回せる道具になる
4. 掃引・revertの経緯はchangelogに教訓ごと記帳

先例: _audit-kana-from-other-volume.py(坊っちゃん型) / サスケ型年版スイープ / 互い違い版分裂スイープ / 著者名ヨミ化け(典拠カンマ型)76件。[[feedback-accuracy-is-the-goal]] [[feedback-dont-repeat-regrouping-error]]
