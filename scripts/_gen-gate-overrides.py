"""検証ゲート裁定 → anilist-link-overrides.yml への畳み込み (= 計画②の適用)。

入力:
  .cache/anilist-gate-adjudication.tsv          (機械裁定: relink / drop)
  <scratch>/anilist-ai-slices/out-*.tsv         (AI裁定: keep / drop / unsure)
ルール:
  - 機械 relink / drop は採用(native/wd完全一致+著者ゲート済み)
  - AI drop は採用 / keep・unsure は entry を作らない(現リンク維持)
  - 既存 overrides と同 key は★新裁定が勝つ(ゲートは既存 override 適用後の状態を検証したため)
  - AI 出力の key は worksheet に実在するものだけ受理(改変・捏造ガード)
出力: data/seeds/anilist-link-overrides.yml を再生成(既存維持分 + 新裁定、 key順)
      検証: 適用前後の件数・置換・新規を表示。 --dry で書き込みなし。
"""
import csv
import glob
import re
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
OVR = ROOT / "data/seeds/anilist-link-overrides.yml"
ADJ = ROOT / ".cache/anilist-gate-adjudication.tsv"
WS = ROOT / ".cache/anilist-gate-ai-worksheet.tsv"
SCRATCH = Path(r"C:\Users\CHIBAS~1\AppData\Local\Temp\claude\C--Users-chiba-shuichi-code-MANGAL\1febbdf3-aa37-441c-889c-0ef8099234ae\scratchpad\anilist-ai-slices")


def read_tsv(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def main():
    dry = "--dry" in sys.argv
    doc = yaml.safe_load(OVR.read_text(encoding="utf-8")) or {}
    old = {o["key"]: o for o in (doc.get("overrides") or []) if isinstance(o, dict) and o.get("key")}
    print(f"既存 overrides: {len(old):,}")

    ws_keys = {r["key"] for r in read_tsv(WS)}
    new = {}
    # 機械裁定
    n_rel = n_drop = 0
    for r in read_tsv(ADJ):
        if r["verdict"] == "relink" and r["to_id"]:
            new[r["key"]] = {"key": r["key"], "action": "relink", "to_id": int(r["to_id"])}
            n_rel += 1
        elif r["verdict"] == "drop":
            new[r["key"]] = {"key": r["key"], "action": "drop"}
            n_drop += 1
    print(f"機械裁定: relink {n_rel} / drop {n_drop}")

    # AI裁定
    ai_drop = ai_keep = ai_unsure = ai_badkey = 0
    confirmed = {}
    verdict_rows = []
    for p in sorted(glob.glob(str(SCRATCH / "out-*.tsv"))):
        for r in read_tsv(p):
            k = r.get("key") or ""
            v = (r.get("verdict") or "").strip().lower()
            if k not in ws_keys:
                ai_badkey += 1
                continue
            verdict_rows.append((r.get("a_id") or "", k, v, r.get("reason") or ""))
            if v == "drop":
                if k not in new:  # 機械裁定優先
                    new[k] = {"key": k, "action": "drop"}
                ai_drop += 1
            elif v == "keep":
                ai_keep += 1
                if r.get("a_id"):
                    confirmed[k] = int(r["a_id"])
            else:
                ai_unsure += 1
    print(f"AI裁定: drop {ai_drop} / keep {ai_keep} / unsure {ai_unsure} / 不正key {ai_badkey}")

    # ★recall v2 の drop→relink 復活(計画③: 正しい付替先が証拠合議で見つかった drop 済み key)
    rl = ROOT / ".cache/recall-drop-relinks.tsv"
    n_revive = 0
    if rl.exists():
        for r in read_tsv(rl):
            if r.get("a_id"):
                new[r["s3_key"]] = {"key": r["s3_key"], "action": "relink", "to_id": int(r["a_id"])}
                n_revive += 1
    print(f"recall drop→relink復活: {n_revive}")

    replaced = sum(1 for k in new if k in old)
    merged = dict(old)
    merged.update(new)
    print(f"→ 置換 {replaced} / 新規 {len(new) - replaced} / 合計 {len(merged):,}")

    if dry:
        print("(--dry: 書き込みなし)")
        return
    lines = [
        "# AniList誤リンク override(自動生成 _gen-anilist-link-overrides.py + _gen-gate-overrides.py)。",
        "# relink: franchise本編へ a_id 付け替え(native完全一致で確証)。",
        "# drop:   高確信誤り(検証ゲートFAIL/AI裁定)で relink先無し → enrich除外。",
        "# ★2026-07-18 検証ゲート裁定([[anilist_link_verification_plan]])を畳み込み済。",
        "overrides:",
    ]
    def esc(s):
        return s.replace('\\', '\\\\').replace('"', '\\"')
    for k in sorted(merged):
        o = merged[k]
        if o.get("action") == "relink":
            lines.append(f'  - {{key: "{esc(k)}", action: relink, to_id: {o["to_id"]}}}')
        else:
            lines.append(f'  - {{key: "{esc(k)}", action: drop}}')
    OVR.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 検証: 読み戻し
    doc2 = yaml.safe_load(OVR.read_text(encoding="utf-8"))
    assert len(doc2["overrides"]) == len(merged), "読み戻し件数不一致"
    print(f"wrote {OVR} ({len(merged):,} entries, 読み戻しOK)")

    # ★AI keep = 確認済みallowlist(key→a_id ペア単位)。 ゲート再走時に PASS 扱い(再フラグ抑止)。
    import json
    conf_p = ROOT / "data/seeds/anilist-link-confirmed.json"
    prev = json.loads(conf_p.read_text(encoding="utf-8")) if conf_p.exists() else {}
    prev.update({k: v for k, v in confirmed.items()})
    conf_p.write_text(json.dumps(prev, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"wrote {conf_p} ({len(prev):,} 確認済みリンク)")

    # ★裁定証跡をgit永続化(.cache/scratchpad は消える → 台帳原則)
    ev = ROOT / "docs/production-diagnostics/anilist-gate-ai-verdicts.tsv"
    with ev.open("w", encoding="utf-8") as f:
        f.write("a_id\tkey\tverdict\treason\n")
        for x in sorted(verdict_rows, key=lambda t: t[1]):
            f.write("\t".join(str(v).replace("\t", " ") for v in x) + "\n")
    print(f"wrote {ev} ({len(verdict_rows):,} 裁定証跡)")


if __name__ == "__main__":
    main()
