"use client";

import { indexVersion } from "./indexVersion";
import { nowMs, perfDiag, since } from "./perfDiag";
import { kanaToRomaji, normalizeForSearch, romajiToHiragana } from "./romaji";
import type { MangaListItem } from "./schema";

/**
 * ★検索v2(2026-07-14 会議決定・穏当ルート) → v2.1(2026-07-21):
 *  - 検索専用索引を廃止し一覧索引を共有。照合材料は初回1回だけここで前計算(haystack)
 *    → 以後は 1作品=1回の .includes(旧: キー入力ごとに作品ごと正規化6-10回+カナ→ローマ字変換)。
 *  - 正規化はTS一箇所(normalizeForSearch)のみ=Python側と二重実装しない(ドリフト封じ)。
 *  - 照合: 題名系(title/kana/subtitle/alt)+著者を併走マージ(2026-07-19: 旧2段は作家名入り題で著者検索が沈黙)。
 *  - ★複数語AND(2026-07-21): 空白区切りの各語をANDで照合(「ワンピース 尾田」型。旧実装は
 *    正規化が空白を全削除し連結1語として照合=2語クエリが全滅していた)。
 *  - ★alt(別名・英題)は常時マージ(2026-07-21): 初回検索時に遅延fetchし、到着後は haystack に
 *    畳み込んで題名と同格で照合(旧「ヒット0の時だけ別走査」は、片語が題名・片語がaltの
 *    AND検索や、題名にも当たる語のalt作品を取りこぼす)。
 *  - 逐次絞り込み: クエリが前回の延長なら前回ヒット集合内だけ再走査(AND照合は単調なので安全)。
 *  - romaji列は廃止: クエリ側で romaji→かな 変換して kana と照合(逆方向 kana→romaji も照合)。
 */

/** 母音の連続を1つに圧縮(ローマ字長音ゆらぎの同一視: wanpiisu/wanpisu/wanpi-su) */
function collapseVowels(s: string): string {
  return s.replace(/([aeiou])\1+/g, "$1");
}

/** ★曖昧部分一致(2026-08-12 ユーザ報告「ぎゃわんぶらー」で0件): Wu-Manber bitap。
 *  pattern が text の中に「編集距離k以内の部分文字列」として現れるかを O(text長×k) で判定。
 *  厳密検索がヒット0の時だけのフォールバック専用(平常時のコストはゼロ)。pattern≤31字(bitマスク上限)。 */
function fuzzyIncludes(text: string, pattern: string, k: number): boolean {
  const m = pattern.length;
  if (m === 0 || m > 31 || text.length === 0) return false;
  const alpha = new Map<string, number>();
  for (let i = 0; i < m; i++) alpha.set(pattern[i], (alpha.get(pattern[i]) ?? 0) | (1 << i));
  const accept = 1 << (m - 1);
  const R: number[] = new Array(k + 1).fill(0);
  for (let j = 0; j < text.length; j++) {
    const cm = alpha.get(text[j]) ?? 0;
    let prevOld = R[0]; // R[d-1] の更新前の値
    R[0] = (((R[0] << 1) | 1) & cm) >>> 0;
    for (let d = 1; d <= k; d++) {
      const old = R[d];
      // 一致 | 置換(prevOld<<1) | 挿入(prevOld) | 削除(R[d-1]新<<1)
      R[d] = (((((old << 1) | 1) & cm) | prevOld | (prevOld << 1) | (R[d - 1] << 1) | 1) >>> 0);
      prevOld = old;
    }
    if (R[k] & accept) return true;
  }
  return false;
}

/**
 * ★haystack(照合材料の前計算)は2層(2026-09-23):
 *  - 基本層: 題名系 title(題+かな+副題+別名)/ 著者 au(名+かな)/ 完全・前方一致用 t0・k0
 *  - ローマ字層: かな→ローマ字形(題 kanaRoma / 著者 auRoma)= 英字の語(ローマ字橋)専用
 * 旧: 1行ごとに両方を作っていた。ローマ字変換(wanakana)が前計算の約半分(PC実測 1,312/2,628ms)を
 * 占め、日本語で検索する人もそれを待っていた。→ 基本層を先に全部埋め、ローマ字層はその後の空き時間へ。
 * 日本語の語(かな/漢字を含む)はローマ字層を見ない(案B 2026-07-23)ので結果は同一。
 * 英字の語が来た時だけ、残りのローマ字層をその場で埋める。
 * ★著者は2本持つ:
 *   - au(基本層)= 名+かな。著者の境目に AU_SEP を挟む(日本語の語が別の著者との継ぎ目で当たらない)
 *   - auFull(ローマ字層)= 旧 au そのもの(名+かな+ローマ字を区切り無しで連結)。英字の語はこれで照合
 *   ★auFull を「ローマ字形だけの連結」にすると、前の著者のローマ字末尾+次の著者のローマ字先頭が
 *     つながって旧実装に無い一致が生まれる(実測: isu が146→149件・順位も変化 = スナップショット・
 *     ゲートが検出)。英字の語は旧と同一の文字列で照合し、一致集合も順位も変えない。
 */
