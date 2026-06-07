"""publishers.yml 拡張 + publisher-aliases.yml 生成。
方針: 新キーは display名=生社名(promoteがnorm照合で自動マッチ)。aliasは別名同一実体のmergeのみ(ISBN帯確認済)。
"""
import json, sys, re, unicodedata, yaml
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\(\[（【].{0,6}?(発売|発行|製作|配給).{0,2}?[\)\]）】]", "", s)
    s = re.sub(r"(株式会社|有限会社|合同会社|\(株\)|\(有\)|㈱|㈲)", "", s)
    s = re.sub(r"[\s・･,，\.\-—–]", "", s).strip()
    return s

# 新キー: (key, 表示名). display名=生社名 → promoteがnorm照合で自動マッチ(alias不要)
NEW = [
 ("ozora-shuppan","宙出版"),("asahi-sonorama","朝日ソノラマ"),("seiunsha","星雲社"),
 ("kill-time-communication","キルタイムコミュニケーション"),("daitosha","大都社"),("akebono-shuppan","曙出版"),
 ("wani-magazine","ワニマガジン社"),("libre","リブレ"),("tousuisha","冬水社"),("ohkura-shuppan","オークラ出版"),
 ("got","ジーオーティー"),("harlequin","ハーレクイン"),("taiyoh-tosho","大洋図書"),("seisensha","青泉社"),
 ("wakagi-shobo","若木書房"),("fusion-product","ふゅーじょんぷろだくと"),("shogakukan-creative","小学館クリエイティブ"),
 ("scola","スコラ"),("hibari-shobo","ひばり書房"),("biblos","ビブロス"),("koike-shoin","小池書院"),
 ("france-shoin","フランス書院"),("east-press","イースト・プレス"),("wani-books","ワニブックス"),
 ("ushio-shuppan","潮出版社"),("oaks","オークス"),("sankosha","三交社"),("frontier-works","フロンティアワークス"),
 ("to-books","TOブックス"),("coamix","コアミックス"),("fukkan-com","復刊ドットコム"),("bright-shuppan","ブライト出版"),
 ("taiheiyo-bunko","太平洋文庫"),("jive","ジャイブ"),("tokyo-mangasha","東京漫画社"),("tokyo-manga-shuppan","東京漫画出版社"),
 ("starts-shuppan","スターツ出版"),("bungei-shunju","文藝春秋"),("kasakura-shuppan","笠倉出版社"),
 ("shopro","小学館集英社プロダクション"),("rippu-shobo","立風書房"),("pan-rolling","パンローリング"),
 ("micro-magazine","マイクロマガジン社"),("tokyo-sanseisha","東京三世社"),("takarajimasha","宝島社"),
 ("earth-star","アース・スターエンターテイメント"),("shobunkan","松文館"),("holp-shuppan","ほるぷ出版"),
 ("studio-ship","スタジオ・シップ"),("j-publishing","Jパブリッシング"),("seirindo","青林堂"),
 ("sony-magazines","ソニー・マガジンズ"),("fusosha","扶桑社"),("rapport","ラポート"),("flex-comix","フレックスコミックス"),
 ("ohta-shuppan","太田出版"),("hifumi-shobo","一二三書房"),("oto-shobo","桜桃書房"),("futami-shobo","二見書房"),
 ("akaneshinsha","茜新社"),("kawade-shobo","河出書房新社"),("softbank-creative","ソフトバンククリエイティブ"),
 ("taibundo","泰文堂"),("nihon-bungasha","日本文華社"),("bun-endo","文苑堂"),("mushi-pro","虫プロ商事"),
 ("nihon-shuppansha","日本出版社"),("goma-books","ゴマブックス"),("tokyo-top","東京トップ社"),
 ("nakamura-shoten","中村書店"),("kinransha","きんらん社"),("village-books","ヴィレッジブックス"),
 ("shinkosha-bl","心交社"),("schubert-shuppan","シュベール出版"),("tairiku-shobo","大陸書房"),("movic","ムービック"),
 ("tsuru-shobo","鶴書房"),("taiseisha","大誠社"),("aspect","アスペクト"),("koei","光栄"),("studio-dna","スタジオDNA"),
 ("issuisha","一水社"),("sekai-bunka","世界文化社"),("highland","ハイランド"),("guide-works","ガイドワークス"),
 ("g-walk","ジーウォーク"),("mediax","メディアックス"),("sankei-shuppan","サンケイ出版"),("hayakawa","早川書房"),
 ("kisotengai","奇想天外社"),("shinseisha-game","新声社"),("san-shuppan","サン出版"),("suzuki-shuppan","鈴木出版"),
 ("kinnohoshi","金の星社"),("totsuki-shobo","兎月書房"),("kinensha","金園社"),("nippan-ips","日販アイ・ピー・エス"),
 ("asuka-shinsha","飛鳥新社"),("junet","ジュネット"),("sunny-shuppan","サニー出版"),("home-sha","ホーム社"),
 ("cosmic-shuppan","コスミック出版"),("fujimi-shobo","富士見書房"),("cygames","Cygames"),("php","PHP研究所"),
 ("heibonsha","平凡社"),("hinomaru-bunko","日の丸文庫"),("shibunsha","汐文社"),("kaiseisha","偕成社"),
 ("tsukasa-shobo","司書房"),("sobisha","創美社"),("sankosha-photo","三栄書房"),("sb-creative","SBクリエイティブ"),
]

