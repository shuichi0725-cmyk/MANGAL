"""_fills/ の fill バッチが 種3 (series-supplement-v2.yml) に 反映済みか 照合。

batch-* = カテゴリー系 (genres/magazine/demographic/synopsis/status/en)
amiss-*  = 英語名 (alternative_titles.en)

key 形式:
  amiss: "name:著者|name:作品" (= 種3 key と同形式) → 直接照合
  batch: "Q2661273|ゴルゴ13" (= qid|title) → "qid:Q2661273|name:ゴルゴ13" に変換

判定: applied (= 種3 に同値あり) / mismatch (= 種3 に別値) / missing_key (= 種3 に key なし)
"""
import sys, json, yaml, glob
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

def batch_key_to_shu3(k):
    parts = k.split('|')
    if parts and parts[0].startswith('Q') and parts[0][1:].isdigit():
        out = 'qid:' + parts[0]
        if len(parts) >= 2: out += '|name:' + parts[1]
        if len(parts) >= 3: out += '|sub:' + parts[2]
        return out
    return k  # name: 形式 ならそのまま

def main():
    print('loading 種3...', flush=True)
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        v2 = yaml.safe_load(f)
    s3 = {e['key']: e for e in v2['series']}
    print(f'  種3 entries: {len(s3):,}', flush=True)

    # ---- amiss-* (en) ----
    print('照合 amiss-* (英語名)...', flush=True)
    am_applied = am_mismatch = am_missing = 0
    am_mismatch_samples = []
    for fp in glob.glob('data/seeds/_fills/amiss-*.json'):
        with open(fp, 'r', encoding='utf-8') as f:
            d = json.load(f)
        for k, v in d.items():
            en = ((v.get('alternative_titles') or {}).get('en')) if isinstance(v, dict) else None
            if not en: continue
            e = s3.get(k)
            if e is None:
                am_missing += 1; continue
            cur = ((e.get('alternative_titles') or {}).get('en')) if isinstance(e.get('alternative_titles'), dict) else None
            if cur == en:
                am_applied += 1
            else:
                am_mismatch += 1
                if len(am_mismatch_samples) < 12:
                    am_mismatch_samples.append((k.split('|')[-1].replace('name:',''), en, cur))

    # ---- batch-* (categories) ----
    print('照合 batch-* (カテゴリー)...', flush=True)
    FIELDS = ['genres', 'magazine', 'demographic', 'synopsis', 'status']
    bt_applied = bt_missing = 0
    field_applied = defaultdict(int); field_mismatch = defaultdict(int)
    bt_missing_samples = []
    for fp in glob.glob('data/seeds/_fills/batch-*.json'):
        with open(fp, 'r', encoding='utf-8') as f:
            d = json.load(f)
        for k, v in d.items():
            if not isinstance(v, dict): continue
            sk = batch_key_to_shu3(k)
            e = s3.get(sk)
            if e is None:
                bt_missing += 1
                if len(bt_missing_samples) < 12:
                    bt_missing_samples.append((k, sk))
                continue
            bt_applied += 1
            for fld in FIELDS:
                if fld not in v: continue
                if e.get(fld) == v.get(fld):
                    field_applied[fld] += 1
                else:
                    field_mismatch[fld] += 1

    print()
    print('=== amiss-* (英語名) 反映状況 ===')
    am_total = am_applied + am_mismatch + am_missing
    print(f'  対象 en fill: {am_total:,}')
    print(f'    反映済 (種3 と一致): {am_applied:,}')
    print(f'    値違い (種3 に別 en): {am_mismatch:,}')
    print(f'    key 未発見 (種3 に無): {am_missing:,}')
    print()
    print('=== batch-* (カテゴリー) 反映状況 ===')
    print(f'  key マッチ (種3 に存在): {bt_applied:,}')
    print(f'  key 未発見: {bt_missing:,}')
    print(f'  --- フィールド別 (マッチした key 内で 値一致 / 不一致) ---')
    for fld in FIELDS:
        a = field_applied[fld]; m = field_mismatch[fld]
        tot = a + m
        if tot:
            print(f'    {fld:14s}: 一致 {a:,} / 不一致 {m:,} ({a*100/tot:.0f}% 反映)')
    print()
    if am_mismatch_samples:
        print('=== amiss 値違い sample (fill値 → 種3現値) ===')
        for t, fill_en, cur_en in am_mismatch_samples:
            print(f'  {t!r}: {fill_en!r} → 種3={cur_en!r}')
    print()
    if bt_missing_samples:
        print('=== batch key 未発見 sample (batch key → 変換後) ===')
        for bk, sk in bt_missing_samples:
            print(f'  {bk!r} → {sk!r}')

if __name__ == '__main__':
    main()