type Hay = {
  title: string[];
  au: string[];
  t0: string[]; // 正規化title単体(完全/前方一致tier判定用 2026-07-23)
  k0: string[]; // 正規化kana単体
  sub: string[]; // 正規化副題(端末保存から title を組み直す材料)
  kanaRoma: string[]; // ローマ字層: 題かな→ローマ字(母音圧縮)
  auFull: string[]; // ローマ字層: 著者 名+かな+かなのローマ字形(旧 au と同一の連結)
};
const AU_SEP = "\u0001"; // au の著者区切り(照合語に現れない制御文字)
let _hay: Hay | null = null;
let _hayOf: MangaListItem[] | null = null;
let _hayAltV = -1; // hayに畳み込み済みのaltバージョン
let _hayHasAlt = false; // 現hayに別名を畳み込み済みか(=追記だけで更新できるかの判定)

let _alt: Record<string, string[]> | null = null; // slug → 別名リスト(正規化済み)
let _altV = 0; // altが届く/差し替わる度に+1(=hay再構築の合図)
let _altInflight = false;
let _altFailedAt = 0; // 直近の取得失敗時刻(=再試行cooldown。0=失敗なし)
const _altListeners = new Set<() => void>();

/** hayの器だけ用意する(中身は fillBase / fillRoma が埋める)。 */
function allocHay(n: number): Hay {
  return {
    title: new Array(n).fill(""),
    au: new Array(n).fill(""),
    t0: new Array(n).fill(""),
    k0: new Array(n).fill(""),
    sub: new Array(n).fill(""),
    kanaRoma: new Array(n).fill(""),
    auFull: new Array(n).fill(""),
  };
}

function creditsOf(m: MangaListItem) {
  return [...(m.authors || []), ...(m.original_authors || [])];
}

/** ★著者の正規化・ローマ字形のメモ(2026-09-23): 著者は約7万行に対して2.4万種類しかない
 *  (同じ作家が何作も持つ)ので、行ごとに毎回変換せず1種類1回にする。関数は純粋=結果は同一。
 *  下ごしらえが終わったら捨てる(メモリを持ち続けない)。 */
type AuMemo = { n: string; k: string; r: string | null };
let _auMemo = new Map<string, AuMemo>();
function auMemo(a: { name: string; kana?: string }): AuMemo {
  const key = a.name + "\t" + (a.kana || "");
  let e = _auMemo.get(key);
  if (!e) {
    e = { n: normalizeForSearch(a.name), k: a.kana ? normalizeForSearch(a.kana) : "", r: null };
    _auMemo.set(key, e);
  }
  return e;
}
function auRomaOf(e: AuMemo, kana: string | undefined): string {
  if (e.r === null) e.r = kana ? collapseVowels(normalizeForSearch(kanaToRomaji(kana))) : "";
  return e.r;
}

/** 基本層の [from, to) 行ぶんを埋める。呼んだ時点の _alt を畳み込む。 */
function fillBase(items: MangaListItem[], hay: Hay, from: number, to: number): void {
  for (let i = from; i < to; i++) {
    const m = items[i];
    const alts = _alt ? _alt[m.slug] : undefined;
    // ★t0/k0 は題名欄の材料と同一なので使い回す(2026-08-01: 旧実装は同じ
    //   normalizeForSearch を1行につき2回よけいに呼んでいた)。
    const nTitle = normalizeForSearch(m.title);
    const nKana = normalizeForSearch(m.title_kana || "");
    const nSub = normalizeForSearch(m.subtitle || "");
    // 題名系 = title/kana/subtitle + alt(別名・英題。ロード済みなら常時同格で照合)
    hay.title[i] = nTitle + nKana + nSub + (alts ? alts.join("") : "");
    // 著者 = 名+かな(著者の境目に区切り。ローマ字形込みの旧連結は auFull = ローマ字層)
    hay.au[i] = creditsOf(m)
      .map((a) => {
        const e = auMemo(a);
        return e.n + e.k;
      })
      .join(AU_SEP);
    hay.t0[i] = nTitle;
    hay.k0[i] = nKana;
    hay.sub[i] = nSub;
  }
}

