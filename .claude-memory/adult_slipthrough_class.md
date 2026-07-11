---
name: adult-slipthrough-class
description: 成年すり抜け型=adult signalがimprint文字列内の社名一致のみで、ブランドimprint(バベルコミックス等)がscore0素通り。除外はforce_adult:true
metadata: 
  node_type: memory
  type: project
  originSessionId: 7b577e00-f57a-4227-841a-32fbd1f45c6c
---

2026-07-11確立(獣耳のリコリス=ユーザ発見が起点)。

- **穴の構造**: 種2 adult_score の publisher signal は「adult_publishers(21社) の社名が editions.imprint 文字列に含まれるか」だけ。成年専業社のブランドimprint(文苑堂=バベルコミックス等)は score=0 で素通りし全年齢として掲載される。
- **per-case封鎖**: `data/seeds/adult-overrides.yml` に **`force_adult: true`** entry(2026-07-11 promoteに実装済・従来はfalse=非adult方向のみだった)。頁除去は `_reflect-targeted.py --drop <stem>`。
- **裁定済4 drop**: 獣耳のリコリス(文苑堂)/ごまんえつ(文苑堂・genre誤分類gourmetだった)/未成熟(久保書店・ユーザ裁定)/あべもりおか(仮)Ex(ヒット出版社・ユーザ裁定)。**存置2**: 赫赫・身代わりなんてお断り(一般BL=茜新社opera/一水社は兼業)。
- **残triage**: `docs/production-diagnostics/adult-slipthrough-triage.tsv` = 成年21社publisherの本番頁871件を T1専業277/T2兼業+書影全滅115/T3弱472 に層別済。**一括drop禁止**(赤塚トリビュート/楽園系など全年齢混在)=全件目視 or レビューUI待ち。
- **ユーザのヒューリスティック**: 近年発行+ISBN有+楽天画像無し = ①ISBN誤り ②版元変更/入手不可(冬水社POD型) ③成年判定 のいずれか。店舗間で判定が割れる境界作あり(Amazon非成年でも楽天撤去)。Kobo含め不在確認してから裁定を仰ぐ。

[[feedback-one-bug-means-a-class]] [[adult-signal-dbsearch]]
