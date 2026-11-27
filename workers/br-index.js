/**
 * 索引JSONの「事前圧縮版」の配信(2026-11-17)。 workers/r2-serve.js から呼ぶ。
 *
 * 背景: 索引は R2 に素のまま置き、Cloudflare のエッジがその場で圧縮して配っている。
 *   その場の圧縮は速さ優先の低い品質で、一覧索引(列形式 22MB)が 4.81MB(zstd)にしかならない。
 *   同じ中身を brotli の最高品質で前もって圧縮しておくと 3.45MB(−28%・2026-11-17 本番の実物で実測)。
 *   4本合計(列形式・キャッチ・別名・羅針盤の隠し要素)で 11.1MB → 8.1MB。
 *
 * 仕組み(元の索引は今までどおり置いたまま・事前圧縮版を「隣に足す」だけ):
 *   - 配る側(scripts/_index_br.py)が、元の中身の MD5 を名前に入れた隣のファイル
 *       <元のキー>.<元の中身のMD5>.br
 *     を R2 に置く。
 *   - ここは要求のたびに「いま配っている元」の ETag(= 中身の MD5)を調べ、その名前の事前圧縮版が在れば
 *     それをそのまま(圧縮済みの印 Content-Encoding: br を付けて)返す。
 *   ★名前に元の中身の MD5 が入っているので、「元だけ更新されて事前圧縮版が古い」取り違えは起きない
 *     (名前が合わない = 見つからない = 従来の配り方に戻るだけ)。 どの配信経路が元を書き換えても安全。
 *   ★止め方 = R2 から *.br を消す(ここは自動で従来の配り方に戻る。Worker の出し直しは要らない)。
 *     ※エッジに焼いた事前圧縮版は名前ごと別物なので、消した後も元の MD5 が同じ間は残る(最長1年)。
 *       すぐ止めたい時は Worker の BR_KEYS を空にして出し直す。
 *
 * ★R2 に当てない(2026-11-17 Opus 点検で是正。 旧 = 毎回 R2 の head + get = エッジキャッシュを素通り):
 *   - 「いま配っている元」の ETag は、従来の経路がエッジに焼いた元の応答(caches.default・URL がキー)から読む。
 *     エッジに無い時だけ R2 の head。 = 鮮度は従来の経路とまったく同じ(デプロイ時の purge で入れ替わる)。
 *   - 事前圧縮版の中身もエッジに焼く(キー = /__br/<事前圧縮版の名前>・中身が変わると名前が変わる = 1年置いてよい)。
 *     ★焼く時は Content-Encoding を付けない(エッジが「圧縮済みの応答」として扱い、解いたり付け替えたりしないように)。
 *       返す時にだけ Content-Encoding: br を付け、encodeBody "manual" でそのまま流す。
 *
 * 従来の配り方に戻る(= null を返す)条件:
 *   対象外のキー / GET 以外(HEAD も従来へ)/ 訪問者が br を受け取れない / 元が無い /
 *   元の ETag が MD5 の形でない(分割アップロード等)/ 事前圧縮版が無い
 *
 * ★ETag は「元の中身の MD5」を弱い形(W/"…")で返す = エッジがその場で圧縮して配る時と同じ値。
 *   どちらの配り方で受け取った端末も、次の確認(If-None-Match)で 304 になる。
 */

/** 事前圧縮版を配る索引(R2 のキー)。 ★scripts/_index_br.py の BR_SOURCES と必ず同じにする(テストで突合)。 */
export const BR_KEYS = new Set([
  "manga-list-cols.v1.json",
  "manga-catch-index.json",
  "manga-catch.v1.json",
  "manga-alt-index.json",
  "data/compass-hidden.v1.json",
]);

/** エッジに焼く事前圧縮版の置き場(URL のパス)。 ここへの外からの要求は r2-serve.js が 404 で断る。 */
export const BR_CACHE_PREFIX = "/__br/";
/** 事前圧縮版をエッジに置く長さ(名前に中身の MD5 が入る = 中身は変わらない) */
const BR_EDGE_CACHE = "public, max-age=31536000, immutable";

/**
 * 訪問者が br を受け取れるか。
 * ★Cloudflare は Worker に渡す前に Accept-Encoding を書き換えることがあり、その時は元の値が
 *   request.cf.clientAcceptEncoding に入る。 本番(request.cf が在る)ではこちらだけを信じる
 *   = 書き換え後の値を見て「受け取れる」と誤認し、圧縮を解けない相手(素の curl 等)に br を返す事故を避ける。
 *   request.cf が無い所(手元の試験)だけ、ヘッダーをそのまま見る。
 */
export function clientAcceptsBr(request) {
  const cf = request.cf;
  const ae = cf ? cf.clientAcceptEncoding : request.headers.get("accept-encoding");
  if (typeof ae !== "string" || !ae) return false;
  return ae.split(",").some((part) => {
    const [name, ...params] = part.trim().toLowerCase().split(";");
    if (name.trim() !== "br") return false;
    const q = params.map((s) => s.trim()).find((s) => s.startsWith("q="));
    return !q || parseFloat(q.slice(2)) > 0; // br;q=0 = 明示の拒否
  });
}

