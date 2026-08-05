---
name: jpro-harvest
description: JPROして=JPRO出版権検索(出版社登録の権利DB)から巻抜け未解決slugの題名検索結果を無判断で全量収集。逐次保存・自然停止・冪等再開。Sonnet運転前提(アイドル運転の柱⑫)。適用=「JPRO判定して」(Opus専権)
---

# JPROハーベスト (= トリガー「JPROして/JPRO続けて」/ アイドル運転の柱⑫。2026-08-05 ユーザ裁定で新設)

## 何の問題か

巻抜けハントでNDL(納本ラグ/欠落)・楽天(在庫切れ非表示)の両方が空振りする層が残る。
**JPRO出版権検索**(jpro2.jpo.or.jp = 出版社が自分で登録する権利DB)は題名検索で
**シリーズ全巻のISBN+発行元が欠けなく出る**(実証=「10年間友達だと思ってた男の子に告白されるお話」
で紙1-10全ISBN一発→欠落7巻を即特定)。ログイン不要・CSRF+cookieの正規POSTで検索可能。

## 設計 = 全量取得→後段判断 (= ユーザ裁定 2026-08-05)

人気作は関連本込みで検索結果100行超(ONE PIECE=355行・ページネーション無し=1POSTで全量)。
**Sonnetは判断せず全部保存**する(= 取れる情報は全部取る)。抜けの判定・seed書込は
後段Opus「**JPRO判定して**」の専権。

## 運転 (= Sonnet。判断は要らない)

```
python scripts/_jpro-harvest.py --limit 100    # 1バッチ(~4分)。再起動で続き
python scripts/_jpro-harvest.py --stats        # 現在地
python scripts/_jpro-harvest.py --build-queue  # queue再算出(巻抜け台帳の未解決slug。Opus作業)
```

- 1slug=1POST(media=0=紙)。レート2.0秒/req・50reqごとにセッション取り直し。
- 成果 = `data/seeds/jpro-harvest.jsonl` に**1slug1行追記**(逐次保存・停止しても残る)。
  行形式: `{slug, query(頁題), missing(抜け巻), n_hits, hits:[{isbn13,title,publisher,media}], at}`
- 進捗 = `.cache/jpro-harvest/done.json`(冪等再開)。queueが尽きたら「消化済み(自然停止)」。
- 連続失敗は script が backoff(5/20/60s)で吸収→ダメなら進捗保存して終了。**待たない・調べない**。

### 締め (= バッチ後)
```
git add data/seeds/jpro-harvest.jsonl && git commit -m "JPROハーベスト N slug" && git push
```

## ★適用(Opus専権)= トリガー「JPRO判定して」

台帳の hits と頁の実ISBNを突き合わせ、抜け巻を埋める。手順の要点:
1. hits から**頁題+巻数パターンの行だけ**を抽出(関連本ノイズ=ファンブック/勝利学/弁当BOOK等を落とす。
   DROP_TITLE_CONTAINS_PATTERNS と同じ感覚。題正規化は巻抜けハントの norm/norm_np を使う)。
2. 巻番号を題末尾から採り、**頁の抜け番号と一致**するISBNだけ候補化。
3. **種2在チェック**(在ればedition-overrides、無ければ種4)。日付・書影は楽天ISBN直引きで補完。
4. 版の判別に注意: JPROは版種を持たない。文庫/新装が同題で混ざる(あばしり一家=角川の新装ISBN群が出る型)
   → **ISBN帯・発行元と頁の版アンカーを突合**してから入れる(版取り違え禁止=[[edition_mix_same_author_ayako]])。
5. 反映=reflect-targeted。台帳TSV(preview-volgap-local.tsv)に裁定を記帳。

## ★このskillが「やらない」こと

- **判断しない**(関連本の除外も巻番号の解釈もしない=全部保存)。
- **seed(種4/overrides)に書かない**。書くのはOpus「JPRO判定して」。
- 電子(media=1)は引かない(電子限定はスコープ外=[[ebook_only_editions_out_of_scope]])。
- 大量並走しない(1プロセス・2秒/req厳守。相手は業界インフラ=行儀最優先)。

## NEVER

- ログイン欄に触らない(検索はログイン不要領域のみ)。
- `--build-queue` を毎バッチ走らせない(queueは台帳更新後にOpusが再算出)。
- SSL検証外し(script内蔵)はこのサイトの読み取り専用文脈に限る。他所へ流用しない。

## 関連

- アクセス手順の記憶=[[jpro_pubrights_search]] / 常設運転=skill idle-run(柱⑫) / 適用先=種4([[volgap_mostly_undermerge]])
