#!/usr/bin/env python3
"""あらすじ検品柱: synopsis-ja.json(39,591件)の「別作品の内容が入っている」型を検出する。

背景(2026-07-30): ばけもの夜話づくし(105592)⇔凪のお暇(105614)の**相互スワップ**を発見。
生成batch内の対交換で、AniListリンクは正しいのにseed本文が別作品。同型が初期waveに潜在しうる。

段階:
  --build          頁マップ(aid→slug/title/catch/synopsis)+caption素材(頁ISBN→楽天itemCaption)を.cacheへ
  --scan           全対象をスコアリング → docs/production-diagnostics/synopsis-audit.tsv
                   (score昇順=怪しい順。swap_hint=synopsisが実は指していそうな別頁の推定)
  --show <aid>     1件の裁定材料を全部表示(synopsis/catch/caption素材/推定相手)
  --fix <aid> --text-file <f>   synopsis-ja.json の該当キーを訂正(backup+changelog。seed手編集禁止の代替)
  --verdict <aid> <ok|fixed|hold> [--note ...]   裁定台帳へ追記(resume用)

スコア = synopsisの内容語トークン(漢字2+/カナ2+連)のうち、同頁の独立証拠
(title+catch+巻caption)に出現する割合。0付近=別作品の疑い。
★catch/captionが乏しい頁は score=-1(判定不能)として別枠。無理に裁かない。
"""
import sys, io, os, re, json, glob, argparse, pickle, unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
try:
    from yaml import CSafeLoader as _L
except Exception:
    from yaml import SafeLoader as _L
import yaml

SYN = ROOT / "data" / "seeds" / "synopsis-ja.json"
PAGEMAP = ROOT / ".cache" / "synopsis-audit-pagemap.json"
CAPS = ROOT / ".cache" / "synopsis-audit-captions.pkl"
TSV = ROOT / "docs" / "production-diagnostics" / "synopsis-audit.tsv"
LEDGER = ROOT / "docs" / "production-diagnostics" / "synopsis-audit-verdicts.jsonl"
CHANGELOG = ROOT / "data" / "seeds" / "enrich-requeue-changelog.jsonl"

TOK = re.compile(r"[一-鿿]{2,}|[ァ-ヴー]{2,}")


def norm(s):
    return unicodedata.normalize("NFKC", str(s or ""))


def tokens(s):
    return set(TOK.findall(norm(s)))


