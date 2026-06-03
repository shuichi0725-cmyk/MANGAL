"""種2 巻番号の復元 = cm101 (metadata101.json) の schema:position/volumeNumber から
number=0/null の巻を正しい巻番号へ patch。

★背景: 種2 build が rdfs:label (裸題=数字なし) を parse して 1冊目を number=0 にし、
promote の「numbered巻があれば number=0 を skip」規則で ★1冊目が消失していた
(= クマとたぬき型、 全 number=0 の79%=71,525件が cm101 に正しい position を持つ)。
fetch-madb.ts は本来 schema:position を優先採用するが、 構築時のデータに position が
無かったため 0 になった → 現 cm101 の position で再復元する。

★安全策:
  - ★number=0 / null の巻のみ更新 (= 既存の有効巻番号は絶対に上書きしない)
  - cm101 position が >=1 の場合のみ採用
  - 実行前に呼び出し側で 種2 backup 推奨 (= CLAUDE.md 保護層1)
  - 冪等 (= 再実行で重複更新しない)

map source = .cache/madb-volnum.json (madb_id -> int)。 不在なら metadata101.json から
再構築。 → 種1 (raw MADB) 由来なので再生成可能 (= git 永続化不要)。

使い方: python scripts/_patch-volnum-from-cm101.py [--dry-run]
"""
import sys
import re
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
META101 = ROOT / ".cache" / "madb" / "metadata101.json"
VOLNUM_MAP = ROOT / ".cache" / "madb-volnum.json"


def build_volnum_map() -> dict:
    """metadata101.json から madb_id -> 巻番号(int) を抽出 (= position 優先)。"""
    rid = re.compile(r'/id/(M\d+)"')
    rpos = re.compile(r'"schema:position": "?([\d.]+)"?')
    rvn = re.compile(r'"schema:volumeNumber": "([^"]+)"')
    id2num, cur = {}, None
    with META101.open(encoding="utf-8") as f:
        for line in f:
            if '"@id"' in line:
                m = rid.search(line)
                if m:
                    cur = m.group(1)
                    continue
            if cur:
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
    return id2num


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv

    if VOLNUM_MAP.exists():
        vm = json.load(VOLNUM_MAP.open(encoding="utf-8"))
        print(f"volnum map: {len(vm):,} (cached)", file=sys.stderr)
    else:
        vm = build_volnum_map()
        json.dump(vm, VOLNUM_MAP.open("w"), ensure_ascii=False)
        print(f"volnum map: {len(vm):,} (built from metadata101.json)", file=sys.stderr)

    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    rows = con.execute(
        "SELECT id, madb_book_id FROM volumes "
        "WHERE (number=0 OR number IS NULL) AND madb_book_id IS NOT NULL "
        "AND madb_book_id!='' AND isbn13 IS NOT NULL AND isbn13!=''"
    ).fetchall()

    updates = []
    for vid, mid in rows:
        n = vm.get(mid)
        if n is not None and n >= 1:
            updates.append((n, vid))

    from collections import Counter
    dist = Counter(n for n, _ in updates)
    print(f"number=0/null(ISBN+madb_id有): {len(rows):,}")
    print(f"  ★復元対象 (position>=1): {len(updates):,}")
    print(f"  復元番号分布: 巻1={dist.get(1,0):,} 巻2={dist.get(2,0):,} 巻3={dist.get(3,0):,} "
          f"巻4+={sum(v for k,v in dist.items() if k>=4):,}")

    if dry:
        print("\n[--dry-run] 更新せず終了")
        return

    cur = con.cursor()
    cur.executemany("UPDATE volumes SET number=? WHERE id=? AND (number=0 OR number IS NULL)", updates)
    con.commit()
    print(f"\n✓ {cur.rowcount if cur.rowcount>=0 else len(updates):,} 行 UPDATE 完了 (number=0/null のみ)")

    # 検証: 残 number=0 と クマとたぬき
    z = con.execute("SELECT COUNT(*) FROM volumes WHERE (number=0 OR number IS NULL) AND isbn13!=''").fetchone()[0]
    print(f"残 number=0/null: {z:,} (= 真に無position の単発/編)")


if __name__ == "__main__":
    main()
