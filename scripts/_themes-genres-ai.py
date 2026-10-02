# -*- coding: utf-8 -*-
"""要素・ジャンルを厚くする(③④)= 材料を読んだAIが閉じた語彙から選び、根拠の語句を材料から抜き出す。
2026-10-02 ユーザ指示「③④をsonnet5.5に指示したい」。分担= Sonnetが判定を書き、Opusが点検する
([[feedback_sonnet_writes_opus_audits]])。AIは「読んで選ぶ」だけ。材料の束ね・機械検査・書込はこの道具。

  task:
    themes = 要素0の頁に要素を足す(③)  → data/seeds/tags-enrich-2425.json (英語タグ名・純粋追加)
    genres = ジャンルが汎用だけ(drama/comedy/romance/slice-of-life/action/other)の頁に具体ジャンルを足す(④)
             → data/seeds/genre-append.yml (既存genres・フラグ不変の union。source で出所を残す=取り消し可能)

  使い方:
    python scripts/_themes-genres-ai.py prep                     # 対象+材料を作る(.cache/tg-ai/<task>-targets.jsonl)
    python scripts/_themes-genres-ai.py show <task> <開始id> <件数> # 材料を読む(判定用)
    python scripts/_themes-genres-ai.py check <task>              # 回答の機械検査だけ(書き込みなし)
    python scripts/_themes-genres-ai.py apply <task> <stage> [--go] [--model=sonnet-5.5]
                                                                   # 未適用の合格回答を書込+台帳+反映用slugリスト(700ずつ)
  回答ファイル: .cache/tg-ai/<task>-ans/*.jsonl  1行=1頁
    {"id": 123, "add": ["結婚", "宮廷"], "basis": {"結婚": "政略結婚を命じられ", "宮廷": "後宮で働く"}}
    {"id": 124, "add": [], "skip": "材料不足"}   ← 付けない頁も必ず1行(どこまで読んだかの記録)
  機械検査(不合格は書かない): 語彙外 / 根拠が材料に無い(完全一致) / 根拠が無い / 既に付いている / 1頁4個以上
"""
import datetime, glob, io, json, os, re, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
OUT = D('.cache', 'tg-ai')
sys.stdout.reconfigure(encoding='utf-8')

GENERIC = {'drama', 'comedy', 'romance', 'slice-of-life', 'action', 'other'}
# ④で足してよいジャンル(具体キー)。2026-10-01 genre-pilot で適合率90%を確認した群 + 明記で判定できる群。
# ★school/ecchi/mind-game は入れない(AI乱発の前歴・境界があいまい)。汎用キー(drama等)も足さない。
GENRE_ALLOW = ['fantasy', 'sci-fi', 'mystery', 'suspense', 'horror', 'adventure', 'historical', 'samurai', 'war',
               'sports', 'baseball', 'soccer', 'romcom', 'gag', 'gourmet', 'music', 'mecha', 'yokai', 'bl',
               'mahou-shoujo', 'isekai', 'supernatural', 'essay', '4-koma']
VOCAB = json.load(open(D('data/enrich-out-2026-07/theme-vocab-ja.json'), encoding='utf-8'))  # 和名→英語タグ名
# ③で使わない要素: 抽象的で材料から言い切れない / ジャンルと同義で畳まれる / 2026-10-02 抜き取りで半分外れ
THEME_DENY = {'悲劇', '成長物語', '哲学', '癒し系', 'シュール', 'ドタバタ', 'パロディ', 'メタ', '疑似家族', '異性愛',
              'ティーンズラブ', '電波系', 'ちび', '美少女日常', '風刺', '青春',
              '異世界', '学園', 'ボーイズラブ', '野球',
              '執筆', '政治', '自殺', '暗殺者'}
THEME_ALLOW = sorted(k for k in VOCAB if k not in THEME_DENY)
MAX_ADD = 3


def _index():
    ix = json.load(open(D('data/manga-list-index.json'), encoding='utf-8'))
    return [dict(zip(ix['f'], r)) for r in ix['d']]


def _pub2src():
    import yaml
    ov = (yaml.safe_load(open(D('data/seeds/slug-overrides.yml'), encoding='utf-8')) or {}).get('overrides', {})
    return {(v or {}).get('slug'): k for k, v in ov.items() if isinstance(v, dict) and v.get('slug')}


def _clip(s, n):
    s = re.sub(r'\s+', ' ', s or '').strip()
    return s if len(s) <= n else s[:n] + '…'


