---
name: ndl_manga_filter_ndc726
description: NDLで漫画を権威判定=NDC726.1 または dcndl:genre=漫画。非漫画(小説913.6/画集/雑誌)除外に使う
metadata: 
  node_type: memory
  type: reference
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

NDL書誌で「これは漫画か」を**権威的に判定**する方法（ユーザ伝授2026-06-20）。2系統:

1. **NDC 726.1**（`dcterms:subject` の分類）= 漫画。726=漫画.劇画.戯画、.1=漫画。
2. **dcndl:genre = 漫画**（`http://id.ndl.go.jp/auth/ndlgft/001347325` ndlgft典拠）= 形式用語「漫画」。
   ★古い1990年代レコードはNDC未付与でも genre で判定できる（例: ARIEL COMIC は genre=漫画 だがNDC無）。

dcndl SRU からの抽出: `<dcterms:subject>`内のNDC値 or `<dcndl:genre><rdf:Description>...<rdf:value>漫画`。

**★最重要・非対称ルール**(ユーザ強調2026-06-20): **NDCの有無は非対称に扱う**。
- 726.1 or genre=漫画 **あり** → 漫画**確定**(陽性)
- 913.6等 別分類 **あり** → 非漫画**確定**(小説等)
- **番号もgenreも無い → 不明=漫画の可能性あり**。★**「NDC無い=非漫画」で除外するのは禁止**。古い/整理不完全レコードはNDC欠落が普通(ARIEL COMIC自体がNDC無・genreのみで漫画だった)。陽性シグナル不在は**判定保留**であって除外根拠でない。非漫画判定は「別分類が明示」された時のみ。

**除外できる非漫画**:
- 小説/ラノベ = **NDC 913.6**（日本文学）。例: 笹本祐一エリアル全20巻=ソノラマ文庫=913.6。
- 画集 = 726.5系/別genre。例: 鈴木雅久エリアル画集 → [[art_book_inclusion]] の画集streamへ。
- 雑誌 = 継続誌（ISBN無・著者=出版社名）。例: エリアルコミック10-14。

**用途**: [[ndl_nonmanga_sweep]] / re-point前の作品実在確認 / アンソロ分割。
**★アンソロジーは現状「出さない方針」**(ユーザ裁定2026-06-20)=多著者アンソロジーコミックは今は掲載しない。ARIELの分割作業(エリアルコミック/シーズン/こんちこれまたえりある)は試したが**巻き戻し済**(まだ出す必要なし)。将来出す場合の原則だけメモ: シリーズ(出版社レーベル)単位で分ける(作画者ごとでない)。絶版巻はマンガ図書館Z等で補完。
**アメコミ(Marvel/DC)は対象外**(ユーザ裁定): manhwa/manhua日本語版は対象だがアメコミは除外(和製X-MENアンソロ含む)。american-comics-drop.tsv。
