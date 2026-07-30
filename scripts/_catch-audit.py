#!/usr/bin/env python3
"""キャッチ検品柱: catch-ja.json(35,188 slug)の「別作品の内容が入っている」型を検出する。

背景(2026-07-30): あらすじ検品(synopsis-ja 全数292件裁定)の副産物として、
**synopsisは正しいのにcatchが別作品**という逆向きの型を4件発見([[catch_side_wrong_work_class]]):
  罪と罰(手塚)=食糧難の新種変異/救世団 / 純情クレイジーフルーツ=「その後を描く」続編扱い /
  +チック姉さん=書道部(実体は模型部) / THE IDOLM@STER=中性的な少年が男性アイドル。
catch は頁上部に出るため誤りの視認性が高い。設計は _synopsis-audit.py と同一。

段階:
  --build           頁マップ(slug→title/catch/synopsis)+caption素材(頁ISBN→楽天itemCaption)を.cacheへ
  --scan            全対象をスコアリング → docs/production-diagnostics/catch-audit.tsv
  --show <slug>     1件の裁定材料を全部表示(catch/synopsis/caption素材/推定相手)
  --fix <slug> --text-file <f>    catch-ja.json の該当キーを訂正(backup+changelog)
  --drop <slug>     素材ゼロ/矛盾で作れない時にキーを削除(=キャッチ欄を出さない。2026-07-30ユーザ裁定)
  --verdict <slug> <ok|fixed|hold|dropped> [--note ...]   裁定台帳へ追記(resume用)

スコア = catchの内容語トークン(漢字2+/カナ2+連)のうち、同頁の**独立証拠(title+巻caption)**に
出現する割合。0付近=別作品の疑い。★synopsisは証拠に入れない(catchと同時生成で同じ誤りを
共有しうるため。ただし参考として syn_ov 列に重なりを出す)。素材の無い頁は score=-1=判定不能で対象外。
"""
import sys, io, os, re, json, glob, argparse, pickle, unicodedata, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
try:
    from yaml import CSafeLoader as _L
except Exception:
    from yaml import SafeLoader as _L
import yaml

CATCH = ROOT / "data" / "seeds" / "catch-ja.json"
PAGEMAP = ROOT / ".cache" / "catch-audit-pagemap.json"
CAPS = ROOT / ".cache" / "catch-audit-captions.pkl"
TSV = ROOT / "docs" / "production-diagnostics" / "catch-audit.tsv"
LEDGER = ROOT / "docs" / "production-diagnostics" / "catch-audit-verdicts.jsonl"
CHANGELOG = ROOT / "data" / "seeds" / "enrich-requeue-changelog.jsonl"

TOK = re.compile(r"[一-鿿]{2,}|[ァ-ヴー]{2,}")


def norm(s):
    return unicodedata.normalize("NFKC", str(s or ""))


def tokens(s):
    return set(TOK.findall(norm(s)))


