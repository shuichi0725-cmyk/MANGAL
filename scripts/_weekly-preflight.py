#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週次蒸留 preflight (2026-07-10 弱モデル耐性ハードニング): ビルド開始前の機械ゲート。

散文チェックリスト(skill手順2-3)をscript強制に。FAILが1つでもあれば exit 1 = ビルド開始禁止。

  python scripts/_weekly-preflight.py          # 検査のみ(FAIL項目と直し方を列挙)
  python scripts/_weekly-preflight.py --fix    # 安全に直せる物は直す(junction再作成/stagingコピー)

検査項目 (★2026-07-17 C:完結に全面改訂=ユーザ裁定「ジャンクション全廃・D:はバックアップ倉庫のみ」。
  旧D:junction構成は旧PCのC:満杯が理由で、新PCはC:856GB空きのため廃止。D:外付けはストールしやすく
  ビルド経路に入れない):
  1. scripts/src/lib/next.config.ts の未コミット変更なし(promote拡張commit漏れ=2026-07-04実害)
  2. next.config.ts staticPageGenerationTimeout=300(無いと重頁3回超過でビルドkill)
  3. ディスク: C:空き30GB+(out/.next 10-15GB + staging ~3GB。ENOSPC=2026-07-05実害)
  4. out/ と .next/ が junctionでない(残骸junctionは--fixで除去。実体dirはそのまま=nextが管理)
  5. staging .cache/proddata: 実体コピー3dir(manga=manga.v2/seeds/art-books)+masters6+索引3本を同期(--fix=robocopy /MIR)
  6. 手順1の生成物鮮度(本番索引が7日超古い=再生成忘れ疑い)=WARN
