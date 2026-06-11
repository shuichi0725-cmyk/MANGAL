#!/usr/bin/env python3
"""slug 数字4分岐 是正 (= gap b)。 ★適用なし、 結果TSVを出力してレビュー。

確定ルール(2026-06-05):
  音読み数詞(kana=ニセン/ジュウゴ等)        → 算用数字keep   15歳→15-sai / 2020→2020
  英語読み・題≒数字(除くと題が空)          → 英単語         19→nineteen
  英語読み・付随/続編番号(除くと題が残る)     → 数字keep       ペルソナ5→persona-5 / ガッシュ!!2→...-2
  ラテン隣接/序数(2nd/AK-69)              → 字面keep(別処理) ※本scriptはflagのみ(latin混じり588は後回し)
  訓読み助数詞/特殊/当て字(ヨンコマ/イサク)   → ヘボン既定     4コマ→yonkoma / 139→isaku

手法: v2のkana_slug(ヘボン)を起点に、 title中の数字を title_kana で型判定し是正(patch)。
"""
import csv
import re
import sys
from pathlib import Path

import pykakasi

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / ".cache" / "slug-gen-v2.tsv"
OUT = ROOT / ".cache" / "slug-num-fixed.tsv"
sys.stdout.reconfigure(encoding="utf-8")
_kks = pykakasi.kakasi()


sys.path.insert(0, str(Path(__file__).resolve().parent))
import _slug_rules as SR


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def drop_long(r):
    # 旧規則(廃止)。 ★latinmix再レンダ(_build-slug-override)の旧render照合用にのみ残存
    return re.sub(r"uu", "u", re.sub(r"oo", "o", re.sub(r"ou", "o", r)))


def hslug(kana):
    # ★2026-06-10 規則: 長音保持/ヲ=o
    return SR.token_roman(kana)


# --- 音読みON 候補(4=シ/ヨン, 7=シチ/ナナ, 9=キュウ/ク を両方) ---
_O1 = {0: ["ゼロ", "レイ"], 1: ["イチ"], 2: ["ニ"], 3: ["サン"], 4: ["ヨン", "シ"],
       5: ["ゴ"], 6: ["ロク"], 7: ["ナナ", "シチ"], 8: ["ハチ"], 9: ["キュウ", "ク"]}


def _join(parts):
    # 直積(候補が複数の桁を合成)
    res = [""]
    for opts in parts:
        res = [r + o for r in res for o in opts]
    return res


# 単独単桁の厳格ON読み(ヨン/ナナ等の訓読み native を除外。 4コマ=ヨンコマ→yonkoma を守る)
_O1_STRICT = {0: ["ゼロ", "レイ"], 1: ["イチ"], 2: ["ニ"], 3: ["サン"], 4: ["シ"],
              5: ["ゴ"], 6: ["ロク"], 7: ["シチ"], 8: ["ハチ"], 9: ["キュウ", "ク"]}


def sino_candidates(n):
    """n の 数詞読み候補(カタカナ)集合。 1-9999(超は非対応=空)。
    ★ヨン/ナナ(4/7 native)も含める=4部→4-bu/4コマ→4-koma で数字keep(ユーザ確定)。
    訓読み助数詞つ(4つ=ヨッツ)は ヨン≠ヨッツ で先頭一致せず自然にヘボン(守られる)。"""
    if n < 0 or n > 9999:
        return set()
    if n == 0:
        return set(_O1[0])
    out = []
    th, h, te, o = n // 1000, (n % 1000) // 100, (n % 100) // 10, n % 10
    parts = []
    if th:
        sen = {1: ["セン"], 2: ["ニセン"], 3: ["サンゼン"], 4: ["ヨンセン"], 5: ["ゴセン"],
               6: ["ロクセン"], 7: ["ナナセン"], 8: ["ハッセン"], 9: ["キュウセン"]}
        parts.append(sen[th])
    if h:
        hya = {1: ["ヒャク"], 2: ["ニヒャク"], 3: ["サンビャク"], 4: ["ヨンヒャク"], 5: ["ゴヒャク"],
               6: ["ロッピャク"], 7: ["ナナヒャク"], 8: ["ハッピャク"], 9: ["キュウヒャク"]}
        parts.append(hya[h])
    if te:
        if te == 1:
            parts.append(["ジュウ"])
        else:
            parts.append([x + "ジュウ" for x in _O1[te]])
    if o:
        parts.append(_O1[o])
    return set(_join(parts))


