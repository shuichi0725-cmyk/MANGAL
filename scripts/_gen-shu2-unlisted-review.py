"""「頁は在るのに巻だけ出ていない」層(トリニティセブン15.5型)の **裁定表 生成器**。

★なぜ生成器が要るか(2026-09-06 新設):
  裁定表 `shu2-unlisted-review.tsv` は当初 **手打ちの静的表**で、生成器が repo に無かった。
  帰結 = ①直した頁が表から消えない ②検出器を回し直しても新規頁が表に入らない。
  = [[volgap_leading_gap_and_frozen_input]] で踏んだ「凍った入力台帳」と同じ形。
  実際 2026-09-06 時点で、是正済みの 悪役令嬢後宮物語(6,7巻) / エイリアンヘッドバット(2巻) が
  芯TSVに残ったままだった。 → **芯TSVの鮮度を見て、古ければ検出器から作り直す**。

★もう一つの目的 = 「判定の目安」を機械で強くする:
  旧実装は 種2imprint と 頁のimprint の **生文字列比較**だったため、
  全角空白違い(モーニングKC ⇔ モーニング　KC)・大小文字(G-Lish comics ⇔ G-Lish Comics)・
  サブレーベル包含(ヤンマガKC ⊂ ヤンマガKCスペシャル)・ラテン⇔カナ(BEAM COMIX ⇔ ビームコミックス)
  まで「★別レーベル(要人手)」に落ちていた。 実測 32頁中13頁が機械で片付く分だった。

使い方:
  python scripts/_gen-shu2-unlisted-review.py               # 芯が古ければ自動で検出器から作り直す
  python scripts/_gen-shu2-unlisted-review.py --rebuild     # 必ず検出器から
  python scripts/_gen-shu2-unlisted-review.py --no-rebuild  # 芯TSVをそのまま使う(古くても)

出力: docs/production-diagnostics/shu2-unlisted-review.tsv (1行1頁・#列=ヘッダ込みの表示行番号)
"""
import io
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kana_romaji import kana2romaji  # noqa: E402  ★カナ→ローマ字の単一ソース(別実装を作らない)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "manga.v2"
CORE = ROOT / "docs" / "production-diagnostics" / "shu2-unlisted-volumes-core.tsv"
OUT = ROOT / "docs" / "production-diagnostics" / "shu2-unlisted-review.tsv"
AUDIT = ROOT / "scripts" / "_audit-shu2-unlisted-volumes.py"

# ---------------------------------------------------------------- 正規化
_SMALL = str.maketrans("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")
_SYM = re.compile("[\\s　・･\\.\\-‐―ー–—_/／\\\\|()（）\\[\\]「」『』【】,、:：;；]+")
# ★skeleton 用は **小書きカナ と ー を残す**(ウィ→ウイ にすると w が消えて Wings と合わなくなる)
_SYM_KEEPKANA = re.compile("[\\s　・･\\.\\-‐―–—_/／\\\\|()（）\\[\\]「」『』【】,、:：;；]+")
_KANA = re.compile("[ァ-ヿ]+")
_KANJI = re.compile("[一-鿿]")
_EDITION_LABELS = {"通常版", "ワイド版", "文庫版", "愛蔵版", "完全版", "新装版", "デラックス版"}


def norm(s):
    """表記ゆれを潰した比較キー(NFKC + 小書きカナ→大書き + 記号/空白除去 + 大文字化)。"""
    s = unicodedata.normalize("NFKC", (s or "").strip())
    return _SYM.sub("", s.translate(_SMALL)).upper()


def skeleton(s):
    """ラテン⇔カナ を突き合わせる **子音スケルトン**。
    カナ部分をヘボンでローマ字化 → c/q/x を k 系に寄せ → 母音を落とし → 連続を畳む。
      ウィングス・コミックス → wingusukomikkusu → wngskmks
      Wings comics          → wingscomics      → wngskmks   (= 一致)
    漢字を含む語は変換不能 = 空文字を返し、比較に使わない(安全側)。
    """
    s = _SYM_KEEPKANA.sub("", unicodedata.normalize("NFKC", (s or "")))
    if not s or _KANJI.search(s):
        return ""
    out, i = [], 0
    for m in _KANA.finditer(s):
        out.append(s[i:m.start()].lower())
        out.append(kana2romaji(m.group(0)).lower())
        i = m.end()
    out.append(s[i:].lower())
    t = re.sub("[^a-z]", "", "".join(out))
    t = t.replace("x", "ks").replace("c", "k").replace("q", "k")
    t = re.sub("[aeiou]", "", t)
    t = re.sub("(.)\\1+", "\\1", t)
    return t


