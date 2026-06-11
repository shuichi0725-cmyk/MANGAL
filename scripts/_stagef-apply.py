"""Stage F 適用: 版クラスタ統合 24群を series-merge-auto へ純粋追加 + survivor slug fix行。
全て確証付き(ISBN出版社帯/巻相補/公知/Web)。 evidence は note に焼く。 ★冪等。
"""
import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent

# (main_rep, ed_rep, evidence)
MERGES = [
    ("qid:Q11561006|name:鉄のラインバレル", "qid:Q11561006|name:鉄のラインバレル完全版", "完全版=同作同qid・マーカー題"),
    ("qid:Q551551|name:ああっ女神さまっ", "qid:Q551551|name:新装版ああっ女神さまっ", "新装版=同作同qid"),
    ("qid:Q11627987|name:世界の終わりの魔法使い", "qid:Q11627987|name:世界の終わりの魔法使い完全版", "完全版=同作同qid"),
    ("qid:Q11648718|name:ブリザードアクセル", "qid:Q11648718|name:新装版ブリザードアクセル", "新装版=同作同qid"),
    ("qid:Q11648718|name:金剛番長", "qid:Q11648718|name:新装版金剛番長", "新装版=同作同qid"),
    ("qid:Q7497596|name:野球狂の詩", "qid:Q7497596|name:野球狂の詩 愛蔵版", "愛蔵版=同作同qid"),
    ("qid:Q11586417|name:純潔のマリア", "qid:Q11586417|name:新装版純潔のマリア", "新装版=同作同qid"),
    ("qid:Q2005281|name:五年生", "qid:Q2005281|name:新装版五年生", "新装版=同作同qid"),
    ("qid:Q403201|name:ユンカース・カム・ヒア", "qid:Q403201|name:完全版 ユンカース・カム・ヒア", "完全版=同作同qid"),
    ("qid:Q3516091|name:がきデカ", "qid:Q3516091|name:豪華版 がきデカ", "豪華版=同作同qid"),
    ("qid:Q193300|name:鉄腕アトム", "qid:Q193300|name:鉄腕アトム カラー版", "カラー版v0 stub吸収=同作同qid"),
    ("qid:Q3776937|name:Barレモン・ハート", "qid:Q3776937|name:BARレモン・ハート", "双葉社575x帯3本共有・同題同qid・年代交差=同作の別装丁クラスタ"),
    ("qid:Q471103|name:マンガ 日本の歴史", "qid:Q471103|name:マンガ日本の歴史", "石ノ森: 単行本48巻(1240帯)+中公文庫55巻(1220帯)=公知の版違い"),
    ("qid:Q11260369|name:ファイアーエムブレム 聖戦の系譜", "qid:Q11260369|name:ファイアーエムブレム聖戦の系譜", "NTT出版8401帯共有・2004新装=公知"),
    ("qid:Q967455|name:新上ってなンボ!!太一よ泣くな", "qid:Q11412214|name:(新)上ってなンボ!!太一よ泣くな", "v0 ISBN無stub吸収・同題"),
    ("qid:Q17159240|name:少女菜美", "qid:Q17159240|name:少女「菜美」", "同qid同題・1987原版(ISBN無)+2009復刻(7659帯)"),
    ("qid:Q17572|name:藤子・F・不二雄 異色短編集", "qid:Q17572|name:藤子・F・不二雄異色短編集", "小学館0919帯共有・B=vol2のみのdup record"),
    ("qid:Q2661273|name:さいとう・たかを池波正太郎時代劇画ワイドセレクション", "qid:Q2661273|name:さいとう・たかを/池波正太郎時代劇画ワイドセレクション", "リイド8458帯共有・巻1-13/14-19連続=同一series分割"),
    ("qid:Q469923|name:3 THREE", "qid:Q469923|name:3THREE", "講談社0630帯共有=文庫版・同qid"),
    ("qid:Q5398742|name:生徒諸君!教師編", "qid:Q5398742|name:生徒諸君! 教師編", "講談社0638帯共有・同題同qid=版クラスタ"),
    ("qid:Q6883357|name:The・かぼちゃワイン", "qid:Q6883357|name:Theかぼちゃワイン", "講談社0617帯共有・同qid=復刻/重複クラスタ"),
    ("qid:Q7385253|name:太陽が見ている（かもしれないから）", "qid:Q7385253|name:太陽が見ている かもしれないから", "集英社0884帯共有・巻1..8相補=同一series分割"),
    ("qid:Q459911|name:SLAM DUNK|sub:新装再編版", "name:ホーム社|name:SLAM DUNK", "集英社文庫0887帯=mainに既含・B=文庫dup(版元名義汚染=文庫型)"),
    ("qid:Q1015799|name:Dear boys", "qid:Q1015799|name:DEAR BOYS", "DEAR BOYS新装版=月マガ50周年KCDX全12巻(kodansha.co.jp/0000411476)"),
]