def prep():
    import yaml
    try:
        from yaml import CSafeLoader as L
    except ImportError:
        from yaml import SafeLoader as L
    os.makedirs(OUT, exist_ok=True)
    rows = _index()
    p2s = _pub2src()
    catch = json.load(open(D('data/manga-catch-index.json'), encoding='utf-8'))
    rcap = {}
    p = D('.cache/genre-rakuten/corpus-v2.jsonl')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            o = json.loads(l); rcap[o['slug']] = o.get('caption') or ''
    kobo = {}
    p = D('.cache/kobo-caption/harvest.jsonl')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            o = json.loads(l)
            st = sorted([m for m in o['matched'] if m.get('match') == 'strict'], key=lambda m: (m.get('vol') or 999))
            if st and st[0].get('cap'):
                kobo[o['slug']] = st[0]['cap']
    out = {'themes': [], 'genres': []}
    for r in rows:
        s = r['slug']
        want_t = not r['themes']
        want_g = set(r['genres'] or []) <= GENERIC
        if not (want_t or want_g):
            continue
        src = p2s.get(s, s)
        syn = ''
        f = D('data/manga.v2', src + '.yml')
        if os.path.exists(f):
            try:
                d = yaml.load(io.open(f, encoding='utf-8'), Loader=L) or {}
                syn = d.get('synopsis') or ''
            except Exception:
                pass
        mat = {k: v for k, v in (('catch', catch.get(s) or ''), ('synopsis', _clip(syn, 500)),
                                 ('rakuten', _clip(rcap.get(s), 700)), ('kobo', _clip(kobo.get(s), 400))) if v}
        if not mat:
            continue
        base = {'slug': s, 'src': src, 'title': r['title'], 'genres': r['genres'] or [], 'themes': r['themes'] or [],
                'material': mat}
        if want_t: out['themes'].append(base)
        if want_g: out['genres'].append(base)
    for task, lst in out.items():
        with open(os.path.join(OUT, f'{task}-targets.jsonl'), 'w', encoding='utf-8') as f:
            for i, x in enumerate(lst):
                f.write(json.dumps({'id': i, **x}, ensure_ascii=False) + '\n')
        os.makedirs(os.path.join(OUT, f'{task}-ans'), exist_ok=True)
        print(f'{task}: 対象 {len(lst)} 頁 → .cache/tg-ai/{task}-targets.jsonl')


def _targets(task):
    return {o['id']: o for o in map(json.loads, open(os.path.join(OUT, f'{task}-targets.jsonl'), encoding='utf-8'))}


def show(task, start, n):
    T = _targets(task)
    allow = THEME_ALLOW if task == 'themes' else GENRE_ALLOW
    print('使える語:', ' '.join(allow))
    for i in range(start, start + n):
        if i not in T:
            break
        o = T[i]
        print(f"\n### id={i} 『{o['title']}』 現ジャンル={','.join(o['genres'])} 現要素={','.join(o['themes']) or '-'}")
        for k, v in o['material'].items():
            print(f'  [{k}] {v}')


def _answers(task):
    A = {}
    for f in sorted(glob.glob(os.path.join(OUT, f'{task}-ans', '*.jsonl'))):
        for n, l in enumerate(open(f, encoding='utf-8'), 1):
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except Exception as e:
                print(f'JSON不正 {os.path.basename(f)}:{n} {e}')
                continue
            A[o['id']] = o
    return A


def _check(task, T, A):
    allow = set(THEME_ALLOW if task == 'themes' else GENRE_ALLOW)
    ok, ng = {}, []
    for i, a in A.items():
        if i not in T:
            ng.append((i, 'idが対象外')); continue
        o = T[i]; mtext = '\n'.join(o['material'].values())
        have = set(o['themes'] if task == 'themes' else o['genres'])
        add = list(dict.fromkeys(a.get('add') or []))
        if len(add) > MAX_ADD:
            ng.append((i, f'{len(add)}個(上限{MAX_ADD})')); continue
        good = []
        for k in add:
            b = (a.get('basis') or {}).get(k) or ''
            if k not in allow: ng.append((i, f'語彙外:{k}'))
            elif k in have: ng.append((i, f'既に付いている:{k}'))
            elif len(b) < 2: ng.append((i, f'根拠なし:{k}'))
            elif b not in mtext: ng.append((i, f'根拠が材料に無い:{k}「{b}」'))
            else: good.append(k)
        if good:
            ok[i] = good
    return ok, ng


