import { EmailMessage } from "cloudflare:email";
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
// ★索引JSON(2026-07-27 会議決定): 同名のまま週次更新するため immutable 不可。
//   ブラウザ4h(週次サイクルに十分)+期限切れ後は If-None-Match 再検証(下の304対応)で
//   本体転送ゼロ。22MBの一覧索引が「再取得しても304の数十バイト」になる。
const JSON_CACHE = "public, max-age=14400, s-maxage=86400, stale-while-revalidate=86400";

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
  if (key.endsWith(".json")) return JSON_CACHE;
  return ASSET;
}

/** ETag条件付き要求 → 304(本体転送なし)。エッジ/R2どちらの応答にも適用。 */
function conditional304(request, res) {
  const inm = request.headers.get("if-none-match");
  const etag = res.headers.get("etag");
  if (!inm || !etag) return res;
  // W/弱ETag・複数候補("a", "b")も許容する素朴比較
  if (inm.split(",").map((s) => s.trim().replace(/^W\//, "")).includes(etag.replace(/^W\//, ""))) {
    const h = new Headers();
    for (const k of ["etag", "cache-control", "content-type"]) {
      const v = res.headers.get(k);
      if (v) h.set(k, v);
    }
    return new Response(null, { status: 304, headers: h });
  }
  return res;
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

    // ★正規ドメイン301(SEO重複対策 2026-07-04): workers.devアクセスは mangal-db.com へ。/api/は除外(ツール互換)
    if (url.hostname.endsWith("workers.dev") && !url.pathname.startsWith("/api/")) {
      return Response.redirect("https://mangal-db.com" + url.pathname + url.search, 301);
    }

    // ★API共通CORS(previewサイト=別オリジンからも叩けるように)
    const CORS = {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "content-type",
    };
    if (url.pathname.startsWith("/api/") && request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ★いいねAPI(匿名カウンタ・PIIゼロ。 KV=LIKES)。 静的配信より前・キャッシュしない。
    // ★/go = Kindle等のブラウザ中継(2026-07-07 本実装): Amazonアプリ(IAP規約でKindle購入不可)への
    //   App Links/Universal Links発火を避けるため、自ドメインの中間ページからJSで遷移させる。
    //   オープンリダイレクタ防止: amazon.co.jp / amzn.to のみ許可。
    if (url.pathname === "/go") {
      let dest = "";
      try { dest = decodeURIComponent(url.searchParams.get("u") || ""); } catch {}
      let ok = false;
      try {
        const h = new URL(dest).hostname;
        ok = h === "www.amazon.co.jp" || h === "amazon.co.jp" || h === "amzn.to";
      } catch {}
      if (!ok) return new Response("bad destination", { status: 400 });
      const esc = dest.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
      const html = `<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>ストアへ移動中… | MANGAL</title>
<style>body{font-family:sans-serif;display:flex;min-height:80vh;align-items:center;justify-content:center;color:#444}</style>
</head><body><p>ストアへ移動しています…<br><a href="${esc}" rel="nofollow sponsored noopener">開かない場合はこちら</a></p>
<script>setTimeout(function(){ location.replace(${JSON.stringify(dest)}); }, 60);</script>
</body></html>`;
      return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
    }
    if (url.pathname === "/api/like" && env.LIKES) {
      if (request.method === "GET") {
        const id = url.searchParams.get("id") || "";
        const v = id ? parseInt((await env.LIKES.get(`like:${id}`)) || "0", 10) : 0;
        return new Response(JSON.stringify({ id, count: v }), {
          headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS },
        });
      }
      if (request.method === "POST") {
        let id = "";
        try { id = String((await request.json()).id || ""); } catch {}
        if (!id || id.length > 80) return new Response("bad request", { status: 400 });
        const key = `like:${id}`;
        const v = parseInt((await env.LIKES.get(key)) || "0", 10) + 1;
        await env.LIKES.put(key, String(v));
        return new Response(JSON.stringify({ id, count: v }), {
          headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS },
        });
      }
      return new Response("Method Not Allowed", { status: 405 });
    }

    // ★edge cache purge(差分反映エンジン用 2026-07-04。 PURGE_TOKEN認証・対象パスのみ)
    if (url.pathname === "/api/purge" && request.method === "POST") {
      let d = {};
      try { d = await request.json(); } catch {}
      if (!env.PURGE_TOKEN || d.token !== env.PURGE_TOKEN) {
        return new Response("forbidden", { status: 403 });
      }
      const paths = Array.isArray(d.paths) ? d.paths.slice(0, 500) : [];
      const cache = caches.default;
      let purged = 0;
      for (const p of paths) {
        const u = new URL(String(p), url.origin);
        if (await cache.delete(new Request(u.toString()))) purged++;
        // trailing slash / index variant も念のため
        if (await cache.delete(new Request(u.toString() + "/"))) purged++;
      }
      return new Response(JSON.stringify({ ok: true, purged, requested: paths.length }), {
        headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS },
      });
    }

    // ★お問い合わせ(受信箱=KV。 送信先メールはコードに置かない=非公開。 将来Email Routing転送)
    if (url.pathname === "/api/contact" && env.CONTACT && request.method === "POST") {
      let d = {};
      try { d = await request.json(); } catch {}
      const body = String(d.body || "").slice(0, 4000);
      if (!body.trim()) return new Response("bad request", { status: 400 });
      const rec = {
        name: String(d.name || "").slice(0, 80),
        email: String(d.email || "").slice(0, 120),
        body,
        at: new Date().toISOString(),
        country: request.headers.get("CF-IPCountry") || "",
      };
      const key = `contact:${rec.at}:${Math.random().toString(36).slice(2, 8)}`;
      await env.CONTACT.put(key, JSON.stringify(rec));
      // ★Gmail転送(2026-07-05 Email Routing): MAILER binding がある時だけ・失敗してもKV保存は成功扱い
      if (env.MAILER) {
        try {
          const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
          const subj = `=?utf-8?B?${b64("【MANGAL】お問い合わせ " + rec.at.slice(0, 16))}?=`;
          const bodyText = `名前: ${rec.name || "(名無し)"}
メール: ${rec.email || "(無し)"}
国: ${rec.country}
受信: ${rec.at}
KVキー: ${key}

--- 本文 ---
${rec.body}`;
          const raw = [
            `From: MANGAL <contact@mangal-db.com>`,
            `To: <${env.MAIL_TO}>`,
            `Subject: ${subj}`,
            `MIME-Version: 1.0`,
            `Content-Type: text/plain; charset=utf-8`,
            `Content-Transfer-Encoding: base64`,
            ``,
            b64(bodyText),
          ].join("\r\n");
          await env.MAILER.send(new EmailMessage("contact@mangal-db.com", env.MAIL_TO, raw));
        } catch (e) { console.error("MAIL_FAIL", (e && e.message) || String(e)); }
      }
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS },
      });
    }

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
    if (res) return conditional304(request, res);

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
    return conditional304(request, res);
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