# survivor slug 確定(fix行)。 両rep keyに張る(非repはmissで無害)
FIXES = [
    ("qid:Q11561006|name:鉄のラインバレル", "tetsu-no-linebarrels", "Stage F: 完全版吸収後のmain slug"),
    ("qid:Q11561006|name:鉄のラインバレル完全版", "tetsu-no-linebarrels", "Stage F: 同上(merge副キー)"),
    ("qid:Q11627987|name:世界の終わりの魔法使い", "sekai-no-owari-no-mahoutsukai", "Stage F: main slug"),
    ("qid:Q11627987|name:世界の終わりの魔法使い完全版", "sekai-no-owari-no-mahoutsukai", "Stage F: 同上(merge副キー)"),
    ("qid:Q459911|name:SLAM DUNK|sub:新装再編版", "slam-dunk", "Stage F: 全版統合後のmain slug(ユーザ版タブ方針)"),
    ("name:ホーム社|name:SLAM DUNK", "slam-dunk", "Stage F: 同上(merge副キー)"),
    ("qid:Q11586892|name:東京喰種", "tokyo-ghoul", "Stage F: 無印が本編=bare slug(:reの占有を解消)"),
    ("qid:Q11586892|name:東京喰種:re", "tokyo-ghoul-re", "Stage F: 続編:reは別ページ+:re明示slug"),
    ("qid:Q2661273|name:さいとう・たかを池波正太郎時代劇画ワイドセレクション", "saitou-takao-ikenami-shoutarou-jidai-gekiga-waido-selection", "Stage F: たかを=Takao定着綴り"),
    ("qid:Q2661273|name:さいとう・たかを/池波正太郎時代劇画ワイドセレクション", "saitou-takao-ikenami-shoutarou-jidai-gekiga-waido-selection", "Stage F: 同上(merge副キー)"),
]

# 抜粋本protocol違反の生存ページ → drop(非漫画dropと同経路の専用list)
DROPS = [
    ("qid:Q2010|name:ONE PIECE 総集編", "総集編=既刊再録(THE LOG)=CLAUDE.md抜粋本drop"),
    ("qid:Q2010|name:ONE PIECE総集編", "同上"),
]


def main():
    p = ROOT / "data/seeds/series-merge-auto.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    added = 0
    for main_rep, ed_rep, ev in MERGES:
        pair = [main_rep, ed_rep]
        if any(set(pair) <= set(g["merge_keys"]) for g in d["merges"]):
            continue
        union = []
        for g in d["merges"]:
            if any(k in g["merge_keys"] for k in pair):
                for k in g["merge_keys"]:
                    if k not in union:
                        union.append(k)
        for k in pair:
            if k not in union:
                union.append(k)
        d["merges"].append({"merge_keys": union, "note": f"Stage F 版クラスタ統合: {ev}(2026-06-11)"})
        added += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"series-merge-auto: +{added} (計{len(d['merges'])})")

    fp = ROOT / "data/seeds/slug-fix-candidates.tsv"
    t = fp.read_text(encoding="utf-8")
    have = {l.split("\t")[0] for l in t.split("\n") if l}
    n = 0
    with fp.open("a", encoding="utf-8", newline="") as f:
        for key, slug, note in FIXES:
            if key in have:
                continue
            f.write(f"{key}\tSTAGE_F\t\t\t{slug}\t{note}\n")
            n += 1
    print(f"fix行: +{n}")

    # drop = c3 と同経路(malformed TSV へ追記は不適=別意味) → 専用: non-manga-drop.yml? 形式調査の上、
    # ここでは integrate が読む fix 層で (DROP) を使う(既存 ndl_junk_drop と同経路=安全)
    n = 0
    t = fp.read_text(encoding="utf-8")
    have = {l.split("\t")[0] for l in t.split("\n") if l}
    with fp.open("a", encoding="utf-8", newline="") as f:
        for key, note in DROPS:
            if key in have:
                continue
            f.write(f"{key}\tSTAGE_F_DROP\t\t\t(DROP)\t{note}\n")
            n += 1
    print(f"drop行: +{n}")


if __name__ == "__main__":
    main()
