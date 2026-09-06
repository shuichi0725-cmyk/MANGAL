"""月次サニティの **登録漏れ番人** (= 2026-09-06 新設)。

★なぜ要るか:
  「1件のバグ = 型と疑う」([[feedback_one_bug_means_a_class]]) で検出器を作り、
  CLAUDE.md の月次サニティ節に「月次=新規増加分を見る」と書く運用をしている。
  ところが **書いただけで `_monthly-distill.py` の DETECTORS に登録し忘れる**と、
  検出器は二度と回らない。 規定は実装の保証ではない([[skill_rule_without_implementation]])。
  実測 2026-09-06: subtitle-orphan-volume(Sugar&Spice型 9/3新設) / furigana-audit /
  anilist-verify-gate / seed1-lost の4本が CLAUDE.md に在って DETECTORS に無かった。

やること = CLAUDE.md「★月次サニティ監査」節に出てくる検出器スクリプトと
  `_monthly-distill.py` の DETECTORS を突合して、片側にしか無いものを出す。

  未登録   = CLAUDE.md に在るが DETECTORS に無い(EXEMPT でもない)  → exit 1
  実体なし = DETECTORS に在るが scripts/ にファイルが無い          → exit 1
  未記載   = DETECTORS に在るが CLAUDE.md 節に記載が無い            → 警告のみ(exit 0)

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
ORCH = SCRIPTS / "_monthly-distill.py"

# ★月次サニティで回さないことに理由がある検出器 = ここに理由つきで書く(黙って外さない)
EXEMPT = {
    "_check-sanity-registry.py": "番人自身。DETECTORS の一員ではなく run sanity の先頭で走る",
    "_audit-preorder-date-drift.py": "日次蒸留で回している(skill daily-distill 手順10.6)",
    "_audit-shu2-unrendered.py": "shu2-unlisted-volumes に統合済(前世代)",
    "_coverage-audit.py": "被覆の土台。件数監視でなく人が読む種類",
}

# 検出器とみなす名前(適用器 _apply-* / 生成器 _gen-* / 頁化 _torikoboshi-* は対象外)
_IS_DETECTOR = re.compile(r"^_(audit|check)-.+\.py$|.+-(audit|gate)\.py$|^_check-.+\.py$")


def detectors_in_claude_md():
    """CLAUDE.md の「★月次サニティ監査」節に出てくる scripts/*.py を拾う。"""
    txt = CLAUDE_MD.read_text(encoding="utf-8")
    m = re.search(r"^### ★月次サニティ監査.*?$", txt, re.M)
    if not m:
        sys.exit("CLAUDE.md に「### ★月次サニティ監査」節が無い(節名を変えたら本script も直す)")
    tail = txt[m.end():]
    nxt = re.search(r"^(###|---)\s*$|^### ", tail, re.M)
    body = tail[: nxt.start()] if nxt else tail
    found = {}
    for mm in re.finditer(r"`?scripts/(_?[A-Za-z0-9_\-]+\.py)`?", body):
        name = mm.group(1)
        if _IS_DETECTOR.match(name):
            found.setdefault(name, body.count(name))
    return found


def detectors_in_registry():
    """_monthly-distill.py の DETECTORS = [...] から script 名を拾う(import せず本文を読む)。"""
    txt = ORCH.read_text(encoding="utf-8")
    m = re.search(r"^DETECTORS = \[(.*?)^\]", txt, re.S | re.M)
    if not m:
        sys.exit("_monthly-distill.py に DETECTORS = [ ... ] が見つからない")
    return dict((mm.group(2), mm.group(1))
                for mm in re.finditer(r'\("([^"]+)",\s*\["([^"]+\.py)"', m.group(1)))


def main() -> None:
    quiet = "--quiet" in sys.argv
    md = detectors_in_claude_md()
    reg = detectors_in_registry()

    missing = sorted(n for n in md if n not in reg and n not in EXEMPT)
    ghost = sorted(n for n in reg if not (SCRIPTS / n).exists())
    undoc = sorted(n for n in reg if n not in md)

    bad = bool(missing or ghost)
    if quiet and not bad and not undoc:
        return

    print("=" * 72)
    print("月次サニティ 登録突合  CLAUDE.md %d本 / DETECTORS %d本" % (len(md), len(reg)))
    print("=" * 72)
    if missing:
        print("★未登録(CLAUDE.md に在るのに月次で回らない) %d本:" % len(missing))
        for n in missing:
            print("   - %s" % n)
        print("   → _monthly-distill.py の DETECTORS に足す。 回さない理由が在るなら")
        print("     本script の EXEMPT に **理由つきで** 書く(黙って外さない)。")
    if ghost:
        print("★実体なし(DETECTORS に在るのに scripts/ に無い) %d本:" % len(ghost))
        for n in ghost:
            print("   - %s  (%s)" % (n, reg[n]))
    if undoc:
        print("参考: DETECTORS に在るが CLAUDE.md 月次サニティ節に記載なし %d本(=節へ追記推奨):" % len(undoc))
        for n in undoc:
            print("   - %s  (%s)" % (n, reg[n]))
    if not bad:
        print("★登録漏れ・実体なし = 0")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
