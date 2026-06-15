"""[修正・ログ付] flag 23作の決着(慎重・per-case)。
RENAME=単独候補orその作品の本編 → 無印slug化。LEAVE=同名別作の集合/本編不在 → 無印作らず(正)としてログ。
非破壊可逆。--apply で適用(既定dry-run)。
"""
import os, json, yaml, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
APPLY = "--apply" in sys.argv
NOW = "2026-06-16"
LAYERS = ["data/manga", "data/manga.v2", ".preview-data/manga"]
LOG, OVR, ALI = "data/seeds/_change-log.jsonl", "data/seeds/slug-overrides.yml", "data/slug-aliases.yml"

RENAME = {  # old_slug -> bare
    "jin-2011": "jin",
    "bara-monogatari-2008": "bara-monogatari",
    "black-jack-kuroi-ishi-2012": "black-jack-kuroi-ishi",
    "cashmere-2001": "cashmere",
    "dai-chouhen-doraemon-1984": "dai-chouhen-doraemon",
    "deep-impact-2007": "deep-impact",
    "inma-no-ikenie-2018": "inma-no-ikenie",
    "kibun-wa-hardboiled-mizushimat": "kibun-wa-hardboiled",
    "ten-yori-takaku-1998": "ten-yori-takaku",
}
LEAVE = {  # base -> reason
    "bakudan": "同名別作の集合(爆男/ばくだん/BAKUDAN/爆弾…)・提案本編は本番不在",
    "en": "同名別作の集合(宴/艶/縁/アンパッサン…)",
    "fetish": "同題別作2件(フェティッシュ・別作者)=無印を決められない",
    "kujira": "同名別作の集合(クジラの子ら/くじらの親子…)",
    "kyou-kara-hitman-special": "副題違いの2分冊(あとしまつ/第2章)=本編無印なし",
    "majo": "魔女系の巨大同名集合=無印不可",
    "message": "同題別作2件(萩尾望都/麻生歩)",
    "nippon-no-rekishi": "日本の歴史 多数の別シリーズ/版=無印不可",
    "pocket-monster-special": "本番は赤緑青編2巻のみ=本編ポケスペ不在(Type B・要復旧調査)",
    "refrain": "同題別作2件(ささやななえこ/岸裕子)",
    "seasons": "同題別作2件(竹宮ジン/高橋しん)",
    "spring": "同名別作の集合(青春兵器/SPRING MAN…)",
    "tenchi-muyou": "天地無用系の別作集合(魎皇鬼/砂沙美…)=単一本編なし",
    "yuuwaku": "誘惑+◯◯ の巨大同名集合=無印不可",
}

print(f"=== RENAME {len(RENAME)} / LEAVE {len(LEAVE)} ===")
for o, n in RENAME.items():
    print(f"  RENAME {o} -> {n}")
for b, r in LEAVE.items():
    print(f"  LEAVE  {b}: {r}")
if not APPLY:
    print("\n(dry-run。--apply で適用)")
    sys.exit(0)

ali = yaml.safe_load(open(ALI, encoding="utf-8")) or {} if os.path.exists(ALI) else {}
ovr = yaml.safe_load(open(OVR, encoding="utf-8")) or {} if os.path.exists(OVR) else {}
ovr.setdefault("overrides", {})
logf = open(LOG, "a", encoding="utf-8")
n_ren = 0
for old, bare in RENAME.items():
    for ly in LAYERS:
        op, np = os.path.join(ly, old + ".yml"), os.path.join(ly, bare + ".yml")
        if not os.path.exists(op) or os.path.exists(np):
            continue
        d = yaml.safe_load(open(op, encoding="utf-8")) or {}
        d["slug"] = bare
        with open(np, "w", encoding="utf-8") as w:
            yaml.safe_dump(d, w, allow_unicode=True, sort_keys=False, width=10000)
        os.remove(op)
    ali[old] = bare
    ovr["overrides"][old] = {"slug": bare, "reason": "flag精査:単独候補/本編を無印化", "at": NOW}
    logf.write(json.dumps({"ts": NOW, "action": "slug_rename", "target": bare, "detected_by": "manual.curator(flag精査)",
                           "source": "slug-final-integrated.tsv+目視", "before": {"slug": old}, "after": {"slug": bare},
                           "checks": ["base接頭の本番候補を全件確認", "単独 or 圧倒的本編", "無印slug空"], "confidence": "high",
                           "undo": "override/alias削除+ファイル名を元へ", "state": "applied"}, ensure_ascii=False) + "\n")
    n_ren += 1
for base, reason in LEAVE.items():
    logf.write(json.dumps({"ts": NOW, "action": "no_action", "target": base, "detected_by": "manual.curator(flag精査)",
                           "reason": reason, "decision": "無印slugは作らない(正しい/別作集合/本編不在)", "state": "reviewed"}, ensure_ascii=False) + "\n")
logf.close()
with open(ALI, "w", encoding="utf-8") as w:
    yaml.safe_dump(ali, w, allow_unicode=True, sort_keys=True, width=10000)
with open(OVR, "w", encoding="utf-8") as w:
    yaml.safe_dump(ovr, w, allow_unicode=True, sort_keys=False, width=10000)
print(f"\n適用: rename {n_ren} / no_action {len(LEAVE)} をログ。")
