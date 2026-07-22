---
name: weekly-distill
description: 週次蒸留=本番フルビルド+R2フルアップ。トリガー「週次蒸留して」。テスト環境で確認済みの変更を本番へ出す唯一の定期ルート
---

# 週次蒸留 (= フルビルド・フルアップ)

トリガー語: **「週次蒸留して」のみ**。
★★このトリガー以外で**絶対に発動しない**(2026-07-21 ユーザ厳命)。「本番化して」「本番に出して」等の
類語・文脈解釈での代行起動は禁止。週次蒸留が必要な場面なら「『週次蒸留して』の発話が必要」と案内して待つ。
(旧「または明示指示」の抜け穴で 本番化して をGO解釈→誤発動した実害への恒久対策)

## NEVER
- 「週次蒸留して」以外のトリガーで発動しない(類語解釈禁止・上記)
- 価格の静的表示を含むUIを出さない(grep で `¥|price` 表示確認)
- `--prune` を安易に付けない(削除は明示判断)
- 完了主張の前に疎通確認を飛ばさない

## 手順

### 1. 事前再生成 (= stale生成物クラスを全部焼き直す)
```
python scripts/_build-calendar.py data/manga.v2 data/calendar <当月YYYY-MM>   # ★本番フル(r2-syncがこれをoverlay)
python scripts/_build-calendar.py .preview-data/manga public/calendar <当月>  # preview版(src=preview自身)
# ★引数なし実行は禁止(2026-07-13実害): 既定out=public/calendarにフル版が書かれ、本番overlay元のdata/calendarは古いまま
#   =本番カレンダーが前週のまま stale。しかも生成器は古い月ファイルを消さないので、srcを替える時は out を rm -rf してから。
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
★**preflight全通過(exit 0)を確認してから開始**。
★**2026-07-17 C:完結に全面改訂(ユーザ裁定)**: ジャンクション全廃・staging=`.cache/proddata`(実体コピー)・
out/.next=C:実体。**D:はバックアップ倉庫のみでビルド経路に入れない**(外付けD:はストールしやすく、
junction経由だとC:側の操作まで巻き込まれる=2026-07-17実害。旧D:構成は旧PCのC:満杯が理由で新PCでは無意味)。
```
$env:MANGAL_DATA_DIR="C:\Users\chiba shuichi\code\MANGAL\.cache\proddata"; npx next build 2>&1 | Out-File .cache\weekly-build.log
```
- ★`staticPageGenerationTimeout=300s`(next.config.ts)前提。既定60sだと重頁(home-design=66k全読込)がワーカー競合で3回超過しビルドkill(2026-07-05 home-design-05で発覚・是正済)。
- Monitor は 1万頁節目+「after 3 attempts / Export encountered / Build error」+完了のみ通知(2分毎は通知過多)。
- attempt 1-2 の retry は **コールドワーカーの初回66k読込(warmup)**=正常。300s猶予で温まればリトライ成功。
- 終盤(6万頁以降)は重頁が残り生成速度が落ちる=正常。完了判定: log 末尾 `✓ Exporting (2/2)` + `out/manga` ファイル数 ≈ 頁数×2(≈132k)。
  ★**`✓ Exporting (2/2)` 単独では完了扱いしない**(2026-07-17実害: その直後に
  `build worker exited with code: 4294967295` でexport copy workerが即死し、生成は全完了なのに
  out/がスケルトン11MBのままだった)。**必ず out/manga 枚数を数えてから** node kill に進む。
  ★**枚数は安定するまで再カウント**(2026-07-22実測: Exporting(2/2)直後の列挙が 9,103→77,047→135,124枚と
  1分弱伸び続けた=巨大ディレクトリの列挙ラグ+書込flush待ち。1回目の過小値でexport copy死と誤判定しない。
  10-20秒間隔で数え、2回連続同値になってから完了/死の判定をする)。
- ★export copy死の復旧(=再ビルド不要・2026-07-05手順の一般化・07-17に67,920頁で実証102秒):
  `.next/server/app` を walk し `*.html→out/<rel>.html` / `*.rsc→out/<rel>.txt`(`.meta`と`_not-found`はskip・既存skip)。
  静的chunk(out/_next)とpublic系はexport序盤で搬出済みのことが多い=検証は du で。
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
- ★**同期後にJSONのedge cache purge必須**(2026-07-13実害): workerのASSET系は `s-maxage=604800`=**エッジ7日**。
  purgeしないと calendar/*.json・data/*-stock.json 等が最長1週間前のまま配信される(ユーザ画面が更新されない)。
  purge = worker `/api/purge`(R2_PURGE_TOKEN認証、_deploy-differential.py step6 と同機構)。最低限
  `/calendar/manifest.json`+`/calendar/release/*.json`(当月〜3ヶ月+beyond)+`/data/*.json` を対象に。
  ★**ルート索引5本も必須**(2026-07-22追記: ASSET=エッジ7日。忘れると検索改善・新頁が最長1週間出ない):
  `/manga-list-index.json` `/manga-list-head.json` `/manga-search-index.json` `/manga-catch-index.json` `/manga-alt-index.json`

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


## ★ディスク方針 (= 2026-07-17 C:完結に改訂。旧D:ジャンクション運用は全廃)
- preflightがC:空き30GB+を検査(out/.next 10-15GB+staging ~3GB)。新PCはC:850GB級空きで余裕。
- **ジャンクションは作らない**(残骸junctionがD:を指しているとD:ストール時にC:側の操作まで固まる=2026-07-17実害)。
- ★D:の役割=**バックアップ倉庫のみ**(stub-manga保険ミラー等)。ビルド・staging・一時ファイルは全てC:。
- ENOSPC復旧(参考・C:が万一逼迫した時): `.next/server/app`の`.html`/`.rsc`を out へ手コピー(.rsc→.txt改名・既存skip)で再ビルド回避可(2026-07-05実証)。

## 備考
- ★カレンダーは索引と同型の二重化(2026-07-06): public/calendar=preview実在フィルタ版なので、_r2-sync.pyが **data/calendar(本番フル)で自動overlay**する。Step1の再生成はフル/preview両方を回すこと(daily-distill Dと同じコマンド)。
- Defender除外は実施済(2026-07-04)。ビルドが異常に遅い時は `Get-MpPreference | Select ExclusionPath` で除外が生きてるか確認。
- 本番ドメイン mangal-db.com = 紐付け済(2026-07-10 疎通200確認。smokeの既定BASE)。
- edge cache(HTML s-maxage=86400)により旧頁が最長1日残る。確認は `?v=` クエリでバイパス。

## ★ビルド環境の罠(2026-07-12 実害3連発→2026-07-17 C:完結化で一部陳腐化。現行版)
- ~~D:\node_modules junction~~ = **C:完結化で不要になった**(.next/outがC:実体になったためrequire解決は普通に届く)。
- **buildは必ずStart-Processでデタッチ起動**: ツールのrun_in_backgroundは~10分で親ごとkillされworker巻き添え死。
  ★**-Fileのパスは引用符を引数の内側に埋め込む**(2026-07-22実害: ArgumentListは空白joinされるため
  「chiba shuichi」の空白で `-File 'C:\Users\chiba'` に分断→無音起動失敗。症状=ログ0バイト+node無し):
  `Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','"C:\Users\chiba shuichi\code\MANGAL\.cache\_wkbuild.ps1"' -WindowStyle Hidden`
- **r2-syncも同様にscript file経由でデタッチ**(`.cache\_r2sync.ps1`・同じ引用符埋め込み起動)。PSの`|Out-File`パイプ直渡しは空ログ即死する
- ★**デタッチしたpythonの生死はMSYSのpsでなく`tasklist`で判定**(2026-07-22実害: 隠しウィンドウ起動の
  プロセスをMSYSのpsが間欠的に見失い「終了」と誤検知×2回。`tasklist //FI "IMAGENAME eq python.exe"`
  +10秒後の2段確認が確実。ログ無言でもpythonのCPU時間が伸びていれば稼働中=ハッシュ照合フェーズ)
- ps1 2本は `.cache/` 置き(C:)。中身のパスはこのPCの絶対パス=PC移行時は書き直す。