/** ローマ字層の [from, to) 行ぶんを埋める(別名に依存しない)。 */
function fillRoma(items: MangaListItem[], hay: Hay, from: number, to: number): void {
  for (let i = from; i < to; i++) {
    const m = items[i];
    // かな→ローマ字形(= ローマ字クエリの照合先。旧title_romaji列の代替)。
    // ★母音連続を圧縮(wanpiisu→wanpisu): 長音表記ゆらぎ(wanpi-su/wanpiisu/wanpisu)を同一視
    hay.kanaRoma[i] = collapseVowels(normalizeForSearch(kanaToRomaji(m.title_kana || "")));
    // 著者= 名+かな+かなのローマ字形(かな/ローマ字入力の著者検索も題名と同機構で。2026-07-19)
    // ★旧 au と同一の連結(区切り無し)。英字の語はこれで照合する = 旧と同じ結果
    hay.auFull[i] = creditsOf(m)
      .flatMap((a) => {
        const e = auMemo(a);
        return [e.n, e.k, auRomaOf(e, a.kana)];
      })
      .join("");
  }
}

/**
 * ★haystackは「細切れに前計算」する(2026-08-01)。
 *
 * 旧: prewarmSearch が requestIdleCallback の中で67k件を一気に構築していた。
 * idle に載せても★1本の巨大タスク★なので、走り出したら主スレッドは最後まで返らない
 * (本番実測4.5秒。初期表示の直後に固まる体感の正体)。
 * 新: 器だけ先に作り、空き時間の許す範囲で行を埋め、足りなければ次の空き時間へ回す。
 * 埋まりきる前に検索が来たら、その場で残りを同期で埋める(結果は常に完全)。
 * ★2026-09-23: 埋める順 = 基本層を全部 → ローマ字層を全部。
 */
// 1回の刻み幅。空き時間が続く限り下のループが続けて回すので、小さくしても総量は変わらず、
// 「一区切りの長さ」だけが短くなる(=描画が詰まらない)。本番実測で500行あたり約20ms。
const FILL_CHUNK = 500;
let _hayFilled = 0; // 基本層: 先頭から何行ぶん埋まっているか
let _romaFilled = 0; // ローマ字層: 先頭から何行ぶん埋まっているか
let _fillScheduled = false;

function hayComplete(): boolean {
  return !!_hayOf && _hayFilled >= _hayOf.length && _romaFilled >= _hayOf.length;
}

/** 下ごしらえが全層終わったら、著者メモを捨てる(以後は使わない)。 */
function releaseMemoIfDone(): void {
  if (hayComplete() && _auMemo.size) _auMemo = new Map();
}

function scheduleFill(items: MangaListItem[]): void {
  if (_fillScheduled) return;
  _fillScheduled = true;
  const step = (deadline?: { timeRemaining: () => number }) => {
    _fillScheduled = false;
    if (!_hay || _hayOf !== items) {
      // ★索引差し替え(head→full等)を跨いだ古いstep(2026-08-31 週次前レビュー):
      //   予約中(_fillScheduled=true)に新itemsのscheduleFillが空振りしていると、
      //   ここでただreturnすると誰も再予約せず前計算が黙って死ぬ(次の検索が67k同期fillを踏む)。
      //   現行hayが未完なら引き継いで再予約する。
      if (_hay && _hayOf && !hayComplete()) scheduleFill(_hayOf);
      return;
    }
    const n = items.length;
    const t0 = nowMs();
    const base0 = _hayFilled;
    const roma0 = _romaFilled;
    while (!hayComplete()) {
      if (_hayFilled < n) {
        const to = Math.min(_hayFilled + FILL_CHUNK, n);
        fillBase(items, _hay, _hayFilled, to);
        _hayFilled = to;
      } else {
        const to = Math.min(_romaFilled + FILL_CHUNK, n);
        fillRoma(items, _hay, _romaFilled, to);
        _romaFilled = to;
      }
      if (!deadline || deadline.timeRemaining() <= 4) break;
    }
    perfDiag.hayIdleMs += since(t0);
    perfDiag.hayIdleRows += _hayFilled - base0;
    perfDiag.romaIdleRows += _romaFilled - roma0;
    if (!hayComplete()) scheduleFill(items);
    else {
      releaseMemoIfDone();
      maybePersist();
    }
  };
  if (typeof requestIdleCallback === "function") requestIdleCallback(step, { timeout: 3000 });
  else setTimeout(step, 0);
}

