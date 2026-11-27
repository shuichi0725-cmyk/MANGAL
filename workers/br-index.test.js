import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { BR_KEYS, BR_CACHE_PREFIX, brKey, clientAcceptsBr, etagMatches, md5FromEtag, planBrIndex } from "./br-index.js";

// 索引の事前圧縮版(workers/br-index.js)の判定。 R2 は入れ物だけ真似る(head / get が呼ばれたキーも記録する)。
const MD5 = "cf99dd0c9bc012f226e8c58be46751b8";
const KEY = "manga-list-cols.v1.json";

function bucket(objects) {
  const calls = [];
  return {
    calls,
    async head(key) {
      calls.push(`head:${key}`);
      return key in objects ? { etag: objects[key].etag } : null;
    },
    async get(key) {
      calls.push(`get:${key}`);
      return key in objects ? { body: objects[key].body, etag: objects[key].etag } : null;
    },
  };
}

/** 本番の形の要求(request.cf が在る)。 ae = 訪問者の元の Accept-Encoding / header = Cloudflare が書き換えた後の値 */
function req(path, { ae, header = "gzip, br", method = "GET", inm, cf = true } = {}) {
  const headers = new Headers();
  if (header !== null) headers.set("accept-encoding", header);
  if (inm) headers.set("if-none-match", inm);
  const r = new Request("https://mangal-db.com/" + path, { method, headers });
  if (cf) Object.defineProperty(r, "cf", { value: { clientAcceptEncoding: ae } });
  return r;
}

const base = () => new Headers({ "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=0, must-revalidate" });
const full = () => ({ [KEY]: { etag: MD5, body: "RAW" }, [brKey(KEY, MD5)]: { etag: "x", body: "BR-BYTES" } });

describe("索引の事前圧縮版: 対象と名前", () => {
  it("対象は索引5本・scripts/_index_br.py の BR_SOURCES と同じ(片方だけ足す結線漏れを防ぐ)", () => {
    expect([...BR_KEYS].sort()).toEqual(
      ["data/compass-hidden.v1.json", "manga-alt-index.json", "manga-catch-index.json", "manga-catch.v1.json", "manga-list-cols.v1.json"].sort(),
    );
    const py = readFileSync(new URL("../scripts/_index_br.py", import.meta.url), "utf-8");
    const block = /BR_SOURCES = \{([\s\S]*?)\n\}/.exec(py)[1];
    const keys = [...block.matchAll(/^\s*"([^"]+)":/gm)].map((m) => m[1]);
    expect(keys.sort()).toEqual([...BR_KEYS].sort());
  });
  it("ETag から MD5 を取り出す", () => {
    expect(md5FromEtag(`"${MD5}"`)).toBe(MD5);
    expect(md5FromEtag(`W/"${MD5}"`)).toBe(MD5);
    expect(md5FromEtag(MD5)).toBe(MD5);
    expect(md5FromEtag(`"${MD5}-3"`)).toBeNull();
    expect(md5FromEtag(null)).toBeNull();
  });
  it("事前圧縮版の名前 = 元のキー + 元の中身のMD5 + .br", () => {
    expect(brKey(KEY, MD5)).toBe(`manga-list-cols.v1.json.${MD5}.br`);
    expect(brKey("data/compass-hidden.v1.json", MD5)).toBe(`data/compass-hidden.v1.json.${MD5}.br`);
  });
});

describe("訪問者が br を受け取れるか", () => {
  it("本番(request.cf が在る)は、書き換え前の値(clientAcceptEncoding)だけで決める", () => {
    expect(clientAcceptsBr(req(KEY, { ae: "gzip, deflate, br, zstd" }))).toBe(true);
    expect(clientAcceptsBr(req(KEY, { ae: "br" }))).toBe(true);
    // 訪問者は gzip だけ・Cloudflare が書き換えた後のヘッダーには br が在る → 受け取れない扱い
    expect(clientAcceptsBr(req(KEY, { ae: "gzip, deflate", header: "gzip, br" }))).toBe(false);
    // 素の curl 等(Accept-Encoding を送らない)= 元の値が空・無い → 受け取れない扱い
    expect(clientAcceptsBr(req(KEY, { ae: "", header: "gzip, br" }))).toBe(false);
    expect(clientAcceptsBr(req(KEY, { ae: undefined, header: "gzip, br" }))).toBe(false);
  });
  it("br;q=0 は拒否・br;q=0.5 は可・brotli 等の別の語には当たらない", () => {
    expect(clientAcceptsBr(req(KEY, { ae: "gzip, br;q=0" }))).toBe(false);
    expect(clientAcceptsBr(req(KEY, { ae: "gzip;q=1.0, br;q=0.5" }))).toBe(true);
    expect(clientAcceptsBr(req(KEY, { ae: "gzip, brotli, xbr" }))).toBe(false);
    expect(clientAcceptsBr(req(KEY, { ae: "GZIP, BR" }))).toBe(true);
  });
  it("request.cf が無い所(手元の試験)はヘッダーを見る", () => {
    expect(clientAcceptsBr(req(KEY, { cf: false, header: "gzip, br" }))).toBe(true);
    expect(clientAcceptsBr(req(KEY, { cf: false, header: "gzip" }))).toBe(false);
    expect(clientAcceptsBr(req(KEY, { cf: false, header: null }))).toBe(false);
  });
});

