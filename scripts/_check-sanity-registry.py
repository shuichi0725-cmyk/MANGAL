"""月次サニティの **登録漏れ番人** (= 2026-09-06 新設 / 同日 3点突合に拡張)。

★なぜ要るか:
  「1件のバグ = 型と疑う」([[feedback_one_bug_means_a_class]]) で検出器を作り、
  CLAUDE.md の月次サニティ節に「月次=新規増加分を見る」と書く運用をしている。
  ところが **書いただけで `_monthly-distill.py` の DETECTORS に登録し忘れる**と、
  検出器は二度と回らない。 規定は実装の保証ではない([[skill_rule_without_implementation]])。
  実測 2026-09-06: subtitle-orphan-volume(Sugar&Spice型 9/3新設) / furigana /
  anilist-verify-gate / seed1-lost の4本が CLAUDE.md に在って DETECTORS に無かった。

★2026-09-06 に本文を `docs/monthly-sanity-detectors.md` へ移し(CLAUDE.md の 39.7% を占めていた)、
  CLAUDE.md 側は **1行索引**にした。 そこで突合を **3点** にする:

    索引  = CLAUDE.md「### ★月次サニティ監査」節      (= 不具合報告時に型を引く入口)
    本文  = docs/monthly-sanity-detectors.md          (= 経緯・実測値・是正手順)
    実装  = _monthly-distill.py の DETECTORS          (= 実際に回るもの)

  未登録   = 索引/本文に在るが DETECTORS に無い(EXEMPT でもない)  → exit 1
  実体なし = DETECTORS に在るが scripts/ にファイルが無い          → exit 1
  索引漏れ = 本文に在るが索引に無い(= 入口から引けない)            → exit 1
  本文漏れ = 索引に在るが本文に無い(= 索引だけ在って中身が無い)     → exit 1
  未記載   = DETECTORS に在るが索引にも本文にも無い                → 警告のみ(exit 0)

使い方:
  python scripts/_check-sanity-registry.py          # 人が見る
  python scripts/_check-sanity-registry.py --quiet  # 差が無ければ黙る(runner から呼ぶ用)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CLAUDE_MD = ROOT / "CLAUDE.md"
DOC = ROOT / "docs" / "monthly-sanity-detectors.md"
ORCH = SCRIPTS / "_monthly-distill.py"

# ★月次サニティで回さないことに理由がある検出器 = ここに理由つきで書く(黙って外さない)
EXEMPT = {
    "_check-sanity-registry.py": "番人自身。DETECTORS の一員ではなく run sanity の先頭で走る",
    "_audit-preorder-date-drift.py": "日次蒸留で回している(skill daily-distill 手順10.6)",
    "_audit-shu2-unrendered.py": "shu2-unlisted-volumes に統合済(前世代)",
    "_coverage-audit.py": "被覆の土台。件数監視でなく人が読む種類",
}

# 検出器とみなす名前(適用器 _apply-* / 生成器 _gen-* / 共有module は対象外)
_IS_DETECTOR = re.compile(r"^_(audit|check)-.+\.py$|.+-(audit|gate)\.py$")


def _detectors(text: str) -> set:
    return set(n for n in re.findall(r"scripts/(_?[A-Za-z0-9_\-]+\.py)", text)
               if _IS_DETECTOR.match(n))


def index_detectors() -> set:
    """CLAUDE.md「### ★月次サニティ監査」節(=索引)から拾う。"""
    txt = CLAUDE_MD.read_text(encoding="utf-8")
    m = re.search(r"^### ★月次サニティ監査.*$", txt, re.M)
    if not m:
        sys.exit("CLAUDE.md に「### ★月次サニティ監査」節が無い(節名を変えたら本script も直す)")
    tail = txt[m.end():]
    nxt = re.search(r"^#{2,3} ", tail, re.M)
    return _detectors(tail[: nxt.start()] if nxt else tail)


def doc_detectors() -> set:
    if not DOC.exists():
        sys.exit(f"本文が無い: {DOC.relative_to(ROOT)}")
    return _detectors(DOC.read_text(encoding="utf-8"))


def registry_detectors() -> dict:
    """_monthly-distill.py の DETECTORS = [...] から script 名を拾う(import せず本文を読む)。"""
    txt = ORCH.read_text(encoding="utf-8")
    m = re.search(r"^DETECTORS = \[(.*?)^\]", txt, re.S | re.M)
    if not m:
        sys.exit("_monthly-distill.py に DETECTORS = [ ... ] が見つからない")
    return dict((mm.group(2), mm.group(1))
                for mm in re.finditer(r'\("([^"]+)",\s*\["([^"]+\.py)"', m.group(1)))


def main() -> None:
    quiet = "--quiet" in sys.argv
    idx, doc, reg = index_detectors(), doc_detectors(), registry_detectors()
    named = idx | doc

    missing = sorted(n for n in named if n not in reg and n not in EXEMPT)
    ghost = sorted(n for n in reg if not (SCRIPTS / n).exists())
    not_in_index = sorted(doc - idx)
    not_in_doc = sorted(idx - doc)
    undoc = sorted(n for n in reg if n not in named)

    bad = bool(missing or ghost or not_in_index or not_in_doc)
    if quiet and not bad and not undoc:
        return

    print("=" * 72)
    print("月次サニティ 3点突合  索引 %d / 本文 %d / DETECTORS %d" % (len(idx), len(doc), len(reg)))
    print("  索引 = CLAUDE.md 月次サニティ節 / 本文 = %s" % DOC.relative_to(ROOT))
    print("=" * 72)
    if missing:
        print("★未登録(書いてあるのに月次で回らない) %d本:" % len(missing))
        for n in missing:
            print("   - %s" % n)
        print("   → _monthly-distill.py の DETECTORS に足す。 回さない理由が在るなら")
        print("     本script の EXEMPT に **理由つきで** 書く(黙って外さない)。")
    if ghost:
        print("★実体なし(DETECTORS に在るのに scripts/ に無い) %d本:" % len(ghost))
        for n in ghost:
            print("   - %s  (%s)" % (n, reg[n]))
    if not_in_index:
        print("★索引漏れ(本文に在るが CLAUDE.md の索引に無い = 入口から引けない) %d本:" % len(not_in_index))
        for n in not_in_index:
            print("   - %s" % n)
    if not_in_doc:
        print("★本文漏れ(索引に在るが本文に無い = 索引だけで中身が無い) %d本:" % len(not_in_doc))
        for n in not_in_doc:
            print("   - %s" % n)
    if undoc:
        print("参考: DETECTORS に在るが索引にも本文にも無い %d本(=索引+本文へ追記推奨):" % len(undoc))
        for n in undoc:
            print("   - %s  (%s)" % (n, reg[n]))
    if not bad:
        print("★未登録・実体なし・索引漏れ・本文漏れ = 0")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
