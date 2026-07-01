---
name: phase2-corrupted-keys
description: phase2-todo.json に長く残った 3 件の PUA 文字混入 key (= 「いずみタッチダウン!」 「キャンディキャンディ」 「Dj vu」) を batch 188 で Python 経由 raw 書き出しで個別 fill 完了 (= todo 0 件達成、 2026-05-27 JST)
metadata: 
  node_type: memory
  type: project
  originSessionId: 6146d01a-d071-41e5-9ffa-4568e252bbb1
---

**解決済 (= batch 188 で個別 fill 完了、 2026-05-27 JST)。** 過去 phase2 batch loop で skip され続けた 3 件:

1. `qid:Q11642002|name:いずみタッチダウン!` → `イズミ タッチダウン`
2. `qid:Q2731432|name:キャンディキャンディ` → `キャンディ キャンディ`
3. `qid:Q6359803|name:Dj vu` → `デジャ ヴュ` (= 藤原カムイのサスペンス短編、 Déjà vu)

**原因:** todo.json 内 key に **PUA (Private Use Area) 文字混入**:
- `` (= 「・」 区切り の PUA 化、 「タッチ・ダウン」 「キャンディ・キャンディ」 で発生)
- ``, `` (= 「Dj vu」 = 「Déjà vu」 の é が PUA 化)

普通に raw JSON を書き出すと PUA 文字が UTF-8 で再現できず matching 失敗 → `[warn] key not in todo: qid:Q...|name:�����݃^�b�`�_�E��!` が出て skip される。

**解決方法 (= 再利用 protocol):**
```python
import json
with open('data/seeds/_fills/phase2-todo.json', 'r', encoding='utf-8') as f:
    todo = json.load(f)
raw = {entry['key']: 'カタカナ読み' for entry in todo if entry['qid'] in target_qids}
with open('.cache/phase2-batch-NNN-raw.json', 'w', encoding='utf-8') as f:
    json.dump(raw, f, ensure_ascii=False, indent=2)
```
= Python から **todo.json の key を そのまま再利用** すれば PUA 文字含む生キーが保存される。

**why 残った:** session 2 では batch 113-187 まで普通の raw 書き出しで skip 継続。 最後 batch 188 で Python 個別書き出しで一発解決。

**learn:** 将来の phase で 似た PUA 文字 問題が出たら、 **最初から Python 経由 raw 書き出し** が確実。

関連: [[phase2-fill-workflow]]
