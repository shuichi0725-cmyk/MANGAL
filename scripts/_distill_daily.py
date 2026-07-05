#!/usr/bin/env python3
"""日次蒸留 = 前回以降のNDL新着だけ取得→掲載ゲート→出せる物は出し、足りない物は欠落表で報告。

後退蒸留(_distill_backward.py)と同一コアの薄いカーソル運転:
  1. --discover : 当月(+月初3日は前月も)のNDL discovery を live 取得(1.2s・resumable)。
                  ★429/throttle検知時は abort して報告(連打しない)。
  2. --plan     : 年planを再実行(冪等) → 前回カーソルとの差分 = 「今日の新着」を報告。
  3. --emit     : 後退蒸留と共通(AI worksheet記入後)。
カーソル = data/seeds/distill-cursor.json (git追跡=消えない)。
掲載ゲート = 必須メタ完備 + 楽天書影v1 (ユーザ裁定 2026-07-02)。不足=欠落表。fail-closed。

usage: python _distill_daily.py --discover   # NDL live(数分)
       python _distill_daily.py --plan       # オフライン差分報告
"""
import json, os, re, subprocess, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURSOR = os.path.join(ROOT, "data", "seeds", "distill-cursor.json")
STAGE = next((a for a in sys.argv[1:] if a.startswith("--")), "--plan")
PY = sys.executable

today = datetime.date.today()
YEAR = str(today.year)

def load_cursor():
    if os.path.exists(CURSOR):
        return json.load(open(CURSOR, encoding="utf-8"))
    return {"last_run": None, "seen_publishable": [], "seen_lacking": []}

def save_cursor(c):
    json.dump(c, open(CURSOR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def run(cmd):
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")

if STAGE == "--discover":
    # ★取得窓=「前回実行から」(2026-07-06 ユーザ指摘で当月固定→動的化)。
    #   前回実行月の前月〜当月を取る(前月余分=NDL遅延収載対策)。間隔が空いても取りこぼさない。
    c0 = load_cursor()
    last = c0.get("last_run") or ""
    start_m = today.month
    if last[:4] == str(today.year):
        start_m = max(1, int(last[5:7]) - 1)
    elif last and last[:4] < str(today.year):
        print(f"★前回={last}が年跨ぎ → 当年1月からに丸め(昨年分の穴は「後退蒸留して {last[:4]}」で回収を推奨)")
        start_m = 1
    else:
        start_m = max(1, today.month - 1)  # カーソル無し初回も前月から
    months = list(range(start_m, today.month + 1))
    print(f"取得窓: 前回({last or '初回'})以降 = {today.year}年 {months[0]}〜{months[-1]}月")
    if len(months) > 6:
        print(f"★窓が{len(months)}ヶ月=間隔が空きすぎ。NDL負荷に注意(1.2s厳守で続行)")
    for m in months:
        r = run([PY, "scripts/_ndl-discovery.py", YEAR, str(m), str(m)])
        out = (r.stdout or "") + (r.stderr or "")
        print(out[-1200:])
        if "429" in out or "Too Many" in out:
            print("★NDL throttle検知 → 中断(連打しない)。時間を置いて再実行。")
            sys.exit(2)
    print("discover完了 → --plan へ")

elif STAGE == "--plan":
    r = run([PY, "scripts/_distill_backward.py", YEAR, "--plan"])
    print((r.stdout or "")[-800:])
    # 差分 = 前回カーソルとの比較
    workdir = os.path.join(ROOT, ".cache", "backward", YEAR)
    pub = json.load(open(os.path.join(workdir, "publishable.json"), encoding="utf-8"))
    lack_path = os.path.join(ROOT, "docs", "production-diagnostics", f"backward-{YEAR}-lacking.tsv")
    lacks = [l.split("\t")[0] for l in open(lack_path, encoding="utf-8").read().splitlines()[1:]]
    c = load_cursor()
    seen_p = set(c.get("seen_publishable") or [])
    seen_l = set(c.get("seen_lacking") or [])
    new_p = [x for x in pub if x["key"] not in seen_p]
    new_l = [t for t in lacks if t not in seen_l]
    print(f"\n=== 日次蒸留レポート ({today}) ===")
    print(f"新規で掲載可になった作品: {len(new_p)}")
    for x in new_p[:15]:
        print(f"  「{x['title'][:24]}」 {'/'.join(x['creators'][:2])[:16]} {len(x['vols'])}巻")
    print(f"新規の欠落(情報不足): {len(new_l)}")
    for t in new_l[:15]:
        print(f"  {t[:32]}")
    print(f"(累計: 掲載可worksheet待ち {len(pub)} / 欠落 {len(lacks)})")
    c["last_run"] = str(today)
    c["seen_publishable"] = sorted({x["key"] for x in pub} | seen_p)
    c["seen_lacking"] = sorted(set(lacks) | seen_l)
    save_cursor(c)
    print(f"カーソル更新 → {CURSOR}")
    if new_p:
        print("→ 掲載するには: worksheet(.cache/backward/%s/ai-todo.jsonl)記入 → _distill_backward.py %s --emit" % (YEAR, YEAR))
else:
    print(__doc__)
