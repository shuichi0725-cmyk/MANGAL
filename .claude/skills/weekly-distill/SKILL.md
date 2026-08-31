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
- ★**R2同期の失敗時に考えずに再実行しない**(2026-08-26実害: 一時エラー1件→全量18万PUTを3回=Class A超過$4.50。
  現行scriptは個別リトライ+ETag実物照合で再走もほぼ0 PUTだが、原則=失敗の構造を見てから動く)
- ★**R2予算(Class A 1M/月・27日〆)**: preflightのcheck 11とsyncの「予算予告」行を必ず読む。
  全頁週(UI共通部の変更)=約19万。**5週入る期に全頁週×5=95万で肉薄**=超過見込みが出たら
  UI変更を1週見送る(=差分週化)か、$4.50を許容するかをユーザに聞く。簿記=data/seeds/r2-ops-ledger.jsonl(全PUT経路配線済)
- 価格の静的表示を含むUIを出さない(grep で `¥|price` 表示確認)
- `--prune` を安易に付けない(削除は明示判断)
- 完了主張の前に疎通確認を飛ばさない

## 手順

### 1. 事前再生成 (= stale生成物クラスを全部焼き直す。★2026-08-26 ラッパ化)
```
python scripts/_weekly-step1.py        # 生成器14step順次(失敗で即exit 1。--from <step>で再開・--listで計画)
```
- ★**生成器リストの正本は `scripts/_weekly-step1.py` の STEPS**。新しい生成器はそこへ足す
  (旧=skillの散文リストに人手追記→追記漏れ=恒久stale化、の構造を廃止)。
- 内容: calendar本番/preview(当月自動・引数なし事故根絶) → cover-release-refresh --days 45
  (touched非空→promote自動連鎖) → shinkan → corner-stocks → daily-feature → corner-auto →
  tameshiyomi(harvest/expand/map/LN検査) → anilist-status-map → placeholder --build-queue →
  本番索引(最後)。~1時間(書影refresh ~40分含む)。
- ai-reviews 等 seed 由来はそのまま(生成不要)。
- ★**art-books昇格**(2026-07-29新設・ユーザ発見「.v2に居るのに公開されない」INTRON DEPOT型):
  ビルドが読むのは `data/art-books`(公開側)で、promoteの再生成は `data/art-books.v2`(中間物)に出る=
  **昇格コピーが無いと新規画集は永遠に出ない**。週次前に diff を確認し、検証(kana非空・yaml parse)して
  `.v2 → data/art-books` へコピー。掲載可否に迷う新規はユーザ裁定を仰いでから。
- 生成物を commit+push。

### 2. ★preflight (= 2026-07-10 script化。手動チェックリスト全廃)
```
python scripts/_weekly-preflight.py --fix     # FAILが1つでもあればビルド開始禁止(exit 1)
```
- 内蔵: コード未コミット検査(2026-07-04実害)/timeout=300/D:空き20GB+/out・.next junction再作成(★実体dirは絶対に自動削除しない=中身有りは手動退避を指示)/staging junction+masters6+索引3本の同期/生成物鮮度WARN。
- ★ISBN消失FAIL(理由なしN件)の標準対応(2026-08-31確立): 1件ずつ調べる前に**機械帰属**=
  snapshot日以降の `git log -p -- data/seeds/` の -行ISBN net集合と突合(大半が裁定済み作業の正当削除)。
  残りは `git log -S <isbn>`。全件コミットに紐付いたら `data/seeds/isbn-loss-acknowledged.jsonl` へ
  根拠コミット付きで記帳(監査が読む・純簿記)→preflight再実行。紐付かない分だけが真の事故候補。
- 下の「ディスク事前確認」の手動PowerShellはpreflightが代替(復旧手順のみ手動参照)。

### 2.5 ★モード判定 (= ハイブリッド週次 2026-08-27 ユーザ裁定。R2費用と3hビルドの節約)
```
python scripts/_weekly-mode.py    # exit 0=DATA / 1=SURFACE / 2=CODE (根拠ファイルと次コマンドを表示)
```
- **DATA週**(コード変更なし): 手順3〜6の代わりに**差分ルート**(数分・数千ops):
  `_deploy-differential.py --weekly-json`(変更頁の部分ビルド+索引+calendar/shinkan/data/idxのJSON面PUT+prune+purge)
  → `_kv-redirects-sync.py` → `_weekly-finalize.py --data-week`(疎通+prune実証+snapshot)。
  ★制約: トップ等の**面HTMLは先週のまま**(サーバ埋込の統計数値が1週古い。コーナーはclient fetchなので中身は新しい)。
- **SURFACE週**(非漫画面コードのみ): DATA週手順+ `_deploy-feature.py`(機能蒸留)を1)と2)の間に。
- **CODE週**(app/manga・layout・components・lib等): 従来どおり手順3〜6のフルビルド。
- 判定の正=script(CODE_SCOPEはdiff-deployと同一定義)。迷ったらCODE週(フル)に倒す。

