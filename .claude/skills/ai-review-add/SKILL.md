---
name: ai-review-add
description: ai書評追加=AI書評家リーグ(corner9)の新しい節を作る。Claudeが課題図書+共通プロンプト+自分(Opus 5)の書評をチャットに出す→ユーザが他AI4本を貼る→verbatimでdata/seeds/ai-reviews.ymlへ格納。トリガー「ai書評追加」
---

# ai書評追加 (トリガー語: **ai書評追加**)

同一プロンプト×各社AIの書評を並べる週刊企画の**在庫を1節作る**手順。
企画の背景/表示は memory [[ai_review_league_operation]]、seed = `data/seeds/ai-reviews.yml`、
公開週の計算は `lib/aiLeagueSchedule.ts`(EPOCH=2026-07-05日曜、節N公開=EPOCH+(N-1)週)。

## 役割分担 (2026-09-15 改訂 = ここが現行)

- **Claude**: ①課題図書を選ぶ ②共通プロンプトを確定 ③**自分(Anthropic / Claude Opus 5 (1M))の書評を書いてチャットに出す** ← 旧ルール「私の文は入れない」はこの改訂で失効
- **ユーザ**: 同じプロンプトを他AIに貼って生成 → **4本**を「会社+モデル名」付きでチャットに貼る
- **Claude**: 5本を verbatim で seed に格納 → 番人を回す → commit & push

## 手順

### 1. 在庫と次の節番号を見る
```
python scripts/_check-ai-reviews.py
grep -nE "^  - setsu:|^    title:" data/seeds/ai-reviews.yml | tail -20
```
最大節 = N → 今回は **節 N+1**、公開日 = 2026-07-05 + (N)週(日曜)。
★**公開待ち在庫が4節を切っていたら、そのことも1行で報告**する。

### 2. 課題図書を選ぶ (Claudeの自由選定)
- **完結作のみ**(連載中・休載中は選ばない)
- **既出の作品/作者を避ける**(既出は step1 の一覧で確認。`_check-ai-reviews.py` も slug 重複を NG にする)
- 本番に頁が在ることを確認: `python scripts/_exists.py --title "<作品名>"` → slug を取る
- 知名度は高め・ジャンルは前節と散らす(バトル続き等にしない)

### 3. チャットに出すもの (= 例題パック)
1行目に「節N+1 / 公開日 / 課題図書(作者『作品』・slug・全X巻完結)」。続けて:
- **コピペ用プロンプト**をコードブロックで(下の共通プロンプト、〇〇『△△』を埋めるだけ。**プロンプト自体は変更しない**)
- **自分の書評本文**(Opus 5 として全力で書く。ネタバレなし・長め=1,500〜3,000字)

共通プロンプト(確定・全員一斉でなければ変えない):
> あなたはプロの編集者で、本の紹介をするプロです。ネタバレなしに、なるべく長く紹介文を書いてほしいです。ストーリーの説明ではなく、なるべく長い読み応えのある文で、読者に『読みたい』と思わせる文を書くのが仕事です。今回の題材は 〇〇『△△』です。

### 4. ユーザの paste を受ける (収集モード)
- paste 中は**受領1行だけ**返す(「受領: OpenAI ChatGPT」)。講評も要約もしない。
- モデル名はユーザのラベルそのまま(例 `DeepSeek (エキスパート)`)。vendor は会社名(Anthropic/OpenAI/Google/Alibaba/DeepSeek/xAI/Moonshot…)。
- 「終わり」等の完了合図が来たら step5 へ。

### 5. 格納
`data/seeds/ai-reviews.yml` の末尾に節を追記(既存節と同じ形):
```yaml
  - setsu: 14
    slug: golden-kamuy
    title: ゴールデンカムイ
    author: 野田サトル
    prompt: >-
      あなたはプロの編集者で、…今回の題材は 野田サトル『ゴールデンカムイ』です。
    reviews:
      - vendor: Anthropic
        model: Claude Opus 5 (1M)
        text: |-
          (本文。段落=改行1つ。インデントは10スペース)
```
★**本文は verbatim**(誤字・事実誤り・「以下に書きます」等の前置きも直さない = AIの実力表示が企画)。
★例外2つ: (a) 表示層は markdown 非対応なので **`#` 見出し / `---` / `**` / ゼロ幅文字だけ機械除去**
(b) **明確な事実誤り**(巻数違い等)は本文末尾に `※編集部注: …` を1行追記。

### 6. 番人 + 反映
```
python scripts/_check-ai-reviews.py       # NG 0 を確認(重複paste/markdown残骸/既出/連番)
git add data/seeds/ai-reviews.yml && git commit -m "AI書評家リーグ 節N: <作品>" && git push
```
seed のみ = 66k頁に無関係。**本番公開は次の「機能蒸留して」または「週次蒸留して」**に乗る
(自発的に本番デプロイしない)。preview で見たいだけなら push で足りる。
