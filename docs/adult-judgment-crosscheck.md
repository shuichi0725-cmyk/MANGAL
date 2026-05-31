# 種3↔種a アダルト判定 クロスチェック(調査 2026-05-31)

> ユーザ依頼: v14マッチを使い、 種3 のアダルト判定漏れ + 種aが非adultなのに種3がadult
> の物を慎重に調査。 ★仕様差で「間違いと言い切れない」点は理解の上、 判別材料を提示。
> ★調査専用 = adult_score / 種2 / 種3 は一切変更しない。

ツール: `scripts/_audit-adult-crosscheck.py`。
- 種3(MANGAL)adult判定 = 種2 `series.adult_score >= 3`(promote が `<3` のみ本番採用)。
- 種a(AniList)adult判定 = dump の `isAdult`。
- 対象 = v14 S-tier マッチ **39,493件**。

## 4象限(一致率 95%)
| | 種a adult | 種a 非adult |
|---|---|---|
| **種3 adult**(score≥3) | 796(一致) | **(B) 55** |
| **種3 非adult** | **(A) 1,913** | 36,729(一致) |

---

## (A) 種3 アダルト漏れ = 1,913件(種a=adult なのに 種3 score<3)

### 内訳
- **score=0(adult signal が皆無): 1,819件** ← MANGAL の signal(imprint/mangaka/keyword)が
  **全く発火していない**
- score=1-2(signal 有るが閾値3未満): 94件 ← 惜しい(閾値 or weight 調整で拾える帯)

### 種a genre/tag による分類(1,846件)
| 分類 | 件数 | 評価 |
|---|---|---|
| **TL/成人ヘテロ等** | **1,680(91%)** | ★**真の漏れ候補** |
| BL(Yaoi/Boys Love) | 100(5%) | 仕様差候補(MANGAL が BL を adult 扱いしない方針なら正当) |
| 百合(Yuri) | 66 | 仕様差候補 |

### 漏れの根本原因(推定)
1. **base題は無難・subtitle が露骨**: 種3 は base題のみ保持(例「25歳の女子高生」)、
   露骨さは subtitle(「～子供には教えられないことシてやるよ」)にあり、 imprint/keyword
   signal が base題だけでは発火しない。
2. **TL/デジタル発の新興 imprint** が adult_imprints リスト未収録。
3. 例: /Blush-DC秘蜜 / 1日1回果てるまで飢えた絶倫オジサマ / 26歳処女チャラ男上司に抱かれました
   / 18禁のつくりかた / 3P始めました 等 = 明確に成人 TL。

→ **種a isAdult を新signal として加える**(BL/百合は方針次第で除外)+ **subtitle keyword 検出**
が有効と推定。 リスト: `.cache/adult-A-leak.tsv`。

---

## (B) 種3のみ adult = 55件(種3 score≥3 なのに 種a=非adult)

### signal 別内訳
| signal | 件数 | 評価 |
|---|---|---|
| **wikipedia_adult_mangaka_list のみ** | **36** | ★**誤発火疑い**(作者が adult も描く→全作品に adult 付与) |
| imprint/content_rating 有 + score≥5 | 9 | 真adult 疑い(種a が isAdult flag 漏れ) |
| imprint/content_rating 有 + score<5 | 10 | 中間 |

### 誤発火パターン(36件)
**「作者が adult も描く」だけで全年齢作品まで adult 判定**される:
- 祝福のカンパネラ / アマガミ Love goes on! / 魔王令嬢から始める三国志 / Fate/stay night
  コミックアンソロジー 等 = 全年齢なのに `wikipedia_adult_mangaka_list` で score=3-4。
- = 作者単位 signal が title 単位の裏取りなしで閾値到達 → 偽陽性。

### 真adult 疑い(9件、 種a の flag 漏れ)
- 禁断 / 肉体関係(score10、 imprint+作者+content)/ いけない！ルナ先生(ecchi古典)/
  コヨーテ / LOVE DELUXE 等 = MANGAL が正しく adult、 **種a 側が isAdult 未設定**。

→ **作者単位 signal は title 単位の裏取り(imprint/keyword/content_rating)と併用すべき**
(単独で閾値到達させない)。 リスト: `.cache/adult-B-over.tsv`。

---

## まとめ(調査結論、 ※適用は要GO)
- **一致 95%**。 食い違いは (A)1,913 / (B)55。
- **(A) 真の漏れ ~1,680**(TL/成人)= MANGAL adult filter の最大の盲点。 種a isAdult +
  subtitle keyword で大幅改善可。 BL/百合166は方針判断。
- **(B) 誤発火 ~36** = 作者単位 signal の単独発火。 title 裏取り併用で是正可。
- いずれも **仕様の議論**(BL/百合を adult とするか、 作者signal の扱い)を経て適用判断。

---

# 続報: 本単位(ISBN)成年判定 = 本道調査(2026-05-31)