function resetHay(items: MangaListItem[]): void {
  _auMemo = new Map();
  _hay = allocHay(items.length);
  _hayOf = items;
  _hayFilled = 0;
  _romaFilled = 0;
  _hayAltV = _altV;
  _hayHasAlt = !!_alt;
  _lastKey = ""; // 索引が替わったら絞り込みキャッシュ破棄
  _lastIdx = null;
}

function ensureHay(items: MangaListItem[], needRoma: boolean): Hay {
  // 器が無い/索引が別物 → 作り直し
  if (!_hay || _hayOf !== items) {
    resetHay(items);
  } else if (_hayAltV !== _altV) {
    // ★alt到着だけなら題名欄に追記して済ませる(2026-08-01)。
    //   旧: altが届くたび67k件を全再計算していた(本番実測5.1秒)。これが「検索して件数が
    //   出た直後にまた固まる」体感の主因。alt は題名系の照合材料を★増やす方向にしか
    //   働かない★ので、未畳み込みのhayには文字列追記だけで等価な結果になる。
    //   まだ埋めていない行は fillBase が最新の _alt を見て畳み込むので触らなくてよい。
    //   ★fetch到着は foldAltIntoHay が到着時に処理済(2026-08-31)= ここに来るのは
    //     テスト注入(__setAltIndexForTest)経路のみ。二重追記はしない(注入時点の充填状態が前提)。
    if (!_hayHasAlt && _alt) {
      for (let i = 0; i < _hayFilled; i++) {
        const alts = _alt[items[i].slug];
        if (alts && alts.length) _hay.title[i] += alts.join("");
      }
      _hayHasAlt = true;
    } else {
      // 別名の差し替え(テスト注入・再fetch)は追記では表せない → 全部作り直す
      _hay = allocHay(items.length);
      _hayFilled = 0;
      _romaFilled = 0;
      _hayHasAlt = !!_alt;
    }
    _hayAltV = _altV;
    _lastKey = ""; // 照合材料が変わった=前回ヒット外にも当たりうる。絞り込みキャッシュ破棄
    _lastIdx = null;
  }
  const hay = _hay as Hay;
  const n = items.length;
  // 前計算が追いついていなければ、ここで残りを同期で埋める(検索結果は常に完全)
  if (_hayFilled < n) {
    // ★ここが「検索を押した瞬間の固まり」。実機の数字を採るため計測する(perfDiag)
    const t0 = nowMs();
    const k = n - _hayFilled;
    fillBase(items, hay, _hayFilled, n);
    _hayFilled = n;
    perfDiag.haySyncMs += since(t0);
    perfDiag.haySyncRows += k;
  }
  // ローマ字層は英字の語がある時だけ待つ(日本語の語はこの層を見ない)
  if (needRoma && _romaFilled < n) {
    const t0 = nowMs();
    const k = n - _romaFilled;
    fillRoma(items, hay, _romaFilled, n);
    _romaFilled = n;
    perfDiag.haySyncMs += since(t0);
    perfDiag.romaSyncRows += k;
  }
  if (hayComplete()) {
    releaseMemoIfDone();
    maybePersist();
  }
  return hay;
}

/** 索引ロード後の手すきで前計算を先回り(検索開始時のワンショット遅延を消す)。 */
export function prewarmSearch(items: MangaListItem[]): void {
  if (_hay && _hayOf === items && _hayAltV === _altV && hayComplete()) return;
  if (!_hay || _hayOf !== items) {
    resetHay(items);
    tryAdoptCached(items); // ★前回訪問の下ごしらえが端末に在れば使う(非同期。届くまでは通常どおり埋める)
  }
  scheduleFill(items);
}

// ─── 下ごしらえの端末保存(2026-09-23) ───────────────────────────────────────
// 2回目以降の訪問で、下ごしらえ(PC実測2.6秒・実機はその数倍)を丸ごと省く。
// 鍵 = 正規化コードの指紋 + 索引の版(列形式索引の src = 内容ハッシュ)。どちらかが変われば使わない。
// ★保存できない環境(プライベートモード・容量不足・IndexedDB無し)は黙って従来どおり毎回作る。
const SEP = "\u001f"; // 行の区切り(正規化後の文字列に現れない制御文字。含む行があれば保存しない)
const IDB_DB = "mangal-search";
const IDB_STORE = "hay";
const IDB_KEY = "latest"; // 1件だけ持つ(版が変われば上書き=古い版の掃除が要らない)
const HAY_FIELDS = ["t0", "k0", "sub", "au", "kanaRoma", "auFull"] as const;
type HayField = (typeof HAY_FIELDS)[number];
type StoredHay = { key: string; n: number } & Record<HayField, string>;

