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
- ★**残11頁も2026-09-06 に全是正 → 頁内ISBN重複は 0頁**。原因は更に2系統あった:
  ②**canonical seedの作り物/誤記ISBN**(4頁): 銀牙伝説Weedに **9789784537100(978が二重の埋め草)が17巻分**
    (Wiki蒸留で日付は取れたがISBNが無く埋めた) / ゴルゴ13 129巻に127巻のISBN / 将太の寿司18巻に17巻のISBN /
    ちばあきお短編集3巻がチェックディジット不正の転記ミス。★44巻のように裏が取れない巻は **null**(作り物を置かない)。
  ③**種4/offsetシードの誤補完**(7頁): 隣巻のISBNを別番号に貼っていた(KYO36・ロマサガ2の1巻・前略の1巻・
    Kissで合格/ヤダモン/くさっても猫の幽霊3巻目・新々上ってナンボの1巻・島耕作全集の課長編ISBN増殖)。
- ★**入口の番人**: `_check-edition-canonical.py` に **検査8=ISBN妥当性(978/979+チェックディジット+978二重)**
  と **検査9=同一ISBNが複数巻に付いていないか** を追加(2026-09-06)。これが無かったので作り物ISBNが素通りしていた。
- ★**per-case道具**: `isbn-fill.json` に `replaces`(現在値を名指しした時だけ上書き)/`drop_if_isbn`
  (名指しした時だけ行削除)を追加。空欄補充しかできなかったので誤ISBNを直せなかった。
- ★**常設検出器**: `scripts/_audit-isbn-dup-in-page.py`(出力 docs/production-diagnostics/isbn-dup-in-page.tsv)。

**Why:** 版の置換系passは「置換先が既に居るか」を必ず見ないと二重化する。
**How to apply:** ISBN置換を伴うpassを足す時は、同じ版の中のISBN衝突チェックを同時に書く。
月次サニティで本検出器の新規増加を見る。[[special_edition_fix_state]] [[isbn_dup_cleanup_state]]
[[feedback_one_bug_means_a_class]]
