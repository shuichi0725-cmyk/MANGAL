"""MADB 作者解決モジュール (= 種2 build 共通)。

旧 _build-series-v2.py は schema:creator のテキストを [著]/[作] 優先で 1 人だけ
抽出し、 [原作]/[作画]/[漫画]/[画] を全部 other 扱いにしていたため、 原作付き作品で
作画者が落ちていた (例: ゼロ = 原作愛英史を採用し作画里見桂が脱落)。

本モジュールは MADB の安定 ID を使って 全著者を役割付きで解決する:
  - dcterms:creator (= 作者 C-ID) を metadata504.json (= Agent master) で名前解決
  - ma:ndla (= NDL authority 8 桁) で 重複 C-ID を名寄せ (例: 高橋留美子は C-ID 3 個)
  - schema:creator の [役割] タグ + ma:originalWorkCreator で 役割 (原作/作画/兼) を付与
  - 団体 (= 出版社/編集部) と 編集系役割は 著者から除外
  - mangaka.csv で qid 解決 (= 名前経由、 ndla 同一 C-ID の別名も試行)
  - dcterms:creator が無い record は schema:creator テキストの旧ロジックを fallback

出力: authors = [{cid, ndla, name, qid, role}] (role: artist/writer_artist/original_author)
"""

import json
import re
from collections import defaultdict


