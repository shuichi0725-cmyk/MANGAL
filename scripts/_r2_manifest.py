"""R2 同期 manifest(.cache/r2-manifest.json)の読み込み。 [[hosting_worker_r2_architecture]]

manifest = {R2キー: ローカルファイルの sha256} = 「前回同期した時点で本番R2に何が在るか」の記録。
_r2-sync.py(差分PUT判定)と _deploy-differential.py(本番稼働頁の判定)が共有する。

★2026-07-17: 中身がバイナリ化した破損を実地で踏んだ(サイズもmtimeも書込時刻のまま=ディスク層の破損)。
  素の json.load は UnicodeDecodeError で落ちるので、読み込みを1本に集約して status を返す。
  破損は「全キー欠損」と等価に扱い、補完は _r2-sync.py 側(R2 の ETag=MD5 照合)が受け持つ。
"""
import json
import os
import time


def ensure_ca_bundle():
    """boto3 を作る前に呼ぶ。 セキュリティソフトの通信検査の証明書を boto3 に信用させる。

    ★2026-11-11 実踏: Norton が R2 への通信を検査して証明書を差し替えるようになり、boto3 だけが
      `SSL: CERTIFICATE_VERIFY_FAILED (unable to get local issuer certificate)` で全滅した。
      urllib は Windows の証明書ストアを見るので通るが、boto3 は同梱の cacert.pem しか見ない。
      Norton は自分の根証明書の場所を NODE_EXTRA_CA_CERTS に入れているので、それを同梱の束に
      足した束を .cache に作り AWS_CA_BUNDLE で渡す(= 検証は切らない。OS が既に信用している証明書を足すだけ)。
    該当しない環境(変数なし/ファイルなし/既に AWS_CA_BUNDLE 指定あり)では何もしない。
    返り値 = 使う束のパス or None。
    """
    if os.environ.get("AWS_CA_BUNDLE"):
        return os.environ["AWS_CA_BUNDLE"]
    extra = os.environ.get("NODE_EXTRA_CA_CERTS", "")
    if not extra or not os.path.isfile(extra):
        return None
    try:
        import botocore
        base = os.path.join(os.path.dirname(botocore.__file__), "cacert.pem")
        with open(base, encoding="utf-8") as f:
            pem = f.read()
        with open(extra, encoding="utf-8", errors="replace") as f:
            pem += "\n" + f.read()
        d = os.path.join(os.getcwd(), ".cache")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, "r2-ca-bundle.pem")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(pem)
        os.environ["AWS_CA_BUNDLE"] = out
        print(f"  証明書の束: 同梱 + {extra} → AWS_CA_BUNDLE (通信検査ソフト対策)")
        return out
    except Exception as e:   # 束が作れなくても同期自体は試す(従来どおりの挙動)
        print(f"  ※証明書の束を作れず: {type(e).__name__}: {str(e)[:100]}")
        return None


def load(path, quarantine=True):
    """(manifest, status) を返す。 status = "ok" | "missing" | "corrupt"。

    corrupt = 読めない or dict でない。 quarantine=True なら破損ファイルを
    r2-manifest-bad-<ts>.json へ退避してから {} を返す(= 可逆。原因調査用に消さない)。
    """
    if not os.path.exists(path):
        return {}, "missing"
    try:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        if not isinstance(m, dict):
            raise ValueError(f"dict でない ({type(m).__name__})")
        return m, "ok"
    except Exception as e:
        print(f"★manifest が読めない: {type(e).__name__}: {str(e)[:100]}")
        if quarantine:
            bad = os.path.join(os.path.dirname(path),
                               f"r2-manifest-bad-{time.strftime('%Y%m%d-%H%M%S')}.json")
            os.replace(path, bad)
            print(f"  → {bad} へ退避(可逆)。全キーを欠損扱いにして続行。")
        return {}, "corrupt"
