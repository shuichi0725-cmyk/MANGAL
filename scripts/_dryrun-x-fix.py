"""B-4: × バグ修正の dry-run。 98 件 全件の before/after を 出す。"""
import re
from pathlib import Path


def slug_old(alt_en: str) -> str:
    s = alt_en.strip()
    s = re.sub(r"['!?.,]", "", s)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def slug_new(alt_en: str) -> str:
    s = alt_en.strip()
    s = s.replace("×", "x")  # ★ 追加
    s = re.sub(r"['!?.,]", "", s)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    s = re.sub(r"-+", "-", s).strip("-")
    return s


text = Path(".cache/slug-audit-seed3.txt").read_text(encoding="utf-8")
sec = text.split("## B-4: × バグ", 1)[1].split("\n## ", 1)[0]
alts = re.findall(r"^    alt_en: (.+)$", sec, re.M)
titles = re.findall(r"^    title: (.+)$", sec, re.M)

print(f"# B-4 dry-run: {len(alts)} 件")
print()
changed = 0
unchanged = 0
for i, alt in enumerate(alts):
    title = titles[i] if i < len(titles) else "?"
    o = slug_old(alt)
    n = slug_new(alt)
    if o == n:
        unchanged += 1
    else:
        changed += 1
        print(f"  {title}")
        print(f"    alt_en: {alt}")
        print(f"    before: {o}")
        print(f"    after:  {n}")
        print()

print(f"## Summary")
print(f"  total:     {len(alts)}")
print(f"  changed:   {changed}")
print(f"  unchanged: {unchanged}")
