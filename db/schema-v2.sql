-- MANGAL database schema v2 (= path B' rebuild)
--
-- v1 (= db/schema.sql) との差分:
--   1. series テーブルに 副題関連 4 columns 追加:
--      - subtitle TEXT           : 副題本文
--      - subtitle_kana TEXT      : 副題ふりがな
--      - title_official_en TEXT  : MADB schema:alternateName 由来
--      - madb_series_ids TEXT    : MADB C25xxxx の JSON array
--      - source TEXT             : 'madb104' / 'orphan101'
--   2. editions テーブルに madb_series_id TEXT 追加
--   3. volumes テーブルに volume_label TEXT 追加 (= 「上」「下」「特装版」)
--   4. series_key 仕様変更:
--      旧: "norm:<baseTitle>|qid:Q…" or "norm:<baseTitle>|name:…"
--      新: "qid:Q…|name:<title>" or "qid:Q…|name:<title>|sub:<subtitle>"
--          または qid 無し時 "name:<creator>|name:<title>"
--   5. editions の UNIQUE(series_id, type) 制約を緩める (= 同一 series で
--      同 type の edition が複数 MADB record になることがあるため)
--
-- 旧 schema.sql は 引き続き 既存 .cache/db.sqlite で稼働。
-- v2 schema は .cache/db-v2.sqlite に 別途投入。
--
-- 設計方針 (v1 から踏襲):
--   - INTEGER PRIMARY KEY AUTOINCREMENT
--   - Wikidata QID / ISBN-13 / 正規化 series_key は UNIQUE 制約
--   - sources テーブルで provenance 追跡
--   - 成人向け も DB に残す (adult_score 列)

PRAGMA foreign_keys = ON;

-- M1: スキーマバージョン管理。今後の破壊的変更時にマイグレーションが
-- 必要かを判断する。値は string で柔軟に扱う（例 "1", "1.1", "2" など）。
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta (key, value) VALUES
  ('schema_version', 'v2.0'),
  ('schema_source',  'db/schema-v2.sql'),
  ('created_at', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
UPDATE meta SET value = 'v2.0' WHERE key = 'schema_version';

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

-- series v2: 副題 / 公式英語題 / MADB 由来情報 columns を追加。
-- qid は 重複可 (= 同 mangaka が 複数 series を持つため)、 UNIQUE 解除。
CREATE TABLE IF NOT EXISTS series (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  series_key          TEXT NOT NULL UNIQUE,
                      -- 形式: "qid:Q...|name:<title>"
                      --       "qid:Q...|name:<title>|sub:<subtitle>"
                      --       "name:<creator>|name:<title>"
                      --       "name:<creator>|name:<title>|sub:<subtitle>"
                      --       "...|source:orphan" suffix で 由来明示
  qid                 TEXT,           -- Wikidata QID (= 重複可、 同 mangaka 複数 series)
  source              TEXT NOT NULL DEFAULT 'madb104',
                      -- 'madb104' = metadata104 由来
                      -- 'orphan101' = metadata101 自前集約由来
  title               TEXT NOT NULL,
  subtitle            TEXT,            -- 副題本文 (= path B' で 新規)
  title_kana          TEXT,
  subtitle_kana       TEXT,            -- 副題ふりがな (= path B' で 新規)
  title_official_en   TEXT,            -- MADB schema:alternateName 由来 (= 新規)
  madb_series_ids     TEXT,            -- JSON array '["C258774", "C258780", ...]' (= 新規)
  year_started        INTEGER,
  year_ended          INTEGER,
  status              TEXT,            -- ongoing/completed/hiatus
  demographic         TEXT,            -- shounen/seinen/...
  publisher_key       TEXT REFERENCES publishers(key) ON DELETE SET NULL,
  magazine_key        TEXT REFERENCES magazines(key)  ON DELETE SET NULL,
  genres              TEXT,            -- `,` 区切り genre key 列
  synopsis            TEXT,
  wikipedia_url       TEXT,
  adult_score         INTEGER NOT NULL DEFAULT 0,
  created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS series_authors (
  series_id    INTEGER NOT NULL,
  mangaka_id   INTEGER NOT NULL,
  role         TEXT NOT NULL,               -- writer / artist / writer_artist / original_author
  PRIMARY KEY (series_id, mangaka_id, role),
  FOREIGN KEY (series_id)  REFERENCES series(id)  ON DELETE CASCADE,
  FOREIGN KEY (mangaka_id) REFERENCES mangaka(id) ON DELETE CASCADE
);

-- editions v2: madb_series_id 追加 (= 該当 MADB record の C25xxxx)。
-- UNIQUE(series_id, type) 制約は 緩める (= 同 type の editions が 複数 brand
-- で存在しうる、 例: 通常版が 「少年サンデーコミックス」 と 「Shonen sunday novels」
-- 両方ある等)。 代わりに (series_id, madb_series_id) または (series_id, type, imprint)
-- で 一意性 担保。
CREATE TABLE IF NOT EXISTS editions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  series_id       INTEGER NOT NULL,
  madb_series_id  TEXT,             -- MADB C25xxxx (= 新規、 orphan 由来は NULL)
  type            TEXT NOT NULL,    -- standard/kanzenban/bunkobon/...
  label           TEXT NOT NULL,    -- 通常版 / 文庫版 / etc.
  imprint         TEXT,             -- レーベル名 (= schema:brand)
  year_started   INTEGER,
  year_ended     INTEGER,
  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  -- madb_series_id 単位で 重複防止 (= 同 MADB record が 複数 edition rows にならない)
  -- ただし orphan は madb_series_id=NULL なので uniqueness 担保せず、
  -- (series_id, type, imprint) で 重複避ける
  UNIQUE (series_id, madb_series_id),
  UNIQUE (series_id, type, imprint),
  FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- volumes v2: volume_label 追加 (= 「上」「下」「特装版」等の生 label)
CREATE TABLE IF NOT EXISTS volumes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  edition_id    INTEGER NOT NULL,
  isbn13        TEXT NOT NULL UNIQUE,
  number        INTEGER NOT NULL,           -- 数字化済 (= 上下は 1/2 に変換、 表示は volume_label 優先)
  volume_label  TEXT,                       -- 生 label (= '上', '下', '特装版', 'vol.1' 等、 新規)
  is_extra      INTEGER NOT NULL DEFAULT 0, -- 外伝・0巻
  release_date  TEXT,                       -- YYYY-MM-DD
  cover_url     TEXT,
  price         INTEGER,                    -- 円
  asin          TEXT,
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

-- Tier 2 (schema v6, 2026-05): imprint レベルの adult シード。
-- adult_publishers (publisher 単位) では捕捉できない「大手 publisher の adult
-- 専用 sub-imprint」 (例: KADOKAWA フルールコミックス、 リイド社クリベロン系、
-- ぶんか社サイベリア系) を編集ぐらしの粒度で識別する。
-- seed source: data/seeds/adult-imprints.yml (~250 entry)
-- 生成: scripts/seed-adult-imprints.ts が yaml を読んで INSERT OR REPLACE。
-- 照合: editions.imprint が `imprint` 列を substring 包含する場合に
-- adult_imprint シグナル (+3) を発火させる (lib/adult-score.ts)。
CREATE TABLE IF NOT EXISTS adult_imprints (
  imprint     TEXT PRIMARY KEY,    -- NFKC 正規化済の imprint 名
  publisher   TEXT,                 -- 補助情報 (検出ロジックは未使用)
  count       INTEGER,              -- raw dump 由来の件数 (信頼度 weight 用)
  source      TEXT NOT NULL,        -- 'manual_seed' / 'wikipedia' / etc.
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

-- Phase 5 prep (schema v5, 2026-05): Amazon PA-API SearchItems の per-ASIN メタデータ。
-- volumes.asin / volumes.cover_url は既存で primary ASIN とカバー URL をキャッシュしているが、
-- BrowseNode 階層 (= 成年コミック判定の決定打) と sales rank、PA-API の rate-limited refresh の
-- freshness 追跡は新規。承認 (180日以内 3 売上) 後の Phase 5 でこのテーブルへ書き込み始める。
-- 承認待ち期間中は空のままで良い。schema を先に確定させて Phase 5 着手時の migration を不要にする。
CREATE TABLE IF NOT EXISTS amazon_metadata (
  asin                 TEXT PRIMARY KEY,
  isbn13               TEXT,                  -- volumes.isbn13 への弱参照（Amazon-only な ASIN もありうるので NOT NULL にしない）
  browse_node_path     TEXT,                  -- "Books > コミック > 成年コミック" 等の `>` 区切り
  is_adult_browse_node INTEGER NOT NULL DEFAULT 0,  -- BrowseNode 階層に成年コミック等の adult node を含むか
  sales_rank           INTEGER,               -- WebsiteSalesRank。NULL = 未取得 or 取得不可
  fetched_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  FOREIGN KEY (isbn13) REFERENCES volumes(isbn13) ON DELETE SET NULL
);

-- 3-state model (schema v7, 2026-05): live / excluded / archive の責務分離。
--
-- 全体像:
--   series_archive   = 全 import 履歴 (= source-of-truth)。 INSERT/UPDATE のみ、 DELETE しない。
--                      adult filter で弾かれた record も、 後から手動除外された record も、
--                      管理者が 「完全削除」 した record も、 ここには残り続ける。
--                      復帰の元データ。
--   series           = 公開用 (= 一般ユーザに見せる現在の state)。 既存テーブル流用。
--                      live state の row だけがここにある。
--   series_excluded  = 管理者の review queue。 「グレーゾーン」 (= adult filter で弾かれたが
--                      実は健全かもしれないもの) を保持。 admin が見て reinstate / 完全削除を判断する。
--
-- 状態遷移:
--   import        → archive に必ず INSERT/UPDATE、 adult なら excluded に追加 + series には入れない、
--                   そうでなければ series (= live) に INSERT。
--   reinstate     → series に archive snapshot から INSERT、 excluded から DELETE、
--                   archive.current_state = 'live'。
--   permanent del → series と excluded から DELETE、 archive.current_state = 'deleted'。
--                   archive 行は残るので 「再 import で復活」 や 「監査」 はずっと可能。
--   re-import     → archive.last_imported_at 更新 + 必要なら state 再評価。

-- series_archive: 全 import 履歴 (= source-of-truth)。 削除しない。
CREATE TABLE IF NOT EXISTS series_archive (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  series_key        TEXT NOT NULL UNIQUE,
  -- series テーブルと同じ列を snapshot
  qid               TEXT,
  title             TEXT NOT NULL,
  title_kana        TEXT,
  year_started      INTEGER,
  year_ended        INTEGER,
  status            TEXT,
  demographic       TEXT,
  publisher_key     TEXT,
  magazine_key      TEXT,
  genres            TEXT,
  synopsis          TEXT,
  wikipedia_url     TEXT,
  adult_score       INTEGER NOT NULL DEFAULT 0,
  -- audit
  first_imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_imported_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  -- 現在の状態。 live=series テーブルにあり公開、 excluded=series_excluded にあり管理者 review 中、
  -- deleted=どちらにも無い (= 完全削除済み、 archive にのみ残る)。
  current_state     TEXT NOT NULL DEFAULT 'live'
                    CHECK(current_state IN ('live','excluded','deleted'))
);

-- series_excluded: 管理者の review queue (= 「グレーゾーン」)。
-- adult filter で auto 除外されたものや、 admin が手動で hide したものを保持。
-- ここから reinstate (= 公開へ戻す) または完全削除 (= series_archive のみ残る) する。
CREATE TABLE IF NOT EXISTS series_excluded (
  archive_id   INTEGER PRIMARY KEY,
  -- 除外理由のラベル。 'adult_score' / 'adult_imprint' / 'manual_admin' / 'duplicate' など。
  -- UI でフィルタリング/集計する用。
  reason       TEXT NOT NULL,
  -- 発火した signal の JSON (= adult-score の signal リスト等)。 admin UI で根拠を表示する用。
  signals_json TEXT,
  excluded_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  -- 'auto' = import 時の rule で自動、 'admin:<user>' = 手動。
  excluded_by  TEXT NOT NULL DEFAULT 'auto',
  FOREIGN KEY (archive_id) REFERENCES series_archive(id) ON DELETE CASCADE
);

-- admin_audit: 管理者操作の監査ログ。
-- reinstate / permanent_delete / manual_exclude の 3 操作を記録する。
-- 「誰が、 いつ、 何を、 なぜ」 を後追いできる。
CREATE TABLE IF NOT EXISTS admin_audit (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  action        TEXT NOT NULL,        -- 'reinstate' | 'permanent_delete' | 'manual_exclude'
  target_table  TEXT NOT NULL,        -- 'series_archive' (= 主に archive_id を指す)
  target_id     INTEGER NOT NULL,
  performed_by  TEXT,                  -- 'admin:<user>' or 'system'
  performed_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  reason        TEXT,                  -- 自由記述
  metadata_json TEXT                   -- 補助情報 (= reinstate 時の signal snapshot 等)
);

CREATE INDEX IF NOT EXISTS idx_adult_imprints_imprint  ON adult_imprints(imprint);
CREATE INDEX IF NOT EXISTS idx_series_archive_state    ON series_archive(current_state);
CREATE INDEX IF NOT EXISTS idx_series_archive_adult    ON series_archive(adult_score);
CREATE INDEX IF NOT EXISTS idx_series_excluded_reason  ON series_excluded(reason);
CREATE INDEX IF NOT EXISTS idx_series_excluded_at      ON series_excluded(excluded_at);
CREATE INDEX IF NOT EXISTS idx_admin_audit_target      ON admin_audit(target_table, target_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_performed   ON admin_audit(performed_at);
CREATE INDEX IF NOT EXISTS idx_volumes_edition         ON volumes(edition_id);
CREATE INDEX IF NOT EXISTS idx_editions_series         ON editions(series_id);
CREATE INDEX IF NOT EXISTS idx_series_authors_mangaka  ON series_authors(mangaka_id);
CREATE INDEX IF NOT EXISTS idx_series_qid              ON series(qid);
CREATE INDEX IF NOT EXISTS idx_sources_ref             ON sources(ref_table, ref_id);
CREATE INDEX IF NOT EXISTS idx_mangaka_name            ON mangaka(name);
CREATE INDEX IF NOT EXISTS idx_asins_isbn              ON asins(isbn13);
CREATE INDEX IF NOT EXISTS idx_amazon_metadata_isbn    ON amazon_metadata(isbn13);
CREATE INDEX IF NOT EXISTS idx_amazon_metadata_adult   ON amazon_metadata(is_adult_browse_node);
