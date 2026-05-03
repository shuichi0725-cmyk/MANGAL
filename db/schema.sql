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

CREATE TABLE IF NOT EXISTS mangaka (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  qid              TEXT NOT NULL UNIQUE,    -- Wikidata QID (例: Q193300)
  name             TEXT NOT NULL,
  birth_year       INTEGER,
  death_year       INTEGER,
  alt_names        TEXT,                    -- pipe-separated
  has_adult_credit INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS series (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  series_key    TEXT NOT NULL UNIQUE,       -- "qid:Q12345" or "norm:<title>:<author>"
  qid           TEXT UNIQUE,                -- Wikidata QID（あれば）
  title         TEXT NOT NULL,
  title_kana    TEXT,
  year_started  INTEGER,
  year_ended    INTEGER,
  status        TEXT,                       -- ongoing/completed/hiatus
  demographic   TEXT,                       -- shounen/seinen/...
  publisher_key TEXT,                       -- data/publishers.yml の key
  magazine_key  TEXT,
  adult_score   INTEGER NOT NULL DEFAULT 0  -- 0=全年齢, 高いほど成人寄り
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

CREATE INDEX IF NOT EXISTS idx_volumes_edition         ON volumes(edition_id);
CREATE INDEX IF NOT EXISTS idx_editions_series         ON editions(series_id);
CREATE INDEX IF NOT EXISTS idx_series_authors_mangaka  ON series_authors(mangaka_id);
CREATE INDEX IF NOT EXISTS idx_series_qid              ON series(qid);
CREATE INDEX IF NOT EXISTS idx_sources_ref             ON sources(ref_table, ref_id);
CREATE INDEX IF NOT EXISTS idx_mangaka_name            ON mangaka(name);
