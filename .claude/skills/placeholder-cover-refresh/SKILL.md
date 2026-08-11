---
name: placeholder-cover-refresh
description: 仮書影直して=発売前に付いた「文字だけの書影(.gif)」を楽天に実物が出たら差し替える。逐次保存・自然停止・冪等再開。Sonnet運転前提(アイドル運転の柱⑩)
---

# 仮書影の差し替え (= トリガー「仮書影直して」/ アイドル運転の柱⑩。2026-08-02 ユーザ発見で新設)

## 何の問題か

楽天は発売前・発売直後の本に**「著者名と書名を並べただけの画像」**を返す。実物が用意されると
★**URL自体が別物に変わる**★ため、こちらが引き直さない限り**永久に仮のまま出続ける**。
ユーザ報告「本物の書影が登録されたら勝手に変わるのかと思っていたらどうやら違うらしい」。

## 判定は URL の形だけで確実にできる (= 実測で裏取り済み)

```
本物 = .../{ISBN}_1_9.jpg    ← サフィックス _N_N 付き
仮   = .../{ISBN}.gif        ← サフィックス無し・拡張子 gif
```

実証(2026-08-02 live): HUNTER×HUNTER 39 は本番 `.gif` → live で `_1_9.jpg` が返った。
100万の命24・100億婚2 も同様。一方 0マン(1997)・100万回聞かせてよ(1999)は live でも `.gif` のまま。
= **新しい本は実物に差し替わり、旧作は絶版で永久に .gif**。

初回実測: 本番 **10,063巻**が `.gif`。うち **2025年以降=1,752巻**が対象(既定)。
2019年以前の約8,300巻は引いても無駄なので既定で除外(`--since-year` で変更可)。

## 運転 (= Sonnet。判断は要らない)

```
python scripts/_placeholder-cover-refresh.py --limit 200   # 1バッチ(~4.5分)。再起動で続き
python scripts/_placeholder-cover-refresh.py --stats       # 現在地
python scripts/_placeholder-cover-refresh.py --build-queue # ★週1でqueue再算出(週次蒸留に組込済 2026-08-12)=次の周回の起点
```

- ★**1バッチ終わったら同じコマンドを再起動**して続きを回す(④⑤⑦⑨と同型)。
- queue が尽きたら「消化済み(自然停止)」と出て終わる。**待たない・調べない**。
- **429 は script が backoff(2-45s)で自動吸収**し、連続429(実スロットル)だけ中断する
  (2026-08-03 偽429恒久対策: 旧の文字列マッチはJSON崩れの「column 429」を誤検知して停止していた。
  瞬断/JSON崩れは1件skipで走り続ける)。楽天レートは `_rate_gate` が
  ホスト単位で直列化するので、他の柱と並走してよい。
- 成果は `data/seeds/cover-override.jsonl` に**1件ごと追記**(停止しても残る)。
- 進捗は `.cache/placeholder-cover/done.json`(冪等再開の済み集合)。

### 締め (= バッチ後)
```
git add data/seeds/cover-override.jsonl && git commit -m "仮書影→実物 差し替え N件" && git push
```

## ★反映(Opus+専権)= トリガー「仮書影反映して」(2026-08-04 明文化)

溜まった cover-override.jsonl を頁に反映する時はこの一言でよい。手順:
1. **未反映slugの列挙**(seedのcover_urlと頁の実値が異なるslugだけ抽出。_ex=200x200/300x300の差は
   promoteが正規化するので同一視):
