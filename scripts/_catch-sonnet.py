#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""書影あり・キャッチ無しの頁に、手元の材料からキャッチを書かせる道具 (= 2026-11-13 新設)。

目的: 羅針盤は「書影+キャッチ」の頁しか載せない(app/compass/compass.ts isEligible)。 条件は緩めず、
  材料の在る頁にキャッチを書いて行き先を増やす [[feedback_compass_reach_via_data_quality]]。
型: 会話でモデルを運転しない。 道具がモデルを1作ずつ直接呼び(_lean_claude)、モデルは「書く/見送る」を
  答えるだけ。 検査(字数・丸写し・材料に無い数字/カタカナ語・文末・電子版の宣伝語・根拠の一字一句)は道具。
  ★この道具は seed にも頁にも書かない。 回答は .cache/catch-sonnet/answers.jsonl に貯まる(再開可)。
  点検(Opus)の後、 emit で既存の適用器 _apply-enrich-batch.py の入力形に出す。

  python scripts/_catch-sonnet.py stage            # 対象と材料を1パスで集める(Kobo以外の材料)
  python scripts/_catch-sonnet.py stage --kobo     # Kobo電子版の紹介文(完全一致)も材料にする
  python scripts/_catch-sonnet.py run --limit 200  # 続きから N 作(失敗したら何も記録せず止まる)
  python scripts/_catch-sonnet.py report           # 進み具合と検査の内訳
  python scripts/_catch-sonnet.py emit 9800        # 合格分を batch-9800 として出す(適用は別コマンド)
"""
import argparse, collections, datetime, html, io, json, os, re, sys
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
WORK = os.path.join(ROOT, ".cache", "catch-sonnet")
WORKLIST = os.path.join(WORK, "work.jsonl")
ANSWERS = os.path.join(WORK, "answers.jsonl")
HOLD = os.path.join(ROOT, "docs", "production-diagnostics", "enrich-hold.tsv")
MODEL = "claude-sonnet-5-5"
CATCH_MIN, CATCH_MAX = 48, 74   # 規格50-70 ±2(_apply-enrich-batch.py と同じ)
BLOCK = 0.55                     # 材料との8-gram重複。 これ以上は丸写し
MINLEN = 60                      # 材料1本の最低字数(あらすじだけ40)
L = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

AD = re.compile(r"電子化|電子書籍|電子版|電子配信|配信|紙のコミックス|単行本未収録|未収録|復刻|復活|シリーズ累計|万部|重版")
KATA = re.compile(r"[ァ-ヴー]{3,}")
NUM = re.compile(r"[0-90-9]+")
CUT_END = re.compile(r"(の|が|を|に|は|と|で|も|や|、|,)$")

SYSTEM = "あなたは漫画データベースの編集者。指示された JSON の形だけで答える。"
RULES = """漫画データベースの一覧に出す「キャッチ」(惹句)を1本書く。材料はその作品の紹介文。

■ 書き方
- 50〜70字(全角で数える)。一覧で足を止めさせるフック。「〜する物語。」のような説明調は避ける。体言止め可。煽りすぎない。
- ★材料に書かれていることだけで書く。人物の名前・肩書き・関係・数字・地名・出来事を足さない。筋を想像で補わない。
- 物語の入口(1〜2巻の範囲)だけ。後半の展開・結末は書かない。
- 材料の文をそのまま写さない(言い換える)。文の途中で切らない。
- 電子版の商品説明(電子化・配信・紙の単行本未収録・復刻 等)や売り文句(累計○万部 等)は使わない。
- 題名の「Ⅱ」「2」を巻数と読み違えない。「表題作ほかN編」の数を自分で数え直さない(書くなら材料のとおり)。

■ 見送る(decision="skip")場合 = 無理に書かない
- 材料に物語の中身(誰が・どんな状況で・何をする)が無い(惹句だけ・収録作の題名や話数の一覧だけ・宣伝だけ)
- 材料が3巻以降の展開しか書いていない
- アンソロジー/複数作家の本・傑作選/選集/自選/名作集/総集編・合本/BOX・画集/イラスト集/ファンブック/資料集
- 映画やアニメを漫画にした本・絵本・学習参考書/解説本/事典・小説/評論/対談
- 原作小説の紹介文など、この漫画そのものの紹介でない疑いがある / 題名・著者と材料が別の作品に見える
- 露骨な性描写の説明が中心で、一般の一覧に出す文にできない

