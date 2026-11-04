"""2026-11-04 MADB 是正の後始末: 誌名の部分一致(別冊コロコロ⊃コロコロ / Cookie BOX⊃Cookie)で A に入っていた3頁を直す。
- good-morning-kiss: 初出= Cookie BOX(増刊・マスタに無い)→ 上書きを外す(頁は元の値に戻る)
- namennayo / usotsuki-gokuoo-kun: 別冊コロコロコミック へ
magazine-corrections.yml の当該ブロックを書き換え、 changelog に1行ずつ足す。"""
import datetime, json, re, sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
CP = ROOT / "data" / "seeds" / "magazine-corrections.yml"
FIX = {
    "namennayo": ("bessatsu-corocoro-comic", "Wiki=別冊コロコロコミック / MADB=月刊コロコロコミック。 Wikiを採る(旧値の「ちゃお」は誤り)"),
    "usotsuki-gokuoo-kun": ("bessatsu-corocoro-comic", "Wiki=別冊コロコロコミック→月刊コロコロコミック。 MADB初出欄も最古は別冊コロコロ2011年6月号。 初出誌=別冊コロコロ"),
}
DROP = {"good-morning-kiss": "Wiki=Cookie BOX(Cookieの増刊)→Cookie。 増刊は別の誌(ユーザ裁定)でマスタに無い = 上書きを外す"}

txt = CP.read_text(encoding="utf-8")
cur = yaml.safe_load(txt)["corrections"]
at = datetime.datetime.now().isoformat(timespec="seconds")
log = []
for s, (mag, why) in FIX.items():
    old = cur[s]["magazine"]
    pat = re.compile(rf"(\n  {re.escape(s)}:\n    magazine: )[^\n]+(\n    source: )[^\n]+(\n    evidence: )[^\n]+")
    ev = yaml.safe_dump({"e": f"{why}。 旧値 {old}(2026-11-04 の部分一致の誤り)を是正"}, allow_unicode=True, width=10000).split(": ", 1)[1].strip()
    txt, n = pat.subn(lambda m: f"{m.group(1)}{mag}{m.group(2)}manual{m.group(3)}{ev}", txt)
    assert n == 1, (s, n)
    log.append({"op": "magazine-correct", "slug": s, "before": old, "after": mag, "evidence": why, "at": at,
                "via": "magazine-corrections.yml → _reflect-targeted --only", "reversible": "magazine-corrections.yml の当該キーを戻して再反映"})
for s, why in DROP.items():
    old = cur[s]["magazine"]
    pat = re.compile(rf"\n  {re.escape(s)}:\n    magazine: [^\n]+\n    source: [^\n]+\n    evidence: [^\n]+\n    added_at: [^\n]+")
    txt, n = pat.subn("", txt)
    assert n == 1, (s, n)
    log.append({"op": "magazine-correct-revert", "slug": s, "before": old, "after": None, "evidence": why, "at": at,
                "via": "magazine-corrections.yml のキー削除 → _reflect-targeted --only", "reversible": "キーを足し戻して再反映"})
CP.write_text(txt, encoding="utf-8")
new = yaml.safe_load(CP.read_text(encoding="utf-8"))["corrections"]
assert all(new[s]["magazine"] == m for s, (m, _) in FIX.items()) and not any(s in new for s in DROP)
assert len(new) == len(cur) - len(DROP)
with open(ROOT / "data" / "seeds" / "magazine-fix-changelog.jsonl", "a", encoding="utf-8") as f:
    for x in log:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
print("直した", list(FIX), "/ 外した", list(DROP), "/ corrections", len(cur), "→", len(new))