# ---------------------------------------------------------------------------
# Agent master (metadata504.json) ローダ
# ---------------------------------------------------------------------------
def load_agent_master(path) -> dict:
    """metadata504.json (class:Agent) → {cid: {"name", "ndla", "genre"}}。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    graph = data.get("@graph", data) if isinstance(data, dict) else data
    out: dict[str, dict] = {}
    for b in graph:
        cid = b.get("schema:identifier", "")
        if not cid:
            continue
        nm = b.get("schema:name", "") or b.get("rdfs:label", "")
        if isinstance(nm, list):
            nm = nm[0] if nm else ""
        if isinstance(nm, dict):
            nm = nm.get("@value", "")
        if not isinstance(nm, str):
            nm = ""
        m = re.search(r"(\d{8})", str(b.get("ma:ndla", "")))
        out[cid] = {
            "name": nm,
            "ndla": m.group(1) if m else "",
            "genre": b.get("ma:additionalGenre", ""),
        }
    return out


# ---------------------------------------------------------------------------
# 役割タグ → role 分類
# ---------------------------------------------------------------------------
# キャラクター原案/デザイン (= 創作クレジット、 原作側扱い)。 editorial の「デザイン」
# より先に判定して [キャラクターデザイン] が編集扱い除外されるのを防ぐ (= 半妖 高橋留美子)。
_CHARDESIGN_RE = re.compile(r"キャラクター(デザイン|原案|設定)|キャラ原案|メインキャラクター")
# 著者から除外する役割 (= 編集/制作/装丁/企画 等の非創作クレジット)
_EDITORIAL_RE = re.compile(
    r"編|協力|企画|監修|装[丁画幀]|デザイン|制作|DTP|ブックデザイン|カバー|翻訳|構成・編|編著"
)
# 作画系 (= 企画 を誤検出しないよう 画 単独/作画/漫画 等を明示)。 絵/イラスト/アーティスト 追加。
_ARTIST_RE = re.compile(r"作画|漫画|まんが|マンガ|劇画|作・画|画$|^画$|・画|^絵$|イラスト|アーティスト")
# 原作系
_STORY_ORIGINAL_RE = re.compile(r"原作|原案|ストーリー|脚本|脚色|シナリオ|^作$|^文$|構成|原著")


def _norm_name(s: str) -> str:
    return re.sub(r"[・\s　,，、.·]+", "", s or "")


def _classify_tag(tag: str) -> str:
    """役割タグ文字列 → 'editorial' / 'artist' / 'story' / 'plain'。"""
    if not tag:
        return "plain"
    if _CHARDESIGN_RE.search(tag):
        return "story"  # キャラ原案/デザイン = 創作 = 原作側 (editorial より優先)
    if _EDITORIAL_RE.search(tag):
        return "editorial"
    if _ARTIST_RE.search(tag):
        return "artist"
    if _STORY_ORIGINAL_RE.search(tag):
        return "story"
    if tag in ("著", "作"):
        return "plain"  # 単独著者候補 (= 後で artist 同居なら story 扱い)
    return "plain"


def parse_role_text(schema_creator) -> dict:
    """schema:creator から {正規化名: 役割タグ} を構築。

    "[漫画]里見桂" / "[原作]X / [漫画]Y" / "里見桂" / kana dict 等を処理。
    """
    items = schema_creator if isinstance(schema_creator, list) else [schema_creator]
    name_role: dict[str, str] = {}
    for it in items:
        if not isinstance(it, str):
            continue  # kana dict 等
        if "[" in it:
            for tag, name in re.findall(r"\[([^\]]+)\]\s*([^\[\]/,:：]*)", it):
                nm = _norm_name(name)
                if nm:
                    name_role.setdefault(nm, tag)
        else:
            for chunk in re.split(r"\s*[/,:：]\s+", it):
                nm = _norm_name(chunk)
                if nm:
                    name_role.setdefault(nm, "")
    return name_role


def original_work_names(ma_owc) -> set:
    """ma:originalWorkCreator から 原作者の正規化名 set を返す。"""
    if not ma_owc:
        return set()
    items = ma_owc if isinstance(ma_owc, list) else [ma_owc]
    out = set()
    for it in items:
        if isinstance(it, dict):
            continue  # kana
        if not isinstance(it, str):
            continue
        name = re.sub(r"^\s*\[[^\]]+\]\s*", "", it)
        nm = _norm_name(name)
        if nm:
            out.add(nm)
    return out


def get_cid_list(dcterms_creator) -> list:
    dc = dcterms_creator
    if isinstance(dc, dict):
        dc = [dc]
    if not isinstance(dc, list):
        return []
    out = []
    for x in dc:
        if isinstance(x, dict):
            cid = x.get("@id", "").rsplit("/", 1)[-1]
            if cid:
                out.append(cid)
    return out


# ---------------------------------------------------------------------------
# 本体: 1 MADB record → authors list
# ---------------------------------------------------------------------------
def resolve_authors(record, agent, name_to_qid, fallback_names_fn=None) -> list:
    """1 record (= 104 シリーズ or 101 巻) から authors を解決。

    agent          : load_agent_master() の dict
    name_to_qid    : (name:str) -> qid:str (= mangaka.csv 解決器、 未解決は "")
    fallback_names_fn: dcterms:creator 無し時に schema:creator から名前 list を返す関数
                       (= 旧 extract_creator_names)。 無ければ [] fallback。
    戻り値: [{cid, ndla, name, qid, role}]  (role: artist/writer_artist/original_author)
    """
    cids = get_cid_list(record.get("dcterms:creator"))
    role_map = parse_role_text(record.get("schema:creator", ""))
    owc = original_work_names(record.get("ma:originalWorkCreator"))

    # --- dcterms:creator 無し → fallback (旧テキストパース) ---
    if not cids:
        names = fallback_names_fn(record.get("schema:creator", "")) if fallback_names_fn else []
        out = []
        seen = set()
        for nm in names:
            q = name_to_qid(nm)
            key = q or _norm_name(nm)
            if key in seen:
                continue
            seen.add(key)
            out.append({"cid": "", "ndla": "", "name": nm, "qid": q,
                        "role": "writer_artist"})
        return out

    # --- C-ID ごとに名前/ndla/genre/raw役割を集める ---
    raw = []  # (cid, name, ndla, genre, tag_class)
    for cid in cids:
        info = agent.get(cid)
        if not info or not info["name"]:
            continue
        nm = info["name"]
        nn = _norm_name(nm)
        tag = role_map.get(nn, None)
        tag_class = _classify_tag(tag if tag is not None else "")
        raw.append({
            "cid": cid, "name": nm, "ndla": info["ndla"],
            "genre": info["genre"], "tag_class": tag_class,
            "is_owc": nn in owc,
        })

    has_artist = any(r["tag_class"] == "artist" for r in raw if r["genre"] != "団体")

    # --- 役割確定 + 団体/編集 除外 ---
    resolved = []
    for r in raw:
        # 団体 (組織) は 著者から除外
        if r["genre"] == "団体":
            continue
        tc = r["tag_class"]
        if tc == "editorial":
            continue
        if r["is_owc"]:
            role = "original_author"
        elif tc == "artist":
            role = "artist"
        elif tc == "story":
            role = "original_author" if has_artist else "writer_artist"
        else:  # plain (= 著/作/タグなし)
            role = "original_author" if has_artist else "writer_artist"
        resolved.append({**r, "role": role})

    # --- ndla 名寄せ (= 重複 C-ID を 1 人に畳む) ---
    by_key: dict[str, dict] = {}
    order = []
    for r in resolved:
        key = r["ndla"] or ("cid:" + r["cid"])
        q = name_to_qid(r["name"])
        entry = {"cid": r["cid"], "ndla": r["ndla"], "name": r["name"],
                 "qid": q, "role": r["role"]}
        if key not in by_key:
            by_key[key] = entry
            order.append(key)
        else:
            # 既存と統合: qid 解決済を優先、 role は artist > original_author > writer_artist
            cur = by_key[key]
            if not cur["qid"] and entry["qid"]:
                cur["qid"] = entry["qid"]
                cur["name"] = entry["name"]
            cur["role"] = _merge_role(cur["role"], entry["role"])
    return [by_key[k] for k in order]


_ROLE_RANK = {"artist": 0, "writer_artist": 1, "original_author": 2}

# union 時の role 統合専用 優先度。 ★ generic な writer_artist を最下位にして
# specific (artist/original_author) を勝たせる (= 半妖: vols9-10 のタグ無し
# writer_artist が vols1-7 の original_author を上書きする退行を防ぐ)。
# _ROLE_RANK (pick_primary/series_key 用) は不変 = series_key への影響なし。
_MERGE_PRI = {"artist": 0, "original_author": 1, "writer_artist": 2}


def _merge_role(a: str, b: str) -> str:
    """同一人物が複数役割タグを持つ場合の代表 role。 artist > original_author > writer_artist。"""
    return a if _MERGE_PRI.get(a, 9) <= _MERGE_PRI.get(b, 9) else b


def union_authors(authors_iter) -> list:
    """複数 record の authors を ndla/cid/name で名寄せ統合 (= cluster 単位の集約用)。"""
    by_key: dict[str, dict] = {}
    order = []
    for a in authors_iter:
        key = a["ndla"] or ("cid:" + a["cid"] if a["cid"] else "name:" + _norm_name(a["name"]))
        if key not in by_key:
            by_key[key] = dict(a)
            order.append(key)
        else:
            cur = by_key[key]
            if not cur["qid"] and a["qid"]:
                cur["qid"] = a["qid"]
                cur["name"] = a["name"]
            cur["role"] = _merge_role(cur["role"], a["role"])
    return [by_key[k] for k in order]


def pick_primary(authors: list) -> dict | None:
    """series_key 用の主著者。 qid 付き artist/writer_artist を最優先。"""
    if not authors:
        return None
    def rank(a):
        return (0 if a["qid"] else 1, _ROLE_RANK.get(a["role"], 9))
    return sorted(authors, key=rank)[0]


# ---------------------------------------------------------------------------
# 単体検証 (= python scripts/_madb_authors.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import csv
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    AGENT = load_agent_master(ROOT / ".cache" / "madb" / "metadata504.json")

    # mangaka.csv 解決器
    mk = {}
    with open(ROOT / "data" / "seed" / "mangaka.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mk[row["name"]] = row["qid"]
            for a in (row.get("alt_names") or "").split("|"):
                a = a.strip()
                if a and a not in mk:
                    mk[a] = row["qid"]
    mk_norm = {}
    for nm, q in mk.items():
        k = _norm_name(nm)
        if k and k not in mk_norm:
            mk_norm[k] = q

    def n2q(nm):
        if not isinstance(nm, str) or not nm:
            return ""
        return mk.get(nm) or mk_norm.get(_norm_name(nm), "")

    # 104 から テストケースを探して resolve
    META104 = ROOT / ".cache" / "madb" / "metadata104.json"
    g = json.load(open(META104, encoding="utf-8"))["@graph"]
    by_id = {b.get("schema:identifier"): b for b in g}

    targets = {
        "C290221": "ゼロ (原作愛英史/漫画里見桂/編ホーム社)",
        "C447634": "シャングリラ・フロンティア (硬梨菜/不二涼介)",
    }
    out_lines = []
    for cid, label in targets.items():
        b = by_id.get(cid)
        out_lines.append(f"=== {cid} {label} ===")
        if not b:
            out_lines.append("  (not found)")
            continue
        authors = resolve_authors(b, AGENT, n2q)
        for a in authors:
            out_lines.append(f"  {a['role']:16} {a['name']}  qid={a['qid'] or '-'}  ndla={a['ndla'] or '-'}  cid={a['cid']}")
        p = pick_primary(authors)
        out_lines.append(f"  → primary: {p['name'] if p else '(なし)'} ({p['role'] if p else '-'})")

    # 高橋留美子 ndla 名寄せ確認: 高橋留美子 を creator に持つ 104 を 1 件
    for b in g:
        if "高橋留美子" in json.dumps(b.get("schema:creator", ""), ensure_ascii=False):
            authors = resolve_authors(b, AGENT, n2q)
            lab = b.get("rdfs:label", "")
            out_lines.append(f"\n=== 高橋留美子作品サンプル: {lab} ({b.get('schema:identifier')}) ===")
            for a in authors:
                out_lines.append(f"  {a['role']:16} {a['name']}  qid={a['qid'] or '-'}  cid={a['cid']}")
            break

    with open(ROOT / ".cache" / "_authors_test.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("written .cache/_authors_test.txt", file=sys.stderr)
