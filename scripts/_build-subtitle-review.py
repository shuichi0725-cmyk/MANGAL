"""raw MADB から 副題候補を抽出し、 heuristic で default policy を付与して
data/seeds/subtitle-review.yml に出力する。

policy 候補:
  - keep:  別作品扱い (= 新 series_key 作成、 AI fill 必要)
  - merge: 同作品扱い (= base series に統合、 AI fill 不要)
  - strip: edition descriptor (= 通常版 / 完全版 等の別 edition、 base に統合 + edition で分ける)

heuristic (= default 推定):
  - 副題が ASCII (= 半角英数 + 記号) のみ          → merge
  - 副題が edition keyword (= 完全版 等) と一致      → strip
  - 副題に edition keyword が 先頭 含む            → strip (= 「決定版 : 春の足音」 等)
  - 副題が 「編」 / 「番外編」 / 「外伝」 で終わる   → keep
  - 副題が 「物語」 で終わる                       → merge (= 〜物語 系の長タイトル)
  - その他                                       → keep (= 安全側)
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".cache" / "madb" / "metadata101-clean.json"
OUT = ROOT / "data" / "seeds" / "subtitle-review.yml"

EDITION_KW = (
    "完全版", "新装版", "文庫版", "文庫", "愛蔵版", "ワイド版",
    "新装再編版", "リニューアル", "カバーリニューアル", "限定版",
    "新装", "新版", "復刻版", "豪華版", "決定版", "プレミアム",
    "オリジナル版",
)


def get_label(name):
    if not name:
        return ""
    if isinstance(name, str):
        return name
    if isinstance(name, list) and name:
        first = name[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("@value", "")
    return ""


def parse_new_rule(label):
    """新ルール v2: base, subtitle, display_sub を返す。"""
    t = label.strip()
    display_sub = ""
    if " = " in t:
        parts = t.split(" = ", 1)
        t = parts[0].strip()
        rest = parts[1].strip()
        if " : " in rest:
            _, sub = rest.split(" : ", 1)
            display_sub = sub.strip()
    bare_sub = ""
    while " : " in t:
        b, y = t.split(" : ", 1)
        y = y.strip()
        if y in EDITION_KW:
            t = b.strip()
            continue
        if " : " in y:
            head, rest = y.split(" : ", 1)
            if head.strip() in EDITION_KW:
                bare_sub = rest.strip()
                t = b.strip()
                break
        bare_sub = y
        t = b.strip()
        break
    t = re.sub(r"\s+\d+$", "", t)
    t = re.sub(r"\s+[上下](巻)?$", "", t)
    t = re.sub(r"\s+第\d+[巻集部]$", "", t)
    t = re.sub(r"\.+$", "", t)
    t = t.strip()
    return t, bare_sub, display_sub


def is_ascii_only(s: str) -> bool:
    return bool(s) and all(ord(c) < 128 for c in s)


def has_edition_kw_lead(s: str) -> bool:
    for kw in EDITION_KW:
        if s.startswith(kw + " ") or s.startswith(kw + ":") or s == kw:
            return True
    return False


def classify(subtitle: str) -> tuple[str, str]:
    """default policy + 理由 を返す"""
    if has_edition_kw_lead(subtitle):
        return ("strip", "先頭が edition keyword")
    if subtitle in EDITION_KW:
        return ("strip", "edition keyword と一致")
    if is_ascii_only(subtitle):
        return ("merge", "ASCII のみ (= 英語サブタイトル候補)")
    if subtitle.endswith("編"):
        return ("keep", "「編」 で終わる (= 続編候補)")
    if subtitle.endswith("外伝"):
        return ("keep", "「外伝」 で終わる")
    if subtitle.endswith("物語"):
        return ("merge", "「物語」 で終わる (= ラノベ系長タイトル候補)")
    return ("keep", "default keep (= 判断微妙、 安全側)")


def main():
    print(f"loading {RAW} ...", file=sys.stderr)
    with RAW.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # (base, subtitle) → list of book metadata
    groups = defaultdict(list)
    for b in data["@graph"]:
        name = b.get("schema:name")
        label = get_label(name)
        if not label:
            continue
        base, sub, _ = parse_new_rule(label)
        if not base:
            continue
        isbn = b.get("schema:isbn", "")
        if isinstance(isbn, list):
            isbn = isbn[0] if isbn else ""
        if not isinstance(isbn, str):
            isbn = str(isbn or "")
        vol = b.get("schema:volumeNumber", "") or ""
        if isinstance(vol, list):
            vol = vol[0] if vol else ""
        if not isinstance(vol, str):
            vol = str(vol or "")
        date = b.get("schema:datePublished", "") or ""
        groups[(base, sub)].append({"isbn": isbn, "vol": vol, "date": date})

    # subtitle ありで n_books >= 2 のものを 抽出 (= 章タイトル除外)
    candidates = []
    for (base, sub), books in groups.items():
        if not sub:
            continue
        if len(books) < 2:
            continue
        # main series (= base, "") の巻数も参考に
        main_count = len(groups.get((base, ""), []))
        policy, reason = classify(sub)
        candidates.append(
            {
                "base": base,
                "subtitle": sub,
                "n_books": len(books),
                "n_main_books": main_count,
                "policy": policy,
                "reason": reason,
                "samples": books[:3],
            }
        )

    # 巻数降順 sort
    candidates.sort(key=lambda x: -x["n_books"])

    print(f"total candidates: {len(candidates)}", file=sys.stderr)

    # default policy 集計
    from collections import Counter
    pc = Counter(c["policy"] for c in candidates)
    print(f"default policy 分布: {dict(pc)}", file=sys.stderr)

    # write yml (= 整形して人間読みやすく)
    lines = [
        "# subtitle-review.yml — 副題候補レビュー",
        "# 各 entry の policy を確認:",
        "#   keep  = 別作品扱い (= 別 series 作成、 AI fill 必要)",
        "#   merge = 同作品扱い (= base series に統合)",
        "#   strip = edition descriptor (= 別 edition で扱う)",
        "# default は heuristic で推定済。 違うものだけ policy を書き換えてください。",
        f"# 全 {len(candidates)} 件 (= 巻数降順)",
        "",
        "entries:",
    ]

    def yaml_str(s):
        if re.match(r"^[\w\-]+$", s):
            return s
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    for c in candidates:
        lines.append(f"  - base: {yaml_str(c['base'])}")
        lines.append(f"    subtitle: {yaml_str(c['subtitle'])}")
        lines.append(f"    n_books: {c['n_books']}")
        lines.append(f"    n_main_books: {c['n_main_books']}")
        lines.append(f"    policy: {c['policy']}")
        lines.append(f"    reason: {yaml_str(c['reason'])}")
        lines.append(f"    samples:")
        for s in c["samples"]:
            lines.append(
                f"      - {{isbn: {yaml_str(s['isbn'])}, vol: {yaml_str(s['vol'])}, date: {yaml_str(s['date'])}}}"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(candidates)} entries)", file=sys.stderr)


if __name__ == "__main__":
    main()
