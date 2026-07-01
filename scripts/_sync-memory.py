#!/usr/bin/env python3
"""Claude Code の記憶(.claude/projects/.../memory/) を repo/.claude-memory/ へミラー。

★なぜ: Claude標準の記憶は **このPCローカルの .claude 配下** にあり git管理外
  = GitHubにバックアップされず別PC/モバイルから見えない。 これを repo に鏡写しして
  git で永続化(バックアップ+可視化+cross-PC)する。 [[reflect_protocol_fast]] 同様の
  「大事なものはgitに焼く」原則。

使い方: python scripts/_sync-memory.py        (ミラー: 追加/更新/削除を反映)
        記憶ファイルを書いた/消した後に実行 → git add .claude-memory && commit && push。

★機械依存: SRC は現PC/プロジェクトのパス。 別PCでは各自の .claude パスに合わせる。
"""
import os, sys, shutil, glob
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Claude記憶の実体(このPC/プロジェクト固有)。 CLAUDE.md冒頭に記載のパスと一致。
SRC = r"C:\Users\shuic\.claude\projects\C--Users-shuic-code-MANGAL\memory"
DST = os.path.join(ROOT, ".claude-memory")

def main():
    if not os.path.isdir(SRC):
        print(f"★SRC無し(別PC?): {SRC}", file=sys.stderr); sys.exit(1)
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