# 別名で同一実体 = ISBN帯で確認済の merge (norm → 既存/新キー)
MERGE = {
 norm("角川書店"):"kadokawa", norm("角川グループパブリッシング"):"kadokawa",
 norm("角川グループホールディングス"):"kadokawa",
 norm("エニックス"):"square-enix",
 norm("中央公論社"):"chuokoron",
 norm("学習研究社"):"gakken", norm("学研マーケティング"):"gakken",
 norm("朝日新聞社"):"asahi-shimbun",
 norm("リブレ出版"):"libre",
 norm("青磁ビブロス"):"biblos",
 norm("大日本雄辯會講談社"):"kodansha", norm("大日本雄弁会講談社"):"kodansha", norm("コミックス"):"kodansha",
 norm("文芸春秋"):"bungei-shunju",
 norm("アスキー"):"ascii-media-works", norm("メディアワークス"):"ascii-media-works",
 norm("青林堂ネットコミュニケーションズ"):"seirindo",
 norm("コスミックインターナショナル"):"cosmic-shuppan",
}

# --- publishers.yml 更新(純粋追加) ---
pubyml = yaml.safe_load(open(ROOT + "/data/publishers.yml", encoding="utf-8"))
before = len(pubyml)
dupes = []
for k, name in NEW:
    if k in pubyml:
        dupes.append(k); continue
    pubyml[k] = {"name": name}
with open(ROOT + "/data/publishers.yml", "w", encoding="utf-8") as f:
    yaml.safe_dump(pubyml, f, allow_unicode=True, sort_keys=False)

# --- publisher-aliases.yml(merge only) ---
with open(ROOT + "/data/publisher-aliases.yml", "w", encoding="utf-8") as f:
    f.write("# 別名で同一出版実体の merge (norm社名 → key)。 ISBN出版者記号(帯)で確認済。\n")
    f.write("# 新キーは publishers.yml の display名=生社名で promote が自動 norm 照合するため不要。\n")
    yaml.safe_dump({k: v for k, v in MERGE.items()}, f, allow_unicode=True, sort_keys=True)

print("publishers.yml: %d → %d (新 %d, dup skip %s)" % (before, len(pubyml), len(pubyml)-before, dupes))
print("aliases(merge):", len(MERGE))

# キー妥当性: 全aliasのターゲットが publishers.yml に在るか
bad = [v for v in MERGE.values() if v not in pubyml]
print("alias先で未定義キー:", bad or "なし")

# --- 被覆検証 ---
g = json.load(open(ROOT + "/.cache/madb/metadata101-clean.json", encoding="utf-8"))
rows = g.get("@graph", g) if isinstance(g, dict) else g
norm2key = {norm(v["name"]): k for k, v in pubyml.items()}
def resolve(rawname):
    n = norm(rawname)
    return MERGE.get(n) or norm2key.get(n)
covered = total = 0
miss = Counter()
for r in rows:
    p = r.get("schema:publisher") or r.get("publisher")
    if isinstance(p, list): p = p[0] if p else None
    if isinstance(p, dict): p = p.get("@value") or p.get("name")
    if not p: continue
    total += 1
    if resolve(p): covered += 1
    else: miss[norm(p)] += 1
print("巻被覆: %d/%d = %.1f%%" % (covered, total, 100*covered/total))
print("未キー上位:", [n for n, _ in miss.most_common(10)])
