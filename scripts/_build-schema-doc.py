"""
種2 (db-v2.sqlite) + 種3 (series-supplement-v2.yml) の キー一覧表 HTML を生成。
A4 縦印刷向け (= ブラウザ「印刷」 で PDF 化可能)。

output: docs/schema-reference.html
"""
import sqlite3
import yaml
import html
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT = ROOT / "docs" / "schema-reference.html"

# 各 column の 日本語説明 (= schema-v2.sql コメント + 私の解釈)
COL_DESC = {
    # mangaka
    "mangaka.id": "内部 ID (= 自動採番)",
    "mangaka.qid": "Wikidata ID (= 例: Q193300)、 漫画家を 一意識別",
    "mangaka.name": "漫画家名 (= 正式表記)",
    "mangaka.birth_year": "生年 (= 西暦、 不明時 NULL)",
    "mangaka.death_year": "没年 (= 西暦、 存命時 NULL)",
    "mangaka.alt_names": "別名・ペンネーム (= pipe 区切り、 例: '尾田っち|月火水木金土')",
    "mangaka.has_adult_credit": "成人向け作品実績フラグ (= 0/1)",
    "mangaka.created_at": "DB 投入日時 (= ISO8601)",
    "mangaka.updated_at": "DB 更新日時 (= ISO8601)",
    # series
    "series.id": "内部 ID (= 自動採番)",
    "series.series_key": "作品の一意キー (= 'qid:Q…|name:タイトル' または 'name:作者|name:タイトル')",
    "series.qid": "Wikidata ID (= 作品が Wikidata に存在する場合のみ)",
    "series.source": "由来 (= 'madb104' = MADB 由来 / 'orphan101' = 自前集約)",
    "series.title": "作品タイトル (= 主タイトル)",
    "series.subtitle": "副題 (= 副題ありの場合のみ、 例: 'JOJOLION')",
    "series.title_kana": "タイトルふりがな (= カタカナ表記)",
    "series.subtitle_kana": "副題ふりがな",
    "series.title_official_en": "MADB 由来の英題 (= schema:alternateName)",
    "series.year_started": "連載開始年",
    "series.year_ended": "連載終了年 (= 連載中は NULL)",
    "series.status": "連載状態 (= ongoing/completed/hiatus) ※ 種3 で上書きされる",
    "series.demographic": "対象年齢層 (= shounen/shoujo/seinen/josei/kodomo/other) ※ 種3 で上書き",
    "series.publisher_key": "出版社キー (= publishers.key、 例: 'shueisha')",
    "series.magazine_key": "連載誌キー (= magazines.key、 例: 'weekly-shonen-jump')",
    "series.genres": "ジャンル (= カンマ区切り、 例: 'action,adventure') ※ 種3 で上書き",
    "series.synopsis": "あらすじ ※ 種3 で上書き",
    "series.wikipedia_url": "Wikipedia URL",
    "series.adult_score": "成人向けスコア (= 5 以上で公開除外)",
    "series.created_at": "DB 投入日時",
    "series.updated_at": "DB 更新日時",
    # editions
    "editions.id": "内部 ID",
    "editions.series_id": "親作品 ID (= series.id への参照)",
    "editions.type": "版型 (= standard/bunkobon/wideban/kanzenban/shinsoban/aizoban/anime/other)",
    "editions.label": "版型ラベル (= 例: '通常版'/'文庫版'/'完全版')",
    "editions.imprint": "レーベル名 (= 例: 'ジャンプコミックス')",
    "editions.year_started": "この版型の発刊開始年",
    "editions.year_ended": "この版型の発刊終了年",
    "editions.created_at": "DB 投入日時",
    "editions.updated_at": "DB 更新日時",
    # volumes
    "volumes.id": "内部 ID",
    "volumes.edition_id": "親版型 ID (= editions.id への参照)",
    "volumes.madb_book_id": "MADB book ID (= M-prefix、 重複防止 PK 代用)",
    "volumes.isbn13": "ISBN-13 (= 古い巻は NULL あり)",
    "volumes.number": "巻数 (= 数字、 例: 111)",
    "volumes.volume_label": "巻ラベル生表記 (= '上'/'下'/'特装版' 等)",
    "volumes.is_extra": "外伝・0 巻フラグ (= 0/1)",
    "volumes.release_date": "発売日 (= YYYY-MM-DD)",
    "volumes.cover_url": "表紙画像 URL",
    "volumes.price": "価格 (= 円)",
    "volumes.asin": "Amazon ASIN (= primary、 詳細は asins テーブル)",
    "volumes.created_at": "DB 投入日時",
    "volumes.updated_at": "DB 更新日時",
    # series_authors
    "series_authors.series_id": "作品 ID",
    "series_authors.mangaka_id": "漫画家 ID",
    "series_authors.role": "役割 (= writer/artist/writer_artist/original_author)",
    # publishers
    "publishers.key": "出版社キー (= 例: 'shueisha')",
    "publishers.name": "出版社名 (= 例: '集英社')",
    # magazines
    "magazines.key": "連載誌キー (= 例: 'weekly-shonen-jump')",
    "magazines.name": "連載誌名 (= 例: '週刊少年ジャンプ')",
    "magazines.publisher": "発行元 (= publishers.key)",
    "magazines.demographic": "対象年齢層 (= shounen/shoujo/seinen/...)",
    # adult_signals
    "adult_signals.series_id": "対象作品 ID",
    "adult_signals.signal": "判定 signal 名 (= 例: 'wikipedia_adult_mangaka_list')",
    "adult_signals.weight": "寄与スコア",
    "adult_signals.evidence": "根拠 (= マッチした文字列など)",
    "adult_signals.fetched_at": "判定実行日時",
    # adult_publishers
    "adult_publishers.name": "成人系出版社・レーベル名 (= NFKC 正規化済)",
    "adult_publishers.source": "由来 (= 'wikipedia_adult_magazines' / 'manual')",
    "adult_publishers.fetched_at": "投入日時",
    # adult_mangaka_known
    "adult_mangaka_known.name": "成人向け作家名 (= NFKC 正規化済)",
    "adult_mangaka_known.display": "元表記",
    "adult_mangaka_known.source": "由来",
    "adult_mangaka_known.fetched_at": "投入日時",
    # adult_imprints
    "adult_imprints.imprint": "成人系 imprint 名 (= NFKC 正規化済)",
    "adult_imprints.publisher": "発行元 (= 補助情報)",
    "adult_imprints.count": "raw dump 件数 (= 信頼度 weight)",
    "adult_imprints.source": "由来",
    "adult_imprints.fetched_at": "投入日時",
    # sources
    "sources.id": "内部 ID",
    "sources.source_name": "由来 source (= wikidata/ndl/openbd/rakuten/wikipedia_llm)",
    "sources.ref_table": "対象 table (= mangaka/series/editions/volumes)",
    "sources.ref_id": "対象 row の 自然キー",
    "sources.fetched_at": "取得日時",
    "sources.raw_json": "生 JSON snapshot",
    # asins
    "asins.isbn13": "ISBN-13",
    "asins.asin": "Amazon ASIN",
    "asins.locale": "ロケール (= 'jp'/'com'/...)",
    "asins.source": "由来 (= 'paapi'/'rakuten'/...)",
    "asins.fetched_at": "取得日時",
    # amazon_metadata
    "amazon_metadata.asin": "Amazon ASIN",
    "amazon_metadata.isbn13": "対応 ISBN-13",
    "amazon_metadata.browse_node_path": "Amazon カテゴリパス (= 'Books > コミック > ...')",
    "amazon_metadata.is_adult_browse_node": "成年コミックノード含むフラグ",
    "amazon_metadata.sales_rank": "Amazon 売上順位",
    "amazon_metadata.fetched_at": "取得日時",
    # series_archive
    "series_archive.id": "内部 ID",
    "series_archive.series_key": "作品の一意キー",
    "series_archive.qid": "Wikidata ID",
    "series_archive.title": "作品タイトル",
    "series_archive.title_kana": "タイトルふりがな",
    "series_archive.year_started": "連載開始年",
    "series_archive.year_ended": "連載終了年",
    "series_archive.status": "連載状態",
    "series_archive.demographic": "対象年齢層",
    "series_archive.publisher_key": "出版社キー",
    "series_archive.magazine_key": "連載誌キー",
    "series_archive.genres": "ジャンル",
    "series_archive.synopsis": "あらすじ",
    "series_archive.wikipedia_url": "Wikipedia URL",
    "series_archive.adult_score": "成人スコア",
    "series_archive.first_imported_at": "初回投入日時",
    "series_archive.last_imported_at": "最終更新日時",
    "series_archive.current_state": "現在の状態 (= live/excluded/deleted)",
    # series_excluded
    "series_excluded.archive_id": "archive ID (= series_archive.id)",
    "series_excluded.reason": "除外理由 (= 'adult_score'/'manual_admin' 等)",
    "series_excluded.signals_json": "発火 signal JSON",
    "series_excluded.excluded_at": "除外日時",
    "series_excluded.excluded_by": "実行者 (= 'auto' / 'admin:<user>')",
    # admin_audit
    "admin_audit.id": "内部 ID",
    "admin_audit.action": "操作種別 (= reinstate/permanent_delete/manual_exclude)",
    "admin_audit.target_table": "対象 table",
    "admin_audit.target_id": "対象 row ID",
    "admin_audit.performed_by": "実行者",
    "admin_audit.performed_at": "実行日時",
    "admin_audit.reason": "理由 (= 自由記述)",
    "admin_audit.metadata_json": "補助情報 (= JSON)",
    # meta
    "meta.key": "メタ情報のキー (= 'schema_version' 等)",
    "meta.value": "値",
}

