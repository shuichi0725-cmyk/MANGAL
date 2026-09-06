---
name: isbn-dup-special-edition-pass
description: 【型・是正済】保健室の僕ら型=特装版パスの置換で同ISBNの巻が二重化(1巻と2巻が同じ本)。promoteに衝突つぶしを結線・12頁是正。残11頁は別要因
metadata: 
  node_type: memory
  type: project
  originSessionId: fa3eed2c-bf86-4ffe-b701-6b416a249bdb
  modified: 2026-09-06T02:53:58.761Z
---

★2026-09-06 ユーザ発見「1と2のisbnが一緒」(bokura-no-koi-to-seishun-no-subete-hokenshitsu-no-bokura)。

- **根因**: 種2が通常版と特装版を**別々の無番号巻(number=0 / is_extra=1)**として持つ作品がある。
  promote は無番号巻を連番に振り、その**後**の最終passで special_isbn→normal_isbn に置換するため、
  **同じ本が「1巻」「2巻」に化ける**。置換側は variants も持つので見た目は完全な双子。
- **是正**(`_promote-bulk-v2.py` 特装版パス直後): 置換した巻を記録し、新ISBNが同じ版の他の巻と
  衝突したら **置換した行だけ**を落として本物へ variants/cover を寄せる。番号が 1..N で完全だった版のみ
  詰め直す(歯抜けの版は実在の巻番号かもしれないので触らない)。
- **検出器**: 頁内で同ISBNが複数の巻に付くものを掃引 → `docs/production-diagnostics/isbn-dup-in-page.tsv`。
  実測 **23頁**。うち本型(variantあり)**12頁を是正**(保健室2→1 / ショコラの魔法15→14 / ぼくは地球と歌う9→8 …)。
- ★**検算の型**: `_reflect-targeted.py` の減少ゲートは**ISBN集合**で見るので、重複行だけを畳んだ時は
  「減少なし」が正しく出る(巻数は減るがISBNは1つも消えない)。これが「本を消していない」証明になる。
- **残11頁は別要因**(自動では触らない): ゴルゴ13 127/129・銀牙伝説Weed(**978が二重の壊れISBN
  9789784537100 が17巻に付く**)・将太の寿司17/18・島耕作全集・SAMURAI DEEPER KYO 35/36・
  ヤダモン・ロマンシング サ・ガ2・前略お兄ちゃん・新々上ってナンボ・Kissで合格・くさっても猫なので。

**Why:** 版の置換系passは「置換先が既に居るか」を必ず見ないと二重化する。
**How to apply:** ISBN置換を伴うpassを足す時は、同じ版の中のISBN衝突チェックを同時に書く。
月次サニティで本検出器の新規増加を見る。[[special_edition_fix_state]] [[isbn_dup_cleanup_state]]
[[feedback_one_bug_means_a_class]]
