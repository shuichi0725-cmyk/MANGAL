/**
 * MANGAL R2配信 Worker(★ドラフト・未デプロイ。 R2移行時に使う)。
 *
 * 背景: 69k頁≈14万ファイルが Workers Static Assets / Pages のファイル数上限超え
 *   → アセットを R2(オブジェクトストレージ・ファイル数無制限・egress無料)から配信。
 *   Worker が前段に立ち、 ①R2 fetch ②エッジキャッシュ ③_redirects(301) ④geo(adult_us) を担う。
 *
 * デプロイ前提(ユーザのCloudflareアカウント側で要設定):
 *   - R2バケット作成 + wrangler の r2_buckets バインディング(下記 wrangler-r2.jsonc)
 *   - `out/` を R2 にアップロード(scripts/_r2-upload.mjs = ハッシュ差分)
 *   - env: REDIRECTS(KVに_redirects) or アセットとして同梱、 ADULT_US_SLUGS(geo用・任意)
 *
 * ★コスト最適化(Gemini/ユーザ確認の要点を反映):
 *   - Cache-Control を必ず付ける(ハッシュ付き不変アセット=immutable長期 / HTML=短期+再検証)
 *   - caches.default で **キャッシュヒットは R2 に当てない**(=アクセス数≠R2読込=Class B節約)
 *   - 本番は r2.dev 直URLを使わない(必ずこのWorker経由=キャッシュ+egress無料)
 */

const HTML_CACHE = "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800";
const IMMUTABLE = "public, max-age=31536000, immutable"; // /_next/static 等ハッシュ付き
const ASSET = "public, max-age=86400, s-maxage=604800";

function contentType(key) {
  if (key.endsWith(".html")) return "text/html; charset=utf-8";
  if (key.endsWith(".json")) return "application/json; charset=utf-8";
  if (key.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (key.endsWith(".css")) return "text/css; charset=utf-8";
  if (key.endsWith(".svg")) return "image/svg+xml";
  if (key.endsWith(".webp")) return "image/webp";
  if (key.endsWith(".png")) return "image/png";
  if (key.endsWith(".woff2")) return "font/woff2";
  if (key.endsWith(".xml")) return "application/xml; charset=utf-8";
  if (key.endsWith(".txt")) return "text/plain; charset=utf-8";
  return "application/octet-stream";
}

function cacheControl(key) {
  if (key.startsWith("_next/static/") || key.includes("/_next/static/")) return IMMUTABLE;
  if (key.endsWith(".html")) return HTML_CACHE;
  return ASSET;
}

/** request path → R2 オブジェクトキー(next export 構造)。 末尾/や拡張子なし→ .html / index.html。 */
function pathToKey(pathname) {
  let p = decodeURIComponent(pathname).replace(/^\/+/, "");
  if (p === "" ) return "index.html";
  if (p.endsWith("/")) return p + "index.html";
  // 既に拡張子あり(アセット)はそのまま
  if (/\.[a-z0-9]+$/i.test(p)) return p;
  // 拡張子なし=ページ: next export は <path>.html を出す(trailingSlash:false 前提)
  return p + ".html";
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    // ① _redirects(alias 301)。 env.REDIRECTS = {from: to} のJSON(KV or アセット)。
    if (env.REDIRECTS) {
      const r = await getRedirects(env);
      const to = r[url.pathname];
      if (to) return Response.redirect(new URL(to, url.origin).toString(), 301);
    }

    // ② エッジキャッシュ参照(ヒットなら R2 に当てない=Class B節約)
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    let res = await cache.match(cacheKey);
    if (res) return res;

    // ③ R2 から取得
    const key = pathToKey(url.pathname);
    let obj = await env.BUCKET.get(key);
    if (!obj && !key.endsWith(".html") && !/\.[a-z0-9]+$/i.test(key)) {
      obj = await env.BUCKET.get(key + "/index.html");
    }
    if (!obj) {
      const nf = await env.BUCKET.get("404.html");
      return new Response(nf ? nf.body : "Not Found", {
        status: 404, headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

    const headers = new Headers();
    headers.set("content-type", contentType(key));
    headers.set("cache-control", cacheControl(key));
    if (obj.httpEtag) headers.set("etag", obj.httpEtag);

    // ④ geo(adult_us): 非日本かつ adult_us ページは出さない(将来。 ADULT_US_SLUGS 必要)。
    //    ※adult(日本基準18禁)は本番に存在しない(別レイヤで除外済み)。これは米基準のみ。
    const country = request.headers.get("CF-IPCountry") || "JP";
    if (env.ADULT_US_SLUGS && country !== "JP" && key.endsWith(".html")) {
      const slug = key.replace(/^manga\//, "").replace(/\.html$/, "");
      const set = await getAdultUsSlugs(env);
      if (set.has(slug)) {
        return new Response("This title is not available in your region.", {
          status: 451, headers: { "content-type": "text/plain; charset=utf-8" },
        });
      }
    }

    res = new Response(obj.body, { headers });
    ctx.waitUntil(cache.put(cacheKey, res.clone())); // エッジに焼く
    return res;
  },
};

let _redirects = null;
async function getRedirects(env) {
  if (_redirects) return _redirects;
  try { _redirects = JSON.parse(await env.REDIRECTS.get("redirects.json")) || {}; }
  catch { _redirects = {}; }
  return _redirects;
}
let _adultUs = null;
async function getAdultUsSlugs(env) {
  if (_adultUs) return _adultUs;
  try { _adultUs = new Set(JSON.parse(await env.ADULT_US_SLUGS.get("adult-us-slugs.json")) || []); }
  catch { _adultUs = new Set(); }
  return _adultUs;
}