### 3. フルビルド (★CODE週のみ。実測2.5〜3.5h、バックグラウンド+Monitor)
★**preflight全通過(exit 0)を確認してから開始**。
★**2026-07-17 C:完結に全面改訂(ユーザ裁定)**: ジャンクション全廃・staging=`.cache/proddata`(実体コピー)・
out/.next=C:実体。**D:はバックアップ倉庫のみでビルド経路に入れない**(外付けD:はストールしやすく、
junction経由だとC:側の操作まで巻き込まれる=2026-07-17実害。旧D:構成は旧PCのC:満杯が理由で新PCでは無意味)。
```
$env:MANGAL_DATA_DIR="C:\Users\chiba shuichi\code\MANGAL\.cache\proddata"
$env:NODE_OPTIONS="--max-old-space-size=12288"     # ★必須(2026-07-27〜)
npx next build 2>&1 | Out-File .cache\weekly-build.log
```
- ★**`NODE_OPTIONS=--max-old-space-size=12288` は必須**(2026-07-27 実害)。 既定のV8ヒープ上限=**約4GB**を
  コンパイル段階で超え、**開始95秒**で `FATAL ERROR: Ineffective mark-compacts near heap limit` →
  `build worker exited with code: 134` で即死した(頁生成に入る前なのでログは3KBしか出ない=原因が見えにくい)。
  ★このとき `out/manga` には **前週ビルドの残骸13.5万枚**が残っているので、枚数だけ見ると成功に見える。
  **必ずログの `FATAL ERROR`/`code: 134` を確認する**こと。 搭載31GBに対し12GB指定で通過(ワーカー実測6.5GB)。
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

### 4. R2 同期 (差分PUT + ★不要頁の削除)
```
python scripts/_r2-sync.py --bucket mangal-site --prune
```
- ★**KV同期(_kv-redirects-sync.py)は r2-sync 成功時に自動連鎖**(2026-08-26機械化。旧=手動2コマンド
  で忘れると「pruneで頁を消したのに301が付いてこない=404の窓」)。自動連鎖が失敗すると exit 4 で
  名指しされるので単独再実行。抑止は `--no-kv`。Worker側は6h TTLで自動再読込。
- 疎通確認(_prod-smoke.py)に **301追跡テスト**が入っており(alias 1件を実プローブ)、KV陳腐化はそこでも鳴る。
- ★**workers/r2-serve.js を変更した週は Worker も deploy**(R2同期はファイルだけ=Workerコードは別デプロイ):
```
npx wrangler deploy -c wrangler-r2.jsonc
```
- ★検索回帰は vitest に内蔵(lib/clientSearch.test.ts=イース型tier/数字表記揺れ/複数語AND)。緑でなければ出さない
- ★**`--prune` 必須**(2026-07-26 追加)。 これが無いと **非掲載にした頁が本番で200のまま残る**。
  prune 無し運用の結果、孤児HTMLが **1,041頁** 溜まっていた([[r2_orphan_pages_prune_missing]])。
  フィルムコミック等をdropしても、prune しない限りユーザには消えて見えない。
- 安全弁は script 内蔵で、**消さない方向に倒す**:
  ①`--prune-floor 0.9` = out/ の manga頁数が前回の90%未満なら**削除中止**(build途中失敗の全消し防止)
  ②`--prune-max 3000` = 削除候補がこれを超えたら**削除中止**して報告のみ
  ③削除キーは実行前に `.cache/r2-pruned-<日時>.txt` へ必ず記録
- 中止された時は一覧を確認し、意図した削除なら `--prune --prune-max <件数+100>` で再実行。
- ★★**ISBN消失snapshot / prune待ち台帳の突合は finalize が自動実行**(2026-08-26 機械化):
  finalize が ①台帳の各slugを本番へ実プローブ(200=prune未実施→**abort** / 404・301=消滅→**行を自動消し込み**)
  ②smoke全PASS後に `_audit-isbn-loss.py --snapshot` で基準取り直し、まで面倒を見る。手動突合・手動snapshotは廃止。
- ★**初回(2026-07-26以降の最初の週次)は約2,100キー削除**の見込み(孤児1,041頁×html+txt)= 正常。
- 起動直後に**生存確認**(python の CPU 時間が伸びているか)。ログ0バイトでもハッシュ照合中は無言(10-25分)が正常。
- スクリプトが .env.local から R2_* 自動読込・**本番索引 overlay(out/ ルートへ)+5MBガード**内蔵。
- レイアウト級の変更(全頁共通部)があった週は全量PUT=正常。
- ★**JSONのedge cache purge(索引4本+data/*.json+calendar/*.json)は finalize が自動実行**
  (2026-08-26 機械化。旧=手でworker /api/purgeを叩く前提で忘れると最長1週間前のまま配信)。

### 5+6. ★finalize (= 2026-07-10 script化+2026-08-26 締め残務を全部内蔵)
```
python scripts/_weekly-finalize.py
```
- 内蔵順序: ①ビルド完了判定(log『✓ Exporting』+out/manga≥120k枚) → ②sitemap存在 → ③疎通確認(`_prod-smoke.py`=主要頁200/索引ルート直下+5MBガード/¥非含有/**301追跡**/contact POST) → ③.5 **prune実証+台帳自動消し込み**(pending slugが本番200なら**abort**=prune忘れ検出) → ③.7 **edge purge自動実行**(索引4本+data+calendar) → ④marker更新 → ⑤`_init-pages-manifest.py` → ⑥ **isbn-loss --snapshot**。
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
