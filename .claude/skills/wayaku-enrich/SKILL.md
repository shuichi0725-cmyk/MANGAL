# 和訳エンリッチ (= AniList英語descの日本語あらすじ化。トリガー語「和訳エンリッチして」)

synopsis-ja.json([[synopsis_ja_seed]] = git追跡seed・高価なAI生成物)への**純粋追加**パイプライン。
月次のAniListフルダンプ更新後に回すと、新しく英語descが付いた作品の和訳が増える。

## ★事実(2026-08-24 実測。「9千件バックログ」の正体)
- 未訳カウント(enrich aid − 既訳)の**大半は素材ゼロ**: 実測9,158中、desc無/短すぎ8,808+注記のみ222。
- **和訳可能なのは desc有りの残りだけ**(初回128件=2batch)。素材ゼロは捏造しない=対象外
  ([[feedback_accuracy_is_the_goal]])。つまりこの柱は「巨大バックログ」でなく**月次の小さなdelta仕事**。

## 手順(1セッションで完結が普通。多い月はbatch分割)
```
1. python scripts/_syn-todo-batches.py            # 未訳delta抽出 → .cache/syn-batches-v2/batch-NNN.json(100件/batch)
2. AIが各batchを読み、{anilist_id: 日本語あらすじ} を .cache/syn-out-v2/batch-NNN.json に書く(下の規律)
3. python scripts/_syn-merge-out.py .cache/syn-batches-v2 .cache/syn-out-v2 .cache/syn-merged.json
4. python scripts/_apply-synopsis.py .cache/syn-merged.json    # 純粋追加。「上書きスキップ」警告=既訳保護が効いた証拠
5. git add data/seeds/synopsis-ja.json && commit && push       # seed永続化(本番反映は次のフルpromote/週次)
```
- ★カーソル= syn-out-v2 に出力済みのbatchはskip(中断→再開可能)。書き出しは**Pythonスクリプト経由**
  (Write直書きはPUA文字が消える [[phase2_fill_workflow]]と同じ理由)。
- 報告= batchごとに「batch NNN: N件和訳 [JST]」。完了時に applied/skip/総数。

## 和訳の規律(NEVER)
- **60-120字の要約・言い換え**(逐語訳禁止=著作権配慮)。キャラ名/舞台/フックを1-2文で。
- **ネタバレ禁止**(結末・最終巻の展開を書かない)。
- **成人作(isAdult)**: 露骨な性描写は書かない/中立化して同じseedに入れる(表示はadult_us/geoで出し分け)。
- **素材ゼロは書かない**: descが実質空/注記のみ(Note: Includes...)は出力に含めない(抽出器+merge器の
  二重濾過があるが、AI自身も「巻数とジャンルから定型文を発明」しない)。
- **既訳の上書き禁止**(_apply-synopsisが警告+スキップする。--forceは使わない)。

## 関連
- 楽天caption由来のキャッチ/あらすじ生成=**別柱**(skill enrich-catch-synopsis・トリガー「エンリッチして」)。
  こちらはAniList英語desc由来。混同しない。
- 月次蒸留skillの手順5(enrich)の後段としても呼べる。
