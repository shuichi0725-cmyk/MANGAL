#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日次蒸留A0: 楽天予約harvestを「増加分だけ」に絞る(2026-07-09 必須ゲート)。

harvest(_rakuten-preorder-harvest.py)の直後・classify(_preorder-classify.py)の直前に必ず走らせる。
これを飛ばすと、fullharvest(未来窓全量)を丸ごと「新規」扱いして昨日以前のbacklogを水増しする(実害2934件)。

2段フィルタ:
  1. fresh = preorders-latest − preorders-prev (ISBN差分。前回harvestに無い=今回の新規)。
  2. 過去draft除外 = .cache/preorders/drafts* と data/seeds/preorder-pages/ の題(base正規化)集合と突合。
     前回previewドラフト化したが未promoteの作品は、後続巻の新ISBNでfreshになっても除外(再カウント防止)。

出力: preorders-latest.jsonl を増加分だけに上書き(fullは preorders-latest-full.jsonl に退避)。
     以後 classify はこの増加分のみを処理する。件数ログを出す。

★prev更新(2026-07-10 取りこぼし22件事故の恒久対処):
  python scripts/_preorder-increment.py --commit-prev
  = 「処理完了後」に必ず実行(runbook締めの一部)。preorders-latest-full → preorders-prev を昇格。
  prevは「最後に処理した時点のfull」であり手で触らない。処理せず件数だけ見た日にprevを
  進めると、その日の増加分が永遠にスルーされる(→このコマンド以外でprevを更新するな)。
"""
import json, os, sys, re, glob, shutil, hashlib

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRE = os.path.join(ROOT, ".cache", "preorders")
LATEST = os.path.join(PRE, "preorders-latest.jsonl")
PREV = os.path.join(PRE, "preorders-prev.jsonl")
FULL = os.path.join(PRE, "preorders-latest-full.jsonl")
STATE = os.path.join(PRE, "increment-state.json")


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def commit_prev():
    """処理完了後にのみ呼ぶ: full → prev 昇格。次回incrementはこの時点との差分になる。"""
    if not os.path.exists(FULL):
        sys.exit("preorders-latest-full.jsonl が無い(=incrementを走らせていない)。commit-prev不可。")
    n = sum(1 for l in open(FULL, encoding="utf-8") if l.strip())
    if os.path.exists(PREV):
        shutil.copy(PREV, PREV + ".bak")
        p = sum(1 for l in open(PREV, encoding="utf-8") if l.strip())
    else:
        p = 0
    shutil.copy(FULL, PREV)
    if os.path.exists(STATE):
        os.remove(STATE)
    print(f"→ prev更新: {p} → {n} 件(=今回処理したharvest全量)。次回の増加分はこの時点との差分。")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    from _preorder_title_lib import split_title
except Exception:
    split_title = None


def norm(s):
    return re.sub(r"[\s　・！!？?〜~（）\(\)【】\[\]、。,\.\-ー：:@]", "", str(s or "")).lower()


def base_of(title):
    if split_title:
        try:
            return norm(split_title(title)["base"])
        except Exception:
            pass
    return norm(title)


def main():
    if "--commit-prev" in sys.argv:
        commit_prev()
        return
    if not os.path.exists(LATEST):
        sys.exit("preorders-latest.jsonl が無い。先に _rakuten-preorder-harvest.py を実行。")
    # ★二重実行ガード: LATESTが既にincrementの出力(絞り済み)なら、それをfullと誤認して
    #   FULL/prevを汚さないよう中断(再実行するなら先にharvestを回す)。
    if os.path.exists(STATE):
        try:
            if json.load(open(STATE)).get("shrunk_sha1") == _sha1(LATEST):
                sys.exit("preorders-latest.jsonl は既に増加分に絞り済み(incrementの出力)。再実行するなら先に harvest を回す。")
        except SystemExit:
            raise
        except Exception:
            pass
    latest = [json.loads(l) for l in open(LATEST, encoding="utf-8") if l.strip()]

    # 1. fresh = latest - prev (ISBN)
    if os.path.exists(PREV):
        prev_isbns = set()
        for l in open(PREV, encoding="utf-8"):
            try:
                prev_isbns.add(json.loads(l).get("isbn"))
            except Exception:
                pass
        fresh = [r for r in latest if r.get("isbn") not in prev_isbns]
        print(f"  fresh(latest−prev): {len(fresh)} / latest {len(latest)} (prev {len(prev_isbns)})")
    else:
        fresh = latest
        print(f"  ★prev無し=初回扱い: 全 {len(fresh)} 件をfresh(次回からは差分になる)")

    # 2. 過去draft題を除外
    past = set()
    for d in glob.glob(os.path.join(PRE, "drafts*")):
        for p in glob.glob(os.path.join(d, "*.yml")):
            try:
                import yaml
                past.add(base_of(yaml.safe_load(open(p, encoding="utf-8")).get("title", "")))
            except Exception:
                pass
    ppdir = os.path.join(ROOT, "data", "seeds", "preorder-pages")
    for p in glob.glob(os.path.join(ppdir, "*.yml")):
        try:
            import yaml
            past.add(base_of(yaml.safe_load(open(p, encoding="utf-8")).get("title", "")))
        except Exception:
            pass
    before = len(fresh)
    inc = [r for r in fresh if base_of(r.get("title", "")) not in past]
    print(f"  過去draft題({len(past)}) 除外: {before} → {len(inc)} (再カウント防止 -{before - len(inc)})")

    # 上書き(fullは退避)。★毎回上書き(旧: 存在時skip=staleなfullが残り --commit-prev が古いprevを作る穴)
    shutil.copy(LATEST, FULL)
    with open(LATEST, "w", encoding="utf-8") as f:
        for r in inc:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({"shrunk_sha1": _sha1(LATEST)}, open(STATE, "w"))
    print(f"→ preorders-latest.jsonl を増加分 {len(inc)} 件に上書き(full={os.path.basename(FULL)})。以後classifyは増加分のみ処理。")
    print("  ★処理(classify→生成→push)が終わったら必ず: python scripts/_preorder-increment.py --commit-prev")


if __name__ == "__main__":
    main()
