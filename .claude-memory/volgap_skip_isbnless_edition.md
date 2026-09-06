---
name: volgap_skip_isbnless_edition
description: 【裁定・恒久】巻抜け(vol_gap)は「ISBNを1本も持たない版の穴」を数えない。ISBN以前の版は確認も充填も原理的に不可
metadata:
  type: feedback
---

2026-09-07 ユーザ裁定「巻抜け対象がISBNがない物を除外して。例えば白いパイロット」。

**Why:** 『白いパイロット』の版「手塚治虫漫画選集版(鈴木出版)」は **1962-63年 = ISBN以前**。
v1 と v3 しか無く v2 が欠番に見えるが、ISBNが存在しない時代の本なので
**実在確認も充填も原理的にできない**。 直せないものを worklist に残すと、
毎回同じ頁を調べ直して空振りする(= [[feedback_raw_count_is_not_worklist]] と同根)。

**How to apply:**
- 規則 = **版(edition)にISBNが1冊も無ければ、その版の穴は vol_gap に数えない**。
  先頭欠け(no_vol1)も同じ = 頁の最小巻を持つ版にISBNが無ければ数えない。
- ★**版に1冊でもISBNが在れば従来どおり数える**(がきデカ型=一部ISBN欠けは
  [[partial_isbn_gap_mechanism]] で埋まるので対象に残す)。
- 実装は **索引と監査の両方**に同じものを置く(定義がズレると worklist が食い違う):
  - `scripts/_build-list-index.py` の `_ed_has_isbn`(vol_gap / no_vol1 の判定)
  - `scripts/_volgap-virtual.py` の `_ed_isbn_keys`
- 形式は不変(fl のビット配置は同じ)なので**索引ファイル名のバンプは不要**
  ([[index_format_change_versioned_filename]] の「中身の更新だけは同名でよい」)。

**実測(2026-09-07):** vol_gapが立つ頁 446 → **394** / 残gap 430 → **379**(除外51頁)。
除外はほぼ1950-70年代(沙漠の魔王1952 / 赤胴鈴之助1957 / 伊賀の影丸1963 / 巨人の星 / 白いパイロット)。
ホーム画面の「巻抜け」フィルターチップ(`app/HomeClient.tsx`)の件数もこの定義で出る。

[[volgap_fill_pipeline_2026_09]] [[volgap_virtual_edition_unit]] [[volgap_virtual_tool_trigger]]
