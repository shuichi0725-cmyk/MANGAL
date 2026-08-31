# -*- coding: utf-8 -*-
"""試し読みアンカーのラノベ/小説混入検査 (2026-08-20 領民0人型=ユーザ発見)。

型: ラノベ原作コミカライズ頁で、BookLive検索が**小説版**のtitle_idを拾い、試し読みが
ラノベになる(領民0人スタートの辺境領主様=556239(ラノベ)→正=621456(コミカライズ))。

検査 = 危険集合(アンカー済み∩原作クレジット持ち頁)の各title_idについて、BookLive商品頁の
JSON-LD category/genre を読み、ライトノベル/文芸/小説ならflag。
- 台帳 = .cache/tameshiyomi/ln-audit.jsonl (title_id単位・再開可能・campaign後の再実行は差分だけ)
- 出力 = docs/production-diagnostics/tameshiyomi-ln-anchors.tsv
- ★レート = _booklive 共通ゲート(2026-08-31: 札・直列2.0秒・日次上限。旧8並列は規制事故と同型なので廃止)。
  是正はflagを見て別途(検索し直し=作画者クエリ+category=マンガ検証)。
"""
import glob
import io
import json
import os
import re
import sys
import time

import _booklive
from _booklive import Blocked, CapReached

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, ".cache", "tameshiyomi", "ln-audit.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "tameshiyomi-ln-anchors.tsv")
NOVEL_CAT = re.compile(r"ライトノベル|ラノベ|文芸|小説|BLノベル|TLノベル")


def category_of(tid: str):
    """→ (catgen, ptitle)。404は("(404)","")=定まった否定として台帳に書く。他の異常はBlocked。"""
    st, html = _booklive.request(f"https://booklive.jp/product/index/title_id/{tid}/vol_no/001")
    if st != 200:
        return "(404)", ""
    cat = re.search(r'"category":\s*"([^"]+)"', html)
    gen = re.search(r'"genre":\s*"([^"]+)"', html)
    t = re.search(r'property="og:title" content="([^"|]+)', html)
    return ((cat.group(1) if cat else "") + "/" + (gen.group(1) if gen else ""),
            t.group(1).strip() if t else "")


def main() -> None:
    _booklive.assert_not_blocked()   # ★入口でも見る=66k走査を始める前に落とす
    anchors = {}
    for line in io.open(os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl"), encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("title_id"):
            anchors[r["slug"]] = r["title_id"]
    # ★--all(2026-08-20 ユーザGO①): 全アンカーを検査(原作クレジット欠け頁の取り漏らしを消す)。
    #   無印=危険集合(原作クレジット持ち)のみ。台帳はtitle_id単位なので--allでも検査済みはskip。
    if "--all" in sys.argv:
        risk = sorted(anchors.items())
    else:
        pat = re.compile(r"(?m)^original_authors:\n- name")
        risk = []
        for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
            t = io.open(f, encoding="utf-8").read()
            m = re.search(r"(?m)^slug: (.+)", t)
            slug = m.group(1).strip() if m else ""
            if slug in anchors and pat.search(t):
                risk.append((slug, anchors[slug]))
    checked = {}
    if os.path.exists(LEDGER):
        for line in io.open(LEDGER, encoding="utf-8"):
            try:
                r = json.loads(line)
                checked[r["tid"]] = r
            except Exception:
                pass
    todo = [(s, t) for s, t in risk if t not in checked]
    print(f"危険集合 {len(risk)} / 検査済 {len(risk) - len(todo)} / 残 {len(todo)}", flush=True)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    # ★直列のみ(2026-08-31 是正): 旧実装は「BookLive CDNだから軽いGETなので並列可」の思い込みで
    #   8並列・間隔なし=2026-08-29規制事故と同型だった。以後 _booklive 共通ゲートを通す
    #   (札・2.0秒/件・日次上限)。Blocked=台帳に書かず即中断(exit 2)、上限到達=正常打ち切り。
    with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as w:
        for i, (slug, tid) in enumerate(todo):
            try:
                catgen, ptitle = category_of(tid)
            except CapReached as e:
                print(f"★打ち切り: {e}(台帳は逐次保存済み・続きは次回)", flush=True)
                break
            except Blocked as e:
                print(f"★中断: BookLiveから200/404以外の応答 ({e})。台帳には書かない。",
                      file=sys.stderr, flush=True)
                sys.exit(2)
            w.write(json.dumps({"tid": tid, "slug": slug, "cat": catgen, "ptitle": ptitle,
                                "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
            w.flush()
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(todo)}", flush=True)
    # 集計(全台帳から)。★現アンカーと一致する行のみflag(是正済みの旧title_id行を除外=偽陽性防止)
    flagged = []
    for line in io.open(LEDGER, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if NOVEL_CAT.search(r.get("cat") or "") and anchors.get(r["slug"]) == r["tid"]:
            flagged.append(r)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as w:
        w.write("slug\ttitle_id\tカテゴリ\t商品題\n")
        for r in sorted(flagged, key=lambda r: r["slug"]):
            w.write(f"{r['slug']}\t{r['tid']}\t{r['cat']}\t{r['ptitle']}\n")
    print(f"flag(ラノベ/小説アンカー): {len(flagged)} → {OUT}")


if __name__ == "__main__":
    main()