let _codeSig: string | null = null;
/** 正規化コードの指紋。下ごしらえの中身は正規化関数の実装で決まるので、実装が変われば保存分は
 *  使えない。固定の試験文字列を実際に通した結果をハッシュして鍵に混ぜる
 *  (= 手で版を上げ忘れても、挙動が変われば鍵が変わる)。 L3 = hay の層構成の版(層を変えたら上げる)。 */
function codeSignature(): string {
  if (_codeSig) return _codeSig;
  const probes = [
    "ワンピース", "わんぴーす", "ONE PIECE", "七つの大罪", "７つの大罪", "らんま1/2", "らんま½",
    "ドラゴンボールＺ", "ヴァイオレット・エヴァーガーデン", "ぢづゐゑ", "シーズンⅡ", "ファイブスター物語",
    "ＧＳ美神 極楽大作戦!!", "きゃりーぱみゅぱみゅ", "っ", "ー", "コウノドリ", "Dr.スランプ", "ゴルゴ13",
    "たかはし るみこ", "サイトウ・タカヲ", "ジョジョの奇妙な冒険 第3部", "ｶﾞﾝﾀﾞﾑ", "ヰタ・セクスアリス",
  ];
  const s =
    "L3|" +
    probes
      .map((p) => normalizeForSearch(p) + "|" + collapseVowels(normalizeForSearch(kanaToRomaji(p))))
      .join("\n");
  let h = 0x811c9dc5; // FNV-1a
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  _codeSig = h.toString(16);
  return _codeSig;
}

function idbUsable(): boolean {
  try {
    return typeof indexedDB !== "undefined" && !!indexedDB;
  } catch {
    return false;
  }
}

function idbOpen(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    let req: IDBOpenDBRequest;
    try {
      req = indexedDB.open(IDB_DB, 1);
    } catch (e) {
      reject(e);
      return;
    }
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) db.createObjectStore(IDB_STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    req.onblocked = () => reject(new Error("blocked"));
  });
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("timeout")), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}

async function idbGet(): Promise<StoredHay | null> {
  const db = await idbOpen();
  try {
    return await new Promise<StoredHay | null>((resolve, reject) => {
      const rq = db.transaction(IDB_STORE, "readonly").objectStore(IDB_STORE).get(IDB_KEY);
      rq.onsuccess = () => resolve((rq.result as StoredHay | undefined) ?? null);
      rq.onerror = () => reject(rq.error);
    });
  } finally {
    db.close();
  }
}

