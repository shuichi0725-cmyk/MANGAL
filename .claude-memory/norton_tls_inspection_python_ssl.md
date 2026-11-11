---
name: norton-tls-inspection-python-ssl
description: Nortonが通信を検査して証明書を差し替える=同梱の証明書束しか見ないPythonライブラリ(boto3等)だけがSSLエラーで全滅する。urllibは通る。対処はNortonの根証明書を束に足す(検証は切らない)
metadata:
  node_type: memory
  type: project
  originSessionId: 007afa68-9e4d-4f99-a558-b1e8f21d0bbb
  modified: 2026-11-11T00:50:41.031Z
---

このPCは **Norton が HTTPS 通信を検査して証明書を差し替えている**(発行者 = `Norton Web/Mail Shield Root`)。
2026-11-11 に R2 接続で初めて踏んだ(11/7 の週次は通っていた = その後に検査対象になった)。

## 症状と見分け方
- `SSL: CERTIFICATE_VERIFY_FAILED (unable to get local issuer certificate)`。
- ★**落ちるのは「同梱の証明書束しか見ない」ライブラリだけ** = boto3(botocore の cacert.pem)、requests/certifi 系。
  **urllib(標準)は Windows の証明書ストアを見るので通る** = `_cf-analytics.py` や curl は正常。
  → 「同じPCで片方だけSSLエラー」ならこれを疑う。
- サンドボックスのせいではない(外しても同じ)。
- 7/17 の「NDLだけSSL失敗」([[pc_migration_2026_07_17]])は中間証明書の未キャッシュで**別原因**。
  見分け = `ssl.create_default_context()` で繋いで発行者を見る。Norton の名が出ればこちら。

## 対処
- Norton は自分の根証明書の場所を環境変数 **`NODE_EXTRA_CA_CERTS`**(`C:\ProgramData\Norton\Antivirus\wscert.pem`)に入れている。
- R2 用は **`_r2_manifest.ensure_ca_bundle()`** に実装済(同梱の束 + Norton の根 → `.cache/r2-ca-bundle.pem` → `AWS_CA_BUNDLE`)。
  `_r2-sync.py` / `_deploy-differential.py` / `_deploy-feature.py` の3本が boto3 を作る前に呼ぶ。
- ★**検証を切る(verify=False)方向には倒さない**。OS が既に信用している証明書を足すだけ。
- 新しく boto3 / requests を使う道具を書く時は同じ関数を呼ぶ(requests は `REQUESTS_CA_BUNDLE` に同じ束を渡せば通るはずだが未検証)。

**How to apply:** Python の外部接続が突然 SSL エラーになったら、まず発行者を確認。Norton なら束に足す。
