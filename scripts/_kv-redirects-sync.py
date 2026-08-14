"""alias 301 の全件map を本番KV(REDIRECTS)へ投入する。週次蒸留 手順4(R2同期)の後に実行。

処理: ①_gen-redirects.py 再実行(.cache/redirects.json 再生成) ②検証(形状/件数)
     ③wrangler kv key put(認証=OAuth `wrangler login` 済み前提)
本番Worker(workers/r2-serve.js)は KV `REDIRECTS` の key `redirects.json` を読む。
Worker側は isolate 内 6h TTL キャッシュ=投入後は最長6hで全エッジに行き渡る
(Workerを deploy した週は新isolate起動で即反映)。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / ".cache" / "redirects.json"


def main() -> None:
    # ① 再生成(slug-aliases.yml が正本。stale JSON を投入しないため毎回焼き直す)
    r = subprocess.run([sys.executable, "scripts/_gen-redirects.py"], cwd=ROOT)
    if r.returncode != 0:
        sys.exit("abort: _gen-redirects.py 失敗")

    # ② 検証: 全キー/宛先が /manga/ 形状・空でない
    m = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    bad = [k for k, v in m.items() if not (k.startswith("/manga/") and v.startswith("/manga/"))]
    if not m or bad:
        sys.exit(f"abort: redirects.json 異常 (件数={len(m)}, 非/manga/形状={len(bad)}: {bad[:5]})")

    # ③ KV投入(--remote=本番。バインディングは wrangler-r2.jsonc の REDIRECTS)
    cmd = ("npx wrangler kv key put redirects.json "
           f"--path \"{JSON_PATH}\" --binding REDIRECTS --remote -c wrangler-r2.jsonc")
    r = subprocess.run(cmd, cwd=ROOT, shell=True)
    if r.returncode != 0:
        sys.exit("abort: wrangler kv put 失敗(`npx wrangler whoami` でOAuth確認)")
    print(f"KV投入完了: redirects.json {len(m)} 件(REDIRECTS)")


if __name__ == "__main__":
    main()
