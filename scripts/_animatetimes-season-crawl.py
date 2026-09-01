#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アニメイトタイムズ季節まとめクローラ (= /anime コーナーの第2情報源。 2026-09-01 新設)。

季節まとめページ(tag/details.php?id=NNNN)は ＜＜前季/次季＞＞ の双方向連鎖リスト。
起点1本から自動発見でき、AniList季節ハーベストの漏れ(国内マイナー/キッズ/新規発表)を
原作クレジット(掲載誌・出版社つき)ごと回収する。

  - HTML は .cache/animatetimes/<id>.html に保存(再解析はネット不要)
  - seed 出力 = data/seeds/animatetimes-seasons.jsonl (season単位で決定的に再生成、
    変更履歴は git diff が台帳)
  - AniList seed との突合 = --report → docs/production-diagnostics/animatetimes-season-gap.tsv

使い方:
  python scripts/_animatetimes-season-crawl.py --crawl --start-id 5947   # 初回(連鎖を両方向へ)
  python scripts/_animatetimes-season-crawl.py --weekly                  # 週次: 先頭2季を再取得→差分報告
  python scripts/_animatetimes-season-crawl.py --report                  # AniList seedとの突合TSV
  python scripts/_animatetimes-season-crawl.py --stats

レート: 2.5s/req。429/403 = 即中断(再実行で再開)。
"""
import argparse, io, json, os, re, sys, time, unicodedata, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "animatetimes")
SEED = os.path.join(ROOT, "data", "seeds", "animatetimes-seasons.jsonl")
AL_SEED = os.path.join(ROOT, "data", "seeds", "anime-seasons.jsonl")
AL_LINKS = os.path.join(ROOT, "data", "seeds", "anime-season-links.jsonl")
REPORT = os.path.join(ROOT, "docs", "production-diagnostics", "animatetimes-season-gap.tsv")
BASE = "https://www.animatetimes.com/tag/details.php?id="
RATE = 2.5

SEASON_JA = {"冬": "WINTER", "春": "SPRING", "夏": "SUMMER", "秋": "FALL"}


def fetch(tag_id, force=False):
    """1季のHTMLを取得(キャッシュ優先)。戻り=html文字列"""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{tag_id}.html")
    if not force and os.path.exists(path) and os.path.getsize(path) > 10000:
        return open(path, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(BASE + str(tag_id), headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read()
    with open(path, "wb") as f:
        f.write(raw)
    time.sleep(RATE)
    return raw.decode("utf-8", "replace")


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


STAFF_KEYS = ["監督", "シリーズ構成", "キャラクターデザイン", "脚本", "音楽", "アニメーション制作",
              "総監督", "助監督", "副監督", "美術監督", "色彩設計", "撮影監督", "編集", "音響監督",
              "制作", "キャスト", "スタッフ", "オープニング", "エンディング", "主題歌", "企画"]


def parse_page(html, tag_id):
    """1季ページ → {season_key, label, prev_id, next_id, works:[...]}"""
    # 季ラベル: <title> か h1 の「2026秋アニメ」
    m = re.search(r"(20\d\d)(冬|春|夏|秋)アニメ", html)
    season_key = label = None
    if m:
        label = m.group(0)
        season_key = f"{m.group(1)}-{SEASON_JA[m.group(2)]}"

    # 前後リンク: ＜＜/＞＞ を含むアンカー
    prev_id = next_id = None
    for url, txt in re.findall(r'href="(?:https://www\.animatetimes\.com)?(/tag/details\.php\?id=(?:\d+))"[^>]*>([^<]*)<', html):
        tid = int(url.rsplit("=", 1)[1])
        if "＜＜" in txt:
            prev_id = tid
        elif "＞＞" in txt:
            next_id = tid

    # 目次: <a href="#N">題</a> (N=数字のみ対象)
    toc = []
    for aid, txt in re.findall(r'<a href="#(\d+)"[^>]*>(.*?)</a>', html, re.S):
        t = strip_tags(txt).replace("&amp;", "&")
        if t:
            toc.append((int(aid), t))
    toc.sort()

    # 本文セクション: id="N" の位置で分割
    positions = {}
    for m2 in re.finditer(r'id="(\d+)"', html):
        n = int(m2.group(1))
        if n not in positions:
            positions[n] = m2.start()
    works = []
    for i, (n, title) in enumerate(toc):
        start = positions.get(n)
        seg_text = ""
        if start is not None:
            nxt = [positions[m3] for m3, _ in toc[i + 1:] if m3 in positions and positions[m3] > start]
            end = min(nxt) if nxt else start + 60000
            seg_text = re.sub(r"<[^>]+>", "\n", html[start:end])
        works.append({
            "season_key": season_key, "at_tag_id": tag_id, "idx": n,
            "title": title,
            "rebroadcast": bool(re.search(r"再放送|地上波放送", title)),
            "gensaku": _extract_after(seg_text, "原作"),
            "kousei": _extract_after(seg_text, "放送形態"),
            "schedule": _extract_after(seg_text, "スケジュール"),
        })
    return {"season_key": season_key, "label": label, "tag_id": tag_id,
            "prev_id": prev_id, "next_id": next_id, "works": works}


def _extract_after(text, key):
    """タグ剥がし済みtextから「key：」直後の値をstaffキー手前まで拾う(最大160字)"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, l in enumerate(lines):
        m = re.match(rf"^{key}[:：](.*)$", l)
        if m is None:
            continue
        buf = [m.group(1).strip()]
        for l2 in lines[i + 1:i + 8]:
            if any(re.match(rf"^{k}[:：]", l2) for k in STAFF_KEYS):
                break
            buf.append(l2)
            if sum(len(b) for b in buf) > 160:
                break
        val = re.sub(r"\s+", " ", " ".join(b for b in buf if b)).strip()
        return val[:160] if val else None
    return None


