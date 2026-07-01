---
name: madb-data-acquisition
description: MADBデータ入手の2経路=GitHub全件baseline + MADBサイトの月次項目別差分(登録日基準)
metadata:
  type: reference
---

★**MADBデータの入手モデル(2026-06-01 ユーザが解説)**:

1. **GitHubリリース(github.com/mediaarts-db/dataset)** = その日までの**全件snapshot**。 ★MADBの認知促進 + 全件を毎回MADBサーバから引くのは重い、 という理由で存在。 月次タグ(1.2.16=2026-05-22等)。 ★baseline用。 ただしcm104/105等のmasterは内部的に凍結([[madb_cm104_frozen]])、 かつリリース断面が実際の発売に若干遅れる(1.2.16=5/22が5/18発売の一部を取りこぼし=19件)。

2. ★**MADBサイト(s-db.artmuseums.go.jp)の詳細検索** = **項目(cm101/cm104等)× 月単位**でCSV DL可能。 ★**登録日基準の増分(差分)**。 軽い・GitHubより新鮮。 例: 「6月」DLは登録日が6月のもの=「5月発売だが6月登録」+「6/18の発売前予約」も含む(=未来の最新刊が載る)。 列は52列固定(MADB ID/ISBN/タイトル/巻/作者名/原作者名/スタッフ名/公開年月日/マンガ単行本シリーズ等)。 複数著者は `＼＼`(全角バックスラッシュ2つ)区切り。

**蒸留設計への帰結**:
- baseline = GitHub全件(数ヶ月に一度re-sync)/ ★増分 = MADBサイトの月次・項目別DL(毎月取込=軽く新鮮)。
- 重複前提で取込(MADB-ID/ISBN/巻番号でdedup=実装済・冪等)。 月次DLはGitHubと重なる(5月は種2と95%重複)が安全。
- ★MADBサイトDLは**未来の発売前予約も載る** → STEP4(末尾/最新刊検出)に直接使える。
- ★新刊は「マンガ単行本シリーズ」链が0%(cm104凍結)= シリーズ層は空 → 著者役割はAniList補完が恒久策。
関連 [[project_architecture_seeds]] [[madb_cm104_frozen]]。
