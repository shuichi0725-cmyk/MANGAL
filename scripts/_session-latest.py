#!/usr/bin/env python3
"""fable.bat / opus.bat / sonnet.bat 用: モデル別・最新セッションのUUIDを返す。

背景 (2026-07-20 判明): claude が cwd を realpath 解決するようになり、
junction (MANGAL-fable 等) によるセッション名前空間分離が無効化された。
全 bat のセッションが同一 project dir に落ちるため、--continue は
「別モデルの最新セッション」を掴んでしまう。
対策: セッション jsonl 末尾の assistant メッセージ model でモデル系列を
判定し、系列ごとの最新セッションを --resume で戻す。

usage: python scripts/_session-latest.py fable|opus|sonnet|haiku
出力: 該当セッションUUID 1行 (stdout)。見つからなければ出力なし exit 1。
"""
import glob
import os
import re
import sys

FAMILY_PREFIX = {
    "fable": "claude-fable-",
    "opus": "claude-opus-",
    "sonnet": "claude-sonnet-",
    "haiku": "claude-haiku-",
}
ANY_MODEL = re.compile(r'"model"\s*:\s*"(claude-[a-z0-9.\-]+)"')
TAIL_BYTES = 256 * 1024  # 末尾だけ読む(巨大セッションでも高速)


def last_model(path: str) -> str | None:
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            data = f.read().decode("utf-8", "ignore")
    except OSError:
        return None
    hits = ANY_MODEL.findall(data)
    return hits[-1] if hits else None


def project_dir() -> str:
    # claude と同じ流儀: cwd の realpath を区切り文字置換した名前が project dir
    real = os.path.realpath(os.getcwd())
    name = re.sub(r"[\\/: .]", "-", real)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", name)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in FAMILY_PREFIX:
        print(f"usage: _session-latest.py {'|'.join(FAMILY_PREFIX)}", file=sys.stderr)
        return 2
    prefix = FAMILY_PREFIX[sys.argv[1]]
    proj = project_dir()
    files = glob.glob(os.path.join(proj, "*.jsonl"))
    files.sort(key=os.path.getmtime, reverse=True)
    for path in files:
        model = last_model(path)
        if model and model.startswith(prefix):
            print(os.path.splitext(os.path.basename(path))[0])
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
