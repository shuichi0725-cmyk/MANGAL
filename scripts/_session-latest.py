#!/usr/bin/env python3
"""fable.bat / opus.bat / sonnet.bat 用: モデル別・最新セッションのUUIDを返す。

背景 (2026-07-20 判明): claude が cwd を realpath 解決するようになり、
junction (MANGAL-fable 等) によるセッション名前空間分離が無効化された。
全 bat のセッションが同一 project dir に落ちるため、--continue は
「別モデルの最新セッション」を掴んでしまう。
対策: セッション jsonl の本線 assistant メッセージ model でモデル系列を
判定し、系列ごとの最新セッションを --resume で戻す。

★2026-07-28 追加(ユーザ要望「勝手な圧縮はやめてほしい」):
前回セッションが文脈満杯近く(既定75%)だと --resume 直後に auto-compact が走り
起動が重くなる。その場合は resume 候補を返さず exit 1 = bat が新規セッションで
即起動する(過去ログは log.bat <family> か claude --resume で見られる)。
閾値は環境変数 CLAUDE_RESUME_MAX_PCT で変更可(0=常に新規, 100=常にresume)。

★2026-07-28b 改修(「三つとも直近ログを読まなくなった」事故の恒久対策):
1. 並び順を mtime → 「最後の本線assistant発言のtimestamp」(=会話の実時刻)に変更。
   mtime は「間違って開いただけ」でも最新化するため、一度誤った旧セッションを
   掴むと以後ずっと旧を選び続ける自己強化があった(07-28朝 opus/fable/sonnet 実害)。
2. 末尾が <synthetic>(APIエラー等の擬似応答)でもファイルを捨てず、遡って
   本物の assistant を探す(旧実装は末尾1件のみ判定→セッション孤児化)。
3. tail 読みの OSError は短いretry(窓を閉じた直後の一時的なロック対策)。
"""
import glob
import json
import os
import re
import sys
import time

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
    for attempt in range(3):
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                f.seek(max(0, size - TAIL_BYTES))
                return f.read().decode("utf-8", "ignore")
        except OSError:
            time.sleep(0.3)  # 閉じた直後の一時ロック対策
    return None


def last_main_assistant(data: str) -> tuple[str | None, int, str]:
    """末尾から本線(非sidechain)の最後の「本物の」assistant 行を探し
    (model, 文脈使用トークン概算, timestamp) を返す。
    regex での usage 拾いは入れ子object/tool_result内の偽usageで壊れた(2026-07-28実踏)ため
    行単位で json parse する。sidechain(サブエージェント)行はモデルも usage も別系、
    <synthetic>(APIエラー等の擬似応答)はモデル名が立たないため、どちらも読み飛ばして遡る。"""
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
        model = msg.get("model")
        if not (model and model.startswith("claude-")):
            continue  # <synthetic> 等 = 本物の応答でない → さらに遡る
        u = msg.get("usage") or {}
        used = sum(
            int(u.get(k) or 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
        )
        return model, used, d.get("timestamp") or ""
    return None, 0, ""


def last_model(data: str) -> str | None:
    return last_main_assistant(data)[0]


def project_dir() -> str:
    # claude と同じ流儀: cwd の realpath を区切り文字置換した名前が project dir
    real = os.path.realpath(os.getcwd())
    name = re.sub(r"[\\/: .]", "-", real)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", name)


def candidates(family: str) -> list[tuple[str, str, int]]:
    """系列 family のセッションを (last_assistant_ts, path, used) で新しい順に返す。
    ★並びは「会話の実時刻」= 最後の本線assistant発言のtimestamp。mtimeは使わない
    (誤って開いただけで最新化し、旧セッションを掴み続ける事故の根)。"""
    prefix = FAMILY_PREFIX[family]
    out = []
    for path in glob.glob(os.path.join(project_dir(), "*.jsonl")):
        data = tail(path)
        if not data:
            continue
        model, used, ts = last_main_assistant(data)
        if model and model.startswith(prefix):
            out.append((ts, path, used))
    out.sort(reverse=True)
    return out


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in FAMILY_PREFIX:
        print(f"usage: _session-latest.py {'|'.join(FAMILY_PREFIX)}", file=sys.stderr)
        return 2
    family = sys.argv[1]
    max_pct = int(os.environ.get("CLAUDE_RESUME_MAX_PCT", "75"))
    cands = candidates(family)
    if not cands:
        return 1
    ts, path, used = cands[0]
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


if __name__ == "__main__":
    sys.exit(main())