# 各 table の 全体的 目的
TABLE_DESC = {
    "mangaka": "漫画家マスタ (= Wikidata QID で一意)",
    "series": "作品マスタ (= 漫画作品の中心 table)",
    "series_authors": "作品と漫画家の関連 (= 1 作品 N 作者の中間 table)",
    "editions": "版型 (= 通常版 / 文庫版 / 完全版 等、 1 作品 N 版型)",
    "volumes": "巻 (= 各版型 N 巻の物理単位、 1 巻 = 1 ISBN)",
    "publishers": "出版社マスタ",
    "magazines": "連載誌マスタ",
    "adult_signals": "成人判定 signal の内訳 (= 何が当たったかの記録)",
    "adult_publishers": "既知の成人系出版社・レーベル seed list",
    "adult_mangaka_known": "既知の成人向け作家 seed list",
    "adult_imprints": "成人系 imprint seed list (= publisher より細かい粒度)",
    "sources": "data provenance 追跡 (= どの source からいつ取ったか)",
    "asins": "ISBN-13 と Amazon ASIN の 多対多関係 (= ロケール別)",
    "amazon_metadata": "Amazon per-ASIN メタデータ (= Phase 5 用、 現状空)",
    "series_archive": "全 import 履歴 (= source-of-truth、 削除しない)",
    "series_excluded": "管理者 review queue (= グレーゾーン)",
    "admin_audit": "管理者操作の監査ログ",
    "meta": "schema 情報など内部メタ",
}

