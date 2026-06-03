"""(A)第3批: 確証済み merge を純粋追加。 [[merge-needs-external-proof]]準拠。"""
import io
import sys
import json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


MERGES = {
    "kenkaku-shoubai": dict(
        note="剣客商売(リイド社SP comics・大島やすいち画・池波正太郎原作)の巻断片統合(巻1-49本編 + 26-47/26-38/28-34重複範囲断片、 relations ALTERNATIVE:剣客商売)。 2026-06",
        exclude=lambda t: False),
    "onihei-hankachou": dict(
        note="鬼平犯科帳(リイド社SP comics・さいとうプロ/金成陽三郎)の巻断片統合(巻1-122本編 + 61-120等の断片)。 2026-06",
        exclude=lambda t: False),
    "takumi-kun-series": dict(
        note="タクミくんシリーズ(ごとうしのぶ原作・おおや和美画・あすかコミックスCL-DX・aid31770)統合=June pride/花散る夜に/季節はずれのカイダン/美貌のディテイル=同一BL連続シリーズの各巻。 2026-06",
        exclude=lambda t: False),
    "minami-no-teiou": dict(
        note="ミナミの帝王 ヤング編 統合(郷力也/天王寺大・Gコミックス、 ヤング編/利権空港スペシャル/利権空港の断片)。 本編187巻は別ページ保持。 2026-06",
        exclude=lambda t: t.strip() == "ミナミの帝王"),
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}
    mp = ROOT / "data/seeds/series-merge.yml"
    ms = io.open(mp, encoding="utf-8").read()
    blocks = []
    for slug, d in MERGES.items():
        pages = col.get(slug, {}).get("pages", [])
        mk = [k for k in pages if not d["exclude"](title_of(k))]
        if len(mk) < 2:
            print(f"  ! {slug}: merge<2 skip"); continue
        if mk[0] in ms:
            print(f"  - {slug}: 既存skip"); continue
        b = ["- merge_keys:"] + [f'  - "{k}"' for k in mk] + [f'  note: {d["note"]}']
        blocks.append("\n".join(b))
        print(f"  ✓ {slug}: merge {len(mk)}")
    if blocks:
        if not ms.endswith("\n"):
            ms += "\n"
        io.open(mp, "w", encoding="utf-8").write(ms + "\n".join(blocks) + "\n")
    m = yaml.safe_load(io.open(mp, encoding="utf-8").read())
    print(f"\nseries-merge.yml: {len(m)} entries (YAML OK)")


if __name__ == "__main__":
    main()