describe("If-None-Match の照合", () => {
  it("強い形・弱い形・複数候補を受ける", () => {
    expect(etagMatches(`"${MD5}"`, MD5)).toBe(true);
    expect(etagMatches(`W/"${MD5}"`, MD5)).toBe(true);
    expect(etagMatches(`"old", W/"${MD5}"`, MD5)).toBe(true);
    expect(etagMatches(`"old"`, MD5)).toBe(false);
    expect(etagMatches(null, MD5)).toBe(false);
    expect(etagMatches("", MD5)).toBe(false);
  });
});

describe("事前圧縮版でどう応えるか(planBrIndex)", () => {
  it("事前圧縮版が在る → 圧縮済みのまま返す(Content-Encoding: br・encodeBody manual・ETag は元のMD5の弱い形)", async () => {
    const b = bucket(full());
    const plan = await planBrIndex(req(KEY, { ae: "gzip, deflate, br, zstd" }), { BUCKET: b }, KEY, base());
    expect(plan).not.toBeNull();
    expect(plan.status).toBe(200);
    expect(plan.body).toBe("BR-BYTES");
    expect(plan.encodeBody).toBe("manual");
    expect(plan.headers.get("content-encoding")).toBe("br");
    expect(plan.headers.get("etag")).toBe(`W/"${MD5}"`);
    expect(plan.headers.get("vary")).toBe("Accept-Encoding");
    expect(plan.headers.get("cache-control")).toBe("public, max-age=0, must-revalidate");
    expect(plan.headers.get("content-type")).toBe("application/json; charset=utf-8");
    expect(b.calls).toEqual([`head:${KEY}`, `get:${brKey(KEY, MD5)}`]);
  });

  it("中身が変わっていない(If-None-Match 一致)→ 体なしの 304・事前圧縮版は読みに行かない", async () => {
    for (const inm of [`W/"${MD5}"`, `"${MD5}"`]) {
      const b = bucket(full());
      const plan = await planBrIndex(req(KEY, { ae: "br", inm }), { BUCKET: b }, KEY, base());
      expect(plan.status).toBe(304);
      expect(plan.body).toBeNull();
      expect(plan.headers.get("content-encoding")).toBeNull();
      expect(plan.headers.get("etag")).toBe(`W/"${MD5}"`);
      expect(b.calls).toEqual([`head:${KEY}`]);
    }
  });

  it("中身が変わった(If-None-Match 不一致)→ 新しい事前圧縮版を丸ごと返す", async () => {
    const b = bucket(full());
    const plan = await planBrIndex(req(KEY, { ae: "br", inm: 'W/"00000000000000000000000000000000"' }), { BUCKET: b }, KEY, base());
    expect(plan.status).toBe(200);
    expect(plan.body).toBe("BR-BYTES");
  });

  it("HEAD は従来の経路へ(null・R2 に触らない)", async () => {
    const env = { BUCKET: bucket(full()) };
    expect(await planBrIndex(req(KEY, { ae: "br", method: "HEAD" }), env, KEY, base())).toBeNull();
    expect(env.BUCKET.calls).toEqual([]);
  });

  it("従来の経路へ戻す(null): 対象外のキー・br を受け取れない・GET/HEAD 以外", async () => {
    const env = { BUCKET: bucket(full()) };
    expect(await planBrIndex(req("manga-list-index.json", { ae: "br" }), env, "manga-list-index.json", base())).toBeNull();
    expect(await planBrIndex(req("browse.html", { ae: "br" }), env, "browse.html", base())).toBeNull();
    expect(await planBrIndex(req(KEY, { ae: "gzip, deflate" }), env, KEY, base())).toBeNull();
    expect(await planBrIndex(req(KEY, { ae: "" }), env, KEY, base())).toBeNull();
    expect(await planBrIndex(req(KEY, { ae: "br", method: "POST" }), env, KEY, base())).toBeNull();
    expect(env.BUCKET.calls).toEqual([]); // どれも R2 に触る前に戻る
  });

  it("従来の経路へ戻す(null): 元が無い・元の ETag が MD5 の形でない(分割アップロード)", async () => {
    expect(await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: bucket({}) }, KEY, base())).toBeNull();
    const multi = { [KEY]: { etag: `${MD5}-3`, body: "RAW" }, [brKey(KEY, `${MD5}-3`)]: { etag: "x", body: "BR" } };
    expect(await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: bucket(multi) }, KEY, base())).toBeNull();
  });

  it("従来の経路へ戻す(null): 事前圧縮版が無い・元だけ新しくなって名前が合わない(古い版しか無い)", async () => {
    const none = { [KEY]: { etag: MD5, body: "RAW" } };
    expect(await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: bucket(none) }, KEY, base())).toBeNull();
    // 元は新しい中身(MD5 が別)・R2 に在るのは前の中身の事前圧縮版だけ → 使わない(古い索引を返さない)
    const NEW = "11111111111111111111111111111111";
    const stale = { [KEY]: { etag: NEW, body: "RAW-NEW" }, [brKey(KEY, MD5)]: { etag: "x", body: "BR-OLD" } };
    const b = bucket(stale);
    expect(await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: b }, KEY, base())).toBeNull();
    expect(b.calls).toEqual([`head:${KEY}`, `get:${brKey(KEY, NEW)}`]);
  });

  it("呼び手のヘッダーを書き換えない(戻り値は写し)", async () => {
    const h = base();
    await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: bucket(full()) }, KEY, h);
    expect(h.get("content-encoding")).toBeNull();
    expect(h.get("etag")).toBeNull();
  });
});

