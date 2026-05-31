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
