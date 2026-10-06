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

★再投入(2026-10-06): fresh=latest−prev だけだと、初見で頁に入らなかった巻は prev に入って二度と分類されない
  (保留・分類漏れ・予約頁の続巻・月次の種4全消しで消えた巻。実例=カクリキ2/猩猩姫3/呪具師15/4軍くん14)。
  → prev 在でも「まだどこにも載っていない」ISBN は毎回 fresh に戻す(材料が揃った日・頁ができた日に自然に通る)。
  載っている = 本番頁(ISBN索引) / 種2 / 種4(auto・手動・offset) / 予約頁seed / ドラフト(全世代) / ISBN除外簿。
  特装版・限定版は戻さない(続巻でも非掲載=毎日同じ保留を積むだけ)。
  再投入行には _requeue を付け、分類器は「既存頁の続巻(zokkan)」と判定された時だけ適用に回す。
  新作・途中巻に落ちた行は requeue_hold(簿のみ)= 過去に見送った新作を毎回ドラフト化して水増ししない。
  初回試算(2026-10-06 harvest): 再投入695 → 続巻182 / 掲載済94 / requeue_hold 419(新作158+途中巻261)。
★本番頁が在る作品の題は「過去draft題除外」から外す(2026-10-06): 予約頁(preorder-pages)出身の頁は題が除外集合に入るため、
  その続巻(カクリキ2/猩猩姫3)が分類の前に黙って捨てられ、triage にすら載らなかった(予約頁は本流を通らない型の7件目)。
  本番索引に在る題は分類器が続巻(zokkan)に回すので再カウントにはならない。除外は未本番化ドラフトと恒久denyだけに効かせる。

★prev更新(2026-07-10 取りこぼし22件事故の恒久対処):
  python scripts/_preorder-increment.py --commit-prev
  = 「処理完了後」に必ず実行(runbook締めの一部)。preorders-latest-full → preorders-prev を昇格。
  prevは「最後に処理した時点のfull」であり手で触らない。処理せず件数だけ見た日にprevを
  進めると、その日の増加分が永遠にスルーされる(→このコマンド以外でprevを更新するな)。
"""
import sys as _sys_h
if any(_a in ("-h", "--help") for _a in _sys_h.argv[1:]):   # ★--help で本体を走らせない(2026-10-03 apply-zokkan を誤実行し touched を空で上書き)
    print(__doc__ or "(no doc)"); _sys_h.exit(0)
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


# apply-zokkan / classify と同じ特装版判定(続巻でも非掲載=再投入しない)
SPECIAL_ED = re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付|DVD付|Blu-?ray|OAD|アクリル|しおり付|カードセット付|ポストカード|クリアスタンド|キーホルダー|フィギュア付", re.I)
ISBN_RE = re.compile(r"97[89]\d{10}")
ISBN_EXCLUDE_FILES = ["volume-exclude.yml", "volume-exclude-isbn.yml", "art-book-exclude-isbn.yml", "preorder-deny.jsonl",
                      "anthology-drop.tsv", "american-comics-drop.tsv", "distill-drop-2026.tsv", "non-manga-drop.yml",
                      "volumes-supplement-retire-changelog.jsonl"]


def resolved_isbns():
    """「もうどこかに載っている/裁定済み」ISBN集合(再投入しない)。ISBN索引は先に作り直す(10秒)。"""
    import sqlite3, subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_exists.py"), "--build"], cwd=ROOT,
                   capture_output=True, check=True)
    out = set(json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8")))
    db = os.path.join(ROOT, ".cache", "db-v2.sqlite")
    if os.path.exists(db):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out |= {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    seeds = os.path.join(ROOT, "data", "seeds")
    files = [os.path.join(seeds, f) for f in ("volumes-supplement-auto.yml", "volumes-supplement.yml",
                                              "volumes-supplement-offset.yml", *ISBN_EXCLUDE_FILES)]
    files += glob.glob(os.path.join(seeds, "preorder-pages", "*.yml"))
    files += glob.glob(os.path.join(PRE, "drafts*", "*.yml"))
    for p in files:
        if os.path.exists(p):
            out |= set(ISBN_RE.findall(open(p, encoding="utf-8", errors="ignore").read()))
    return out


def live_titles():
    """本番一覧索引に在る作品題(base正規化)。ここに在る題は分類器が続巻に回せる=過去draft除外から外す。"""
    p = os.path.join(ROOT, "data", "manga-list-index.json")
    if not os.path.exists(p):
        return set()
    li = json.load(open(p, encoding="utf-8"))
    ti = li["f"].index("title")
    return {base_of(r[ti]) for r in li["d"] if r[ti]}


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
        # 1b. 再投入: prev 在でも、まだどこにも載っていない ISBN は毎回分類に戻す(上の docstring)
        done = resolved_isbns()
        requeue = [r for r in latest if r.get("isbn") in prev_isbns and r.get("isbn") not in done
                   and not SPECIAL_ED.search(str(r.get("title") or ""))]
        for r in requeue:
            r["_requeue"] = True   # ★分類器は「続巻」と判定された時だけ適用に回す(新作/途中巻はドラフトにしない)
        fresh += requeue
        print(f"  再投入(prev在・未掲載・未裁定): +{len(requeue)} → {len(fresh)}")
    else:
        fresh = latest
        print(f"  ★prev無し=初回扱い: 全 {len(fresh)} 件をfresh(次回からは差分になる)")

    # 2. 過去draft題を除外(★本番頁が在る題は除外しない=続巻として分類器へ通す)
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
    live = live_titles()
    n_live = len(past & live)
    past -= live
    # ★恒久除外簿(2026-07-19 麻雀コンボ理論=戦術書すり抜け対策): 非漫画とdrop裁定済みの題は
    #   preorder-pages seedを消しても再提案しない。1行={"title":..., "reason":...}(title=base正規化前でよい)
    #   ★deny は本番頁が在っても常に効かせる(再編集本が本編と同じ書き出しのことがある)。
    deny_p = os.path.join(ROOT, "data", "seeds", "preorder-deny.jsonl")
    n_deny = 0
    if os.path.exists(deny_p):
        for l in open(deny_p, encoding="utf-8"):
            try:
                past.add(base_of(json.loads(l).get("title", ""))); n_deny += 1
            except Exception:
                pass
    before = len(fresh)
    inc = [r for r in fresh if base_of(r.get("title", "")) not in past]
    print(f"  過去draft題({len(past)}、うち恒久deny {n_deny}・本番頁が在るので除外しない {n_live}) 除外: "
          f"{before} → {len(inc)} (再カウント防止 -{before - len(inc)})")

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
