# -*- coding: utf-8 -*-
"""seed健全性lint (2026-08-26 新設。種4-auto全消し/2スペsilent不着/YAML崩れの汎用番人)。

検査(FAILが1つでも exit 1):
  1. parse: data/seeds/ の *.yml(巨大種3含む)/*.json/*.jsonl が全部読めるか
  2. 台帳ファイルのentry数が git HEAD より**減っていない**か(純粋追加台帳=減少は全消し/silent不着の症状。
     正当な退役は --allow-shrink <file名,...> で明示して通す)
  3. 巻台帳(volumes-supplement*)の必須フィールド: isbn13(13桁)/number(int>=0)/series_keys非空

使い所: _reflect-targeted.py の検証ゲート / intake.py の先頭stage(結線済み)。
  python scripts/_check-seeds.py
  python scripts/_check-seeds.py --allow-shrink volumes-supplement-auto.yml
"""
import argparse
import glob
import gzip
import io
import json
import os
import re
import subprocess
import sys

import yaml

try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDS = os.path.join(ROOT, "data", "seeds")

# 台帳(純粋追加)ファイル: (相対名, entry数の取り方)
LEDGERS = {
    "volumes-supplement.yml": lambda d: len((d or {}).get("volumes") or []),
    "volumes-supplement-auto.yml": lambda d: len((d or {}).get("volumes") or []),
    "volume-exclude.yml": lambda d: len((d or {}).get("excludes") or []),
    "non-manga-drop.yml": lambda d: len((d or {}).get("non_manga") or []),
    "page-dedup.yml": lambda d: len((d or {}).get("dedup") or []),
}
SKIP_PARSE_OVER_MB = 64  # これ超は存在チェックのみ(covers.jsonl.gz等はgzで別扱い)


def _load_yml(text):
    return yaml.load(io.StringIO(text), Loader=_L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-shrink", default="", help="減少を許すファイル名(カンマ区切り・basename)")
    a = ap.parse_args()
    allow = {s.strip() for s in a.allow_shrink.split(",") if s.strip()}
    fails = []

    # 1. parse全数
    n_ok = 0
    for p in sorted(glob.glob(os.path.join(SEEDS, "*"))):
        base = os.path.basename(p)
        if os.path.isdir(p):
            continue
        mb = os.path.getsize(p) / 1048576
        try:
            if base.endswith(".yml") or base.endswith(".yaml"):
                if mb > SKIP_PARSE_OVER_MB:
                    continue
                _load_yml(io.open(p, encoding="utf-8").read())
            elif base.endswith(".json"):
                json.load(io.open(p, encoding="utf-8"))
            elif base.endswith(".jsonl"):
                # 家内jsonlは先頭に#コメント行を持つものがある(pending-r2-prune等)=許容
                for i, ln in enumerate(io.open(p, encoding="utf-8")):
                    if ln.strip() and not ln.lstrip().startswith("#"):
                        json.loads(ln)
            elif base.endswith(".jsonl.gz"):
                continue  # 巨大バイナリ台帳は対象外(promoteが実利用で検証)
            else:
                continue
            n_ok += 1
        except Exception as e:
            fails.append(f"parse死: {base}: {str(e)[:120]}")

    # 2. 台帳のentry数 vs git HEAD (減少=FAIL)
    for base, counter in LEDGERS.items():
        p = os.path.join(SEEDS, base)
        if not os.path.exists(p):
            continue
        try:
            cur = counter(_load_yml(io.open(p, encoding="utf-8").read()))
        except Exception:
            continue  # parse死は1で報告済み
        r = subprocess.run(["git", "show", f"HEAD:data/seeds/{base}"],
                           capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
        if r.returncode != 0:
            print(f"  INFO {base}: HEADに無い(新規) cur={cur}")
            continue
        try:
            prev = counter(_load_yml(r.stdout))
        except Exception:
            continue
        if cur < prev and base not in allow:
            fails.append(f"台帳減少: {base} {prev} → {cur} (純粋追加台帳=全消し/silent不着の症状。"
                         f"正当な退役なら --allow-shrink {base})")
        else:
            print(f"  OK   {base}: {prev} → {cur}")

    # 3. 巻台帳の必須フィールド
    for base in ("volumes-supplement.yml", "volumes-supplement-auto.yml"):
        p = os.path.join(SEEDS, base)
        if not os.path.exists(p):
            continue
        try:
            vols = (_load_yml(io.open(p, encoding="utf-8").read()) or {}).get("volumes") or []
        except Exception:
            continue
        bad = []
        for i, v in enumerate(vols):
            if not isinstance(v, dict):
                bad.append(f"#{i}: dictでない(2スペ不着型?)")
                continue
            ib = re.sub(r"[^0-9X]", "", str(v.get("isbn13") or "").upper())
            if len(ib) != 13:
                bad.append(f"#{i} {str(v.get('title_display'))[:20]}: isbn13不正={v.get('isbn13')!r}")
            n = v.get("number")
            if not (isinstance(n, int) and n >= 0):
                bad.append(f"#{i}: number不正={n!r}")
            if not v.get("series_keys"):
                bad.append(f"#{i}: series_keys空")
        if bad:
            fails.append(f"{base} フィールド不正 {len(bad)}件: " + " / ".join(bad[:5]))
        else:
            print(f"  OK   {base}: フィールド検査 {len(vols)}巻")

    # 4. ★slug-overrides.yml の**死に形**検出(2026-09-05 新設)。
    #    promote の _slug_override は `doc["overrides"]` 配下の **入れ子dict(slugキー付き)しか読まない**。
    #    トップレベルの平坦形 `old: new` と、overrides配下でも値がstrのものは **永久に効かない**。
    #    書いた人は直したつもりでいるので silent。実測 2026-09-05: 平坦形143件のうち116件が
    #    旧slugのまま公開され続けていた(ティールーム=teiiruumu をユーザに指摘されて発覚)。
    _sop = os.path.join(SEEDS, "slug-overrides.yml")
    if os.path.exists(_sop):
        try:
            _doc = _load_yml(io.open(_sop, encoding="utf-8").read()) or {}
            _dead = [k for k, v in _doc.items() if k != "overrides" and isinstance(v, str)]
            _dead += ["overrides/" + k for k, v in (_doc.get("overrides") or {}).items()
                      if not (isinstance(v, dict) and v.get("slug"))]
            if _dead:
                # ★2026-09-05 に既存142件を移行済み(残0)。以後は**新たに死に形を書いたら止める**。
                #   移行しなかった既裁定は not_applied: に退避してある(dict値なのでここには掛からない)。
                fails.append("slug-overrides.yml 死に形 %d件(promoteが読まない形式=書いても効かない。"
                             "overrides: 配下に {slug:, reason:, at:} で書く): %s"
                             % (len(_dead), ", ".join(_dead[:5])))
            else:
                print("  OK   slug-overrides.yml: 死に形なし")
        except Exception as _e:
            fails.append("slug-overrides.yml 検査失敗: %s" % _e)

    print(f"\nseed lint: parse OK {n_ok} / FAIL {len(fails)}")
    for f in fails:
        print(f"  FAIL {f}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
