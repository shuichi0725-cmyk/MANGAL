---
name: edition_run_split_arms_wide_type
description: 【型・57頁適用済】ARMSワイド版型=1本の刊行runが複数の版タブに割れる。名前非依存の検出器で59頁→全数裁定→57統合。真因3層(表記ゆれ/種2クラスタ分裂/★種4のedition_type既定値)
metadata:
  node_type: memory
  type: project
---

2026-08-28。[[imprint_split_arms_type]](名前の近さで探す検出器)が **英字レーベル名↔和名**や**略称↔正式名**を
取り逃すことがユーザ指摘(ARMSワイド版)で判明し、名前を一切見ない構造的検出器を作って全数裁定した。

## 検出器 = `scripts/_audit-edition-run-split.py`
①出版社一致(orISBN出版者記号共通) ②巻番号が重複しない ③合わせて連番 ④巻順で発売日が単調増加。
新装版/復刻版は②か④で落ちる。tierA=imprint正規化で一致 / tierB=名前が違う。
初回65ペア/59頁 → **57頁を統合適用・残7**。

## ★真因は3層あった(表記ゆれだけではない)
1. **MADBのレーベル表記ゆれ** — 英字↔和名(Bamboo comics/バンブーコミックス)、略称↔正式名
   (KCスペシャル/講談社コミックススペシャル)、小書きカナ誤記(コミ**ツ**クス、スペシ**ア**ル)、中黒。
2. **種2のクラスタ分裂** — 一部の巻にだけ付く編集クレジット、**著者名の大小文字**(CLAMP vs Clamp)で別seriesに割れる。
3. ★**種4(`volumes-supplement*.yml`)の `edition_type` 既定値 standard** — 2026-07-28の続巻ハーベストが
   既定値で投入 → 種2にstandard版が無い頁では promote が「通常版 / imprint=出版社名 / publisher=None」という
   **実在しない幻の版**を新造する。the-band / hata-manjirou / hi-ni-nagarete / ennead / sekai-no-hate で実踏。
   ★**canonicalを起こすのではなく種4のedition_typeを直すのが根本**(連載中の巻固定も避けられる)。

## 裏取りの規律(この順で安い→高い)
1. 楽天キャッシュを**1パス**走査(`re.compile(r'"isbn":\s*"(\d{13})"')`+集合。ISBN毎に舐めると死ぬ)
2. MADB rawの**シリーズ容器ID `schema:isPartOf`**
   ★★**容器IDは「作品」容器であって「版」容器ではない**。243容器中**81本(33%)が複数brandを含み**、
   実在するレーベル変更(花衣夢衣 YOU COMICS DELUXE→YOU COMICS / FE聖戦 エニックス→スタジオDNA)も同居する。
   **単独では同一runの証明にならない** — ISBN連番・刊行ペース・楽天seriesName・外部刊行リストと合議させること。
3. 外部の刊行リスト(Wikipedia/版元公式/Amazonの実物書名)。

## ★反証役を別に立てること(効いた)
調査エージェントの merge 判定に対し反証専任を立てたら **1件が覆った**:
biba-usagi-kozou(ノーラコミックスdeluxe 1-4 → 無印 5)は真のレーベル変更の可能性が高く**統合しない**。
決着には NDL by-ISBN で 5巻(9784056011487)の奥付シリーズ表示を引く必要がある(未実施)。
逆に hanagoromo-yumegoromo は反証役が「集英社YOUコミックスlineが1995年10-11月に一斉にDX表記→標準表記へ切替
(無関係な5作品が同月に反転)」を突き止めて統合を**補強**した。

## 残7 と持ち越し
- **統合しない**: biba-usagi-kozou / manmaru-highschool(1巻=新書判・2-5巻=A5ワイド版が実在。ただし現在の
  境界1-4|5は誤りで正しくは1|2-5) / survival(別作品=宮川輝リメイクの混入) / blue-sakisaka-2006(同題異作3人の過統合)
- **保留**: toki-no-daichi 9-10巻(ガンガン→**Gファンタジー**はレーベル改称。畳むと実在レーベル名が消える=ユーザ裁定待ち)
- 別件で見つけた欠け: the-band に**1巻が無い**(Wikipedia 2025-04-16 / 978-4-06-538946-1)

関連: [[imprint_split_arms_type]] [[merge_needs_external_proof]] [[never_delete_because_broken]]
[[edition_canonical_key_is_src_slug]] [[feedback_one_bug_means_a_class]] [[seed4_auto_wipe_accident]]