def imprint_relation(a, b):
    """種2imprint a と 頁imprint b の関係 → (種別, 説明) or None。"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return None
    if na == nb:
        return ("EXACT", "正規化で一致")
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na):
        return ("INCLUDE", "包含(サブレーベル)")
    sa, sb = skeleton(a), skeleton(b)
    if sa and sb and len(sa) >= 4 and sa == sb:
        return ("ROMAJI", "ラテン⇔カナで同一")
    return None


# ---------------------------------------------------------------- 入力
def load_pub2stem():
    """公開slug → manga.v2 の SRC stem (= slug-overrides.yml の逆引き)。
    ★_gen-shinkan-data.py / _preorder-apply-zokkan.py と同実装 ([[pubslug_src_stem_generator_trap]])。"""
    m = {}
    p = ROOT / "data" / "seeds" / "slug-overrides.yml"
    if p.exists():
        d = yaml.safe_load(io.open(str(p), encoding="utf-8")) or {}
        ov = d.pop("overrides", {}) or {}
        for stem, pub in d.items():
            if isinstance(pub, str) and pub != stem:
                m[pub] = stem
        for stem, rec in ov.items():
            pub = (rec or {}).get("slug")
            if pub and pub != stem:
                m[pub] = stem
    return m


def newest_src_mtime():
    newest = 0.0
    with os.scandir(str(SRC)) as it:
        for e in it:
            if e.name.endswith(".yml"):
                mt = e.stat().st_mtime
                if mt > newest:
                    newest = mt
    return newest


def ensure_core(mode):
    """芯TSVの鮮度を見る。 本番ymlの方が新しければ **検出器から作り直す**(凍結防止)。"""
    if mode == "no-rebuild":
        if not CORE.exists():
            sys.exit("芯TSVが無い: --no-rebuild を外す")
        print("[1/3] --no-rebuild = 芯TSVをそのまま使う(鮮度は見ない)", flush=True)
        return
    if not CORE.exists():
        why = "芯TSVが無い"
    elif mode == "rebuild":
        why = "--rebuild 指定"
    elif newest_src_mtime() > CORE.stat().st_mtime:
        why = "★本番ymlの方が新しい(是正済みの巻が残っている恐れ)"
    else:
        print("[1/3] 芯TSV 鮮度OK", flush=True)
        return
    print("[1/3] %s → 検出器を回し直す: %s" % (why, AUDIT.name), flush=True)
    r = subprocess.run([sys.executable, str(AUDIT)], cwd=str(ROOT))
    if r.returncode != 0 or not CORE.exists():
        sys.exit("検出器が失敗 (exit %s)" % r.returncode)


def read_core():
    rows = []
    with CORE.open(encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("\t")
        idx = dict((k, i) for i, k in enumerate(head))
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < len(head):
                continue
            rows.append(dict((k, c[i]) for k, i in idx.items()))
    return rows


def page_editions(slug, pub2stem):
    """頁の版一覧 → [(type, imprint, min巻, max巻)]。 頁が引けなければ None。"""
    p = SRC / (slug + ".yml")
    if not p.exists():
        st = pub2stem.get(slug)
        if st:
            p = SRC / (st + ".yml")
    if not p.exists():
        return None
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    out = []
    for ed in d.get("editions") or []:
        nums = [v.get("number") for v in (ed.get("volumes") or []) if v.get("number") is not None]
        out.append((ed.get("type") or "?", (ed.get("imprint") or "").strip(),
                    min(nums) if nums else None, max(nums) if nums else None))
    return out


# ---------------------------------------------------------------- 判定
def classify(seed2_imprints, eds):
    """判定の目安。 ★人手が要るものほど後ろのバケツへ。"""
    if eds is None:
        return "★頁が引けない(slug要確認)"
    page_imps = [i for (_t, i, _a, _b) in eds]
    if not any(page_imps):
        return "★頁側imprintが空=比較不能"
    if all((not i) or i in _EDITION_LABELS for i in page_imps):
        return "★頁側imprintが版ラベル=未設定"
    hits, miss = [], []
    for s2 in seed2_imprints:
        rel = None
        for i in page_imps:
            if rel is None:
                rel = imprint_relation(s2, i)
        if rel:
            hits.append(rel)
        else:
            miss.append(s2)
    if not miss and hits:
        kinds = set(r[0] for r in hits)
        if kinds == set(["EXACT"]):
            return "同レーベル=素直な取りこぼし"
        return "同レーベル(%s)" % "/".join(sorted(set(r[1] for r in hits)))
    if hits:
        return "★一部だけ別レーベル=混在"
    return "★別レーベル=版タブ・別作品を先に判断"


_ORDER = ["同レーベル", "★一部", "★頁側", "★誤番号", "★別レーベル", "★頁が引けない"]


def sort_key(guide):
    for i, p in enumerate(_ORDER):
        if guide.startswith(p):
            return i
    return len(_ORDER)


def main():
    mode = "auto"
    if "--rebuild" in sys.argv:
        mode = "rebuild"
    if "--no-rebuild" in sys.argv:
        mode = "no-rebuild"

    prev = set()
    if OUT.exists():
        with OUT.open(encoding="utf-8") as f:
            f.readline()
            for line in f:
                c = line.rstrip("\n").split("\t")
                if len(c) > 1:
                    prev.add(c[1] if c[0].isdigit() else c[0])

    ensure_core(mode)
    rows = read_core()
    pub2stem = load_pub2stem()
    print("[2/3] 芯 %d巻 / %d頁 を頁単位に畳む"
          % (len(rows), len(set(r["owner_slug"] for r in rows))), flush=True)

    pages = OrderedDict()
    for r in rows:
        pages.setdefault(r["owner_slug"], []).append(r)

    out = []
    for slug, rs in pages.items():
        eds = page_editions(slug, pub2stem)
        nums = sorted(set(r["number"] for r in rs if r["number"]), key=float)
        s2imps = sorted(set((r["imprint"] or "").strip() for r in rs if (r["imprint"] or "").strip()))
        if any(float(n) >= 900 for n in nums):
            guide = "★誤番号(900以上)"
        else:
            guide = classify(s2imps, eds)
        ed_str = " | ".join("%s:%s:%s..%s" % (t, i or "(空)", a, b)
                            for (t, i, a, b) in (eds or [])) or "(頁が引けない)"
        out.append(OrderedDict([
            ("公開slug", slug),
            ("作品", rs[0]["title"]),
            ("欠けている巻", ",".join(nums)),
            ("種2のimprint", " / ".join(s2imps) or "(空)"),
            ("頁の版(type:imprint:巻範囲)", ed_str),
            ("判定の目安", guide),
            ("isbn", ",".join(r["isbn"] for r in rs)),
        ]))

    out.sort(key=lambda d: (sort_key(d["判定の目安"]), d["判定の目安"], d["公開slug"]))
    cols = ["#"] + (list(out[0].keys()) if out else [])
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for i, d in enumerate(out, start=2):   # ★#=ヘッダ込みの表示行番号(「見なおしの N 行目」の N)
            f.write("\t".join([str(i)] + [str(d[c]) for c in cols[1:]]) + "\n")

    now = set(d["公開slug"] for d in out)
    solved, fresh = sorted(prev - now), sorted(now - prev)
    print("[3/3] %s = %d頁" % (OUT.relative_to(ROOT), len(out)), flush=True)
    for g, c in Counter(d["判定の目安"] for d in out).most_common():
        print("   %4d頁  %s" % (c, g))
    if prev:
        print("  ★前回比: 解決 %d頁 / 新規 %d頁" % (len(solved), len(fresh)))
        for s in solved[:20]:
            print("     - 解決 %s" % s)
        for s in fresh[:20]:
            print("     + 新規 %s" % s)


if __name__ == "__main__":
    main()
