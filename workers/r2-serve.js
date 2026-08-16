import { EmailMessage } from "cloudflare:email";
/**
 * MANGAL R2配信 Worker(★本番稼働中 mangal-db.com。 デプロイ= wrangler deploy -c wrangler-r2.jsonc)。
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

// ★HTML は「常に最新」(2026-08-01 実害を受けて是正)。
//   旧: max-age=300 + stale-while-revalidate=604800(7日)。SWRは【古いのを返しながら裏で更新】
//   する指定なので、デプロイしても★必ず1回は古い画面が出る★。実際 2026-08-01 に性能改修が
//   7時間ユーザに届かず、「直っていない」と誤判断して存在しない原因を探す事故になった。
//   新: stale-while-revalidate を撤去し、ブラウザ側は60秒だけ保持。
//   ★max-age=0(毎回再検証)にはしない: 実測で HTML 応答に ETag が付いておらず
//     (下の conditional304 が当てにできない)、毎ナビゲーションで183KBを再取得してしまう。
//     60秒なら「デプロイ後すぐ最新」と「連続操作で再取得しない」を両立できる。
//   ★コスト方針は不変: s-maxage=86400 でエッジが受け止めるので R2 読込(Class B)は増えない。
//   デプロイ時は /api/purge でエッジを明示的に失効させるため、purge後の初回で最新に入れ替わる。
const HTML_CACHE = "public, max-age=60, s-maxage=86400";
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

    // ★正規URL301(SEO正準化。2026-07-04 workers.dev→2026-08-17 www/httpにも拡張):
    //   全入口(workers.dev / www.mangal-db.com / http)を https://mangal-db.com へ**1回の301**で一本化。
    //   canonicalタグはヒント・301は指示。ホストは明示列挙=wrangler dev(localhost)を巻き込まない。
    //   /api/は除外(ツール互換)
    if (
      (url.hostname.endsWith("workers.dev") ||
        url.hostname === "www.mangal-db.com" ||
        (url.hostname === "mangal-db.com" && url.protocol !== "https:")) &&
      !url.pathname.startsWith("/api/")
    ) {
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

    // (旧/go 302中継と/go-test実験頁は2026-07-29撤去: App Links奪取は最終URLパスで決まり
    //  中継無関係と実機確定→ボタンは/dp直リンク化で中継不要に。経緯=記憶kindle-link-browser-not-app)
    // ★いいねAPI(匿名カウンタ・PIIゼロ。 KV=LIKES)。 静的配信より前・キャッシュしない。
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

    // ① alias 301。 env.REDIRECTS = KV(key "redirects.json" = {"/manga/旧": "/manga/新"})。
    //    投入= scripts/_kv-redirects-sync.py(2026-08-14 リダイレクト層復旧)。末尾スラッシュも許容。
    if (env.REDIRECTS) {
      const r = await getRedirects(env);
      const to = r[url.pathname] || r[url.pathname.replace(/\/+$/, "")];
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

// ★6h TTLで再読込(週次のKV更新をデプロイ無しでも拾う。KV読込は isolate×6hに1回=コスト微少)
let _redirects = null;
let _redirectsAt = 0;
async function getRedirects(env) {
  if (_redirects && Date.now() - _redirectsAt < 6 * 3600 * 1000) return _redirects;
  try {
    _redirects = JSON.parse(await env.REDIRECTS.get("redirects.json")) || {};
    _redirectsAt = Date.now();
  } catch { _redirects = _redirects || {}; _redirectsAt = Date.now(); }
  return _redirects;
}
let _adultUs = null;
async function getAdultUsSlugs(env) {
  if (_adultUs) return _adultUs;
  try { _adultUs = new Set(JSON.parse(await env.ADULT_US_SLUGS.get("adult-us-slugs.json")) || []); }
  catch { _adultUs = new Set(); }
  return _adultUs;
}