# 種3 yaml の field 説明
SEED3_FIELDS = [
    ("key", "string", "必須", "(qid + baseTitle) 複合 ID。 例: 'qid:Q2010|name:ONE PIECE' / 'name:作者|name:タイトル'", "qid:Q2010|name:ONE PIECE"),
    ("slug", "string?", "任意", "AI 提案 slug (= フォルダ名 / URL)。 promote-bulk の自動 slug より優先。 ほぼ未使用 (= 自動生成に任せる)", "(空)"),
    ("magazine", "string?", "任意", "連載誌キー (= magazines.yml の key)。 不明時 null", "weekly-shonen-jump"),
    ("demographic", "enum?", "任意", "対象年齢層 (= shounen/shoujo/seinen/josei/kodomo/other)", "shounen"),
    ("genres", "string[]?", "任意", "ジャンルタグ 1-4 個 (= genres.yml の master keys から)", "['action', 'adventure', 'fantasy', 'comedy', 'drama']"),
    ("synopsis", "string?", "任意", "あらすじ 80-200 字 (= 独自要約)", "ゴム人間の能力を持つ海賊ルフィが、 仲間と共に伝説の秘宝「ひとつなぎの大秘宝」 を求めて..."),
    ("status", "enum?", "任意", "連載状態 (= ongoing/completed/hiatus)", "ongoing"),
    ("anime_adapted", "bool?", "任意", "アニメ化されたか", "true"),
    ("awards", "string[]?", "任意", "受賞歴 (= ほぼ未使用)", "(空)"),
    ("alternative_titles", "object?", "任意", "他言語タイトル (= {en, fr, de, it, pt})。 ⚠️ en は slug 生成に使うため カタカナ title では必須 fill", "{'en': 'One Piece'}"),
]


