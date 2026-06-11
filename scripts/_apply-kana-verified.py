# -*- coding: utf-8 -*-
"""著者kana完埋め: AI高確信(high 1,281) + Web裏取り(confirmed/corrected)を
data/seeds/author-yomi.yml に純粋追加する。

- 既存キーは絶対に触らない(overwrites=0 を機械確認)
- 団体(kana空)・role文字列混入名はskip
- unresolved は data/seeds/author-yomi-unresolved.json に保留リスト化
- .new に書いて parse 検証 → 置換
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
YML = ROOT / "data" / "seeds" / "author-yomi.yml"
FILL = ROOT / ".cache" / "kana-fill-results.json"
VERIFY1 = ROOT / ".cache" / "kana-verify-results-1.json"
VERIFY_OUT_DIR = ROOT / ".cache" / "kana-verify-out"
UNRESOLVED_OUT = ROOT / "data" / "seeds" / "author-yomi-unresolved.json"

ROLE_TOKENS = ("原作者", "漫画家", "作画者", "イラストレーター", "編集部", "編著")

# 全角カタカナ + 長音 + 中点 + 空白 + 英数字(既存ファイルに前例あり)
KANA_OK = re.compile(r"^[ァ-ヶーヴ・　 0-9A-Za-z()]+$")


def load_existing():
    with open(YML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["yomi"]


def yaml_line(key, value):
    """既存スタイル(  key: value)で1行生成。plain scalarで往復しない場合はJSON引用。"""
    for k in (key, json.dumps(key, ensure_ascii=False)):
        for v in (value, json.dumps(value, ensure_ascii=False)):
            line = f"  {k}: {v}"
            try:
                parsed = yaml.safe_load(line.strip().replace(f"{k}:", f"{k}:", 1))
            except yaml.YAMLError:
                continue
            try:
                parsed = yaml.safe_load("x:\n" + line)["x"]
            except yaml.YAMLError:
                continue
            if isinstance(parsed, dict) and parsed.get(key) == value:
                return line
    raise ValueError(f"cannot serialize: {key!r}: {value!r}")


def main():
    existing = load_existing()
    print(f"existing keys: {len(existing)}")

    candidates = {}  # name -> (kana, origin)
    conflicts = []
    skipped_role = []
    flagged_kana = []

    def add(name, kana, origin):
        name = name.strip()
        kana = kana.strip()
        if not name or not kana:
            return
        if any(t in name for t in ROLE_TOKENS):
            skipped_role.append(name)
            return
        if not KANA_OK.match(kana):
            flagged_kana.append((name, kana, origin))
            return
        if name in candidates and candidates[name][0] != kana:
            conflicts.append((name, candidates[name], (kana, origin)))
            return
        candidates[name] = (kana, origin)

    # 1) AI高確信
    with open(FILL, encoding="utf-8") as f:
        fills = json.load(f)
    fill_by_name = {e["name"]: e for e in fills}
    high = [e for e in fills if e.get("confidence") == "high" and e.get("kana")]
    for e in high:
        add(e["name"], e["kana"], "ai-high")
    print(f"ai-high candidates: {len(high)}")

    # 2) Web裏取り (batch1-14 + batch15-30)
    verified = []
    with open(VERIFY1, encoding="utf-8") as f:
        verified.extend(json.load(f))
    for p in sorted(VERIFY_OUT_DIR.glob("batch-*.json")):
        with open(p, encoding="utf-8") as f:
            verified.extend(json.load(f)["results"])
    print(f"web-verified records: {len(verified)}")

    unresolved = []
    for r in verified:
        if r["verdict"] in ("confirmed", "corrected") and r.get("kana"):
            add(r["name"], r["kana"], f"web-{r['verdict']}")
        else:
            fe = fill_by_name.get(r["name"], {})
            unresolved.append({
                "name": r["name"],
                "ai_kana": fe.get("kana", ""),
                "note": fe.get("note", ""),
                "verify_source": r.get("source", ""),
            })

    # 3) 既存キーとの突合(純粋追加 = 既存はskip、上書きゼロ)
    new_entries = {n: kv for n, kv in candidates.items() if n not in existing}
    skipped_existing = len(candidates) - len(new_entries)

    print(f"candidates: {len(candidates)} / new: {len(new_entries)} / "
          f"already-in-yml(skip): {skipped_existing}")
    print(f"skipped role-contaminated: {len(skipped_role)} {skipped_role[:10]}")
    print(f"flagged bad-kana: {len(flagged_kana)}")
    for n, k, o in flagged_kana[:20]:
        print(f"  FLAG {n!r}: {k!r} ({o})")
    print(f"conflicts: {len(conflicts)}")
    for c in conflicts[:20]:
        print(f"  CONFLICT {c}")
    print(f"unresolved: {len(unresolved)}")

    if "--apply" not in sys.argv:
        print("(dry-run。--apply で書込)")
        return

    # 4) 末尾に純粋追加 → .new 検証 → 置換
    original = YML.read_text(encoding="utf-8")
    lines = [yaml_line(n, k) for n, (k, _) in sorted(new_entries.items())]
    new_text = original.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
    new_path = YML.with_suffix(".yml.new")
    new_path.write_text(new_text, encoding="utf-8")

    reloaded = yaml.safe_load(new_path.read_text(encoding="utf-8"))["yomi"]
    overwrites = sum(1 for k, v in existing.items() if reloaded.get(k) != v)
    missing = sum(1 for k in existing if k not in reloaded)
    added = len(reloaded) - len(existing)
    print(f"applied={added}, missing={missing}, overwrites={overwrites}")
    if overwrites or missing or added != len(new_entries):
        print("ABORT: 検証不一致。.new を残して停止")
        sys.exit(1)
    new_path.replace(YML)
    print(f"OK: {YML.name} -> {len(reloaded)} keys")

    with open(UNRESOLVED_OUT, "w", encoding="utf-8") as f:
        json.dump(unresolved, f, ensure_ascii=False, indent=1)
    print(f"unresolved list -> {UNRESOLVED_OUT.name} ({len(unresolved)})")


if __name__ == "__main__":
    main()