async function idbPut(rec: StoredHay): Promise<void> {
  const db = await idbOpen();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).put(rec, IDB_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

let _persist: { key: string; items: MangaListItem[] } | null = null; // 保存すべき版(読み出しが外れた時に立つ)
let _persistedKey: string | null = null;

function tryAdoptCached(items: MangaListItem[]): void {
  const v = indexVersion(items);
  if (!v || items.length === 0) return; // 版の無い索引(head・行配列フォールバック)は保存しない
  if (!idbUsable()) {
    perfDiag.hayCache = "off";
    return;
  }
  const key = codeSignature() + "|" + v;
  const t0 = nowMs();
  withTimeout(idbGet(), 5000)
    .then((rec) => {
      if (_hayOf !== items || !_hay) return; // 読み出し中に索引が差し替わった
      if (rec && rec.key === key && rec.n === items.length) {
        if (hayComplete() || adoptStored(items, rec)) {
          perfDiag.hayCache = "hit";
          perfDiag.hayCacheMs = since(t0);
          _persistedKey = key;
          return;
        }
      }
      perfDiag.hayCache = "miss";
      _persist = { key, items };
      maybePersist(); // 既に作り終えていれば今すぐ保存へ
    })
    .catch(() => {
      perfDiag.hayCache = "off";
    });
}

/** 保存分を現hayとして採用する。行数や形が合わなければ何もせず false。 */
function adoptStored(items: MangaListItem[], rec: StoredHay): boolean {
  const n = items.length;
  const parts = {} as Record<HayField, string[]>;
  for (const k of HAY_FIELDS) {
    if (typeof rec[k] !== "string") return false;
    const a = rec[k].split(SEP);
    if (a.length !== n) return false;
    parts[k] = a;
  }
  const title = new Array<string>(n);
  for (let i = 0; i < n; i++) {
    const alts = _alt ? _alt[items[i].slug] : undefined;
    title[i] = parts.t0[i] + parts.k0[i] + parts.sub[i] + (alts ? alts.join("") : "");
  }
  _hay = { title, ...parts };
  _hayOf = items;
  _hayFilled = n;
  _romaFilled = n;
  _hayHasAlt = !!_alt; // 別名は採用時点の _alt を畳んだ(未着なら到着時に foldAltIntoHay が追記)
  _hayAltV = _altV;
  _lastKey = "";
  _lastIdx = null;
  return true;
}

function exportHay(hay: Hay, key: string, n: number): StoredHay | null {
  const rec = { key, n } as StoredHay;
  for (const k of HAY_FIELDS) {
    const arr = hay[k];
    for (let i = 0; i < arr.length; i++) if (arr[i].includes(SEP)) return null; // 区切り文字を含む=保存しない
    rec[k] = arr.join(SEP);
  }
  return rec;
}

function maybePersist(): void {
  const p = _persist;
  if (!p || p.key === _persistedKey || !_hay || _hayOf !== p.items || !hayComplete()) return;
  _persistedKey = p.key; // 二重保存しない(失敗しても今回の滞在中は再試行しない)
  const hay = _hay;
  const run = () => {
    if (_hay !== hay) return; // 作り直された
    const rec = exportHay(hay, p.key, p.items.length);
    if (rec) idbPut(rec).catch(() => {});
  };
  if (typeof requestIdleCallback === "function") requestIdleCallback(run, { timeout: 10000 });
  else setTimeout(run, 0);
}

/** テスト用: 現hay(全層が埋まっていること)を保存形式にして返す。 */
export function __exportHayForTest(key = "test"): StoredHay | null {
  if (!_hay || !_hayOf || !hayComplete()) return null;
  return exportHay(_hay, key, _hayOf.length);
}

/** テスト用: 保存形式から hay を採用する(端末保存の読み出し経路と同じ関数)。 */
export function __adoptHayForTest(items: MangaListItem[], rec: StoredHay): boolean {
  return adoptStored(items, rec);
}

/** テスト用: hay を捨てる(下ごしらえ前の状態に戻す)。 */
export function __resetHayForTest(): void {
  _hay = null;
  _hayOf = null;
  _hayFilled = 0;
  _romaFilled = 0;
  _lastKey = "";
  _lastIdx = null;
}

/** テスト用: 各層が何行まで埋まっているか。 */
export function __hayFillForTest(): { base: number; roma: number } {
  return { base: _hayFilled, roma: _romaFilled };
}

/** ★alt到着をその場でhaystackへ確定させる(2026-08-31 週次前レビューで発見した競合の是正):
 *  ホームwarm(prewarmSearch+prewarmAlt並走 = c74fa2f6b)ではidle充填の途中にaltが届く。
 *  旧実装は「既充填行=alt無し」を前提に次回検索のensureHayで[0,_hayFilled)へ全行追記していたため、
 *  到着後にfillHayがalt込みで埋めた行に二重追記され、継ぎ目を跨ぐ部分一致の偽ヒットが出得た。
 *  到着時に既充填行へ追記して _hayAltV を確定=未充填行はfillHayが最新_altを畳む(二重なし)。 */
function foldAltIntoHay(): void {
  if (!_hay || !_hayOf || !_alt || _hayAltV === _altV) return;
  if (_hayHasAlt) return; // 差し替え(テスト注入等)は追記で表せない=ensureHayの作り直しに任せる
  for (let i = 0; i < _hayFilled; i++) {
    const alts = _alt[_hayOf[i].slug];
    if (alts && alts.length) _hay.title[i] += alts.join("");
  }
  _hayHasAlt = true;
  _hayAltV = _altV;
  _lastKey = ""; // 照合材料が増えた=絞り込みキャッシュ破棄(ensureHay追記ブランチと同じ)
  _lastIdx = null;
}

function fetchAlt(): void {
  if (_alt || _altInflight) return;
  // ★失敗後30秒は再試行しない(2026-08-31): 失敗通知→再レンダー→再検索→再fetchの
  //   無限ループ防止(オフライン時に毎レンダー1リクエストが回り続けるのを封鎖)。
  if (_altFailedAt && nowMs() - _altFailedAt < 30_000) return;
  _altInflight = true;
  const _tAlt = nowMs();
  fetch("/manga-alt-index.json")
    .then((r) => (r.ok ? r.json() : {}))
    .then(async (raw: Record<string, string[]>) => {
      // ★正規化はチャンクで(2026-08-31): 82k本を1タスクで回すと中位モバイルで数百msの
      //   ロングタスク。8,000 slugごとに主スレッドを返す(到着はどうせ非同期=等価)。
      const norm: Record<string, string[]> = {};
      let n = 0;
      for (const [slug, alts] of Object.entries(raw)) {
        norm[slug] = alts.map(normalizeForSearch);
        if (++n % 8000 === 0) await new Promise((r) => setTimeout(r, 0));
      }
      _alt = norm;
      _altV++;
      _altInflight = false;
      _altFailedAt = 0;
      foldAltIntoHay(); // 充填中/充填済みのhayへ即畳み込み(次回検索での後追い追記を廃止)
      perfDiag.altFetchMs = since(_tAlt);
      _altListeners.forEach((fn) => fn());
    })
    .catch(() => {
      // ★旧 `_alt = {}` は ①再fetch永久不可 ②リスナー非発火で「検索中」バッジが
      //   次の操作まで固着、の2穴(2026-08-31是正)。未ロードに戻し+通知+cooldown再試行に。
      _altInflight = false;
      _altFailedAt = nowMs();
      _altListeners.forEach((fn) => fn());
    });
}

/** ホーム到着ウォーム用(2026-08-31): 別名索引を先読みし、初回検索後の後追い再照合を無くす。冪等。 */
export function prewarmAlt(): void {
  fetchAlt();
}

/** alt索引(別名)を取得中か(=題名ヒット0の直後、別名での再照合がまだ終わっていない)。
 *  検索UIが「0件」と断言してよいかの判定に使う(2026-08-18 偽0件対策=B案)。 */
export function isAltLoading(): boolean {
  return _altInflight && _alt === null;
}

/** テスト用: alt索引を直接注入(fetch不要)。nullで未ロード状態に戻す。 */
export function __setAltIndexForTest(raw: Record<string, string[]> | null): void {
  _altInflight = false;
  _altFailedAt = 0;
  if (raw === null) {
    _alt = null;
  } else {
    const norm: Record<string, string[]> = {};
    for (const [slug, alts] of Object.entries(raw)) norm[slug] = alts.map(normalizeForSearch);
    _alt = norm;
  }
  _altV++;
}

/** テスト用: 逐次絞り込みキャッシュだけを捨てる(haystackは作り直さない)。
 *  スナップショット試験で「クエリを毎回まっさらな状態から引いた結果」を得るために使う。 */
export function __resetSearchCacheForTest(): void {
  _lastKey = "";
  _lastIdx = null;
}

/** alt(別名)到着時に再検索させたいコンポーネント用の購読。 戻り値=解除。 */
export function onAltLoaded(fn: () => void): () => void {
  _altListeners.add(fn);
  return () => _altListeners.delete(fn);
}

// 逐次絞り込みキャッシュ(クエリ延長時は前回ヒットの行だけ再走査)。
// AND照合は各語・語追加とも単調(ヒット集合は縮むだけ)なので延長判定は正規化語連結キーで安全。
let _lastKey = "";
let _lastIdx: number[] | null = null;

type Forms = { q: string; qKana: string; qRoma: string; jp: boolean };

/** 1語ぶんの照合形を作る(1クエリ1回)。 */
function tokenForms(token: string): Forms {
  const q = normalizeForSearch(token);
  // ★案B(2026-07-23 ユーザ裁定): かな/漢字を含む語はローマ字橋を使わない。
  //   橋はローマ字入力者のための機能で、日本語入力に適用すると「イース」→isu が
  //   arisu/ofisu 等に爆発ヒットする(実測: イース3,522件→835件)。
  const jp = /[ぁ-んァ-ヶ一-龯々ゝゞ]/.test(token);
  const qKana = normalizeForSearch(romajiToHiragana(q)); // ローマ字入力→かな
  const qRoma = jp ? "" : collapseVowels(normalizeForSearch(kanaToRomaji(token))); // かな入力→ローマ字(母音圧縮)
  return { q, qKana, qRoma, jp };
}

/** 1作品×1語の照合。戻り値=一致した経路の強さ(0=不一致 / 1=題名系 / 2=著者 / 3=ローマ字橋)。 */
function rowMatchTier(hay: Hay, i: number, f: Forms): number {
  const kanaDiff = !!f.qKana && f.qKana !== f.q;
  if (hay.title[i].includes(f.q) || (kanaDiff && hay.title[i].includes(f.qKana))) return 1;
  // 著者: 日本語の語は基本層(名+かな)、英字の語はローマ字形込みの旧連結(auFull)で照合
  const au = f.jp ? hay.au[i] : hay.auFull[i];
  if (au.includes(f.q) || (kanaDiff && au.includes(f.qKana))) return 2;
  if (f.qRoma && (hay.kanaRoma[i].includes(f.qRoma) || au.includes(f.qRoma))) return 3;
  return 0;
}

/**
 * ★検索本体v2.2(2026-07-23 案A): マッチした slug → 一致tier の Map を返す。
 * tier(小さいほど強い): 0=完全一致(題orかな) / 1=前方一致 / 2=題名系部分一致 /
 * 3=著者一致 / 4=ローマ字橋のみ。複数語は「最弱の語」のtier(AND全語の支えの強さ)。
 * 呼び手は検索中かつ並び順既定の時に tier で安定ソートする(同tier内=従来順)。
 * alt は初回検索で遅延fetch(到着で onAltLoaded 通知→呼び直し→hayに畳み込み済みで照合)。
 */
export function searchWithTiers(query: string, items: MangaListItem[]): Map<string, number> {
  const _t0 = nowMs();
  const out = new Map<string, number>();
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) return out;
  if (!_alt) fetchAlt(); // 検索する人だけaltを読む(一覧閲覧のみの人に3MBを課さない)
  const forms = tokens.map(tokenForms).filter((f) => f.q);
  if (!forms.length) return out;
  // ★ローマ字層は英字の語がある時だけ待つ(2026-09-23)。日本語の語は基本層だけで完結する
  const hay = ensureHay(items, forms.some((f) => !f.jp));
  const fullQ = normalizeForSearch(query); // 完全/前方一致は全文で判定(空白は正規化で消える)

  // 走査対象: 逐次絞り込み(前回クエリの延長なら前回ヒット行だけ再走査)
  const key = forms.map((f) => f.q).join(" ");
  const scanAll = !(_lastIdx && _lastKey && key.startsWith(_lastKey) && key !== _lastKey);
  const scanLen = scanAll ? items.length : (_lastIdx as number[]).length;
  const hits: number[] = [];

  for (let s = 0; s < scanLen; s++) {
    const i = scanAll ? s : (_lastIdx as number[])[s];
    let worst = 0; // 語ごとの最弱経路
    let ok = true;
    for (const f of forms) {
      const tr = rowMatchTier(hay, i, f);
      if (!tr) {
        ok = false;
        break;
      }
      if (tr > worst) worst = tr;
    }
    if (!ok) continue;
    hits.push(i);
    // tier確定: 完全一致(0)/前方一致(1)は全文×題/かな単体で判定、以外は経路tier+1(2..4)
    let tier: number;
    if (hay.t0[i] === fullQ || hay.k0[i] === fullQ) tier = 0;
    else if (fullQ && (hay.t0[i].startsWith(fullQ) || hay.k0[i].startsWith(fullQ))) tier = 1;
    else tier = worst + 1; // 1→2(題部分一致), 2→3(著者), 3→4(ローマ字橋)
    out.set(items[i].slug, tier);
  }

  // ★曖昧フォールバック(2026-08-12): 厳密照合が0件の時だけ、編集距離1〜2の近似部分一致を全行走査。
  //   tier=5(最弱)。単語1語×正規化4字以上のみ(短語は誤爆が多すぎる)。多語ANDは対象外。
  //   逐次絞り込みキャッシュは残さない(曖昧ヒット集合は延長クエリの上位集合と保証できないため)。
  if (out.size === 0 && forms.length === 1) {
    const f = forms[0];
    const pat = f.q.slice(0, 31);
    const k = pat.length >= 8 ? 2 : pat.length >= 4 ? 1 : 0;
    if (k > 0) {
      const patKana = f.qKana && f.qKana !== f.q ? f.qKana.slice(0, 31) : "";
      const patRoma = f.qRoma ? f.qRoma.slice(0, 31) : "";
      for (let i = 0; i < items.length; i++) {
        if (
          fuzzyIncludes(hay.title[i], pat, k) ||
          (patKana && fuzzyIncludes(hay.title[i], patKana, k)) ||
          (patRoma && fuzzyIncludes(hay.kanaRoma[i], patRoma, k))
        ) {
          out.set(items[i].slug, 5);
        }
      }
      if (out.size > 0) {
        _lastKey = "";
        _lastIdx = null;
        perfDiag.searchMs = since(_t0);
        perfDiag.searchHits = out.size;
        return out;
      }
    }
  }

  _lastKey = key;
  _lastIdx = hits;
  perfDiag.searchMs = since(_t0);
  perfDiag.searchHits = out.size;
  return out;
}

/** 互換API: マッチした slug 集合(一覧 filter と AND 合成して使う)。 */
export function searchSlugs(query: string, items: MangaListItem[]): Set<string> {
  return new Set(searchWithTiers(query, items).keys());
}
