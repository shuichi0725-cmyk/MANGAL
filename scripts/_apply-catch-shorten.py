"""短縮版を catch-ja.json に上書き適用(慎重に検証)。
受理条件: 25<=len<=75 かつ 元より短い。 それ以外は元を保持し flag。
適用後、全体の >80 / >72 残数を再検証。"""
import json, io, glob

SEED = "data/seeds/catch-ja.json"
catch = json.load(io.open(SEED, encoding="utf-8"))

short = {}
for f in glob.glob(".cache/catch-short-out/b-*.json"):
    try:
        short.update(json.load(io.open(f, encoding="utf-8")))
    except Exception as e:
        print("PARSE FAIL", f, e)

applied = 0
rej_short = rej_long = rej_notshorter = rej_nokey = 0
not_ideal = []  # 69-75字: 受理だが理想超
for slug, new in short.items():
    new = (new or "").strip()
    if slug not in catch:
        rej_nokey += 1
        continue
    old_len = len(catch[slug])
    if not new or len(new) < 25:
        rej_short += 1
        continue
    if len(new) > 78:
        rej_long += 1
        continue
    if len(new) >= old_len:
        rej_notshorter += 1
        continue
    catch[slug] = new
    applied += 1
    if len(new) > 68:
        not_ideal.append((slug, len(new)))

out = {k: catch[k] for k in sorted(catch.keys())}
json.dump(out, io.open(SEED, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
io.open(SEED, "a", encoding="utf-8").write("\n")

lens = [len(v) for v in out.values()]
print(f"適用={applied} / 弾いた: 短すぎ{rej_short} 縮まらず{rej_notshorter} まだ長い(>75){rej_long} キー無{rej_nokey}")
print(f"受理だが69-75字={len(not_ideal)}")
print(f"--- 全体再検証 --- 総数={len(out)} 平均={sum(lens)//len(lens)} 最長={max(lens)}")
print(f"  80字超 残={sum(1 for x in lens if x>80)} / 72字超={sum(1 for x in lens if x>72)}")