def truncate(s, n=80):
    if s is None:
        return '<i class="null">NULL</i>'
    s = str(s)
    if len(s) > n:
        return html.escape(s[:n]) + '<i class="truncate">…</i>'
    return html.escape(s)


def gen_table_section(table_name: str, table_data: dict) -> str:
    cols = table_data["cols"]
    sample = table_data["sample"]
    count = table_data["count"]
    coverage = table_data["coverage"]
    desc = TABLE_DESC.get(table_name, "")

    rows = []
    for c in cols:
        name = c["name"]
        ctype = c["type"]
        notnull = "○" if c["notnull"] else ""
        pk = "PK" if c["pk"] else ""
        desc_text = COL_DESC.get(f"{table_name}.{name}", "")
        sample_val = sample.get(name) if sample else None
        cov = coverage.get(name, 0)
        cov_pct = f"{cov/count*100:.0f}%" if count > 0 else "—"
        rows.append(f"""
          <tr>
            <td class="key">{html.escape(name)}</td>
            <td class="type">{html.escape(ctype)}</td>
            <td class="flag">{pk}{notnull}</td>
            <td class="desc">{html.escape(desc_text)}</td>
            <td class="sample">{truncate(sample_val, 50)}</td>
            <td class="cov">{cov_pct}</td>
          </tr>""")

    return f"""
    <section class="table-section">
      <h3>{html.escape(table_name)} <span class="count">({count:,} rows)</span></h3>
      <p class="table-desc">{html.escape(desc)}</p>
      <table>
        <thead>
          <tr>
            <th>キー名</th>
            <th>型</th>
            <th>制約</th>
            <th>日本語説明</th>
            <th>サンプル値</th>
            <th>充足率</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
"""