■ 答え
- decision: "write" か "skip"
- catch: 書いたキャッチ(skip の時は空文字)
- basis: キャッチの根拠にした材料の一節を、★一字一句そのまま 12〜40字で抜き出す(skip の時は空文字)
- reason: skip の理由を短く(write の時は空文字)
"""
SCHEMA = {"type": "object", "required": ["decision", "catch", "basis", "reason"], "additionalProperties": False,
          "properties": {"decision": {"type": "string", "enum": ["write", "skip"]}, "catch": {"type": "string"},
                         "basis": {"type": "string"}, "reason": {"type": "string"}}}


def nows():
    return datetime.datetime.now().isoformat(timespec="seconds")


def squash(s):
    return re.sub(r"\s", "", s or "")


def ngram_overlap(a, b, k=8):
    a, b = squash(a), squash(b)
    if len(a) < k or len(b) < k:
        return 0.0
    bs = {b[i:i + k] for i in range(len(b) - k + 1)}
    return sum(1 for i in range(len(a) - k + 1) if a[i:i + k] in bs) / max(1, len(a) - k + 1)


def z2h(s):
    return s.translate(str.maketrans("0123456789", "0123456789"))


def check(catch, basis, w):
    """→ 検査で落ちた理由の一覧(空 = 合格)。 w = work.jsonl の1行"""
    mats = [m["text"] for m in w["materials"]]
    hay = squash(" ".join(mats))
    known = hay + squash(w["title"]) + squash("".join(w["authors"]))
    c = catch.strip()
    bad = []
    if not (CATCH_MIN <= len(c) <= CATCH_MAX):
        bad.append(f"字数{len(c)}(50〜70字にする)")
    ov = max([ngram_overlap(c, m) for m in mats] or [0])
    if ov >= BLOCK:
        bad.append(f"材料の丸写し(重なり{ov:.2f})。言い換える")
    if CUT_END.search(c):
        bad.append("文の途中で切れている")
    m = AD.search(c)
    if m:
        bad.append(f"電子版の商品説明・売り文句の語「{m.group(0)}」")
    kh = z2h(known)
    for n in set(NUM.findall(c)):
        if z2h(n) not in kh:
            bad.append(f"材料に無い数字「{n}」")
    for k in set(KATA.findall(c)):
        if k not in known:
            bad.append(f"材料に無いカタカナ語「{k}」")
    b = squash(basis)
    if len(b) < 10 or b not in hay:
        bad.append("basis が材料の一字一句の抜き出しになっていない")
    return bad, round(ov, 2)


# ───────────────────────── stage ─────────────────────────

def stage(a):
    os.makedirs(WORK, exist_ok=True)
    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    rows = [dict(zip(idx["f"], r)) for r in idx["d"]]
    cat = json.load(io.open(os.path.join(ROOT, "data", "manga-catch-index.json"), encoding="utf-8"))
    seed = json.load(io.open(os.path.join(ROOT, "data", "seeds", "catch-ja.json"), encoding="utf-8"))
    hold = {l.split("\t")[0] for l in io.open(HOLD, encoding="utf-8")}
    ov = (yaml.safe_load(io.open(os.path.join(ROOT, "data", "seeds", "slug-overrides.yml"), encoding="utf-8")) or {}).get("overrides", {})
    pub2src = {v.get("slug"): k for k, v in ov.items() if isinstance(v, dict) and v.get("slug")}

    def src_of(pub):
        for s in (pub, pub2src.get(pub)):
            if s and os.path.exists(os.path.join(ROOT, "data", "manga.v2", s + ".yml")):
                return s
        return None

    info, isb = {}, collections.defaultdict(list)
    n_tgt = 0
    for m in rows:
        pub = m["slug"]
        if not m.get("cover") or cat.get(pub):
            continue
        n_tgt += 1
        src = src_of(pub)
        if not src or pub in hold or src in hold or src in seed:
            continue
        y = yaml.load(io.open(os.path.join(ROOT, "data", "manga.v2", src + ".yml"), encoding="utf-8"), Loader=L) or {}
        if (y.get("catch") or "").strip():
            continue
        mats = []
        syn = str(y.get("synopsis") or "").strip()
        if len(syn) >= 40:
            mats.append({"kind": "頁のあらすじ", "text": syn})
        for e in y.get("editions") or []:
            for vs in [e.get("volumes") or []] + [x.get("volumes") or [] for x in e.get("versions") or []]:
                for v in vs:
                    n = v.get("number")
                    if v.get("isbn13"):
                        isb[str(v["isbn13"])].append((pub, n))
                    d = str(v.get("description") or "").strip()
                    if n in (1, 2) and len(d) >= MINLEN:
                        mats.append({"kind": f"{n}巻の説明", "text": d})
        info[pub] = {"slug": pub, "src": src, "title": str(y.get("title") or m.get("title") or ""), "authors": [x.get("name") for x in (y.get("authors") or []) if isinstance(x, dict) and x.get("name")],
                     "year": m.get("year_started"), "vols": m.get("max_edition_volumes") or m.get("total_volumes") or 0, "materials": mats}
    # 楽天の紙の本の紹介文(1〜2巻だけ・宣伝だけの文は道具では落とさず、モデルに見送らせる)
    for p in (".cache/rakuten-isbn.jsonl", ".cache/rakuten-isbn-delta.jsonl"):
        for line in io.open(os.path.join(ROOT, p), encoding="utf-8"):
            mm = re.search(r'"isbn":\s*"(97\d{11})"', line)
            if not mm or mm.group(1) not in isb:
                continue
            try:
                it = json.loads(line).get("item") or {}
            except ValueError:
                continue
            c = html.unescape((it.get("itemCaption") or "").strip())
            if len(c) < MINLEN:
                continue
            for pub, n in isb[mm.group(1)]:
                if n in (1, 2):
                    info[pub]["materials"].append({"kind": f"楽天 {n}巻の紹介文", "text": c})
    if a.kobo:
        for line in io.open(os.path.join(ROOT, ".cache", "kobo-caption", "harvest.jsonl"), encoding="utf-8"):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            w = info.get(o.get("slug"))
            if not w:
                continue
            for mt in o.get("matched") or []:
                c = str(mt.get("cap") or "").strip()
                if mt.get("match") == "strict" and len(c) >= MINLEN and (mt.get("vol") in (None, 1, 2)):
                    w["materials"].append({"kind": f"電子版 {mt.get('vol') or ''}巻の紹介文", "text": c})
    out = []
    for w in info.values():
        seen, ms = set(), []
        for mt in w["materials"]:      # 同じ文の重複を落とす
            k = squash(mt["text"])
            if k not in seen:
                seen.add(k); ms.append(mt)
        w["materials"] = ms[:6]
        if ms:
            out.append(w)
    out.sort(key=lambda w: w["slug"])
    with io.open(WORKLIST, "w", encoding="utf-8") as f:
        for w in out:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")
    kinds = collections.Counter(mt["kind"].split(" ")[0] for w in out for mt in w["materials"])
    print(f"書影あり・キャッチ無し {n_tgt} / 頁あり・保留台帳に無い {len(info)} / 材料あり = 対象 {len(out)}")
    print("材料の種類(延べ):", dict(kinds))
    print("→", WORKLIST)


# ───────────────────────── run ─────────────────────────

def load_answers():
    d = {}
    if os.path.exists(ANSWERS):
        for l in io.open(ANSWERS, encoding="utf-8"):
            if l.strip():
                r = json.loads(l); d[r["slug"]] = r
    return d


def prompt_of(w, retry=None):
    p = [RULES, "■ 作品", f"題名: {w['title']}", f"著者: {'・'.join(w['authors']) or '(不明)'}",
         f"巻数: {w['vols'] or '?'} / 開始年: {w['year'] or '?'}", "", "■ 材料"]
    for i, mt in enumerate(w["materials"], 1):
        p.append(f"[{i}] {mt['kind']}: {mt['text']}")
    if retry:
        p += ["", "■ 前の答えは検査で落ちた。直して答え直す(直せないなら skip)", f"前のキャッチ: {retry[0]}"] + [f"- {x}" for x in retry[1]]
    return "\n".join(p)


def run(a):
    import _lean_claude
    works = [json.loads(l) for l in io.open(WORKLIST, encoding="utf-8") if l.strip()]
    done = load_answers()
    todo = [w for w in works if w["slug"] not in done][: a.limit]
    print(f"対象 {len(works)} / 済 {len(done)} / 今回 {len(todo)}(model={a.model})", flush=True)
    cost = 0.0
    for i, w in enumerate(todo, 1):
        try:
            ans, use = _lean_claude.ask(prompt_of(w), SCHEMA, a.model, system=SYSTEM, timeout=300)
            tries, bad, ov = 1, [], 0.0
            if ans["decision"] == "write":
                bad, ov = check(ans["catch"], ans["basis"], w)
                if bad:   # 1回だけ、落ちた理由を渡して書き直させる
                    first = ans["catch"]
                    ans, u2 = _lean_claude.ask(prompt_of(w, (first, bad)), SCHEMA, a.model, system=SYSTEM, timeout=300)
                    tries = 2
                    use["cost_usd"] = (use.get("cost_usd") or 0) + (u2.get("cost_usd") or 0)
                    use["sec"] = round(use["sec"] + u2["sec"], 1)
                    bad, ov = check(ans["catch"], ans["basis"], w) if ans["decision"] == "write" else ([], 0.0)
        except _lean_claude.LeanError as e:
            print(f"★止まる(何も記録しない): {w['slug']}: {e}", flush=True)
            sys.exit(3)
        status = "skip" if ans["decision"] == "skip" else ("fail" if bad else "ok")
        r = {"slug": w["slug"], "src": w["src"], "status": status, "catch": ans["catch"].strip(), "basis": ans["basis"].strip(),
             "reason": ans["reason"].strip(), "bad": bad, "overlap8": ov, "tries": tries, "model": a.model,
             "sec": use["sec"], "cost_usd": use.get("cost_usd"), "at": nows()}
        with io.open(ANSWERS, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        cost += use.get("cost_usd") or 0
        if i % 20 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} 累計${cost:.2f}", flush=True)
    report(a)


def report(a):
    works = sum(1 for l in io.open(WORKLIST, encoding="utf-8") if l.strip())
    d = load_answers()
    c = collections.Counter(r["status"] for r in d.values())
    print(f"対象 {works} / 済 {len(d)}: 書けた {c['ok']} / 見送り {c['skip']} / 検査落ち {c['fail']}"
          f" / 書き直し1回 {sum(1 for r in d.values() if r['tries'] > 1)}"
          f" / 費用 ${sum(r.get('cost_usd') or 0 for r in d.values()):.2f} / 平均 {sum(r['sec'] for r in d.values()) / max(1, len(d)):.0f}秒")
    for st, key in (("skip", "reason"), ("fail", "bad")):
        cc = collections.Counter()
        for r in d.values():
            if r["status"] == st:
                v = r[key]
                for x in (v if isinstance(v, list) else [v]):
                    cc[re.sub(r"「.*?」|[0-9.]+", "", x)[:22]] += 1
        if cc:
            print(f"  [{st}]", cc.most_common(8))


def emit(a):
    """合格分を既存の適用器の入力形に出す(seed には書かない)。 適用 = python scripts/_apply-enrich-batch.py N [--apply]"""
    works = {json.loads(l)["slug"]: json.loads(l) for l in io.open(WORKLIST, encoding="utf-8") if l.strip()}
    ok = [r for r in load_answers().values() if r["status"] == "ok"]
    out = {r["src"]: {"catch": r["catch"]} for r in ok}
    items = [{"slug": r["src"], "captions": [{"caption": m["text"]} for m in works[r["slug"]]["materials"]]} for r in ok if r["slug"] in works]
    p1 = os.path.join(ROOT, "data", "enrich-out-2026-07", f"batch-{a.n}.json")
    p2 = os.path.join(ROOT, ".cache", "enrich-batches", f"batch-{a.n}.json")
    for p in (p1, p2):
        if os.path.exists(p):
            sys.exit(f"既に在る: {p}(番号を変える)")
    json.dump(out, io.open(p1, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump({"kind": "catch-sonnet", "items": items}, io.open(p2, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"batch-{a.n}: {len(out)}作 → {p1}")


def hold(a):
    """見送り分を理由つきで保留台帳へ追記(純粋追加・既に在る slug は飛ばす)。 次の stage で「書ける」に戻さないため。"""
    works = {json.loads(l)["slug"]: json.loads(l) for l in io.open(WORKLIST, encoding="utf-8") if l.strip()}
    have = {l.split("\t")[0] for l in io.open(HOLD, encoding="utf-8")}
    rows = []
    for r in load_answers().values():
        if r["status"] == "ok" or r["src"] in have:
            continue
        why = re.sub(r"\s+", " ", r.get("reason") or "検査落ち: " + ",".join(r.get("bad") or [])).strip()
        who = "Opus点検で除外" if r.get("model") == "opus-audit" else "Sonnet見送り"
        rows.append("\t".join([r["src"], works.get(r["slug"], {}).get("title", ""), nows()[:10], "catch-sonnet", f"{who}: {why}"]))
    if not a.apply:
        print(f"追記予定 {len(rows)}行(--apply で書く)"); return
    raw = io.open(HOLD, "rb").read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    with io.open(HOLD, "ab") as f:
        if raw and not raw.endswith(b"\n"):
            f.write(nl.encode())
        f.write("".join(x + nl for x in rows).encode("utf-8"))
    print(f"保留台帳へ {len(rows)}行 追記")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage"); s.add_argument("--kobo", action="store_true"); s.set_defaults(f=stage)
    s = sub.add_parser("run"); s.add_argument("--limit", type=int, default=200); s.add_argument("--model", default=MODEL); s.set_defaults(f=run)
    s = sub.add_parser("report"); s.set_defaults(f=report)
    s = sub.add_parser("emit"); s.add_argument("n"); s.set_defaults(f=emit)
    s = sub.add_parser("hold"); s.add_argument("--apply", action="store_true"); s.set_defaults(f=hold)
    a = ap.parse_args()
    a.f(a)