```
python - <<'EOF'
import json,io,yaml,os,re
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
norm=lambda u: re.sub(r"\?_ex=\d+x\d+$","",u or "")
ovr={}
for ln in io.open("data/seeds/cover-override.jsonl",encoding="utf-8"):
    d=json.loads(ln); ovr[str(d.get("isbn13"))]=(d.get("slug"), d.get("cover_url") or None)
todo=set()
for ib,(s,want) in ovr.items():
    p=f"data/manga.v2/{s}.yml"
    if not s or not os.path.exists(p): continue
    y=yaml.load(io.open(p,encoding="utf-8"),Loader=L)
    for e in y.get("editions") or []:
        for v in e.get("volumes") or []:
            if str(v.get("isbn13"))==ib and norm(v.get("cover_url"))!=norm(want):
                todo.add(s)
print(",".join(sorted(todo)))
EOF
```
2. `python scripts/_reflect-targeted.py --only <slugリスト> --push`(多い時は700件/チャンクで
   `--commit-only` を重ね、最後に1回push。[[romcom_backfill_state]]のチャンク実測=700頁/約65秒)。
3. 反映されない時の既知型: slug-override頁は**SRC stem**で指定(公開slugでない)。

## ★このskillが「やらない」こと

- **頁への反映はしない**。seed に書くだけ。実際に頁の書影が変わるのは上位モデルの
  「**仮書影反映して**」(上記)か週次蒸留。Sonnetは seed 追記まで。
- **旧作(2019年以前)は既定で触らない**。引いても `.gif` のままで無駄撃ちになる。
  やるなら明示的に `--build-queue --since-year 2000`(Opus判断)。
- 書影URLの**構築はしない**(ISBNからパス/サフィックス/拡張子は推測不可=実URLのみ。
  2026-07-09 の実害で確立した規律)。

## 実測の目安

試走12件で**実物7件(約6割)**。1,752件を200件/バッチ=9バッチ、合計~40分で一巡する見込み。

## NEVER

- 楽天の呼び方を自分で組み直さない(★`Referer`+`Origin` ヘッダが無いと **403**。
  2026-08-02 に実際に踏んだ。script内の `rakuten_by_isbn` が正)。
- 429 で待機しない(他の柱を回す。[[idle-run]] の共通ルール)。
- `--build-queue` を毎バッチ走らせない(66k頁走査で数分かかる。週1=週次蒸留での実行で足りる)。
- ★**「一巡完了」は終わりではない**(2026-08-03 ユーザ指摘で周回設計を実装): 実物への差し替わり時期は
  不定なので、「まだ仮のまま/no_item/error」だった巻も**次周回で全部引き直す**。--build-queue が
  done.json を自動rotateし、seed(cover-override.jsonl)在籍分だけを除外して再出発する(reflect前の
  二重照会防止)。= 週1(週次蒸留)の --build-queue → queue枯れまでバッチ再起動、の繰り返しが恒常運転。
- ★**プレースホルダは .gif だけではない**(2026-08-04 ユーザ発見で2型追加):
  ①**レーベルロゴ型**(LV999の村人21) = URL形式は本物と同じ `_1_6.jpg` なのに中身が出版社ロゴ。
    発売後に楽天が**新しい画像番号(_1_10等)で実物を追加**するため、URLパターンでは検出不能。
    → queueに**新刊窓**(発売日が直近180日〜未来の巻全部)を含め、liveのURLが**変わっていたら**差し替える
    (変わらなければ何もしない=冪等)。reason=`cover_url変化(レーベルロゴ型)`。
  ②**noimage型**(三つ目がとおる全集6巻) = 楽天の実体が緑の本アイコンでURLは正常形式。楽天に実画像が
    無いので差し替え先も無い → **cover-override.jsonl に空文字**(`"cover_url": ""`)= 書影なし確定。
    promote(`_cover_for`/適用点)と `_gen-zenshuu-data.py` が空値=削除として尊重する(2026-08-04結線)。
    このクラスは機械検出不能(内容の問題)= ユーザ報告ベースのper-case対応。

## 関連

- 常設運転=skill idle-run(柱⑩) / 頁反映=skill reflect-targeted / 書影の全体計画=[[cover_harvest_plan]]
- 同種の「実URLのみ」規律=skill daily-distill の A2-7
