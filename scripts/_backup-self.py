"""Claude(この PC で MANGAL を回している私)を、 C: が壊れても戻せるように D: へ週1回写す(2026-11-07 ユーザ「復元できるようにしたいのはあなただ」)。

  python scripts/_backup-self.py run       # 写す(枠 A/B を交互に上書き = 2週分残る)
  python scripts/_backup-self.py status    # 最後に写せた日時(8日より古い/失敗なら ★)
  python scripts/_backup-self.py install   # タスクスケジューラに週1回(日曜 4:00)を登録

写すもの(= 私の一式。 私の指示で落とし直せる物は写さない = ユーザ裁定):
  ~/.claude(記憶・会話履歴・skill・設定。 ★ログイン鍵 .credentials.json と一時物は除く)/ ~/.claude.json / ~/.gitconfig
  リポジトリ(git に無い頁データ manga.v2・SRC・.env 類・起動bat・.cache の作り直せない物=種2 db-v2.sqlite・台帳・有料で集めた材料)
  入れ直し用の控え(pip freeze・node / python / Claude Code の版)
写さないもの: .git(GitHub)・node_modules・.next/out(ビルド物)・MADB/Wikipedia/楽天/AniList のダウンロード物・*.bak 退避
置き場: D:\\claude-backup(★D: 全体が共有なので、 このフォルダだけ継承を切り 私・SYSTEM・Administrators に絞る = share1 からは開けない)
戻し方: docs/restore-claude.md(写し先にも README-restore.md として置く)
"""
import datetime, json, os, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
DEST = r"D:\claude-backup"
STATUS = os.path.join(ROOT, ".cache", "backup-status.json")      # C: 側の控え(D: が外れていても読める)
STALE_DAYS = 8

HOME_CLAUDE_XD = ["cache", "telemetry", "shell-snapshots", "session-env", "uploads", "statsig", "ide", "todos"]
HOME_CLAUDE_XF = [".credentials.json"]                           # ★ログイン鍵は写さない(戻した後に claude で入り直す)
REPO_XD_NAMES = [".git", "node_modules", ".next", "out", "__pycache__", "*.bak", "*.bak-*", "*-bak-*", "next-bak*", "out-bak*"]
CACHE_XD = ["jawiki-dump", "madb", "madb-extra", "madb-distill", "madb-1219", "weekly-out", "proddata", "featdata", "appdata",
            "diffdata", "wiki-sweep", "magazine-wiki", "wiki-sample"]   # 落とし直せる/作り直せる
REPO_XF = ["*.pyc", "tsconfig.tsbuildinfo", "*.bak", "*.bak-*", "*-bak-*", "*-temp.sqlite", "_dbr_tmp.pkl",
           "rakuten-isbn.jsonl", "rakuten-isbn-delta.jsonl", "anilist-delta.jsonl", "audit-hnop-revcache.json",
           "jawiki-*.gz", "jawiki-*.bz2"]


def _status_write(d):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    json.dump(d, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _robocopy(src, dst, xd=(), xf=()):
    cmd = ["robocopy", src, dst, "/MIR", "/R:1", "/W:1", "/NFL", "/NDL", "/NP", "/NJH", "/XJ", "/MT:8"]
    if xd:
        cmd += ["/XD", *xd]
    if xf:
        cmd += ["/XF", *xf]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="cp932", errors="replace")
    ok = r.returncode < 8                                         # robocopy: 0-7 = 成功(8以上 = 失敗あり)
    tail = [l.strip() for l in r.stdout.splitlines() if l.strip()][-6:]
    return ok, r.returncode, tail


def _protect(path):
    """継承を切り、 今の利用者・SYSTEM・Administrators だけにする(D: 共有の share1 から見えないように)。"""
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ['USERNAME']}".lstrip("\\")
    r = subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
                        "*S-1-5-32-544:(OI)(CI)F"], capture_output=True, text=True, encoding="cp932", errors="replace")
    if r.returncode != 0:
        sys.exit(f"★アクセス権を絞れない: {r.stdout} {r.stderr}")
    acl = subprocess.run(["icacls", path], capture_output=True, text=True, encoding="cp932", errors="replace").stdout
    if "Authenticated Users" in acl or "Everyone" in acl or "BUILTIN\\Users" in acl:
        sys.exit(f"★共有の利用者が残っている = 中止\n{acl}")


def _env_snapshot(d):
    os.makedirs(d, exist_ok=True)
    def out(name, cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, shell=isinstance(cmd, str))
            open(os.path.join(d, name), "w", encoding="utf-8").write(r.stdout + r.stderr)
        except Exception as e:
            open(os.path.join(d, name), "w", encoding="utf-8").write(f"取れなかった: {e}")
    out("pip-freeze.txt", [sys.executable, "-m", "pip", "freeze"])
    out("versions.txt", "python --version && node --version && npm --version && git --version && claude --version")
    out("npm-global.txt", "npm ls -g --depth=0")
    out("scheduled-tasks.txt", "schtasks /query /fo LIST /v")


