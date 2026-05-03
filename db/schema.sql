-- MANGAL データベーススキーマ
--
-- このファイルは scripts/db-init.ts が読み取って空 DB を作る。
-- 実データの投入は Phase 1 以降のフェッチスクリプトが行う。
--
-- Hybrid 戦略:
--   .cache/db.sqlite — このスキーマで生成され、scripts/fetch-* が書き込む
--                      （gitignore 済み・人手では編集しない）
--   data/manga/<slug>.yml — 人手 override・Zod 検証通過必須
--                            （loadData がマージ時に SQLite より優先）
--
-- 重複・整合性の考え方:
--   - mangaka.qid が一意キー（Wikidata QID）
--   - series.series_id は Wikidata QID 優先、無ければ "norm:<title>:<author>"
--   - volumes.isbn13 が一意キー（ISBN-13 は世界的に一意）
--   - sources は (source_name, ref_table, ref_id) の複合キーで provenance を追跡

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mangaka (
  qid              TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  birth_year       INTEGER,
  death_year       INTEGER,
  alt_names        TEXT,
  has_adult_credit INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS series (
  series_id     TEXT PRIMARY KEY,
  qid           TEXT,
  title         TEXT NOT NULL,
  title_kana    TEXT,
  year_started  INTEGER,
  year_ended    INTEGER,
  status        TEXT,
  demographic   TEXT,
  publisher_key TEXT,
  magazine_key  TEXT,
  adult_score   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS series_authors (
  series_id    TEXT NOT NULL,
  mangaka_qid  TEXT NOT NULL,
  role         TEXT NOT NULL,
  PRIMARY KEY (series_id, mangaka_qid, role),
  FOREIGN KEY (series_id)   REFERENCES series(series_id)  ON DELETE CASCADE,
  FOREIGN KEY (mangaka_qid) REFERENCES mangaka(qid)       ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS editions (
  edition_id   TEXT PRIMARY KEY,
  series_id    TEXT NOT NULL,
  type         TEXT NOT NULL,
  label        TEXT NOT NULL,
  imprint      TEXT,
  year_started INTEGER,
  year_ended   INTEGER,
  FOREIGN KEY (series_id) REFERENCES series(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS volumes (
  isbn13        TEXT PRIMARY KEY,
  edition_id    TEXT NOT NULL,
  number        INTEGER NOT NULL,
  is_extra      INTEGER NOT NULL DEFAULT 0,
  release_date  TEXT,
  cover_url     TEXT,
  price         INTEGER,
  asin          TEXT,
  FOREIGN KEY (edition_id) REFERENCES editions(edition_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
  source_name TEXT NOT NULL,
  ref_table   TEXT NOT NULL,
  ref_id      TEXT NOT NULL,
  fetched_at  TEXT NOT NULL,
  raw_json    TEXT,
  PRIMARY KEY (source_name, ref_table, ref_id)
);

CREATE INDEX IF NOT EXISTS idx_volumes_edition         ON volumes(edition_id);
CREATE INDEX IF NOT EXISTS idx_editions_series         ON editions(series_id);
CREATE INDEX IF NOT EXISTS idx_series_authors_mangaka  ON series_authors(mangaka_qid);
CREATE INDEX IF NOT EXISTS idx_series_qid              ON series(qid);
CREATE INDEX IF NOT EXISTS idx_sources_ref             ON sources(ref_table, ref_id);
