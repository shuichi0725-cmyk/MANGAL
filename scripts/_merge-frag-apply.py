"""merge-frag-proposal.json(安全43)を series-merge.yml に純粋追加。

- merge_keys が 種2 で解決するもののみ(orphan 排除)、 解決2件以上で採用
- 既存ファイルは text 追記で不変(整形/コメント保持)
- 種2/種3 不変・非デプロイ。 適用は全DB promote 時に効く(現42には無関係)
"""
import sys, json, sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]  # 旧PCパス→動的導出(2026-07-21一括是正)
prop = json.load((ROOT / ".cache/merge-frag-proposal.json").open(encoding="utf-8"))
con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
valid = {k for (k,) in con.execute("SELECT series_key FROM series")}
con.close()

def yq(s):  # YAML 安全な single-quote
    return "'" + str(s).replace("'", "''") + "'"

lines = ["", "# ── frag-merge: 同題+著者完全一致+無副題の版違い統合 (_merge-frag-build.py) ──"]
applied = 0; skipped = 0
for pr in prop:
    keys = [k for k in pr["merge_keys"] if k in valid]
    if len(keys) < 2:
        skipped += 1; continue
    lines.append(f"- main: {yq(pr['main'])}")
    lines.append("  merge_keys:")
    for k in keys:
        lines.append(f"  - {yq(k)}")
    lines.append(f"  note: {yq('frag-merge: 著者完全一致+無副題の版違い ' + str(len(keys)) + 'key')}")
    applied += 1

path = ROOT / "data/seeds/series-merge.yml"
before = path.read_text(encoding="utf-8")
path.write_text(before.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
print(f"★追加 {applied} エントリ / skip(キー未解決){skipped}")
print(f"  series-merge.yml: {len(before.splitlines())} → {len(path.read_text(encoding='utf-8').splitlines())} 行")
