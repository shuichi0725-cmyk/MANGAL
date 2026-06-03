"""(A)証拠確証済みの franchise merge を series-merge.yml に純粋追加 + 外国版/アニメ版を
non-manga-drop.yml に追加 (純粋追加・既存不変)。 [[merge-needs-external-proof]] 準拠。

各 decision = 確証済み:
  mizu-wakusei  : Wikipedia「全7巻」確定 → 7断片 merge(renumber)
  kowai-hon     : 楳図恐怖文庫 連番ISBN(...720027-720140)同年同社 = 1シリーズ + 角川再刊 → merge
  mikosuri      : 本編18巻 + ぶんか社テーマ別デラックス編(同著者同社) = 同一作 → merge
  hamtaro       : Wikipedia「独立作でなく連続作品」→ merge、 アニメ版(ハムージャ)は drop
  keroro        : ケロロ軍曹 + green/pink/red(角川 同一作の版) merge、 スウェーデン版(Keroro/978-91) drop
  tennis        : 本編 + 完全版season1-3 merge、 都大会編(コミック版=アニメ)は merge除外
"""
import io
import sys
import json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


# slug -> (note, renumber, exclude_predicate(title)->True で merge から除外, drop_predicate)
def excl_none(t):
    return False


DECISIONS = {
    "mizu-wakusei-nendaiki": dict(
        note="大石まさる 水惑星年代記 全7巻統合(Wikipedia『全7巻』確証=続/環/翠/碧/月娘/月刊サチサチ)。 2026-06 検証済",
        renumber=True, exclude=excl_none, drop=excl_none),
    "kowai-hon": dict(
        note="楳図かずお こわい本 統合(恐怖文庫 連番ISBN9784257720027-720140・同1996・同社=1シリーズの闇/異形/影/怨念/顔/狂乱/蛇/呪縛/神罰/蜘蛛/虫 + 角川ホラー文庫再刊こわい本/ゾク)。 構造証拠。 2026-06",
        renumber=False, exclude=excl_none, drop=excl_none),
    "mikosuri-han-gekijou": dict(
        note="岩谷テンホー みこすり半劇場 統合(本編18巻 + ぶんか社テーマ別デラックス/文庫編=カップル/刑事/時代劇/青春/病院/ファミリー/タイフーン/ハリケーン、 同著者同社の同一作編集版)。 2026-06",
        renumber=False, exclude=excl_none, drop=excl_none),
    "hamtaro": dict(
        note="河井リツ子 とっとこハム太郎 統合(Wikipedia『独立作でなく同一世界観の連続作品』確証=でちゅ系続刊)。 アニメ版ハムージャは除外drop。 2026-06 検証済",
        renumber=False, exclude=lambda t: "ハムージャ" in t, drop=lambda t: "ハムージャ" in t),
    "keroro-gunsou": dict(
        note="吉崎観音 ケロロ軍曹 統合(本編 + green/pink/red=角川の同一作の版)。 スウェーデン語版(Keroro/ISBN978-91)はdrop。 2026-06",
        renumber=False, exclude=lambda t: t.strip() == "Keroro", drop=lambda t: t.strip() == "Keroro"),
    # tennis-no-ouji-sama / manga-greece-shinwa = defer(主ページ所在不明 / Wiki確証不足=安全のため分離保持)
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}

    mp = ROOT / "data/seeds/series-merge.yml"
    ms = io.open(mp, encoding="utf-8").read()
    nm_path = ROOT / "data/seeds/non-manga-drop.yml"
    nm_text = io.open(nm_path, encoding="utf-8").read()

    merge_blocks = []
    drop_lines = []
    for slug, d in DECISIONS.items():
        pages = col.get(slug, {}).get("pages", [])
        merge_keys = [k for k in pages if not d["exclude"](title_of(k))]
        drop_keys = [k for k in pages if d["drop"](title_of(k))]
        if len(merge_keys) < 2:
            print(f"  ! {slug}: merge_keys<2 skip"); continue
        # 既存チェック(代表key)
        if merge_keys[0] in ms:
            print(f"  - {slug}: 既存skip"); continue
        block = ["- merge_keys:"]
        for k in merge_keys:
            block.append(f'  - "{k}"')
        if d["renumber"]:
            block.append("  renumber: true")
        block.append(f'  note: {d["note"]}')
        merge_blocks.append("\n".join(block))
        for k in drop_keys:
            if k not in nm_text:
                drop_lines.append(f'  - series_key: "{k}"\n    reason: foreign_or_anime_edition\n    note: "(A)merge検証で除外: {title_of(k)[:30]}"')
        print(f"  ✓ {slug}: merge {len(merge_keys)} / drop {len(drop_keys)}")

    if merge_blocks:
        if not ms.endswith("\n"):
            ms += "\n"
        io.open(mp, "w", encoding="utf-8").write(ms + "\n".join(merge_blocks) + "\n")
    if drop_lines:
        if not nm_text.endswith("\n"):
            nm_text += "\n"
        io.open(nm_path, "w", encoding="utf-8").write(nm_text + "\n".join(drop_lines) + "\n")

    # 検証
    m = yaml.safe_load(io.open(mp, encoding="utf-8").read())
    n = yaml.safe_load(io.open(nm_path, encoding="utf-8").read())
    print(f"\nseries-merge.yml: {len(m)} entries (YAML OK)")
    print(f"non-manga-drop.yml: {len(n.get('non_manga') or [])} entries (YAML OK)")


if __name__ == "__main__":
    main()
