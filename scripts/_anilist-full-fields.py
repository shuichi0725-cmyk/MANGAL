"""AniList の 1 作品 (= 鬼滅の刃) で 取得可能な全 field を 取得 + 日本語解説で出力。"""
import sys, json, urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'
OUT = Path('.cache/anilist-full-fields-kimetsu.json')
OUT_MD = Path('.cache/anilist-full-fields-kimetsu.md')

# 全 field (= auth 不要 + マンガ関連 のみ)
QUERY = '''
query ($search: String) {
  Media(search: $search, type: MANGA) {
    id
    idMal
    title { romaji english native userPreferred }
    type
    format
    status
    description(asHtml: false)
    startDate { year month day }
    endDate { year month day }
    chapters
    volumes
    countryOfOrigin
    isLicensed
    source(version: 3)
    hashtag
    updatedAt
    coverImage { extraLarge large medium color }
    bannerImage
    genres
    synonyms
    averageScore
    meanScore
    popularity
    favourites
    trending
    isAdult
    siteUrl
    tags {
      id name description category rank
      isGeneralSpoiler isMediaSpoiler isAdult
    }
    externalLinks {
      id url site siteId type language color icon
    }
    streamingEpisodes { title thumbnail url site }
    rankings {
      id rank type format year season allTime context
    }
    relations {
      edges {
        relationType
        node { id title { romaji english native } type format }
      }
    }
    characters(perPage: 5, sort: [ROLE, RELEVANCE]) {
      edges {
        role name
        node {
          id
          name { full native }
          image { medium }
        }
      }
    }
    staff(perPage: 5) {
      edges {
        role
        node {
          id
          name { full native }
          image { medium }
        }
      }
    }
    stats {
      scoreDistribution { score amount }
      statusDistribution { status amount }
    }
  }
}
'''

FIELD_DESCRIPTIONS = {
    'id': 'AniList 内部 ID (= 唯一の作品 識別子)',
    'idMal': 'MyAnimeList ID (= MAL との突合 ID)',
    'title.romaji': 'ローマ字 タイトル (= ヘボン式 / 訓令式 揺れあり)',
    'title.english': '英語 公式 タイトル (= 翻訳出版社が付けた名前)',
    'title.native': '日本語 タイトル (= 原語)',
    'title.userPreferred': 'ユーザ表示優先 (= romaji / english / native 切替設定)',
    'type': 'MEDIA 種別 (= MANGA / ANIME)',
    'format': '作品形式 (= MANGA / NOVEL = ライトノベル / ONE_SHOT = 読切 / MANHWA = 韓国 / MANHUA = 中国 / OEL = 海外原作)',
    'status': '連載状態 (= FINISHED / RELEASING / NOT_YET_RELEASED / CANCELLED / HIATUS)',
    'description': 'あらすじ (= 英語 / HTML or plain)',
    'startDate': '連載開始日 (= year/month/day)',
    'endDate': '連載終了日 (= 完結時のみ)',
    'chapters': '話数 (= 完結時の最終話数 or 進行中の最新)',
    'volumes': '巻数 (= 単行本数)',
    'countryOfOrigin': '原産国 (= JP = 日本、 KR = 韓国、 CN = 中国)',
    'isLicensed': '英訳ライセンス済か (= 海外出版有無)',
    'source': '原作 ソース (= ORIGINAL / MANGA / LIGHT_NOVEL / NOVEL / VISUAL_NOVEL / GAME / OTHER)',
    'hashtag': 'Twitter ハッシュタグ',
    'updatedAt': '最終更新 (= UNIX timestamp)',
    'coverImage': '表紙画像 URL (= extraLarge/large/medium + color = メインカラー)',
    'bannerImage': 'バナー画像 URL',
    'genres': 'ジャンル list (= AniList 標準 19 種、 例 Action/Romance/Drama)',
    'synonyms': '別名 list (= ローマ字以外の表記、 各種翻訳タイトル含む)',
    'averageScore': '平均評価 (= 0-100)',
    'meanScore': '中央評価 (= averageScore と微妙に違う計算)',
    'popularity': '人気度 (= ユーザの favourite + planning + reading + ... の総数)',
    'favourites': 'お気に入り数',
    'trending': 'トレンド スコア',
    'isAdult': '成人指定 boolean',
    'siteUrl': 'AniList 上の作品ページ URL',
    'tags[].name': '細分タグ名 (= "Vampires", "Schoolgirl" 等 100+ 種)',
    'tags[].description': 'タグの定義 説明',
    'tags[].category': 'タグカテゴリ (= Setting / Theme / Demographic / 等)',
    'tags[].rank': 'タグの強さ (= 0-100、 何 % この要素を含むか)',
    'tags[].isGeneralSpoiler': '一般 spoiler フラグ',
    'tags[].isMediaSpoiler': 'この作品 固有 spoiler フラグ',
    'tags[].isAdult': '成人タグ',
    'externalLinks[].url': '外部リンク URL',
    'externalLinks[].site': 'サイト名 (= "Official Site", "Twitter", "Crunchyroll" 等)',
    'externalLinks[].siteId': 'サイト内部 ID',
    'externalLinks[].type': 'リンク種別 (= INFO / STREAMING / SOCIAL)',
    'externalLinks[].language': 'リンク言語',
    'rankings': 'ランキング (= 年間 best、 anime全体 等の順位)',
    'relations.edges': '関連作品 (= SEQUEL / PREQUEL / ADAPTATION / SIDE_STORY 等)',
    'characters.edges': 'キャラクター list (= role = MAIN/SUPPORTING/BACKGROUND)',
    'staff.edges': 'スタッフ list (= 作画/原作/編集 等の role 付き)',
    'stats.scoreDistribution': 'ユーザ評価の分布 (= score別 votes 数)',
    'stats.statusDistribution': '視聴/読書 状態 分布 (= CURRENT/COMPLETED/PAUSED/DROPPED/PLANNING)',
}