/** 事前圧縮版の R2 キー。 etag = 元の中身の MD5(16進32桁)。 */
export function brKey(key, etag) {
  return `${key}.${etag}.br`;
}

/** ETag の値(`"md5"` / `W/"md5"`)から MD5 を取り出す。 MD5 の形でなければ null。 */
export function md5FromEtag(v) {
  if (typeof v !== "string") return null;
  const m = /^(?:W\/)?"?([0-9a-f]{32})"?$/.exec(v.trim());
  return m ? m[1] : null;
}

/** If-None-Match が、この ETag(MD5・引用符なし)を指しているか。 弱い形(W/)・複数候補も受ける。 */
export function etagMatches(ifNoneMatch, etag) {
  if (!ifNoneMatch) return false;
  return ifNoneMatch
    .split(",")
    .map((s) => s.trim().replace(/^W\//, ""))
    .includes(`"${etag}"`);
}

/** R2 の head の結果をエッジに覚えておく長さ(秒)。 元がエッジに無い時だけ使う = 反映直後の古さは最長これだけ */
export const BR_ETAG_MEMO_SEC = 60;

/**
 * いま配っている元の MD5(どれも体は読まない)。
 *   1. 従来の経路がエッジに焼いた元の応答の ETag(= 鮮度は従来とまったく同じ)
 *   2. 無ければ、前に R2 の head で調べた値の控え(エッジ・60秒)
 *      ★これが無いと、br を受け取れる訪問者しか来ない間は元がエッジに焼かれない = 毎回 R2 の head になる
 *   3. それも無ければ R2 の head(結果を 2 に控える)
 */
async function currentMd5(env, key, cache, origKey, origin, waitUntil) {
  if (cache && origKey) {
    const hit = await cache.match(origKey);
    if (hit) {
      const v = md5FromEtag(hit.headers.get("etag"));
      if (hit.body && typeof hit.body.cancel === "function") hit.body.cancel().catch(() => {});
      if (v) return v;
    }
  }
  const memoKey = cache && origin ? new Request(`${origin}${BR_CACHE_PREFIX}etag/${key}`) : null;
  if (memoKey) {
    const memo = await cache.match(memoKey);
    if (memo) {
      const v = md5FromEtag(await memo.text());
      if (v) return v;
    }
  }
  const head = await env.BUCKET.head(key);
  const v = head ? md5FromEtag(head.etag) : null;
  if (v && memoKey) {
    const put = cache.put(memoKey, new Response(v, { headers: { "cache-control": `public, max-age=${BR_ETAG_MEMO_SEC}` } }));
    if (waitUntil) waitUntil(put);
  }
  return v;
}

/**
 * 事前圧縮版でどう応えるかを決める。 応えられない時は null(= 呼び手は従来の経路へ)。
 * baseHeaders = 呼び手が決めた content-type / cache-control など(そのまま付ける)。
 * deps = { cache, origKey, origin, waitUntil }(本番は caches.default・従来の経路のキャッシュキー・url.origin・ctx.waitUntil)。
 *   無い所(手元の試験)ではエッジを使わず R2 だけで答える。
 * 戻り値 { status, headers, body, encodeBody } = そのまま new Response(body, { status, headers, encodeBody }) にする。
 *   ★encodeBody "manual" = 「体はもう圧縮済み。 そのまま流せ」の指定。 付け忘れると二重に圧縮されて壊れる。
 */
export async function planBrIndex(request, env, key, baseHeaders, deps = {}) {
  if (!BR_KEYS.has(key)) return null;
  if (request.method !== "GET") return null;
  if (!clientAcceptsBr(request)) return null;
  const { cache, origKey, origin, waitUntil } = deps;

  const etag = await currentMd5(env, key, cache, origKey, origin, waitUntil);
  if (!etag) return null;

  const headers = new Headers(baseHeaders);
  headers.set("etag", `W/"${etag}"`);
  headers.set("vary", "Accept-Encoding");

  // 中身が変わっていない = 体なしの 304(事前圧縮版を読みに行かない)
  if (etagMatches(request.headers.get("if-none-match"), etag)) {
    return { status: 304, headers, body: null, encodeBody: "automatic" };
  }

  const name = brKey(key, etag);
  const edgeKey = cache && origin ? new Request(origin + BR_CACHE_PREFIX + name) : null;
  let body = null;
  if (edgeKey) {
    const hit = await cache.match(edgeKey);
    if (hit) body = hit.body;
  }
  if (!body) {
    const obj = await env.BUCKET.get(name);
    if (!obj) return null;
    if (edgeKey) {
      // ★エッジへは Content-Encoding なしの素のバイト列として焼く(上の冒頭コメント)
      const stored = new Response(obj.body, {
        headers: { "content-type": "application/octet-stream", "cache-control": BR_EDGE_CACHE },
      });
      const put = cache.put(edgeKey, stored.clone());
      if (waitUntil) waitUntil(put);
      body = stored.body;
    } else {
      body = obj.body;
    }
  }
  headers.set("content-encoding", "br");
  return { status: 200, headers, body, encodeBody: "manual" };
}
