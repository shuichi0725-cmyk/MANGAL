#!/usr/bin/env python3
"""Claude Code の記憶(.claude/projects/.../memory/) を repo/.claude-memory/ へミラー。

★なぜ: Claude標準の記憶は **このPCローカルの .claude 配下** にあり git管理外
  = GitHubにバックアップされず別PC/モバイルから見えない。 これを repo に鏡写しして
  git で永続化(バックアップ+可視化+cross-PC)する。 [[reflect_protocol_fast]] 同様の
  「大事なものはgitに焼く」原則。

使い方: python scripts/_sync-memory.py        (ミラー: 追加/更新/削除を反映)
        記憶ファイルを書いた/消した後に実行 → git add .claude-memory && commit && push。

★SRC は自動判定(= PC/ユーザ名に依存させない)。 上書きしたい時だけ env CLAUDE_MEMORY_SRC。
  2026-07-17: 旧PCのパス(C:\\Users\\shuic\\...)が固定で書かれており、PC移行後は
  「★SRC無し(別PC?)」と出して**何もせず終了** = 記憶のgit永続化が黙って止まっていた。
"""
import os, sys, shutil, glob
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, ".claude-memory")

def find_src():
    """Claude記憶(.claude/projects/<repo>/memory)の実体を、このPCの環境から見つける。"""
    env = os.environ.get("CLAUDE_MEMORY_SRC")
    if env:
        return env
    projects = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    # Claude Code の命名 = repo絶対パスの ":" "\" "/" " " を全て "-" に潰したもの
    mangled = ROOT.replace(":", "-").replace("\\", "-").replace("/", "-").replace(" ", "-")
    p = os.path.join(projects, mangled, "memory")
    if os.path.isdir(p):
        return p
    # 命名規則が変わった時の保険: 末尾が repo 名で一致する候補が1つだけなら採用
    cand = [d for d in glob.glob(os.path.join(projects, "*", "memory"))
            if os.path.basename(os.path.dirname(d)).endswith("-" + os.path.basename(ROOT))]
    return cand[0] if len(cand) == 1 else p   # 0件/複数なら p のまま下で止める

SRC = find_src()

def main():
    if not os.path.isdir(SRC):
        print(f"★abort: 記憶の実体が見つからない: {SRC}\n"
              f"  env CLAUDE_MEMORY_SRC で明示指定できる。", file=sys.stderr); sys.exit(1)
    os.makedirs(DST, exist_ok=True)
    src_md = {os.path.basename(p) for p in glob.glob(os.path.join(SRC, "*.md"))}
    dst_md = {os.path.basename(p) for p in glob.glob(os.path.join(DST, "*.md"))}
    added = updated = removed = 0
    for name in src_md:
        s = os.path.join(SRC, name); d = os.path.join(DST, name)
        if not os.path.exists(d):
            shutil.copyfile(s, d); added += 1
        elif open(s, "rb").read() != open(d, "rb").read():
            shutil.copyfile(s, d); updated += 1
    for name in dst_md - src_md:  # .claude側で消した記憶は鏡からも削除
        os.remove(os.path.join(DST, name)); removed += 1
    print(f"記憶ミラー: 追加{added} / 更新{updated} / 削除{removed} / 計{len(src_md)}ファイル → .claude-memory/")
    print("→ git add .claude-memory && git commit && git push で GitHub に永続化")

if __name__ == "__main__":
    main()