// エッジ(caches.default)の真似。 キーは URL 文字列
function edge(init = {}) {
  const store = new Map(Object.entries(init));
  const calls = [];
  return {
    store,
    calls,
    async match(r) {
      const k = typeof r === "string" ? r : r.url;
      calls.push(`match:${k}`);
      const v = store.get(k);
      return v ? v.clone() : undefined;
    },
    async put(r, res) {
      const k = typeof r === "string" ? r : r.url;
      calls.push(`put:${k}`);
      store.set(k, new Response(await res.arrayBuffer(), { headers: res.headers }));
    },
  };
}
const ORIGIN = "https://mangal-db.com";
const deps = (cache, waits = []) => ({ cache, origKey: new Request(`${ORIGIN}/${KEY}`), origin: ORIGIN, waitUntil: (p) => waits.push(p) });
const bytes = (s) => new TextEncoder().encode(s);

describe("エッジを使う(本番の形): 定常では R2 に当てない", () => {
  it("元がエッジに在る → その ETag で決める・事前圧縮版は R2 から読んでエッジに素のバイト列で焼く → 次は R2 に当てない", async () => {
    const cache = edge({ [`${ORIGIN}/${KEY}`]: new Response("RAW", { headers: { etag: `"${MD5}"` } }) });
    const b = bucket({ [KEY]: { etag: MD5, body: "RAW" }, [brKey(KEY, MD5)]: { etag: "x", body: bytes("BR-BYTES") } });
    const waits = [];
    const p1 = await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: b }, KEY, base(), deps(cache, waits));
    expect(await new Response(p1.body).text()).toBe("BR-BYTES");
    await Promise.all(waits);
    expect(b.calls).toEqual([`get:${brKey(KEY, MD5)}`]); // 元の head はしない
    const stored = cache.store.get(`${ORIGIN}${BR_CACHE_PREFIX}${brKey(KEY, MD5)}`);
    expect(stored.headers.get("content-encoding")).toBeNull(); // ★焼く時は圧縮の印を付けない
    expect(stored.headers.get("cache-control")).toContain("immutable");

    const p2 = await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: b }, KEY, base(), deps(cache));
    expect(await new Response(p2.body).text()).toBe("BR-BYTES");
    expect(p2.headers.get("content-encoding")).toBe("br");
    expect(p2.encodeBody).toBe("manual");
    expect(b.calls).toEqual([`get:${brKey(KEY, MD5)}`]); // 2回目は R2 ゼロ
  });

  it("元がエッジに無い → R2 の head を60秒控える(次は head しない)", async () => {
    const cache = edge();
    const b = bucket({ [KEY]: { etag: MD5, body: "RAW" }, [brKey(KEY, MD5)]: { etag: "x", body: bytes("BR") } });
    const waits = [];
    await planBrIndex(req(KEY, { ae: "br", inm: `W/"${MD5}"` }), { BUCKET: b }, KEY, base(), deps(cache, waits));
    await Promise.all(waits);
    const memo = cache.store.get(`${ORIGIN}${BR_CACHE_PREFIX}etag/${KEY}`);
    expect(await memo.clone().text()).toBe(MD5);
    expect(memo.headers.get("cache-control")).toBe("public, max-age=60");
    const plan = await planBrIndex(req(KEY, { ae: "br", inm: `W/"${MD5}"` }), { BUCKET: b }, KEY, base(), deps(cache));
    expect(plan.status).toBe(304);
    expect(b.calls).toEqual([`head:${KEY}`]); // head は1回だけ
  });

  it("元が新しくなった(エッジの元の ETag が変わった)→ 古い事前圧縮版がエッジに在っても使わない", async () => {
    const NEW = "11111111111111111111111111111111";
    const cache = edge({
      [`${ORIGIN}/${KEY}`]: new Response("RAW-NEW", { headers: { etag: `"${NEW}"` } }),
      [`${ORIGIN}${BR_CACHE_PREFIX}${brKey(KEY, MD5)}`]: new Response("BR-OLD"),
    });
    const b = bucket({ [KEY]: { etag: NEW, body: "RAW-NEW" } });
    expect(await planBrIndex(req(KEY, { ae: "br" }), { BUCKET: b }, KEY, base(), deps(cache))).toBeNull();
  });
});