def check(task):
    T, A = _targets(task), _answers(task)
    ok, ng = _check(task, T, A)
    print(f'{task}: 回答 {len(A)} 頁 / 付与あり {len(ok)} 頁・のべ {sum(map(len, ok.values()))} / 不合格 {len(ng)} 件')
    for i, why in ng[:60]:
        print(f'  NG id={i} {why}')


def apply(task, stage, go, model):
    T, A = _targets(task), _answers(task)
    ok, ng = _check(task, T, A)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    logp = D('docs', 'production-diagnostics', f'{task}-ai-changelog.jsonl')
    done = set()
    if os.path.exists(logp):
        for l in open(logp, encoding='utf-8'):
            o = json.loads(l)
            if 'id' in o and o.get('task') == task:
                done.add(o['id'])
    todo = {i: v for i, v in ok.items() if i not in done}
    logs, changed = [], []
    if task == 'themes':
        tp = D('data/seeds/tags-enrich-2425.json')
        tags = json.load(open(tp, encoding='utf-8'))
        for i, ks in todo.items():
            o = T[i]; k = o['src']
            en = [VOCAB[x] for x in ks]
            add = [t for t in en if t not in tags.get(k, [])]
            if not add:
                continue
            tags[k] = list(tags.get(k, [])) + add
            changed.append(k)
            logs.append({'id': i, 'task': task, 'slug': o['slug'], 'src': k, 'themes_add': ks,
                         'basis': {x: A[i]['basis'][x] for x in ks}, 'stage': stage, 'model': model, 'at': now})
    else:
        gp = D('data/seeds/genre-append.yml')
        lines = []
        for i, ks in todo.items():
            o = T[i]
            add = list(ks)
            if {'baseball', 'soccer'} & set(add) and 'sports' not in o['genres'] and 'sports' not in add:
                add.append('sports')  # 階層検索の規約(CLAUDE.md)
            # ★slugは必ず引用符(数字だけの題「300」がYAMLでintになり黙って効かなかった 2026-10-03)
            lines.append(f"  - slug: {json.dumps(o['slug'], ensure_ascii=False)}\n    add: [{', '.join(add)}]\n    source: \"{stage}:{model}\"\n")
            changed.append(o['src'])
            logs.append({'id': i, 'task': task, 'slug': o['slug'], 'src': o['src'], 'genres_add': add,
                         'basis': {x: A[i]['basis'][x] for x in ks}, 'stage': stage, 'model': model, 'at': now})
    print(f'{task}/{stage}: 新規書込 {len(logs)} 頁・のべ {sum(len(l.get("themes_add") or l.get("genres_add")) for l in logs)}'
          f' (合格済み {len(ok)} / 既に適用 {len(ok) - len(todo)} / 不合格 {len(ng)})')
    if not go or not logs:
        return
    stamp = now.replace(':', '')
    if task == 'themes':
        shutil.copy2(tp, D('.cache', f'tags-enrich-2425.json.bak-{stage}-{stamp}'))
        json.dump(tags, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    else:
        shutil.copy2(gp, D('.cache', f'genre-append.yml.bak-{stage}-{stamp}'))
        with open(gp, 'a', encoding='utf-8') as f:  # 既存ファイルはCRLF = Windows既定の改行で揃える
            f.write(''.join(lines))
    with open(logp, 'a', encoding='utf-8') as f:
        for l in logs:
            f.write(json.dumps(l, ensure_ascii=False) + '\n')
    chs = list(dict.fromkeys(changed))
    for old in glob.glob(os.path.join(OUT, f'{task}-{stage}-changed-*.txt')):
        os.remove(old)
    for n in range(0, len(chs), 700):
        open(os.path.join(OUT, f'{task}-{stage}-changed-{n // 700}.txt'), 'w', encoding='utf-8').write(','.join(chs[n:n + 700]))
    print(f'書込済。反映用slugリスト: .cache/tg-ai/{task}-{stage}-changed-*.txt ({(len(chs) + 699) // 700} 個)')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'prep':
        prep()
    elif a[0] == 'show':
        show(a[1], int(a[2]), int(a[3]))
    elif a[0] == 'check':
        check(a[1])
    elif a[0] == 'apply':
        model = next((x.split('=', 1)[1] for x in a if x.startswith('--model=')), 'sonnet-5.5')
        apply(a[1], a[2], '--go' in a, model)