def main():
    # === 種2 snapshot ===
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]

    # ONE PIECE 関連で sample を統一 (= 主要 table)
    sample_overrides = {}
    cur.execute("SELECT * FROM series WHERE title='ONE PIECE' AND subtitle IS NULL LIMIT 1")
    op = cur.fetchone()
    if op:
        sample_overrides["series"] = dict(op)
        sid = op["id"]
        cur.execute("SELECT * FROM editions WHERE series_id=? LIMIT 1", (sid,))
        r = cur.fetchone()
        if r: sample_overrides["editions"] = dict(r)
        eid = sample_overrides["editions"]["id"] if "editions" in sample_overrides else None
        if eid:
            cur.execute("SELECT * FROM volumes WHERE edition_id=? LIMIT 1", (eid,))
            r = cur.fetchone()
            if r: sample_overrides["volumes"] = dict(r)
        cur.execute("SELECT * FROM series_authors WHERE series_id=? LIMIT 1", (sid,))
        r = cur.fetchone()
        if r:
            sample_overrides["series_authors"] = dict(r)
            cur.execute("SELECT * FROM mangaka WHERE id=?", (r["mangaka_id"],))
            mr = cur.fetchone()
            if mr: sample_overrides["mangaka"] = dict(mr)
    # 出版社 / 雑誌 は集英社 / WJ
    cur.execute("SELECT * FROM publishers WHERE key='shueisha' LIMIT 1")
    r = cur.fetchone()
    if r: sample_overrides["publishers"] = dict(r)
    cur.execute("SELECT * FROM magazines WHERE key='weekly-shonen-jump' LIMIT 1")
    r = cur.fetchone()
    if r: sample_overrides["magazines"] = dict(r)

    # snapshot 各 table
    table_data = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        if t in sample_overrides:
            sample = sample_overrides[t]
        else:
            cur.execute(f"SELECT * FROM {t} LIMIT 1")
            row = cur.fetchone()
            sample = dict(row) if row else {}
        coverage = {}
        for c in cols:
            cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c['name']} IS NOT NULL AND {c['name']} != ''")
            coverage[c["name"]] = cur.fetchone()[0]
        table_data[t] = {"count": count, "cols": cols, "sample": sample, "coverage": coverage}

    # 主要 / 補助 / 管理 で grouping
    groups = {
        "主要 (= 漫画作品の中心 data)": ["series", "mangaka", "series_authors", "editions", "volumes"],
        "マスタ (= 参照辞書)": ["publishers", "magazines"],
        "成人判定": ["adult_signals", "adult_publishers", "adult_mangaka_known", "adult_imprints"],
        "data 由来追跡": ["sources"],
        "Amazon 連携 (= 現状空、 Phase 5 で稼働)": ["asins", "amazon_metadata"],
        "3-state model (= 公開 / 除外 / 履歴、 現状空)": ["series_archive", "series_excluded", "admin_audit"],
        "内部": ["meta"],
    }

    # === 種3 snapshot ===
    with SEED3.open("r", encoding="utf-8") as f:
        seed3 = yaml.safe_load(f)
    seed3_total = len(seed3["series"])

    # 各 field の coverage
    seed3_coverage = {}
    for field, *_ in SEED3_FIELDS:
        if field == "alternative_titles":
            cnt = sum(1 for e in seed3["series"] if (e.get("alternative_titles") or {}).get("en"))
        else:
            cnt = sum(1 for e in seed3["series"] if e.get(field))
        seed3_coverage[field] = cnt

    # ONE PIECE seed3 entry
    op_seed3 = next((e for e in seed3["series"] if e.get("key") == "qid:Q2010|name:ONE PIECE"), {})

    # === HTML 構築 ===
    out = ROOT / "docs"
    out.mkdir(exist_ok=True)

    head = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>MANGAL データベース キー一覧 (= 種2 + 種3 v2)</title>