def run():
    started = datetime.datetime.now().isoformat(timespec="seconds")
    if not os.path.exists("D:\\"):
        _status_write({"ok": False, "at": started, "why": "D: が見えない(外付けの認識外れ = 挿し直し待ち)"})
        print("★D: が見えない = 写さずに終了(挿し直してから run)。 ほかのドライブは探さない")
        return 2
    os.makedirs(DEST, exist_ok=True)
    _protect(DEST)
    metas = {}
    for s in ("A", "B"):
        p = os.path.join(DEST, s, "backup-meta.json")
        metas[s] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    # 古い方(または未使用・前回失敗)の枠に書く = 直近の成功は常に残る
    slot = min(("A", "B"), key=lambda s: (metas[s].get("ok") is True, metas[s].get("at", "")))
    base = os.path.join(DEST, slot)
    os.makedirs(base, exist_ok=True)
    print(f"写す先: {base}(もう1つの枠 = 前回分を残す)", flush=True)
    res = {}
    hc = os.path.join(HOME, ".claude")
    res["home/.claude"] = _robocopy(hc, os.path.join(base, "home", ".claude"),
                                    xd=[os.path.join(hc, x) for x in HOME_CLAUDE_XD], xf=HOME_CLAUDE_XF)
    for f in (".claude.json", ".gitconfig"):
        if os.path.exists(os.path.join(HOME, f)):
            res["home/" + f] = _copy1(os.path.join(HOME, f), os.path.join(base, "home", f))
    cache = os.path.join(ROOT, ".cache")
    res["MANGAL"] = _robocopy(ROOT, os.path.join(base, "MANGAL"),
                              xd=REPO_XD_NAMES + [os.path.join(cache, x) for x in CACHE_XD], xf=REPO_XF)
    _env_snapshot(os.path.join(base, "env-snapshot"))
    doc = os.path.join(ROOT, "docs", "restore-claude.md")
    if os.path.exists(doc):
        _copy1(doc, os.path.join(DEST, "README-restore.md"))
    ok = all(v[0] for v in res.values())
    meta = {"ok": ok, "at": started, "finished": datetime.datetime.now().isoformat(timespec="seconds"), "slot": slot,
            "parts": {k: {"ok": v[0], "code": v[1], "summary": v[2]} for k, v in res.items()}}
    json.dump(meta, open(os.path.join(base, "backup-meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _status_write({**meta, "dest": base})
    for k, v in res.items():
        print(f"  {'OK' if v[0] else '★失敗'} {k}(robocopy {v[1]})")
        for line in v[2][-3:]:
            print("     ", line)
    print("★写し終わり" if ok else "★一部失敗 = status を見る")
    return 0 if ok else 1


def _copy1(src, dst):
    import shutil
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.copy2(src, dst)
        return (True, 0, [os.path.basename(src)])
    except OSError as e:
        return (False, 99, [str(e)])


def status():
    if not os.path.exists(STATUS):
        print("★まだ一度も写していない(python scripts/_backup-self.py run)"); return 1
    d = json.load(open(STATUS, encoding="utf-8"))
    age = (datetime.datetime.now() - datetime.datetime.fromisoformat(d["at"])).days
    bad = (not d.get("ok")) or age >= STALE_DAYS
    print(f"{'★' if bad else ''}最後の写し: {d['at']}({age}日前)/ {'成功' if d.get('ok') else '失敗: ' + str(d.get('why') or d.get('parts'))}"
          f" / 枠 {d.get('slot', '-')}")
    if bad:
        print("  → D: を確かめて python scripts/_backup-self.py run(D: が外れていたら挿し直す)")
    return 1 if bad else 0


def install():
    py = sys.executable
    tr = f'"{py}" "{os.path.join(ROOT, "scripts", "_backup-self.py")}" run'
    r = subprocess.run(["schtasks", "/Create", "/F", "/TN", r"MANGAL\ClaudeBackup", "/SC", "WEEKLY", "/D", "SUN", "/ST", "04:00", "/TR", tr],
                       capture_output=True, text=True, encoding="cp932", errors="replace")
    print(r.stdout or r.stderr)
    # 予定時刻に PC が止まっていたら次に動いた時に走らせる
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$t=Get-ScheduledTask -TaskPath '\\MANGAL\\' -TaskName ClaudeBackup; $t.Settings.StartWhenAvailable=$true; "
                    "$t.Settings.ExecutionTimeLimit='PT3H'; Set-ScheduledTask -InputObject $t | Out-Null; 'StartWhenAvailable=on'"])
    return r.returncode


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"run": run, "status": status, "install": install}.get(cmd, lambda: sys.exit(__doc__))())
