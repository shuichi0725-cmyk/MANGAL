"""配信する索引ファイルの一覧(= 配信経路の単一ソース)と、ブラウザ専用の列形式索引の生成。

★2026-09-23 検索の読み込み高速化:
  一覧索引 manga-list-index.json は「1作品=1行」の行配列({f,d})。同じ種類の値が離れて並ぶので
  圧縮が効きにくい。列ごとに並べ直し(+著者名を番号化)すると、中身は同じまま転送量が約3割減る
  (実測 gzip 6.40MB → 4.26MB)。

  ★行配列の本体は触らない: Python の道具67本が manga-list-index.json を直接読んでいるため。
    列形式は「ブラウザに配るためだけの派生ファイル」として別名で並べて置く
    (= 形式を変える時はファイル名を変える規約 [[index_format_change_versioned_filename]] に沿う)。

  ★鮮度は内容ハッシュで保証する: 列形式の先頭に元ファイル(行配列)の sha1 を焼く。
    配信経路は送る直前に ensure_columnar() を呼び、ハッシュが合わなければ作り直す
    = 行配列だけ更新されて列形式が古いまま配られる、という事故を構造的に起こさない。

使い方:
  python scripts/_index_files.py ensure <dir>   # 行配列と合っていなければ列形式を作り直す
  python scripts/_index_files.py build  <dir>   # 無条件に作り直す
"""
import hashlib
import json
import os
import re
import sys

ROW = "manga-list-index.json"
# ★列形式の器を変える時は v を上げて別名にする(lib/useMangaIndex.ts の fetch 先も同時に)。
COLUMNAR = "manga-list-cols.v1.json"

# ★配信する索引の全リスト。r2-sync / 差分反映 / 機能蒸留 / 週次preflight・finalize は全部ここを読む
#   (旧: 各scriptが4本のタプルを個別に持っていた=1本足すたびに結線漏れの危険があった)。
INDEX_FILES = (
    "manga-list-index.json",
    "manga-catch-index.json",
    "manga-list-head.json",
    "manga-alt-index.json",
    COLUMNAR,
)

# 番号化する列(値= "name\tkana" 文字列の配列)。著者は約7万行に対して2.4万種類しかない。
DICT_COLS = ("authors", "original_authors")


def _sha(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def build_columnar(dirpath: str) -> str:
    """dirpath/manga-list-index.json から dirpath/manga-list-cols.v1.json を作る。戻り値=元ファイルのハッシュ。

    形式: {"src": 元ハッシュ, "n": 行数, "f": 列名[], "c": 列ごとの値配列[], "A": 番号→著者文字列[], "dc": 番号化した列名[]}
    ★src を先頭キーにする(ensure_columnar が先頭64バイトだけ読んで照合するため)。"""
    row_p = os.path.join(dirpath, ROW)
    out_p = os.path.join(dirpath, COLUMNAR)
    src = _sha(row_p)
    with open(row_p, encoding="utf-8") as f:
        raw = json.load(f)
    fields = raw["f"]
    rows = raw["d"]
    cols = [[r[i] if i < len(r) else None for r in rows] for i in range(len(fields))]
    table: dict = {}
    coded = []
    for name in DICT_COLS:
        if name not in fields:
            continue
        j = fields.index(name)
        col = cols[j]
        # 旧形式(オブジェクト)が混ざっていたら番号化しない(=そのまま載せる。復元側は両対応)
        if any(v is not None and not all(isinstance(x, str) for x in v) for v in col):
            continue
        cols[j] = [None if v is None else [table.setdefault(x, len(table)) for x in v] for v in col]
        coded.append(name)
    obj = {"src": src, "n": len(rows), "f": fields, "c": cols, "A": list(table), "dc": coded}
    tmp = out_p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fo:
        json.dump(obj, fo, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_p)
    return src


def columnar_is_fresh(dirpath: str) -> bool:
    row_p = os.path.join(dirpath, ROW)
    out_p = os.path.join(dirpath, COLUMNAR)
    if not os.path.exists(row_p) or not os.path.exists(out_p):
        return False
    with open(out_p, encoding="utf-8") as f:
        head = f.read(64)
    m = re.search(r'"src":"([0-9a-f]+)"', head)
    return bool(m) and m.group(1) == _sha(row_p)


def ensure_columnar(dirpath: str) -> str:
    """行配列と合っていなければ列形式を作り直す。戻り値 = "fresh" / "rebuilt" / "no-row"。"""
    if not os.path.exists(os.path.join(dirpath, ROW)):
        return "no-row"
    if columnar_is_fresh(dirpath):
        return "fresh"
    build_columnar(dirpath)
    return "rebuilt"


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("ensure", "build"):
        print(__doc__)
        sys.exit(2)
    d = sys.argv[2]
    if sys.argv[1] == "build":
        build_columnar(d)
        st = "rebuilt"
    else:
        st = ensure_columnar(d)
    p = os.path.join(d, COLUMNAR)
    sz = os.path.getsize(p) / 1e6 if os.path.exists(p) else 0
    print(f"列形式索引 {COLUMNAR}: {st} ({sz:.1f}MB) @ {d}")
    if st == "no-row":
        sys.exit(1)