# --- 英語(0-99): 語 + カタカナ ---
_E1W = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_ETW = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_ETN = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_E1K = ["ゼロ", "ワン", "ツー", "スリー", "フォー", "ファイブ", "シックス", "セブン", "エイト", "ナイン"]
_ETWK = ["テン", "イレブン", "トゥエルブ", "サーティーン", "フォーティーン", "フィフティーン",
         "シックスティーン", "セブンティーン", "エイティーン", "ナインティーン"]
_ETNK = ["", "", "トゥエンティ", "サーティ", "フォーティ", "フィフティ", "シックスティ", "セブンティ", "エイティ", "ナインティ"]


def eng_word(n):
    if 0 <= n <= 9:
        return _E1W[n]
    if 10 <= n <= 19:
        return _ETW[n - 10]
    if 20 <= n <= 99:
        return _ETN[n // 10] + ("-" + _E1W[n % 10] if n % 10 else "")
    return None


def eng_kana(n):
    if 0 <= n <= 9:
        return _E1K[n]
    if 10 <= n <= 19:
        return _ETWK[n - 10]
    if 20 <= n <= 99:
        return _ETNK[n // 10] + (_E1K[n % 10] if n % 10 else "")
    return None


def _norm_n(ds):
    return int(ds.translate(str.maketrans("０１２３４５６７８９", "0123456789")))


def sandhi_variants(r):
    """音便変化形(数字+助数詞で先頭が変化): ヒャク→ヒャッ, イチ→イッ, ロク→ロッ, ジュウ→ジッ/ジュッ 等。"""
    out = {r}
    if r and r[-1] in "クチツ":
        out.add(r[:-1] + "ッ")
    if r.endswith("ジュウ"):
        out.add(r[:-3] + "ジッ")
        out.add(r[:-3] + "ジュッ")
    return out


def _nk(s):
    """カタカナ正規化(ヴ→ブ系・長音/中黒除去)で照合のゆれを吸収。"""
    s = (s or "")
    for a, b in (("ヴァ", "バ"), ("ヴィ", "ビ"), ("ヴェ", "ベ"), ("ヴォ", "ボ"), ("ヴュ", "ビュ"), ("ヴ", "ブ")):
        s = s.replace(a, b)
    return re.sub(r"[ー・]", "", s)


def classify_and_fix(title, seg, slug):
    """分かち書き token 単位で再構築。 数字の読みに一致する token 列を数字/英単語に置換。
    → (new_slug, type, flag)。"""
    if re.search(r"[A-Za-z]", title):
        return slug, "latin-mixed", "latin混じり(別処理)"
    digits = re.findall(r"[0-9０-９]+", title)
    if not digits:
        return slug, "no-digit", ""
    if not seg or not re.search(r"[\s　]", seg):
        return slug, "no-segment", "分かち書き無=token置換不可"

    tokens = seg.split()
    # 各数字の候補読み(カタカナ)→ token列照合
    targets = []  # (candidate_set, kind, n)
    rest_nondigit = re.sub(r"[0-9０-９\s　!！?？・:：。、\-‐〜~]+", "", title)
    for ds in digits:
        n = _norm_n(re.sub(r"[^0-9０-９]", "", ds))
        sino = sino_candidates(n)
        ek = eng_kana(n)
        targets.append((sino, ek, n))

    out_tokens = []
    types = []
    flag = ""
    i = 0
    used = set()
    while i < len(tokens):
        matched = False
        for sino, ek, n in targets:
            if n in used:
                continue
            # token 列(1〜4連結)が読み候補に一致するか
            sino_n = {_nk(s) for s in sino}
            ek_n = _nk(ek) if ek else None
            # (a) 完全一致(token列 == 読み)
            for span in range(1, min(4, len(tokens) - i) + 1):
                joined = _nk("".join(tokens[i:i + span]))
                if joined in sino_n:
                    out_tokens.append(str(n)); types.append("音読み→数字"); used.add(n)
                    i += span; matched = True; break
                if ek_n and joined == ek_n:
                    if len(rest_nondigit) <= 1:
                        out_tokens.append(eng_word(n) or str(n)); types.append("英語読み→英単語")
                    else:
                        out_tokens.append(str(n)); types.append("英語読み付随→数字")
                    used.add(n); i += span; matched = True; break
            if matched:
                break
            # (b) ★先頭一致(合体token: 数字読み+助数詞)= sandhi変化形で分割
            sino_pref = sorted({sv for s in sino for sv in sandhi_variants(s)}, key=len, reverse=True)
            for V in sino_pref:
                if tokens[i].startswith(V) and len(tokens[i]) > len(V):
                    rest = tokens[i][len(V):]
                    if rest.startswith("ツ"):  # 訓読み助数詞つ(7つ=ナナツ等)→分割せずヘボン
                        continue
                    out_tokens.append(str(n)); out_tokens.append(hslug(rest))
                    types.append("音読み→数字(先頭分割)"); used.add(n); i += 1; matched = True; break
            if not matched and ek and tokens[i].startswith(ek) and len(tokens[i]) > len(ek):
                out_tokens.append(str(n) if len(rest_nondigit) > 1 else (eng_word(n) or str(n)))
                out_tokens.append(hslug(tokens[i][len(ek):]))
                types.append("英語読み(先頭分割)"); used.add(n); i += 1; matched = True
            if matched:
                break
        if not matched:
            out_tokens.append(hslug(tokens[i])); i += 1
    # 未消化の数字(token列に読みが見つからなかった=sandhi合体等)
    if any(n not in used for *_, n in targets):
        flag = "数字の読みがtoken分割と不一致(sandhi等)→要確認"
        types.append("訓読み/当て字 or sandhi")
    new = re.sub(r"-{2,}", "-", "-".join(t for t in out_tokens if t)).strip("-")
    return new, " ; ".join(dict.fromkeys(types)), flag


def main():
    import pickle
    # title_kana(カタカナ)は v2 TSV に無い → pickle から key→title_kana を取得
    d = pickle.load((ROOT / ".cache" / "seed3-promote.pkl").open("rb"))
    key2seg = {e["key"]: (e.get("title_kana_segmented") or e.get("title_kana") or "") for e in d.values()}
    rows = [r for r in csv.DictReader(V2.open(encoding="utf-8"), delimiter="\t") if r["source"] == "kana-num"]
    out = []
    from collections import Counter
    tcount = Counter()
    changed = 0
    for r in rows:
        seg = key2seg.get(r["key"], "")
        new, typ, flag = classify_and_fix(r["title"], seg, r["slug"])
        ch = new != r["slug"]
        if ch:
            changed += 1
        for t in typ.split(" ; "):
            tcount[t] += 1
        out.append((r["title"], r["kana_slug"], r["slug"], new, typ, "CHANGED" if ch else "", flag))
    with OUT.open("w", encoding="utf-8") as f:
        f.write("title\tkana_slug\tv2_slug\tnew_slug\ttype\tchanged\tflag\n")
        for x in out:
            f.write("\t".join(str(v) for v in x) + "\n")
    print(f"=== num {len(rows)}件 / 変更 {changed}件 → {OUT} (適用なし) ===")
    for k, v in tcount.most_common():
        print(f"  {k}: {v}")
    flagged = sum(1 for x in out if x[6])
    print(f"要レビューflag: {flagged}")
    print("\n=== 既知例の検証 ===")
    want = ["麻雀放浪記2020", "ペルソナ5", "金色のガッシュ!!2", "公爵夫人の50のお茶レシピ", "君と100回目の恋", "139", "ソードアート・オンライン 4コマ公式アンソロジー"]
    for w in want:
        for x in out:
            if x[0] == w:
                print(f"  {x[0][:24]:<24} v2={x[2]:<28} → {x[3]:<28} [{x[4]}]")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
