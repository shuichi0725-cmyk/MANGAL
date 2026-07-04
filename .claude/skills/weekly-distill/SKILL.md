---
name: weekly-distill
description: 週次蒸留=本番フルビルド+R2フルアップ。トリガー「週次蒸留して」。テスト環境で確認済みの変更を本番へ出す唯一の定期ルート
---

# 週次蒸留 (= フルビルド・フルアップ)

トリガー語: **「週次蒸留して」**(完全一致でなくてよい)。
★本番へのアップはこのトリガー(または明示指示)以外で**絶対に自発実行しない**。

## NEVER
- トリガー無しで本番 build/sync しない
- 価格の静的表示を含むUIを出さない(grep で `¥|price` 表示確認)
- `--prune` を安易に付けない(削除は明示判断)
- 完了主張の前に疎通確認を飛ばさない

## 手順

### 1. 事前再生成 (= stale生成物クラスを全部焼き直す)
```
python scripts/_build-calendar.py            # カレンダー(~3分)
python scripts/_gen-corner-stocks.py         # 三世代/featured stock JSON
python scripts/_gen-corner-auto.py           # 周年/豪華版 JSON(66k走査 ~5分)
python scripts/_build-list-index.py data/manga.v2 data   # 本番索引(~10分)
```
- ai-reviews 等 seed 由来はそのまま(生成不要)。
- 生成物を commit+push。

### 2. ステージング鮮度 + git 確認
- `D:\mangal-cache\proddata` は junction(manga/seeds/art-books)=自動追随、**コピー物は手動更新**:
  masters(demographics/genres/magazines/publisher-aliases/publishers/slug-aliases).yml と索引3本(manga-list/search/catch-index.json)を `data/` から cp。
- `git status` を見て **scripts/ の未コミット変更が無いか**確認(promote拡張のcommit漏れ=2026-07-04実害)。

### 3. フルビルド (~2.5h、バックグラウンド+Monitor)
```
$env:MANGAL_DATA_DIR="D:\mangal-cache\proddata"; npx next build 2>&1 | Out-File .cache\weekly-build.log
```
- Monitor は 1万頁節目+「attempt 3 of 3 / Export encountered / Build error」+完了のみ通知(2分毎は通知過多)。
- attempt 1-2 の retry は warmup 通常挙動。
- 完了判定: log 末尾 `✓ Exporting (2/2)` + `out/manga` ファイル数 ≈ 頁数×2。

### 3.5 sitemap生成 (build後・sync前)
```
python scripts/_gen-sitemap.py
```
(out/ に sitemap.xml+分割を書く=syncが拾う。SEO②)

### 4. R2 同期 (差分PUT)
```
python scripts/_r2-sync.py --bucket mangal-site
```
- 起動直後に**生存確認**(python の CPU 時間が伸びているか)。ログ0バイトでもハッシュ照合中は無言(10-25分)が正常。
- スクリプトが .env.local から R2_* 自動読込・**本番索引 overlay(out/ ルートへ)+5MBガード**内蔵。
- レイアウト級の変更(全頁共通部)があった週は全量PUT=正常。

### 5. 疎通確認 (URLを間違えるな)
```
B=https://mangal-db.com
主要頁: / /manga/urusei-yatsura /contact /about → 200
★索引は**ルート直下**: $B/manga-list-index.json → 25MB級/200 (★/data/ ではない! 2026-07-04誤検証の教訓)
コーナーデータ: $B/data/anniversaries.json 等 → 200
API: POST $B/api/contact {"body":"smoke"} → {"ok":true}
価格非表示: 作品頁に ¥ が無い
```

### 6. marker更新 (= 差分反映エンジンの基準点)
```
python -c "import json,subprocess;h=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip();json.dump({'code_commit':h,'data_commit':h,'note':'週次蒸留'},open('.cache/prod-deploy-marker.json','w'),indent=1)"
```
続けて pages-manifest も初期化:
```
python scripts/_init-pages-manifest.py
```
(diff-deploy の検出基準点。marker と対。忘れると差分反映が過剰検出/誤abortする)

### 7. 報告
工程表(ビルド頁数/PUT数/疎通結果)で完了報告。異常は隠さずそのまま。

## 備考
- Defender除外は実施済(2026-07-04)。ビルドが異常に遅い時は `Get-MpPreference | Select ExclusionPath` で除外が生きてるか確認。
- 本番ドメイン mangal-db.com の紐付けは別タスク(未実施)。
- edge cache(HTML s-maxage=86400)により旧頁が最長1日残る。確認は `?v=` クエリでバイパス。
