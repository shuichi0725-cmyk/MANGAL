-- MANGAL データベーススキーマ
--
-- このファイルは scripts/db-init.ts が読み取って空 DB を作る。
-- 実データの投入は Phase 1 以降のフェッチスクリプトが行う。
--
-- 設計方針:
--   - 各テーブルに INTEGER PRIMARY KEY AUTOINCREMENT の内部 ID を持たせる
--     （外部識別子の変更や正規化アルゴリズムの改良に対して FK が壊れないため）
--   - Wikidata QID / ISBN-13 / 正規化 series_key は UNIQUE 制約に降格
--   - sources テーブルは provenance を追跡し、後で人手レビューを可能にする
--   - 成人向けで弾かれたものも DB には残す（adult_score 列で表現）。
--     掲載側で score >= しきい値を除外する運用。db:report で目視できる。

PRAGMA foreign_keys = ON;

-- M1: スキーマバージョン管理。今後の破壊的変更時にマイグレーションが
-- 必要かを判断する。値は string で柔軟に扱う（例 "1", "1.1", "2" など）。
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta (key, value) VALUES
  ('schema_version', '4'),
  ('created_at', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));

-- M3: publishers / magazines は data/*.yml が source-of-truth だが、
-- series.publisher_key が孤立しないかチェックできるよう SQLite にも
-- ミラーする。読み込みは scripts/import-masters.ts。
CREATE TABLE IF NOT EXISTS publishers (
  key  TEXT PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS magazines (
  key         TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  publisher   TEXT NOT NULL,
  demographic TEXT NOT NULL,
  FOREIGN KEY (publisher) REFERENCES publishers(key) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS mangaka (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  qid              TEXT NOT NULL UNIQUE,    -- Wikidata QID (例: Q193300)
  name             TEXT NOT NULL,
  birth_year       INTEGER,
  death_year       INTEGER,
  alt_names        TEXT,                    -- pipe-separated
  has_adult_credit INTEGER NOT NULL DEFAULT 0,
  -- M2: 行タイムスタンプ。「いつ NDL から取った」を後追いするため。
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS series (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  series_key    TEXT NOT NULL UNIQUE,       -- "norm:<base>|qid:Q…" or "norm:<base>|name:…"
  qid           TEXT UNIQUE,                -- Wikidata QID（あれば）
  title         TEXT NOT NULL,
  title_kana    TEXT,
  year_started  INTEGER,
  year_ended    INTEGER,
  status        TEXT,                       -- ongoing/completed/hiatus
  demographic   TEXT,                       -- shounen/seinen/...
  publisher_key TEXT REFERENCES publishers(key) ON DELETE SET NULL,
  magazine_key  TEXT REFERENCES magazines(key)  ON DELETE SET NULL,
  -- B-1 (Wikipedia 連携) で追加: NDL から取れない metadata。
  --   genres は `,` 区切りの genre key 列（例 "action,adventure,fantasy"）。
  --   loadData は配列が要るので promote-bulk が split する。
  --   synopsis は Wikipedia 記事冒頭抜粋。CC BY-SA なので UI で帰属表示必須。
  genres        TEXT,
  synopsis      TEXT,
  -- B-1: Wikipedia 探索結果のキャッシュ（再 fetch をスキップする目印）。
  --   wikipedia_url が NULL = 未探索、'' = 探索したが該当記事なし、URL = 該当あり。
  wikipedia_url TEXT,
  adult_score   INTEGER NOT NULL DEFAULT 0, -- 0=全年齢, 高いほど成人寄り
  -- M2 timestamps
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS series_authors (
  series_id    INTEGER NOT NULL,
  mangaka_id   INTEGER NOT NULL,
  role         TEXT NOT NULL,               -- writer / artist / writer_artist / original_author
  PRIMARY KEY (series_id, mangaka_id, role),
  FOREIGN KEY (series_id)  REFERENCES series(id)  ON DELETE CASCADE,
  FOREIGN KEY (mangaka_id) REFERENCES mangaka(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS editions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  series_id    INTEGER NOT NULL,
  type         TEXT NOT NULL,               -- standard/kanzenban/bunkobon/shinsoban/aizoban/wideban/renewal/other
  label        TEXT NOT NULL,
  imprint      TEXT,
  year_started INTEGER,
  year_ended   INTEGER,
  -- M2 timestamps
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (series_id, type),
  FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS volumes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  edition_id    INTEGER NOT NULL,
  isbn13        TEXT NOT NULL UNIQUE,
  number        INTEGER NOT NULL,
  is_extra      INTEGER NOT NULL DEFAULT 0, -- 外伝・0巻
  release_date  TEXT,                       -- YYYY-MM-DD
  cover_url     TEXT,
  price         INTEGER,                    -- 円
  asin          TEXT,
  -- M2 timestamps
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  FOREIGN KEY (edition_id) REFERENCES editions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  source_name TEXT NOT NULL,                -- wikidata / ndl / openbd / rakuten / wikipedia_llm
  ref_table   TEXT NOT NULL,                -- mangaka / series / editions / volumes
  ref_id      TEXT NOT NULL,                -- 自然キー (qid/isbn13/series_key) を文字列化
  fetched_at  TEXT NOT NULL,                -- ISO8601
  raw_json    TEXT,
  UNIQUE (source_name, ref_table, ref_id)
);

-- L3: 成人判定スコアの内訳。なぜ score=N になったかを追跡できるように。
-- 単一の signal が増減した時に他の signal を巻き込まずに更新でき、
-- レビューでも「どの signal が誤検出を起こしているか」が一目で分かる。
CREATE TABLE IF NOT EXISTS adult_signals (
  series_id INTEGER NOT NULL,
  signal    TEXT NOT NULL,    -- "wikidata_hentai_credit" / "wikipedia_adult_mangaka_list" / "adult_publisher_imprint" / "title_keyword" / "isbn_prefix" など
  weight    INTEGER NOT NULL, -- このシグナルが寄与したスコア
  evidence  TEXT,             -- 何が当たったかの根拠（マッチした単語・該当 ISBN 接頭辞 等）
  fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (series_id, signal),
  FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- Fix C (2026-05): Wikipedia 由来の「既知の成人系出版社・レーベル」シード。
-- imprint 文字列に substring match させて adult_score を加算する。
-- scripts/fetch-adult-lists.ts が JA Wikipedia 「成人向け漫画雑誌の一覧」を
-- パースして seed する。手動追加は source='manual' で書き込む運用。
CREATE TABLE IF NOT EXISTS adult_publishers (
  name        TEXT PRIMARY KEY,    -- 出版社/レーベル名 (NFKC 正規化済)
  source      TEXT NOT NULL,        -- 'wikipedia_adult_magazines' or 'manual'
  fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Fix C: Wikipedia 由来の「既知の成人向け漫画家リスト」シード。
-- mangaka.name (および alt_names) と NFKC 正規化後の文字列で照合。
-- Wikidata の P136=Q172241 で取れない作家 (例: 唯登詩樹) を補完する。
CREATE TABLE IF NOT EXISTS adult_mangaka_known (
  name        TEXT PRIMARY KEY,    -- NFKC 正規化済 (空白・記号・カンマ除去)
  display     TEXT NOT NULL,       -- 元表記 (UI 表示・デバッグ用)
  source      TEXT NOT NULL,        -- 'wikipedia_adult_mangaka_list' or 'manual'
  fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- L4: ASIN は ISBN-13 と 1:N（ロケール別・楽天/Amazon 出品差異など）。
-- volumes.asin の単一カラムだと運用で詰まるので、別表で複数登録を許す。
-- volumes.asin はキャッシュとして「主に使う1件」を保持する位置付けに留める。
CREATE TABLE IF NOT EXISTS asins (
  isbn13     TEXT NOT NULL,
  asin       TEXT NOT NULL,
  locale     TEXT NOT NULL,   -- "jp" / "com" / "co.uk" / "de" など
  source     TEXT NOT NULL,   -- "paapi" / "rakuten" / "manual" / "openbd" など
  fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (isbn13, asin, locale),
  FOREIGN KEY (isbn13) REFERENCES volumes(isbn13) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_volumes_edition         ON volumes(edition_id);
CREATE INDEX IF NOT EXISTS idx_editions_series         ON editions(series_id);
CREATE INDEX IF NOT EXISTS idx_series_authors_mangaka  ON series_authors(mangaka_id);
CREATE INDEX IF NOT EXISTS idx_series_qid              ON series(qid);
CREATE INDEX IF NOT EXISTS idx_sources_ref             ON sources(ref_table, ref_id);
CREATE INDEX IF NOT EXISTS idx_mangaka_name            ON mangaka(name);
CREATE INDEX IF NOT EXISTS idx_asins_isbn              ON asins(isbn13);