def run():
    q = json.dumps({'query': QUERY, 'variables': {'search': '鬼滅の刃'}}).encode('utf-8')
    req = urllib.request.Request(
        ENDPOINT, data=q,
        headers={'User-Agent': UA, 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())['data']['Media']

def main():
    media = run()
    OUT.write_text(json.dumps(media, ensure_ascii=False, indent=2), encoding='utf-8')

    # Markdown 出力
    lines = ['# AniList 全 field サンプル = 鬼滅の刃 (= Demon Slayer)\n\n']
    lines.append(f'- 取得 URL: `https://graphql.anilist.co`\n')
    lines.append(f'- AniList ID: `{media["id"]}` ({media.get("siteUrl")})\n\n')

    # 各 field を 順に
    def emit(path: str, val, desc: str | None = None):
        d = desc or FIELD_DESCRIPTIONS.get(path, '')
        v = val
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + '...'
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)[:300]
        lines.append(f'- `{path}`: **{v}**  \n  → {d}\n')

    emit('id', media.get('id'))
    emit('idMal', media.get('idMal'))
    t = media.get('title') or {}
    emit('title.romaji', t.get('romaji'))
    emit('title.english', t.get('english'))
    emit('title.native', t.get('native'))
    emit('title.userPreferred', t.get('userPreferred'))
    emit('type', media.get('type'))
    emit('format', media.get('format'))
    emit('status', media.get('status'))
    emit('description', media.get('description'))
    emit('startDate', media.get('startDate'))
    emit('endDate', media.get('endDate'))
    emit('chapters', media.get('chapters'))
    emit('volumes', media.get('volumes'))
    emit('countryOfOrigin', media.get('countryOfOrigin'))
    emit('isLicensed', media.get('isLicensed'))
    emit('source', media.get('source'))
    emit('hashtag', media.get('hashtag'))
    emit('updatedAt', media.get('updatedAt'))
    emit('coverImage', media.get('coverImage'))
    emit('bannerImage', media.get('bannerImage'))
    emit('genres', media.get('genres'))
    emit('synonyms', media.get('synonyms'))
    emit('averageScore', media.get('averageScore'))
    emit('meanScore', media.get('meanScore'))
    emit('popularity', media.get('popularity'))
    emit('favourites', media.get('favourites'))
    emit('trending', media.get('trending'))
    emit('isAdult', media.get('isAdult'))
    emit('siteUrl', media.get('siteUrl'))

    lines.append('\n## tags (= 細分タグ、 抜粋 5 件)\n\n')
    for tag in (media.get('tags') or [])[:5]:
        lines.append(f'- name=**{tag.get("name")}** rank={tag.get("rank")} category={tag.get("category")}  \n  → 説明: {tag.get("description")}\n')

    lines.append('\n## externalLinks (= 外部リンク)\n\n')
    for el in (media.get('externalLinks') or []):
        lines.append(f'- site=**{el.get("site")}** type={el.get("type")} lang={el.get("language")}  \n  URL: {el.get("url")}\n')

    lines.append('\n## relations (= 関連作品 抜粋 5 件)\n\n')
    edges = (media.get('relations') or {}).get('edges') or []
    for e in edges[:5]:
        nt = (e.get('node') or {}).get('title') or {}
        lines.append(f'- relationType=**{e.get("relationType")}** type={(e.get("node") or {}).get("type")} format={(e.get("node") or {}).get("format")}  \n  ja: {nt.get("native")} / en: {nt.get("english") or nt.get("romaji")}\n')

    lines.append('\n## characters (= キャラ 抜粋 5 件)\n\n')
    cedges = (media.get('characters') or {}).get('edges') or []
    for e in cedges[:5]:
        n = (e.get('node') or {}).get('name') or {}
        lines.append(f'- role=**{e.get("role")}** ja: {n.get("native")} / en: {n.get("full")}\n')

    lines.append('\n## staff (= スタッフ 抜粋 5 件)\n\n')
    sedges = (media.get('staff') or {}).get('edges') or []
    for e in sedges[:5]:
        n = (e.get('node') or {}).get('name') or {}
        lines.append(f'- role=**{e.get("role")}** ja: {n.get("native")} / en: {n.get("full")}\n')

    lines.append('\n## stats (= 統計)\n\n')
    st = media.get('stats') or {}
    sd = st.get('scoreDistribution') or []
    lines.append(f'- scoreDistribution: {len(sd)} buckets\n')
    for s in sd[:5]:
        lines.append(f'  - score={s.get("score")} amount={s.get("amount")}\n')
    stt = st.get('statusDistribution') or []
    lines.append(f'- statusDistribution: {len(stt)} buckets\n')
    for s in stt:
        lines.append(f'  - status={s.get("status")} amount={s.get("amount")}\n')

    OUT_MD.write_text(''.join(lines), encoding='utf-8')
    print(f'wrote {OUT}')
    print(f'wrote {OUT_MD}')
    print(f'fields output: {len(lines)} lines')

if __name__ == '__main__':
    main()
