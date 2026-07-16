---
name: pc-migration-2026-07-17
description: 新PCへ移行完了(fresh clone + D:\migrate 搬入)。移行で欠けるのは pip依存4つ(boto3/reportlab/Pillow)。.cache=C:実体だがD:はDIFFDATAで生きている
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

2026-07-17、**新PCへ移行完了**(= このリポジトリは `github.com/shuichi0725-cmyk/MANGAL` からの fresh clone + pull)。搬入経路 = **`D:\migrate\`**(manga.v2 / data-index / env)。全て適用済みで実データと一致確認済み(manga.v2 68,973件 / 本番索引 22MB+10.5MB がバイト一致 / `.env.local` 11キー全て値あり)。★**`D:\migrate` は用済み**(削除可・未実施)。

## ★次にPCを移る時に効く教訓 = gitに載らないのは「pip依存」

**移行で欠けたのは pip依存だけ**だった(他は git + `D:\migrate` で揃う)。**requirements.txt が無い**ので手で入れ直しが要る:

- **boto3 / botocore** = ★これだけが実害。`_r2-sync.py`(週次蒸留の本番R2アップ)と `_deploy-differential.py`(差分反映)が import で落ちる。**無症状のまま「週次蒸留して」の瞬間に止まる**タイプ。
- reportlab(PDF生成器10本) / Pillow(coverflowモック2本) = パイプライン外の単発ツールのみ。
- ★**`requests` は元々未使用**(全て urllib 運用)。「requestsが無い」は偽陽性なので入れなくてよい。

## 環境の実態(このPC)

- `.cache` は **C: の実体ディレクトリ**(junction ではない)。1,824件。★ただし `_deploy-differential.py` が `DIFFDATA = D:\mangal-cache\diffdata` を**ハードコード参照**しているので **D: は外せない**([[d-drive-external-flaky]] = 認識が外れたら挿し直し待ちのみ、レター探索/変更は絶対しない)。
- `c.bat` / `d.bat` は先頭が `cd /d "%~dp0"` = **自己相対なので移行で書き換え不要**(旧PCの絶対パスは埋まっていない)。`claude` も PATH 解決OK(`~\.local\bin\claude.exe`)。★c.bat のモデルは `fable[1m]`、d.bat は `sonnet`(idle-run前提)= ユーザ裁定で**そのまま**。
- ★**Defender除外は未設定の可能性**(確認に管理者権限が要り未確認)。旧PCでは repo と `D:\mangal-cache` を除外していた。I/Oが遅いと感じたらここを疑う。
- R2認証はこのPCから疎通確認済み(mangal-site 読取OK / 134,066オブジェクト / 100%が単一part=ETagはMD5)。
- git push権限OK。記憶ミラー `.claude-memory` 154 = ローカル154で同期済み。

移行で壊れたものは無い。唯一の破損 [[r2-manifest-corrupt-pending-repair]] は移行前(7/11)から壊れていた。