def build():
    catch = json.load(open(CATCH, encoding="utf-8"))
    pm = {}
    isbns_by_slug = {}
    files = sorted(glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")))
    print(f"頁走査 {len(files)}件(数分)...", flush=True)
    for i, p in enumerate(files):
        if i % 10000 == 0:
            print(f"  {i}...", flush=True)
        slug = os.path.basename(p)[:-4]
        if slug not in catch:
            continue
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
        except Exception:
            continue
        if not d:
            continue
        ib = []
        for e in d.get("editions") or []:
            for v in e.get("volumes") or []:
                if v.get("isbn13"):
                    ib.append(str(v["isbn13"]).replace("-", ""))
        pm[slug] = {"title": d.get("title"), "catch": d.get("catch") or "",
                    "synopsis": d.get("synopsis") or "", "authors": [a.get("name") for a in (d.get("authors") or [])]}
        isbns_by_slug[slug] = ib[:12]
    json.dump(pm, open(PAGEMAP, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"pagemap: {len(pm)} slug → {PAGEMAP}")
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
                done[str(r["slug"])] = r["verdict"]
            except Exception:
                pass
    return done


def scan():
    pm = json.load(open(PAGEMAP, encoding="utf-8"))
    catch = json.load(open(CATCH, encoding="utf-8"))
    slug_caps = pickle.load(open(CAPS, "rb")) if CAPS.exists() else {}
    done = load_ledger()
    title_tok = {s: tokens(v["title"]) for s, v in pm.items()}
    rows = []
    for slug, v in pm.items():
        if slug in done:
            continue
        text = catch.get(slug) or ""
        ct = tokens(text)
        if len(ct) < 4:
            continue  # 材料不足=判定対象外(短キャッチはエンリッチ柱のrequeue領域)
        cap = slug_caps.get(slug, "")
        syn_t = tokens(v["synopsis"])
        syn_ov = (len(ct & syn_t) / len(ct)) if syn_t else -1.0
        # ★2ストリーム(2026-07-30 実測でcaption単独だと偽陽性2,718件。証拠2系統の合議に締める)
        #   A: caption素材あり = title+caption と交差せず、かつ頁synopsisとも交差しない(両証拠が否定)
        #   B: caption素材なし = 頁synopsisが唯一の独立証拠。title+synopsis と交差しない(罪と罰型)
        if cap:
            ev = tokens(v["title"]) | tokens(cap)
            score = len(ct & ev) / len(ct)
            if score >= 0.12:
                continue
            if syn_ov >= 0.15:
                continue  # synopsisは支持=同一作品を別語彙で言い換えただけ(偽陽性)
            stream = "A"
        else:
            if syn_ov < 0:
                continue  # 証拠ゼロ=判定不能
            ev = tokens(v["title"]) | syn_t
            score = len(ct & ev) / len(ct)
            if score >= 0.12:
                continue
            stream = "B"
        best, bestn = "", 0
        for s2, tt in title_tok.items():
            if s2 == slug or not tt:
                continue
            n = len(ct & tt)
            if n > bestn:
                bestn, best = n, f"{s2}({pm[s2]['title']})"
        rows.append((score, syn_ov, stream, slug, v["title"], text[:60], v["synopsis"][:40],
                     best if bestn >= 2 else ""))
    rows.sort(key=lambda r: (r[0], r[1]))
    os.makedirs(TSV.parent, exist_ok=True)
    with TSV.open("w", encoding="utf-8", newline="\n") as f:
        f.write("score\tsyn_ov\tstream\tslug\ttitle\tcatch_head\tsynopsis_head\tswap_hint\n")
        for r in rows:
            f.write("\t".join([f"{r[0]:.3f}", f"{r[1]:.3f}"] +
                              [str(x).replace("\t", " ").replace("\n", " ") for x in r[2:]]) + "\n")
    na = sum(1 for r in rows if r[2] == "A")
    print(f"flag {len(rows)}件(A={na} caption系 / B={len(rows)-na} synopsis系・裁定済{len(done)}除外) → {TSV}")
    for r in rows[:10]:
        print(f"  {r[0]:.3f} syn={r[1]:.2f} [{r[2]}] {r[3]} | {r[4]} | catch={r[5][:34]}… | hint={r[7]}")


def show(slug):
    pm = json.load(open(PAGEMAP, encoding="utf-8"))
    catch = json.load(open(CATCH, encoding="utf-8"))
    slug_caps = pickle.load(open(CAPS, "rb")) if CAPS.exists() else {}
    v = pm.get(slug)
    if not v:
        print("slug不明(pagemapに無い)"); return
    print("slug:", slug, "| title:", v["title"], "| authors:", v.get("authors"))
    print("--- seed catch (catch-ja.json) ---"); print(catch.get(slug))
    print("--- 頁 synopsis ---"); print(v["synopsis"])
    print("--- caption素材(楽天) ---"); print(slug_caps.get(slug, "(無し)")[:900])


def _backup():
    import shutil
    bak = ROOT / ".cache" / f"catch-ja-bak-{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy(CATCH, bak)
    return bak


def fix(slug, text_file):
    text = open(text_file, encoding="utf-8").read().strip()
    assert text, "訂正文が空"
    catch = json.load(open(CATCH, encoding="utf-8"))
    assert slug in catch, f"slug {slug} はseedに無い"
    bak = _backup()
    old = catch[slug]
    catch[slug] = text
    json.dump(catch, open(CATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with CHANGELOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"op": "catch_ja_fix", "slug": slug, "old_head": old[:50],
                            "at": time.strftime("%Y-%m-%d"), "via": "_catch-audit"}, ensure_ascii=False) + "\n")
    print(f"fixed {slug} (backup={bak.name})。★反映は reflect-targeted で。")


def drop(slug):
    catch = json.load(open(CATCH, encoding="utf-8"))
    assert slug in catch, f"slug {slug} はseedに無い"
    bak = _backup()
    old = catch.pop(slug)
    json.dump(catch, open(CATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with CHANGELOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"op": "catch_ja_drop", "slug": slug, "old_head": old[:50],
                            "at": time.strftime("%Y-%m-%d"), "via": "_catch-audit"}, ensure_ascii=False) + "\n")
    print(f"dropped {slug} (backup={bak.name})。★反映は reflect-targeted で。")


def verdict(slug, v, note):
    with LEDGER.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"slug": slug, "verdict": v, "note": note,
                            "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
    print(f"verdict {slug}={v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--fix")
    ap.add_argument("--drop")
    ap.add_argument("--text-file")
    ap.add_argument("--verdict", nargs=2, metavar=("SLUG", "V"))
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
    elif a.drop:
        drop(a.drop)
    elif a.verdict:
        assert a.verdict[1] in ("ok", "fixed", "hold", "dropped"), "verdictは ok|fixed|hold|dropped"
        verdict(a.verdict[0], a.verdict[1], a.note)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