"""
import os, sys, json, shutil, subprocess, time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, ".cache", "proddata")
MASTERS = ["demographics.yml", "genres.yml", "magazines.yml",
           "publisher-aliases.yml", "publishers.yml", "slug-aliases.yml"]
INDEXES = ["manga-list-index.json", "manga-catch-index.json",
           # ★titles-pages(2026-08-31): /titles静的ルートの単一ソース。staging未同期だと
           #   ビルドが空フォールバックで351頁が _empty だけになる(初回週次で実踏)
           "titles-pages.json"]

fails, warns = [], []


def ok(msg):
    print(f"  OK   {msg}")


def fail(msg, how=""):
    fails.append(msg)
    print(f"  FAIL {msg}" + (f"\n       → {how}" if how else ""))


def warn(msg):
    warns.append(msg)
    print(f"  WARN {msg}")


def is_junction(path):
    try:
        os.readlink(path)
        return True
    except OSError:
        return False


def main():
    fix = "--fix" in sys.argv
    os.chdir(ROOT)

    # 1. コード未コミット
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8")
    dirty_code = [l for l in (r.stdout or "").splitlines()
                  if l[3:].startswith(("scripts/", "src/", "lib/", "next.config", "package.json"))]
    if dirty_code:
        fail(f"コード未コミット {len(dirty_code)} 件(ビルドに乗るのにgitに無い=diff-deploy基準が壊れる)",
             "commit+pushしてから: " + " / ".join(l.strip() for l in dirty_code[:5]))
    else:
        ok("scripts/src/lib/next.config = コミット済")

    # 2. timeout設定
    try:
        cfg = open(os.path.join(ROOT, "next.config.ts"), encoding="utf-8").read()
        if "staticPageGenerationTimeout" in cfg and "300" in cfg:
            ok("staticPageGenerationTimeout=300")
        else:
            fail("staticPageGenerationTimeout=300 が next.config.ts に無い", "無いと重頁が3回超過でビルドkill(2026-07-05)")
    except OSError:
        fail("next.config.ts が読めない")

    # 3. ディスク (★C:のみ=D:はビルド経路から完全排除 2026-07-17)
    try:
        c_free = shutil.disk_usage("C:\\").free / 1e9
        if c_free < 30:
            fail(f"C: 空き {c_free:.1f}GB < 30GB", "out/.next 10-15GB + staging ~3GB 要る")
        else:
            ok(f"C: 空き {c_free:.1f}GB")
    except OSError as e:
        fail(f"ディスク確認不能: {e}")

    # 4. out/.next は junction 禁止 (★残骸junctionがD:を指すとD:ストールに巻き込まれる)
    for name in ("out", ".next"):
        p = os.path.join(ROOT, name)
        if is_junction(p):
            if fix:
                os.rmdir(p)   # junction自体のみ除去(再帰しない)
                ok(f"{name}/ 残骸junction除去(以後C:実体でnextが自動作成)")
            else:
                fail(f"{name}/ が junction({os.readlink(p)})", "--fix で除去(C:完結方針)")
        else:
            ok(f"{name}/ = {'C:実体dir' if os.path.exists(p) else '無し(ビルドが作る)'}")

    # 5. staging同期 (★実体コピー。junction不使用)
    os.makedirs(STAGE, exist_ok=True)
    for sub, src_name in (("manga", os.path.join("data", "manga.v2")),
                          ("seeds", os.path.join("data", "seeds")),
                          ("art-books", os.path.join("data", "art-books"))):
        sp, dp = os.path.join(ROOT, src_name), os.path.join(STAGE, sub)
        if not os.path.isdir(sp):
            fail(f"{src_name} が無い")
            continue
        if fix:
            r2 = subprocess.run(["robocopy", sp, dp, "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/R:2", "/W:2"],
                                capture_output=True, text=True)
            if r2.returncode <= 7:   # robocopy 0-7=成功
                ok(f"staging/{sub} 同期(robocopy /MIR ← {src_name})")
            else:
                fail(f"staging/{sub} robocopy失敗 rc={r2.returncode}")
        else:
            n_src = sum(len(f) for _, _, f in os.walk(sp))
            n_dst = sum(len(f) for _, _, f in os.walk(dp)) if os.path.isdir(dp) else 0
            if n_src == n_dst and n_dst > 0:
                ok(f"staging/{sub} 件数一致 {n_dst:,}")
            else:
                fail(f"staging/{sub} 不一致 src={n_src:,} dst={n_dst:,}", "--fix でrobocopy /MIR")
    if True:
        stale = []
        for f in MASTERS + INDEXES:
            src, dst = os.path.join(ROOT, "data", f), os.path.join(STAGE, f)
            if not os.path.exists(src):
                fail(f"data/{f} が無い(手順1の生成漏れ?)")
                continue
            if (not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst) + 1
                    or os.path.getsize(src) != os.path.getsize(dst)):
                if fix:
                    shutil.copy2(src, dst)
                    ok(f"staging同期: {f}")
                else:
                    stale.append(f)
        if stale:
            fail(f"staging未同期 {len(stale)} 件: {', '.join(stale)}", "--fix でコピー")
        elif not fix:
            ok("staging masters+索引 = 同期済")

    # 6. 生成物鮮度(WARN)
    idx = os.path.join(ROOT, "data", "manga-list-index.json")
    if os.path.exists(idx):
        age = (time.time() - os.path.getmtime(idx)) / 86400
        if age > 7:
            warn(f"本番索引が {age:.0f} 日前(手順1の再生成を忘れていないか)")
        else:
            ok(f"本番索引 鮮度 {age:.1f} 日")

    # 7. ★索引衛生監査(2026-07-14 新設: cover短縮漏れ/スキーマドリフト/head・alt整合。fail=ビルド禁止)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_audit-index-hygiene.py"), "data"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        ok("索引衛生(cover slim/スキーマ/head/alt) = OK")
    else:
        fail("索引衛生NG", (r.stdout or "") + (r.stderr or ""))

    # 8. ★R2 prune 待ち(2026-08-08 新設・ユーザ指示「週次蒸留するときにわかるように」):
    #    頁を drop / slug rename しても R2 の実体フォルダは残る([[r2_orphan_pages_prune_missing]])。
    #    per-case作業で消した公開slugを pending-r2-prune.jsonl に積んでおき、ここで必ず目に入れる。
    pend = os.path.join(ROOT, "data", "seeds", "pending-r2-prune.jsonl")
    rows = []
    if os.path.exists(pend):
        for ln in open(pend, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    if rows:
        warn(f"★R2 prune 待ち {len(rows)} 件 = 今回の r2-sync に必ず --prune を付ける")
        for r2 in rows[:30]:
            print(f"         /{r2.get('slug')}  ({r2.get('reason','')} {r2.get('at','')})")
        if len(rows) > 30:
            print(f"         …ほか {len(rows)-30} 件")
        print("       → 実行後 .cache/r2-pruned-<日時>.txt に載ったか照合し、"
              "載った行を data/seeds/pending-r2-prune.jsonl から消し込む")
    else:
        ok("R2 prune 待ち = なし")

    # 8b. ★リダイレクト衛生(2026-08-14 新設・ユーザ指示「調査して間違いないようだったら週次蒸留時削除」):
    #    slug-aliases.yml は per-case の drop/rename のたび増えるが、宛先が後で消えても誰も気付かない。
    #    2026-08-14 の初回掃除で 死に転送422 + ★alias キーが実在の公開slugと衝突51 を検出した
    #    (衝突は転送が効き出した瞬間に実頁を隠す=デビルマン等)。同じ腐り方を二度させないための番人。
    #    3種を FAIL にする: ①連鎖解決後も宛先が非公開 ②キーが公開slugと衝突 ③自己参照。
    try:
        import re as _re
        _idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
        _si = _idx["f"].index("slug")
        _pub = {r[_si] for r in _idx["d"]}
        _al = {}
        for _ln in open(os.path.join(ROOT, "data", "slug-aliases.yml"), encoding="utf-8"):
            _m = _re.match(r"^(\S+):\s*(.+)$", _ln)
            if _m:
                _al[_m.group(1)] = _m.group(2).strip()

        def _resolve(k, limit=10):
            seen, cur = set(), _al[k]
            while cur in _al and cur not in seen and limit > 0:
                seen.add(cur)
                cur = _al[cur]
                limit -= 1
            return cur

        _dead = [k for k in _al if _resolve(k) not in _pub]
        _clash = [k for k in _al if k in _pub]
        _self = [k for k, v in _al.items() if k == v]
        # ★形状番人(2026-08-14 リダイレクト層復旧): _redirects は /manga/<旧> /manga/<新> 301 形状で
        #   yml と1:1 でなければならない(ルート直下形状は届かない=記憶 redirect_layer_inactive)。
        #   ★比較先は連鎖の最終解決先(2026-08-18 修正: _gen-redirects は連鎖を平坦化して書くため、
        #     yml の直接宛先と比べると連鎖alias 658件が全部偽NGになっていた)。
        _rd = {}
        for _ln in open(os.path.join(ROOT, "public", "_redirects"), encoding="utf-8"):
            _p = _ln.split()
            if len(_p) >= 3 and _p[2] == "301":
                _rd[_p[0]] = _p[1]
        _shape = ([k for k in _al if _rd.get(f"/manga/{k}") != f"/manga/{_resolve(k)}"]
                  + [k for k in _rd if not k.startswith("/manga/")])
        if _dead or _clash or _self or _shape:
            _how = ""
            if _dead:
                _how += f"死に転送 {len(_dead)} 件(宛先が公開slugに無い): " + ", ".join(_dead[:10]) + "\n"
            if _clash:
                _how += f"★キーが実在の公開slugと衝突 {len(_clash)} 件(転送が効くと実頁が消える): " + ", ".join(_clash[:10]) + "\n"
            if _self:
                _how += f"自己参照 {len(_self)} 件: " + ", ".join(_self[:10]) + "\n"
            if _shape:
                _how += (f"★_redirects 形状/同期NG {len(_shape)} 件(/manga/形状でyml未反映): "
                         + ", ".join(_shape[:10]) + "\n")
            _how += ("→ 宛先が rename/dedup で移っただけなら付け替え、頁ごと drop 済みなら行を削除。"
                     "その後 python scripts/_gen-redirects.py で public/_redirects を再生成"
                     "(本番KVは r2-sync 後に python scripts/_kv-redirects-sync.py)")
            fail(f"リダイレクト衛生NG(死{len(_dead)}/衝突{len(_clash)}/自己{len(_self)}/形状{len(_shape)})", _how)
        else:
            ok(f"リダイレクト衛生 = OK(alias {len(_al)} 件・死に転送0・衝突0・/manga/形状同期済)")
    except Exception as _e:
        warn(f"リダイレクト衛生チェックを実行できず: {_e}")

    # 9. ★ISBN消失監視(2026-08-08 新設・ユーザ裁定「本当にある物を消したときに私は気がつけない」):
    #    前回スナップショットから消えたISBNを台帳(non-manga-drop/deny/exclude/prune)と突合し、
    #    **理由なしの消失**を FAIL にする。変なslugはユーザが見つけられるが、
    #    存在しないものは誰にも見えない=機械で名指しするしかない。
    r9 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_audit-isbn-loss.py")],
                        capture_output=True, text=True, encoding="utf-8")
    _o9 = (r9.stdout or "") + (r9.stderr or "")
    if r9.returncode == 0:
        ok("ISBN消失監視 = 理由なしの消失なし")
    else:
        fail("★理由なくISBNが本番から消えている(実在する巻を消した疑い)", _o9)
    print("       ※週次の最後に `python scripts/_audit-isbn-loss.py --snapshot` で基準を取り直す")

    # 10. ★品質ベースライン番人(2026-08-24 ユーザGO⑤): publisher(unknown)とslug無分割塊の
    #     **増加**を公開前に止める(蒸留以外の経路=per-case作業で入った同型も捕まえる)。
    #     基準 = data/seeds/preflight-baselines.json(git)。改善で減った時は基準を自動で下げる。
    try:
        import json as _json
        _bp = os.path.join(ROOT, "data", "seeds", "preflight-baselines.json")
        _base = _json.load(open(_bp, encoding="utf-8")) if os.path.exists(_bp) else {}
        _li = _json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
        _isl = _li["f"].index("slug")
        _mush = sorted(s for s in (str(r[_isl]) for r in _li["d"])
                       if max((len(x) for x in s.split("-")), default=0) >= 15 or len(s) >= 78)
        import glob as _glob
        _unk = 0
        for _f in _glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
            for _ln in open(_f, encoding="utf-8"):
                if _ln.startswith("publisher:"):
                    if "(unknown)" in _ln:
                        _unk += 1
                    break
        _changed = False
        for _k, _v in (("slug_mush", len(_mush)), ("publisher_unknown", _unk)):
            _b = _base.get(_k)
            if _b is None or _v < _b:
                _base[_k] = _v
                _changed = True
                ok(f"品質基準 {_k} = {_v}(基準を{'初期化' if _b is None else '更新'})")
            elif _v > _b:
                fail(f"★{_k} が増加 {_b} → {_v}(公開前に是正する)",
                     "slug_mush=題の切れ目でrename / publisher_unknown=cleanの正規パス差し替え漏れを疑う(月次skill罠)")
            else:
                ok(f"品質基準 {_k} = {_v}(基準内)")
        # ★逆向きベースライン(2026-08-26 種4-auto全消し事故883巻の最安の網): 蓄積台帳は
        #   **減少=FAIL**(増加が正常)。全消し/大量退役が公開前に鳴る。
        try:
            import yaml as _yaml
            _s4 = len((_yaml.safe_load(open(os.path.join(ROOT, "data", "seeds",
                       "volumes-supplement-auto.yml"), encoding="utf-8")) or {}).get("volumes") or [])
        except Exception:
            _s4 = -1
        if _s4 < 0:
            fail("★種4-auto(volumes-supplement-auto.yml)が読めない", "parse死=全消し前兆。先に直す")
        else:
            _b4 = _base.get("seed4_auto_volumes")
            if _b4 is None or _s4 > _b4:
                _base["seed4_auto_volumes"] = _s4
                _changed = True
                ok(f"品質基準 seed4_auto_volumes = {_s4}(基準を{'初期化' if _b4 is None else '更新'})")
            elif _s4 < _b4:
                fail(f"★種4-auto台帳が減少 {_b4} → {_s4}(蓄積台帳=全消し/誤退役の疑い)",
                     "正当な退役(種2追いつき分の個別除去)なら data/seeds/preflight-baselines.json の"
                     " seed4_auto_volumes を手で下げて通す(理由をcommitメッセージに書く)")
            else:
                ok(f"品質基準 seed4_auto_volumes = {_s4}(基準内)")
        if _changed:
            _json.dump(_base, open(_bp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception as _e:
        warn(f"品質ベースライン番人を実行できず: {_e}")

    # 11. ★R2 Class A 予算予測 (2026-08-26 ユーザ裁定「週次は絶対毎週やる」: 27日〆期に週次が
    #     5回入る月は全頁週×5=95万で枠1Mに肉薄する。ビルド開始前に着地見込みを必ず見せる)
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import _r2_ops_ledger as _rl
        _used, _wl, _proj = _rl.projection()
        _line = f"R2予算: 今期Class A {_used:,} / 週次あと{_wl}回 → 着地見込み {_proj:,} / 枠 1,000,000"
        if _proj > 1_000_000:
            warn(_line + " ★超過見込み=今週のUI共通部変更を見送れば全頁週→差分週になり収まる")
        else:
            ok(_line)
    except Exception as _e:
        warn(f"R2予算予測を実行できず: {_e}")

    print(f"\n結果: FAIL {len(fails)} / WARN {len(warns)}")
    if fails:
        print("★ビルド開始禁止。上のFAILを直してから再実行。")
        sys.exit(1)
    print("→ preflight全通過。ビルド開始可:")
    print(f'  $env:MANGAL_DATA_DIR="{STAGE}"; npx next build 2>&1 | Out-File .cache\\weekly-build.log')


if __name__ == "__main__":
    main()
