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

★2026-07-28 追加(ユーザ要望「勝手な圧縮はやめてほしい」):
前回セッションが文脈満杯近く(既定75%)だと --resume 直後に auto-compact が走り
起動が重くなる。その場合は resume 候補を返さず exit 1 = bat が新規セッションで
即起動する(過去ログは log.bat <family> か claude --resume で見られる)。
閾値は環境変数 CLAUDE_RESUME_MAX_PCT で変更可(0=常に新規, 100=常にresume)。
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
# 文脈窓の概算(トークン)。fable/opus は bat が [1m] 付きで起動するので 1M。
CONTEXT_LIMIT = {
    "fable": 1_000_000,
    "opus": 1_000_000,
    "sonnet": 200_000,
    "haiku": 200_000,
}
TAIL_BYTES = 256 * 1024  # 末尾だけ読む(巨大セッションでも高速)


def tail(path: str) -> str | None:
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            return f.read().decode("utf-8", "ignore")
    except OSError:
        return None


def last_main_assistant(data: str) -> tuple[str | None, int]:
    """末尾から本線(非sidechain)の最後の assistant 行を探し (model, 文脈使用トークン概算) を返す。
    regex での usage 拾いは入れ子object/tool_result内の偽usageで壊れた(2026-07-28実踏)ため
    行単位で json parse する。sidechain(サブエージェント)行はモデルも usage も別系なので除外。"""
    import json

    for line in reversed(data.split("\n")):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue  # tail 切断行など
        if d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        msg = d.get("message") or {}
        u = msg.get("usage") or {}
        used = sum(
            int(u.get(k) or 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
        )
        return msg.get("model"), used
    return None, 0


def last_model(data: str) -> str | None:
    return last_main_assistant(data)[0]


def project_dir() -> str:
    # claude と同じ流儀: cwd の realpath を区切り文字置換した名前が project dir
    real = os.path.realpath(os.getcwd())
    name = re.sub(r"[\\/: .]", "-", real)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", name)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in FAMILY_PREFIX:
        print(f"usage: _session-latest.py {'|'.join(FAMILY_PREFIX)}", file=sys.stderr)
        return 2
    family = sys.argv[1]
    prefix = FAMILY_PREFIX[family]
    max_pct = int(os.environ.get("CLAUDE_RESUME_MAX_PCT", "75"))
    proj = project_dir()
    files = glob.glob(os.path.join(proj, "*.jsonl"))
    files.sort(key=os.path.getmtime, reverse=True)
    for path in files:
        data = tail(path)
        if not data:
            continue
        model, used = last_main_assistant(data)
        if not (model and model.startswith(prefix)):
            continue
        pct = used * 100 // CONTEXT_LIMIT[family]
        if pct > max_pct:
            print(
                f"[{family}] 前回ログは文脈{pct}%で満杯近く → 起動時の自動圧縮を避けるため"
                f"新規セッションで起動します (過去ログ: log.bat {family})",
                file=sys.stderr,
            )
            return 1
        print(os.path.splitext(os.path.basename(path))[0])
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
