"""非漫画/関連書のdropパターン共有モジュール (= CLAUDE.md 掲載対象protocol + NDL discovery FP型)。
promote本体のパターンと同期させること。日次/後退蒸留の漫画性フィルタが使う。"""
import re

# CLAUDE.md DROP_TITLE_CONTAINS_PATTERNS 系 + NDL discovery特有FP(研究書/評論/図録/全史/インタビュー)
_CONTAINS = [
    "ガイドブック", "ファンブック", "設定資料", "公式図録", "公式読本", "公式ファン", "図録",
    "アンソロジー", "公式コミックガイド", "コミックガイド",
    "キャラクター名鑑", "人物名鑑", "キャラクターブック",
    "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本", "解析書", "解体新書",
    "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖", "大全史", "全史",
    "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法",
    "傑作選", "傑作集", "ベストセレクション", "特集号", "特別総集編", "名作集", "名作選", "自選", "総集編",
    "原画集", "画集", "ポケット画廊", "うちあけ話", "イラスト集", "画業",
    "設定集", "設定資料集",  # 2021後退蒸留すり抜け(クロスボーン設定集)。「紀行」「〜の世界」は誤爆リスクでworksheetゲート任せ
    "の描き方", "の描き方", "デッサン", "作画技法", "漫画の描き", "マンガの描き",
    "研究序説", "論考", "評論", "を読む", "で読む",
    "インタビュー", "対談集", "回顧録",
    "』論", "」論", "論 :", "の研究", "を語る", "読本",
    "公式コミックガイド", "展公式", "展図録",
]
_PREFIX = ["テレビアニメ版", "TVアニメ版", "アニメコミック", "劇場版", "映画 ", "OVA", "ノベライズ", "英訳"]

# ★コンビニ本/廉価再編レーベル(A2規約=題でなくimprint判定 2026-07-15。クッキングパパ・プラチナ型すり抜けから)
_LABEL_KONBINI = ["My first big", "SP pocket", "ポケットワイド", "プラチナコミックス",
                  "ジャンプリミックス", "ジャンプremix", "Gコミックス", "コンビニコミック"]

def is_droppable(title: str, series_label: str = "", creators_roled: str = "") -> bool:
    # 役割ベース: インタビュアー/聞き手 = 漫画でない
    cr = str(creators_roled or "")
    if "インタビュア" in cr or "聞き手" in cr or "絵と文" in cr:
        return True
    t = str(title or "")
    s = str(series_label or "")
    for p in _PREFIX:
        if t.startswith(p):
            return True
    for p in _CONTAINS:
        if p in t or p in s:
            return True
    sl = s.lower()
    for p in _LABEL_KONBINI:
        if p.lower() in sl:  # ★レーベルのみ照合(題は誤爆リスク)
            return True
    # 大全集/短編集/作品集 は keep (= CLAUDE.md: 描き下ろし多い)。ここでは除外しない。
    return False