★ユーザ指摘「成年判定は本(巻)単位、 種1/種2 が本道」を受け、 MADB raw の
本単位 `schema:contentRating="成年コミック"` を直接調査。 ツール `_audit-adult-perbook.py`。

## MADB 本単位 成年(日本の権威18禁)
- metadata101 raw: **8,179冊 = 成年コミック**(per-ISBN)。 schema:isbn で本単位。
- これが日本の権威フラグ。 取込時に series へ集約され `madb_content_rating` signal(weight5)に。

## ★現 adult_score の精度(6,739除外の内訳)
| 区分 | 件数 | 評価 |
|---|---|---|
| **madb_content_rating 有(権威)** | **4,935(73%)** | 正しい18禁 |
| imprint のみ(権威無) | 1,300(19%) | 大半正当・KADOKAWA型誤爆が潜む |
| **作者リストのみ** | **504(7%)** | ★誤爆濃厚(全年齢×adult作者) |

- madb_content_rating signal = 4,935、 **score<3の漏れ 0**(本単位成年は確実に除外済)。
- ※注意: 種2 volumes 経由の ISBN-join は adult巻が種2から除外され**過小カウント**(誤って3,745と出た)→
  権威は **madb_content_rating signal**(取込時 raw 由来)で測るのが正。

## ★日本基準 vs 米基準(点1の答え)= v14マッチ
| | 米◯ | 米✗ |
|---|---|---|
| 日◯(MADB成年) | 551 | **3** |
| 日✗ | **2,158** | 36,781 |
- **日✗米◯ = 2,158**(BL/TL/ecchi、 米のみadult)= 日本で成年マーク無 = **18禁基準なら載せる**。
- **日◯米✗ = 3のみ** = MADB成年を AniList はほぼ取りこぼさない(米⊃日)。
- → **基準は日本(MADB成年)を採用すべき**。 種a isAdult を使うと BL/TL 2,158件を誤って弾く。

## 粒度: 混在シリーズ 23件(一部巻のみ成年)
例: 精霊特捜フェアリィセイバーW 14/20成年 / コスは淫らな仮面(商業版) 1/3。
→ 成年判定は**本単位で保持**すべき(volumes に per-book adult列)。

## 改善アーキテクチャ(提案・要GO)
1. **権威 = MADB成年(本単位)を第1軸**。 4,935 series は確実。 volumes に per-book adult 列を持たせ粒度保持。
2. **作者リスト signal を裏取り必須に降格**(504件の誤爆解消)。
3. **imprint 1,300 を純adult専門 vs 一般出版社混在(KADOKAWA型)に分離**精査。
4. **Amazon 成年コミック browse node を fetch**(本単位ISBN、 第2権威)→ MADB漏れ catch + 3者突合。
5. 種a isAdult は**米基準=参考のみ**(BL/TL 2,158は日本基準で除外しない)。

---

# ★重要訂正: レーベル signal は「正しく」adult を捕捉していた(2026-05-31)

「MADB成年のみに絞る(option A)」を検討したが、 **復活候補1,804を精査して訂正**:
- v14マッチ162件中 **145(90%)が種a adult系タグ**(Hentai/Ecchi/BL/Smut)
- **1,642件は種aマッチ無し** = AniList が追わないニッチ官能/TL = ほぼ成人向け
- 全年齢FP濃厚は **17件のみ**

→ ★**「MADB成年マーク無し ≠ 全年齢」**。 imprint signal は **adult出版社の TL/官能(成年マーク
外だが成人向け)を正しく捕捉**。 MADB単独に絞ると ~1,800 の成人作品が本番流出 = 危険。
**ユーザの「レーベル判断がかなり有効」は正解**。 レーベル品質分析の「成年本無率高」も、
フランス書院コミック文庫/GOT 等 = adult出版社の TL/官能ライン(成年マーク外の成人向け)で
あり、 誤爆でなく正当な捕捉だった。

## 修正後の redesign 方向(surgical = 大改造でない)
- **MADB成年(4,935)+ adult出版社imprint(1,300、 大半正当)は維持** = adult判定の主軸。
- **真のFPは小さい**:
  - 作者のみ signal で **種a が全年齢と確認**できる物(祝福のカンパネラ/アマガミ型、 B-checkの~36)
    → 種a 裏取りで un-flag。 ※作者のみでも adult(人妻戦士ケイコさん)は維持。
  - 一般出版社(KADOKAWA等)の imprint が誤って adult_imprints に入っている物 → 個別除去。
- **本単位粒度の保持**(混在23 + per-volume adult列)= 別途の構造改善。
- TL/官能の最終扱い(成年マーク外を adult とするか)= 種a タグ上 90%成人向けなので
  **現状の「除外」が妥当**(= point1 の暫定結論: 日本でも adult出版社content は除外側)。

## 結論
adult判定は **思ったより健全**(95%一致 + レーベル捕捉が正当)。 改善は **surgical**
(作者FP ~数十件の un-flag + 一般imprint 個別除去 + 本単位粒度)。 大改造は不要・危険。
