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
