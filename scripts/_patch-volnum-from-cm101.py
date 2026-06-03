"""種2 巻番号の復元 = cm101 (metadata101.json) の schema:position と schema:isPartOf
(シリーズ容器) を使い、 number=0/null の巻を ★容器ゲート付き で正しい巻番号へ patch。

★背景: 種2 build が rdfs:label (裸題=数字なし) を parse して 1冊目を number=0 にし、
promote の「numbered巻があれば number=0 を skip」規則で ★1冊目が消失していた
(= クマとたぬき型)。 number=0 の79%が cm101 に position を持つ。

★★容器ゲート (= 別作品の誤接続を防ぐ最重要安全策):
  build は「著者+題幹」でクラスタするため、 ★同じ題幹のスピンオフ/関連本 (= 別容器) が
  本編 edition に紛れ込む (例: 恋愛ラボ本編[C336182] に 恋愛研究レポート[C448333])。
  単純に番号を振ると別作品を vol1 等にくっつけてしまう。 → ★volume の schema:isPartOf
  容器が edition の主流容器と ★遠い (C-ID距離>20) なら patch しない。 隣接 (≤20) は
  同一シリーズの別容器レコードとして許容。 容器情報が無い場合は反証できないので許容。

2 パス:
  - Pass 1 (position): number=0 で cm101 position>=1 → position を採用 (容器ゲート: 遠容器除外)
  - Pass 2 (先頭欠充当): position 無の number=0 で、 edition に先頭欠 (numbered が 2+ 始まり)
    かつ ★容器が主流と一致(≤20) かつ 日付が最古numbered以前 → 先頭の欠位置へ充当
    (= 漏れた vol1。 146 型。 容器一致必須=より厳格)

★安全策: number=0/null のみ更新・既存有効値不変・冪等。 実行前に種2 backup 推奨。
map = .cache/madb-volnum.json (位置) / .cache/madb-ispartof.json (容器)。 種1由来=再生成可。

使い方: python scripts/_patch-volnum-from-cm101.py [--dry-run]
"""
import sys
import re
import json
import sqlite3
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
META101 = ROOT / ".cache" / "madb" / "metadata101.json"
VOLNUM_MAP = ROOT / ".cache" / "madb-volnum.json"
ISPART_MAP = ROOT / ".cache" / "madb-ispartof.json"
GATE_DIST = 20  # C-ID 距離 これ以下は同一シリーズ扱い (= 隣接容器を許容)


def build_maps():
    """metadata101.json から id->position と id->container を抽出。"""
    rid = re.compile(r'/id/(M\d+)"')
    rpos = re.compile(r'"schema:position": "?([\d.]+)"?')
    rvn = re.compile(r'"schema:volumeNumber": "([^"]+)"')
    rpart = re.compile(r'/id/(C\d+)"')
    id2num, id2c, cur, in_part = {}, {}, None, False
    with META101.open(encoding="utf-8") as f:
        for line in f:
            if '"@id"' in line:
                m = rid.search(line)
                if m:
                    cur = m.group(1); in_part = False
                    continue
            if not cur:
                continue
            if "isPartOf" in line:
                in_part = True
                m = rpart.search(line)
                if m:
                    id2c[cur] = m.group(1); in_part = False
                continue
            if in_part:
                m = rpart.search(line)
                if m:
                    id2c[cur] = m.group(1); in_part = False
                continue
            mp = rpos.search(line)
            if mp:
                try:
                    id2num[cur] = int(float(mp.group(1)))
                except ValueError:
                    pass
                continue
            if cur not in id2num:
                mv = rvn.search(line)
                if mv:
                    try:
                        id2num[cur] = int(float(mv.group(1)))
                    except ValueError:
                        pass
    return id2num, id2c


def cdist(c1, c2):
    try:
        return abs(int(c1[1:]) - int(c2[1:]))
    except (TypeError, ValueError):
        return 10 ** 9


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv

    if VOLNUM_MAP.exists() and ISPART_MAP.exists():
        volnum = json.load(VOLNUM_MAP.open(encoding="utf-8"))
        ispart = json.load(ISPART_MAP.open(encoding="utf-8"))
        print(f"maps: volnum {len(volnum):,} / ispart {len(ispart):,} (cached)", file=sys.stderr)
    else:
        volnum, ispart = build_maps()
        json.dump(volnum, VOLNUM_MAP.open("w"), ensure_ascii=False)
        json.dump(ispart, ISPART_MAP.open("w"), ensure_ascii=False)
        print(f"maps built: volnum {len(volnum):,} / ispart {len(ispart):,}", file=sys.stderr)

    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    rows = con.execute(
        "SELECT id, edition_id, madb_book_id, number, isbn13, release_date "
        "FROM volumes WHERE isbn13 IS NOT NULL AND isbn13!=''"
    ).fetchall()
    ed_vols = defaultdict(list)
    for r in rows:
        ed_vols[r[1]].append(r)  # by edition_id

    updates = []          # (number, vol_id)
    stat = Counter()
    for eid, vols in ed_vols.items():
        conts = [ispart.get(v[2]) for v in vols if ispart.get(v[2])]
        dom = Counter(conts).most_common(1)[0][0] if conts else None

        def gated(mid):  # 遠容器でなければ True (= 反証できなければ許容)
            c = ispart.get(mid)
            if c is None or dom is None:
                return True
            return cdist(c, dom) <= GATE_DIST

        # Pass 1: position
        for v in vols:
            if v[3] in (0, None):
                p = volnum.get(v[2])
                if p and p >= 1:
                    if gated(v[2]):
                        updates.append((p, v[0])); stat["pass1_position"] += 1
                    else:
                        stat["skip_far_container(別作品)"] += 1

        # Pass 2: 先頭欠 + position無 + 容器一致 の 0 を vol1.. へ充当
        numbered = sorted({v[3] for v in vols if v[3] and 1 <= v[3] < 400})
        if numbered and numbered[0] >= 2:
            earliest = min((v[4] or "9999" for v in vols if v[3] and 1 <= v[3] < 400), default="9999")
            cand = [v for v in vols
                    if v[3] in (0, None) and not volnum.get(v[2])
                    and ispart.get(v[2]) and dom and cdist(ispart.get(v[2]), dom) <= GATE_DIST
                    and (v[4] or "9999") <= earliest]
            cand.sort(key=lambda v: (v[4] or "9999", v[5] or ""))
            for pos, v in zip(range(1, numbered[0]), cand):
                updates.append((pos, v[0])); stat["pass2_fill(146型)"] += 1

    print(f"=== container-gated patch 計画 ===")
    for k, v in stat.most_common():
        print(f"  {k}: {v:,}")
    print(f"  → 更新総数: {len(updates):,}")

    if dry:
        print("\n[--dry-run] 更新せず終了")
        return

    cur = con.cursor()
    cur.executemany("UPDATE volumes SET number=? WHERE id=? AND (number=0 OR number IS NULL)", updates)
    con.commit()
    z = con.execute("SELECT COUNT(*) FROM volumes WHERE (number=0 OR number IS NULL) AND isbn13!=''").fetchone()[0]
    print(f"\n✓ {len(updates):,} 行 UPDATE 完了 / 残 number=0/null: {z:,}")


if __name__ == "__main__":
    main()
