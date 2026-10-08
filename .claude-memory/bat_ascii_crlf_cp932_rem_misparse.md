---
name: bat-ascii-crlf-cp932-rem-misparse
description: 起動bat(.bat)は英数字のみ+CRLFで書く。cmd.exe(コードページ932)がUTF-8の日本語rem行を読み違え、コメントの断片を命令として実行する(2026-10-08 実測)。sonnet/opus/fable/log.bat は日本語コメント+LFのみのまま=未修正
metadata:
  node_type: memory
  type: reference
  originSessionId: 60837ea9-16b4-4ef2-9200-391e3397c8aa
  modified: 2026-10-08T14:12:03.760Z
---

2026-10-08、ユーザ依頼「haiku5.5のバッチ作り直して」で `haiku.bat` を作り直した時に実測した。

## 事実
- cmd.exe はこのPCで**コードページ932**。bat の中身が UTF-8 の日本語だと、`rem` 行でも読み違えて**コメントの断片を命令として実行**する。
  - 稼働中の `sonnet.bat`(LFのみ・日本語コメント)の空運転: `'5-5)' は…認識されていません` ほか2件のエラーが出てから claude の行に届く。
  - 同じ中身を CRLF にしても別の断片(`'bat'` `'…resume'`)が実行される = 改行だけ直しても消えない。
  - **日本語コメントを落とした版(英数字のみ・CRLF)はエラー0**。
- いままで実害が無かったのは、断片がたまたま実在の命令に当たらなかっただけ(窓の先頭にエラーが2〜3行流れていたはず)。
- 追跡済みの `sonnet.bat` `opus.bat` `fable.bat` `log.bat` は作業ツリー上 **LFのみ**(git の autocrlf はまだ当たっていない)。LFのみの bat は cmd がラベルを見失うことがある。
- `claude-haiku-5-5-20251001` というモデル名は存在しない(起動に失敗。20251001 は Haiku 4.5 の日付)。正しくは `claude-haiku-5-5`。

## いまの状態
- `haiku.bat` = 英数字のみ・CRLF・実行行は sonnet.bat と名前とモデル以外同一(機械で突合)。実起動して Remote Control「haiku」が idle で出るところまで確認し、git 追跡に入れた。
- 他の4本は**未修正**(毎日使っている起動口なので、直すかはユーザ裁定。2026-10-08 に報告済み)。

## How to apply
- bat を書く・直す時は **英数字のみ+CRLF**。日本語の説明は bat の外(記憶や docs)に置く。`%` `&` `|` `<` `>` `^` もコメントに入れない。
- 直した後は「claude の行を echo に変えた写し」を `cmd /c ".\写し.bat __inner"` で空運転し、エラー0で命令行に届くことを見る。
- ★Bash/heredoc 経由だと `\\` が1個に潰れる層がある(`".\\$f.bat"` が `.$f.bat` になった)。bat の空運転は PowerShell から呼ぶ方が確実。
- ★Write ツールは LF で書く。bat は Python で `'\r\n'.join(...)` をバイトで書いて CRLF を数える。

関連: [[element-harvest-pillar-state]]