<style>
  @page {{ size: A4 portrait; margin: 12mm 10mm; }}
  body {{
    font-family: "Hiragino Sans", "Yu Gothic", "Noto Sans CJK JP", sans-serif;
    font-size: 9pt;
    line-height: 1.4;
    color: #111;
    margin: 0;
  }}
  h1 {{ font-size: 18pt; border-bottom: 2px solid #222; padding-bottom: 4pt; margin: 0 0 6pt; }}
  h2 {{ font-size: 14pt; background: #222; color: #fff; padding: 4pt 8pt; margin: 16pt 0 8pt; page-break-before: always; }}
  h2:first-of-type {{ page-break-before: auto; }}
  h3 {{ font-size: 11pt; border-left: 4pt solid #222; padding-left: 6pt; margin: 12pt 0 4pt; page-break-after: avoid; }}
  h3 .count {{ font-size: 9pt; color: #666; font-weight: normal; }}
  h4 {{ font-size: 10pt; margin: 10pt 0 4pt; color: #444; }}
  p.intro {{ margin: 4pt 0 8pt; font-size: 9pt; }}
  p.table-desc {{ margin: 0 0 4pt; font-size: 8.5pt; color: #555; font-style: italic; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8pt; page-break-inside: avoid; }}
  th, td {{ border: 0.5pt solid #aaa; padding: 2pt 4pt; vertical-align: top; }}
  th {{ background: #eee; font-weight: 600; font-size: 8.5pt; text-align: left; }}
  td.key {{ font-family: "Menlo", "Consolas", monospace; font-size: 8.5pt; white-space: nowrap; }}
  td.type {{ font-family: "Menlo", "Consolas", monospace; font-size: 8pt; color: #666; white-space: nowrap; }}
  td.flag {{ text-align: center; font-size: 8pt; color: #c00; white-space: nowrap; }}
  td.desc {{ font-size: 8.5pt; }}
  td.sample {{ font-family: "Menlo", "Consolas", monospace; font-size: 8pt; color: #036; word-break: break-all; }}
  td.cov {{ text-align: right; font-size: 8pt; color: #666; white-space: nowrap; }}
  i.null {{ color: #999; font-size: 7.5pt; font-style: italic; }}
  i.truncate {{ color: #999; font-style: normal; }}
  .group-intro {{ background: #f5f5f5; padding: 6pt 8pt; margin: 6pt 0; font-size: 9pt; border-left: 3pt solid #888; }}
  .meta-box {{ background: #fffde7; border: 1pt solid #c90; padding: 6pt 8pt; margin: 8pt 0; font-size: 9pt; }}
  .meta-box ul {{ margin: 4pt 0 0 16pt; padding: 0; }}
  .col-widths col:nth-child(1) {{ width: 18%; }}
  .col-widths col:nth-child(2) {{ width: 8%; }}
  .col-widths col:nth-child(3) {{ width: 6%; }}
  .col-widths col:nth-child(4) {{ width: 32%; }}
  .col-widths col:nth-child(5) {{ width: 28%; }}
  .col-widths col:nth-child(6) {{ width: 8%; }}
  table {{ table-layout: fixed; }}
  td, th {{ overflow-wrap: break-word; }}
</style>
</head>
<body>

<h1>MANGAL データベース キー一覧</h1>
<p class="intro">
  生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')} JST<br>
  対象: 種2 (= <code>.cache/db-v2.sqlite</code>、 18 tables) + 種3 (= <code>data/seeds/series-supplement-v2.yml</code>、 {seed3_total:,} entries)
</p>

<div class="meta-box">
  <strong>サンプル値について</strong>
  <ul>
    <li>主要 table (= series / editions / volumes / mangaka / series_authors / publishers / magazines) は <strong>「ONE PIECE」 系列の実 data</strong> を使用 (= 把握しやすさのため)。 他 table は最初の 1 row。</li>
    <li>「充足率」 = その column が NULL でも空文字でもない row の割合 (= data の埋まり具合)。</li>
    <li>「制約」 PK = 主キー、 ○ = NOT NULL。</li>
  </ul>
</div>

<h2>パート 1: 種2 = MADB 由来 DB (= <code>.cache/db-v2.sqlite</code>)</h2>
<p class="intro">
  MADB (= マンガデータベース) から取得した <strong>客観的 data</strong> を SQLite に格納。
  158,263 series / 176,319 editions / 381,393 volumes。 ジャンル / あらすじ / 雑誌 等の
  「客観的に取れない data」 は ここに無く、 種3 (= 次のパート) で補う。
</p>
"""

    body = ""
    for group_name, ts in groups.items():
        body += f'<h3 class="group-header" style="background:#444;color:#fff;padding:3pt 6pt;border:0;">{html.escape(group_name)}</h3>\n'
        for t in ts:
            if t not in table_data:
                continue
            body += gen_table_section(t, table_data[t]).replace(
                '<table>', '<table><colgroup class="col-widths"><col><col><col><col><col><col></colgroup>'
            )

    # 種3 part
    seed3_rows = []
    for field, ftype, req, desc, sample in SEED3_FIELDS:
        cov = seed3_coverage.get(field, 0)
        cov_pct = f"{cov/seed3_total*100:.1f}%" if seed3_total > 0 else "—"
        actual_sample = op_seed3.get(field, sample)
        if field == "alternative_titles":
            actual_sample = op_seed3.get(field, sample)
        sample_str = repr(actual_sample) if actual_sample is not None else "(空)"
        seed3_rows.append(f"""
          <tr>
            <td class="key">{html.escape(field)}</td>
            <td class="type">{html.escape(ftype)}</td>
            <td class="flag">{html.escape(req)}</td>
            <td class="desc">{html.escape(desc)}</td>
            <td class="sample">{truncate(sample_str, 50)}</td>
            <td class="cov">{cov_pct}</td>
          </tr>""")

    seed3_section = f"""
<h2>パート 2: 種3 = AI 補完 yaml (= <code>data/seeds/series-supplement-v2.yml</code>)</h2>
<p class="intro">
  種2 に <strong>無い</strong> 「主観的 / curated data」 を AI (= Claude Opus 4.7) で 1 件ずつ補完し
  yaml に蓄積。 {seed3_total:,} entries (= 種2 series の subset)。
  promote-bulk 起動時に 種2 + 種3 を merge して 最終 <code>data/manga/&lt;slug&gt;/index.yml</code> を生成。
</p>

<div class="meta-box">
  <strong>種3 の キー体系</strong>
  <ul>
    <li>各 entry は <code>key</code> field で 種2 の series 1 件と紐づく。</li>
    <li>key 形式: <code>qid:Q…|name:&lt;タイトル&gt;</code> または <code>name:&lt;作者&gt;|name:&lt;タイトル&gt;</code> (= qid 無し時)</li>
    <li>fill 漏れた entry は yaml に 存在しない or field が空 → promote-bulk で fallback (= TODO_genre / 空文字 / null) 化。</li>
  </ul>
</div>

<h3>seed3 entry の 全 field <span class="count">({seed3_total:,} entries)</span></h3>
<p class="table-desc">サンプル値は ONE PIECE entry の実 data。</p>
<table>
  <colgroup class="col-widths"><col><col><col><col><col><col></colgroup>
  <thead>
    <tr>
      <th>キー名</th>
      <th>型</th>
      <th>必須</th>
      <th>日本語説明</th>
      <th>サンプル値 (= ONE PIECE)</th>
      <th>充足率</th>
    </tr>
  </thead>
  <tbody>{''.join(seed3_rows)}</tbody>
</table>

<h3>種2 ⟷ 種3 の対応 (= 同じ概念がどちら側にあるか)</h3>
<table>
  <colgroup><col style="width:20%"><col style="width:20%"><col style="width:35%"><col style="width:25%"></colgroup>
  <thead><tr><th>概念</th><th>種2 (DB)</th><th>種3 (yaml)</th><th>備考</th></tr></thead>
  <tbody>
    <tr><td>タイトル</td><td><code>series.title</code></td><td>(key 内に含む)</td><td>種2 が主、 種3 は紐付けに使う</td></tr>
    <tr><td>ジャンル</td><td><code>series.genres</code></td><td><code>genres</code></td><td>種3 で上書き (= 種2 はほぼ空)</td></tr>
    <tr><td>あらすじ</td><td><code>series.synopsis</code></td><td><code>synopsis</code></td><td>種3 で上書き</td></tr>
    <tr><td>連載誌</td><td><code>series.magazine_key</code></td><td><code>magazine</code></td><td>種3 で上書き</td></tr>
    <tr><td>対象年齢</td><td><code>series.demographic</code></td><td><code>demographic</code></td><td>種3 で上書き</td></tr>
    <tr><td>連載状態</td><td><code>series.status</code></td><td><code>status</code></td><td>種3 で上書き</td></tr>
    <tr><td>アニメ化</td><td>(無)</td><td><code>anime_adapted</code></td><td>種3 のみ</td></tr>
    <tr><td>英題</td><td><code>series.title_official_en</code></td><td><code>alternative_titles.en</code></td><td>種3 を slug 生成に使う</td></tr>
    <tr><td>巻 / ISBN</td><td><code>volumes.*</code></td><td>(無)</td><td>種2 のみ (= 客観的 data)</td></tr>
    <tr><td>作者</td><td><code>mangaka.* + series_authors</code></td><td>(無)</td><td>種2 のみ</td></tr>
  </tbody>
</table>

</body>
</html>
"""
    html_out = head + body + seed3_section
    OUT.write_text(html_out, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
