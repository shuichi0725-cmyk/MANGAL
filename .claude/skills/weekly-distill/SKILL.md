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

### 2. ★preflight (= 2026-07-10 script化。手動チェックリスト全廃)
```
python scripts/_weekly-preflight.py --fix     # FAILが1つでもあればビルド開始禁止(exit 1)
```
- 内蔵: コード未コミット検査(2026-07-04実害)/timeout=300/D:空き20GB+/out・.next junction再作成(★実体dirは絶対に自動削除しない=中身有りは手動退避を指示)/staging junction+masters6+索引3本の同期/生成物鮮度WARN。
- 下の「ディスク事前確認」の手動PowerShellはpreflightが代替(復旧手順のみ手動参照)。

### 3. フルビルド (★実測2.5〜3.5h、バックグラウンド+Monitor)
★**preflight全通過(exit 0)を確認してから開始**(C:満杯だと終盤のexportコピーがENOSPC死する)。
```
$env:MANGAL_DATA_DIR="D:\mangal-cache\proddata"; npx next build 2>&1 | Out-File .cache\weekly-build.log
```
- ★`staticPageGenerationTimeout=300s`(next.config.ts)前提。既定60sだと重頁(home-design=66k全読込)がワーカー競合で3回超過しビルドkill(2026-07-05 home-design-05で発覚・是正済)。
- Monitor は 1万頁節目+「after 3 attempts / Export encountered / Build error」+完了のみ通知(2分毎は通知過多)。
- attempt 1-2 の retry は **コールドワーカーの初回66k読込(warmup)**=正常。300s猶予で温まればリトライ成功。
- 終盤(6万頁以降)は重頁が残り生成速度が落ちる=正常。完了判定: log 末尾 `✓ Exporting (2/2)` + `out/manga` ファイル数 ≈ 頁数×2(≈132k)。
- ★完了後の**居座りnodeをStop-Process**(Windows恒例。file lock解除)。

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

### 5+6. ★finalize (= 2026-07-10 script化。疎通→marker→manifestをゲート連鎖で1本化)
```
python scripts/_weekly-finalize.py
```
- 内蔵順序: ①ビルド完了判定(log『✓ Exporting』+out/manga≥120k枚) → ②sitemap存在 → ③疎通確認(`_prod-smoke.py`=主要頁200/索引ルート直下+5MBガード/¥非含有/contact POST) → ④marker更新 → ⑤`_init-pages-manifest.py`。
- ★**①〜③のどれかがFAILならmarkerを書かずabort**(=diff-deployは前回基準のまま安全側)。手動one-liner写経は廃止。
- 疎通だけ単独で回す時: `python scripts/_prod-smoke.py`(検証練習は `--no-post`)。URL正解はscriptに焼き込み済(索引は**ルート直下**=/data/ではない。2026-07-04誤検証の教訓)。

### 7. 報告
工程表(ビルド頁数/PUT数/疎通結果)で完了報告。異常は隠さずそのまま。

## ★成功判定 (= 完了主張の前にこの数字を全部言えること)
- preflight exit 0 / out/manga ≈ **132k files**(≥120kがfinalize下限) / R2 PUT数(全量=レイアウト週・少数=データ週)
- smoke **PASS 10/10**(FAIL 0) / 索引 **25MB級**(5MB未満=preview索引化事故)
- marker `note=週次蒸留` + pages-manifest 初期化ログ
- どれかが言えない=完了していない(finalizeがexit 0を返すまで完了報告禁止)


## ★ディスク事前確認 (= 2026-07-10より `_weekly-preflight.py --fix` が自動実施。以下は仕組みの説明+ENOSPC復旧手順)
★**out/と.nextは常にD:へジャンクションしてからビルド**(C:は満杯気味・D:に455GB空き)。`out/+.next`で計10-15GB要る。
手動でやる場合(PowerShell):
```
Get-PSDrive C,D | Select Name,@{n='Free_GB';e={[math]::Round($_.Free/1GB,1)}}   # 確認
cmd /c rmdir "C:\Users\shuic\code\MANGAL\out" "C:\Users\shuic\code\MANGAL\.next" 2>$null
New-Item -ItemType Directory -Force "D:\mangal-cache\weekly-out","D:\mangal-cache\next-build" | Out-Null
cmd /c mklink /J "C:\Users\shuic\code\MANGAL\out" "D:\mangal-cache\weekly-out"
cmd /c mklink /J "C:\Users\shuic\code\MANGAL\.next" "D:\mangal-cache\next-build"
```
- junction中は `next build` がout/を消す時リンクを触るので、**毎ビルド前にrmdir→mklinkし直す**のが安全。
- ★ENOSPC復旧(万一C:直ビルドで途中失敗した時): outをD:へ`robocopy SRC DST /E /MOVE`退避→`cmd /c rmdir`でjunction作成→`.next/server/app`の`.html`/`.rsc`を out へ手コピー(.rsc→.txt改名・既存skip)で**2h再ビルド回避**できる(2026-07-05実証)。junction除去は`cmd /c rmdir`(Remove-Itemは中身を追ってD:保護に弾かれる)。

## 備考
- ★カレンダーは索引と同型の二重化(2026-07-06): public/calendar=preview実在フィルタ版なので、_r2-sync.pyが **data/calendar(本番フル)で自動overlay**する。Step1の再生成はフル/preview両方を回すこと(daily-distill Dと同じコマンド)。
- Defender除外は実施済(2026-07-04)。ビルドが異常に遅い時は `Get-MpPreference | Select ExclusionPath` で除外が生きてるか確認。
- 本番ドメイン mangal-db.com = 紐付け済(2026-07-10 疎通200確認。smokeの既定BASE)。
- edge cache(HTML s-maxage=86400)により旧頁が最長1日残る。確認は `?v=` クエリでバイパス。

## ★ビルド環境の罠(2026-07-12 実害3連発→恒久対処済み。消すな)
- **D:\node_modules junction 必須**: `.next`をD:へjunctionすると、ビルド成果物からの`require('react')`が
  node_modulesに届かず`Cannot find module 'react/jsx-runtime'`で死ぬ。対処= `cmd /c mklink /J D:\node_modules C:\Users\shuic\code\MANGAL\node_modules`
  (作成済み。消えていたら再作成)。next-build内に旧ビルド残骸があると同エラー→`rm -rf D:/mangal-cache/next-build/*`
- **buildは必ずStart-Processでデタッチ起動**: ツールのrun_in_backgroundは~10分で親ごとkillされworker巻き添え死。
  `Start-Process powershell -ArgumentList "-NoProfile","-File","D:\mangal-cache\_wkbuild.ps1" -WindowStyle Hidden`
- **r2-syncも同様にscript file経由でデタッチ**(`D:\mangal-cache\_r2sync.ps1`作成済み)。PSの`|Out-File`パイプ直渡しは空ログ即死する