# ---------- seed I/O ----------

def load_seed():
    rows = []
    if os.path.exists(SEED):
        for line in open(SEED, encoding="utf-8"):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_seed(rows):
    rows.sort(key=lambda r: (r.get("season_key") or "", r.get("at_tag_id") or 0, r.get("idx") or 0))
    with open(SEED, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def upsert_season(rows, page):
    """seed rows から当該seasonの旧行を除き、新行を入れる。戻り=(rows, added, removed, changed)"""
    old = {r["title"]: r for r in rows if r.get("at_tag_id") == page["tag_id"]}
    keep = [r for r in rows if r.get("at_tag_id") != page["tag_id"]]
    new = {w["title"]: w for w in page["works"]}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(t for t in set(new) & set(old)
                     if any(new[t].get(k) != old[t].get(k) for k in ("gensaku", "kousei", "schedule", "idx")))
    return keep + page["works"], added, removed, changed


# ---------- crawl ----------

def crawl(start_id, max_pages=200, force_ids=()):
    """start_id から両方向へ連鎖を歩く。既キャッシュ季はネット不要で再解析のみ。"""
    rows = load_seed()
    seen, queue = set(), [start_id]
    pages = []
    while queue and len(seen) < max_pages:
        tid = queue.pop(0)
        if tid in seen:
            continue
        seen.add(tid)
        try:
            html = fetch(tid, force=(tid in force_ids))
        except urllib.error.HTTPError as e:
            print(f"  id={tid}: HTTP {e.code} → 中断(再実行で再開)")
            break
        page = parse_page(html, tid)
        if not page["season_key"]:
            print(f"  id={tid}: 季ラベル無し(まとめページでない?) skip")
            continue
        pages.append(page)
        print(f"  id={tid} {page['label']}: {len(page['works'])}作 (prev={page['prev_id']} next={page['next_id']})")
        for nid in (page["prev_id"], page["next_id"]):
            if nid and nid not in seen:
                queue.append(nid)
    total_added = total_removed = 0
    for page in pages:
        rows, added, removed, changed = upsert_season(rows, page)
        total_added += len(added)
        total_removed += len(removed)
        for t in added:
            print(f"    + {page['season_key']} {t}")
        for t in removed:
            print(f"    - {page['season_key']} {t}")
        for t in changed:
            print(f"    ~ {page['season_key']} {t}")
    save_seed(rows)
    print(f"季={len(pages)} / seed行={len(load_seed())} (+{total_added} -{total_removed})")
    return pages


def weekly():
    """週次: 連鎖の先頭(最新)側 2季 + 未発見の次季 を強制再取得して差分報告。
    ★fail-soft: ネットワーク断等で失敗しても exit 0(週次step1を止めない。WARNのみ)"""
    rows = load_seed()
    if not rows:
        print("WARN: seedが空。先に --crawl --start-id NNNN を実行して下さい(週次は続行)")
        return
    by_season = {}
    for r in rows:
        by_season.setdefault(r["season_key"], r["at_tag_id"])
    newest = sorted(by_season)[-2:]
    ids = [by_season[s] for s in newest]
    print(f"週次チェック対象: {', '.join(f'{s}(id={i})' for s, i in zip(newest, ids))} + 次季探索")
    try:
        crawl(ids[0], force_ids=set(ids))
        report()
    except Exception as e:
        print(f"WARN: animatetimes週次チェック失敗({type(e).__name__}: {e})。週次は続行、次週に自然再試行")


# ---------- report (AniList seedとの突合) ----------

SUFFIX = re.compile(r"(season\s*\d+|第?\d+期|第?\d+クール|シーズン\s*\d+|2nd\s*season|restart"
                    r"|act.?|Ⅱ|II\b|（再放送）|（\d{4}）|\(\d{4}\))", re.I)


def norm_title(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = SUFFIX.sub("", s)
    return re.sub(r"[\s　・:：、。！!？?「」『』【】〜~\-–—☆★#/\.®]+", "", s)


MANGA_HINTS = re.compile(r"連載|コミック|comic|webtoon|漫画|まんが|マガジン|ジャンプ|サンデー|チャンピオン"
                         r"|ヤンマガ|ゼノン|ガンガン|きらら|アフタヌーン|イブニング|ビッグコミック|COMIC", re.I)
NONMANGA_HINTS = re.compile(r"文庫|ノベル|novel|books|ブックス|小説|ブシロード|コナミ|カプコン|セガ|タカラトミー"
                            r"|トミーテック|バンダイ|グッドスマイル|サンリオ|絵本|ぬいぐるみ|ゲーム", re.I)


def classify(gensaku):
    if not gensaku:
        return "?"
    if MANGA_HINTS.search(gensaku):
        return "MANGA?"
    if NONMANGA_HINTS.search(gensaku):
        return "non-manga"
    return "?"


def report():
    rows = load_seed()
    al = {}
    for line in open(AL_SEED, encoding="utf-8"):
        r = json.loads(line)
        al.setdefault(r["season_key"], []).append(norm_title(r["anime_title"]))
    linked = set()
    if os.path.exists(AL_LINKS):
        for line in open(AL_LINKS, encoding="utf-8"):
            r = json.loads(line)
            linked.add((r["season_key"], norm_title(r["anime_title"])))
    out = []
    for r in rows:
        if r["rebroadcast"]:
            continue
        sk, n = r["season_key"], norm_title(r["title"])
        pool = al.get(sk, [])
        in_al = n in pool or any(n and (n in k or k in n) for k in pool if k)
        if in_al:
            continue
        out.append((sk, r["title"], classify(r.get("gensaku")), r.get("gensaku") or "", r.get("kousei") or ""))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8", newline="") as f:
        f.write("season\ttitle\tclass\tgensaku\tkousei\n")
        for row in sorted(out, reverse=True):
            f.write("\t".join(row) + "\n")
    manga = [r for r in out if r[2] == "MANGA?"]
    print(f"AniList seed非掲載: {len(out)}作 (うちMANGA?={len(manga)}, 対象外={sum(1 for r in out if r[2]=='non-manga')}, 不明={sum(1 for r in out if r[2]=='?')})")
    print(f"→ {os.path.relpath(REPORT, ROOT)}")
    for r in sorted(manga, reverse=True)[:40]:
        print(f"  [{r[0]}] {r[1]} | {r[3][:60]}")


def stats():
    rows = load_seed()
    by = {}
    for r in rows:
        by.setdefault(r["season_key"], []).append(r)
    for k in sorted(by):
        print(f"  {k}: {len(by[k])}作 (id={by[k][0]['at_tag_id']})")
    print(f"計 {len(by)}季 {len(rows)}行")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", action="store_true")
    ap.add_argument("--start-id", type=int, default=5947)
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.crawl:
        crawl(a.start_id)
    elif a.weekly:
        weekly()
    elif a.report:
        report()
    elif a.stats:
        stats()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