def build():
    syn = json.load(open(SYN, encoding="utf-8"))
    pm = {}
    isbns_by_slug = {}
    files = sorted(glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")))
    print(f"頁走査 {len(files)}件(数分)...", flush=True)
    for i, p in enumerate(files):
        if i % 10000 == 0:
            print(f"  {i}...", flush=True)
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
        except Exception:
            continue
        if not d:
            continue
        aid = d.get("anilist_id")
        if not aid or str(aid) not in syn:
            continue
        slug = os.path.basename(p)[:-4]
        ib = []
        for e in d.get("editions") or []:
            for v in e.get("volumes") or []:
                if v.get("isbn13"):
                    ib.append(str(v["isbn13"]).replace("-", ""))
        pm[str(aid)] = {"slug": slug, "title": d.get("title"), "catch": d.get("catch") or "",
                        "synopsis": d.get("synopsis") or ""}
        isbns_by_slug[slug] = ib[:12]  # 先頭12巻で十分(素材用)
    json.dump(pm, open(PAGEMAP, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"pagemap: {len(pm)} aid → {PAGEMAP}")
    # caption素材: 楽天cache 1パス
    need = {i for v in isbns_by_slug.values() for i in v}
    print(f"caption回収: 対象ISBN {len(need):,} / 楽天cache 1パス(数分)...", flush=True)
    caps = {}
    for path in (ROOT / ".cache" / "rakuten-isbn-delta.jsonl", ROOT / ".cache" / "rakuten-isbn.jsonl"):
        if not path.exists():
            continue
        with path.open(encoding="utf-8", errors="replace") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                item = r.get("item") or r
                isbn = str(r.get("isbn") or item.get("isbn") or "").replace("-", "")
                if isbn in need and isbn not in caps:
                    c = str(item.get("itemCaption") or "")
                    if c:
                        caps[isbn] = c[:400]
    slug_caps = {}
    for slug, ibs in isbns_by_slug.items():
        t = " ".join(caps[i] for i in ibs if i in caps)
        if t:
            slug_caps[slug] = t[:1600]
    pickle.dump(slug_caps, open(CAPS, "wb"))
    print(f"captions: {len(slug_caps)} slug → {CAPS}")


def load_ledger():
    done = {}
    if LEDGER.exists():
        for ln in LEDGER.open(encoding="utf-8"):
            try:
                r = json.loads(ln)
                done[str(r["aid"])] = r["verdict"]
            except Exception:
                pass
    return done


def scan():
    pm = json.load(open(PAGEMAP, encoding="utf-8"))
    slug_caps = pickle.load(open(CAPS, "rb")) if CAPS.exists() else {}
    done = load_ledger()
    # swap相手推定用: title token → aid
    title_tok = {aid: tokens(v["title"]) for aid, v in pm.items()}
    rows = []
    for aid, v in pm.items():
        if aid in done:
            continue
        syn_t = tokens(v["synopsis"])
        if len(syn_t) < 4:
            continue  # 材料不足=判定対象外
        ev = tokens(v["title"]) | tokens(v["catch"]) | tokens(slug_caps.get(v["slug"], ""))
        has_ev = bool(v["catch"]) or v["slug"] in slug_caps
        if not has_ev:
            score = -1.0
        else:
            score = len(syn_t & ev) / len(syn_t)
        if score >= 0.12 or score < 0:
            continue  # 交差が一定以上=正常扱い(検品対象外)。-1=判定不能は別途
        # swap相手推定: このsynopsisのトークンを title に多く含む別頁
        best, bestn = "", 0
        for a2, tt in title_tok.items():
            if a2 == aid or not tt:
                continue
            n = len(syn_t & tt)
            if n > bestn:
                bestn, best = n, f"{pm[a2]['slug']}({pm[a2]['title']})"
        rows.append((score, aid, v["slug"], v["title"], v["synopsis"][:60], v["catch"][:40], best if bestn >= 2 else ""))
    rows.sort(key=lambda r: r[0])
    os.makedirs(TSV.parent, exist_ok=True)
    with TSV.open("w", encoding="utf-8", newline="\n") as f:
        f.write("score\taid\tslug\ttitle\tsynopsis_head\tcatch_head\tswap_hint\n")
        for r in rows:
            f.write("\t".join([f"{r[0]:.3f}"] + [str(x).replace("\t", " ").replace("\n", " ") for x in r[1:]]) + "\n")
    print(f"flag {len(rows)}件(裁定済{len(done)}除外) → {TSV}")
    print("上位10:")
    for r in rows[:10]:
        print(f"  {r[0]:.3f} {r[2]} | {r[3]} | syn={r[4][:36]}… | hint={r[6]}")


def show(aid):
    pm = json.load(open(PAGEMAP, encoding="utf-8"))
    slug_caps = pickle.load(open(CAPS, "rb")) if CAPS.exists() else {}
    v = pm.get(str(aid))
    if not v:
        print("aid不明(pagemapに無い)"); return
    syn = json.load(open(SYN, encoding="utf-8"))
    print("slug:", v["slug"], "| title:", v["title"])
    print("--- seed synopsis (synopsis-ja.json) ---"); print(syn.get(str(aid)))
    print("--- catch ---"); print(v["catch"])
    print("--- caption素材(楽天) ---"); print(slug_caps.get(v["slug"], "(無し)")[:800])


def fix(aid, text_file):
    text = open(text_file, encoding="utf-8").read().strip()
    assert text, "訂正文が空"
    syn = json.load(open(SYN, encoding="utf-8"))
    assert str(aid) in syn, f"aid {aid} はseedに無い"
    import shutil, time
    bak = ROOT / ".cache" / f"synopsis-ja-bak-{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy(SYN, bak)
    old = syn[str(aid)]
    syn[str(aid)] = text
    json.dump(syn, open(SYN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with CHANGELOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"op": "synopsis_ja_fix", "aid": str(aid), "old_head": old[:50],
                            "at": __import__("time").strftime("%Y-%m-%d"), "via": "_synopsis-audit"},
                           ensure_ascii=False) + "\n")
    print(f"fixed aid={aid} (backup={bak.name})。★反映は該当slugを reflect-targeted で。")


def verdict(aid, v, note):
    with LEDGER.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"aid": str(aid), "verdict": v, "note": note,
                            "at": __import__("time").strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
    print(f"verdict {aid}={v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--fix")
    ap.add_argument("--text-file")
    ap.add_argument("--verdict", nargs=2, metavar=("AID", "V"))
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.build:
        build()
    elif a.scan:
        scan()
    elif a.show:
        show(a.show)
    elif a.fix:
        assert a.text_file, "--text-file 必須"
        fix(a.fix, a.text_file)
    elif a.verdict:
        assert a.verdict[1] in ("ok", "fixed", "hold"), "verdictは ok|fixed|hold"
        verdict(a.verdict[0], a.verdict[1], a.note)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
