/**
 * 3-state model 用の local-only 管理 UI サーバ。
 *
 * 設計方針:
 *   - 本番サイトは Next.js の `output: "export"` で静的書き出しのため、
 *     server 側ロジックを置く場所が無い。 admin UI は別プロセスとして
 *     localhost で運用し、 公開デプロイには含めない。
 *   - フレームワーク無し (= node:http + 文字列テンプレート)。 admin の規模では
 *     Hono / Express を入れるほうがオーバーヘッド。
 *   - Basic Auth は env (ADMIN_USER / ADMIN_PASS) で。 デフォルト値が無ければ
 *     起動拒否 (= 開発者が事故で公開ポートに上げないよう)。
 *   - 全ての state 変更は POST で受け、 lib/admin-state.ts を通す
 *     (= CLI と同じ transaction / audit logging が走る)。
 *
 * 使い方:
 *   ADMIN_USER=ops ADMIN_PASS=secret npm run admin:server
 *   open http://localhost:8787/admin/excluded
 *
 * 環境変数:
 *   ADMIN_USER, ADMIN_PASS  必須
 *   ADMIN_PORT              省略時 8787
 *   ADMIN_HOST              省略時 127.0.0.1 (= LAN に出さない)
 *
 * 注意:
 *   admin 操作後は静的サイトを再ビルド (`npm run build`) する必要がある。
 *   admin 側で本番サイトの cache invalidation までは行わない。
 */
import "./_env";
import http from "node:http";
import { URL } from "node:url";
import { openDb, type DB } from "./_db";
import {
  countExcluded,
  excludedReasonCounts,
  listAudit,
  listExcluded,
  manualExcludeSeries,
  permanentDelete,
  reinstate,
  type ExcludedRow,
  type AdminAuditRow,
} from "../lib/admin-state";

const PORT = Number(process.env.ADMIN_PORT ?? 8787);
const HOST = process.env.ADMIN_HOST ?? "127.0.0.1";
const USER = process.env.ADMIN_USER ?? "";
const PASS = process.env.ADMIN_PASS ?? "";

if (!USER || !PASS) {
  console.error(
    "[admin-server] ADMIN_USER and ADMIN_PASS must be set in env. refusing to start.",
  );
  process.exit(1);
}

// -------------------------------------------------------------- HTML helpers

function esc(s: string | number | null | undefined): string {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function layout(title: string, body: string, current: string): string {
  return `<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<title>${esc(title)} - MANGAL admin</title>
<style>
  body { font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; margin: 0; background: #0b0c10; color: #e5e7eb; }
  header { background: #111827; padding: 12px 20px; border-bottom: 1px solid #1f2937; display: flex; gap: 16px; align-items: center; }
  header h1 { font-size: 16px; margin: 0; color: #fbbf24; font-weight: 600; }
  header nav a { color: #93c5fd; text-decoration: none; padding: 6px 10px; border-radius: 4px; font-size: 14px; }
  header nav a:hover { background: #1f2937; }
  header nav a.active { background: #1e40af; color: #fff; }
  main { padding: 20px; max-width: 1400px; margin: 0 auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #1f2937; vertical-align: top; }
  th { background: #111827; color: #94a3b8; font-weight: 500; }
  tr:hover { background: #111827; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #1f2937; color: #cbd5e1; font-size: 11px; margin-right: 4px; }
  .pill.adult_rating       { background: #7f1d1d; color: #fee2e2; }
  .pill.adult_imprint      { background: #92400e; color: #fef3c7; }
  .pill.adult_publisher    { background: #92400e; color: #fef3c7; }
  .pill.adult_description  { background: #4338ca; color: #e0e7ff; }
  .pill.manual_admin       { background: #374151; color: #e5e7eb; }
  button { padding: 6px 12px; border-radius: 4px; border: 1px solid #374151; background: #1f2937; color: #e5e7eb; font-size: 13px; cursor: pointer; }
  button:hover { background: #374151; }
  button.danger { background: #7f1d1d; border-color: #991b1b; color: #fee2e2; }
  button.danger:hover { background: #991b1b; }
  button.primary { background: #1e40af; border-color: #1e3a8a; color: #fff; }
  button.primary:hover { background: #1e3a8a; }
  form.inline { display: inline; }
  .filters { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
  .filters a { padding: 4px 10px; border-radius: 999px; background: #1f2937; color: #cbd5e1; text-decoration: none; font-size: 12px; }
  .filters a.active { background: #1e40af; color: #fff; }
  .pager { margin-top: 16px; display: flex; gap: 12px; align-items: center; font-size: 13px; color: #94a3b8; }
  .pager a { color: #93c5fd; text-decoration: none; padding: 4px 10px; background: #1f2937; border-radius: 4px; }
  .signals { color: #94a3b8; font-size: 11px; }
  .meta { color: #94a3b8; font-size: 12px; }
  .stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #111827; padding: 12px 18px; border-radius: 6px; min-width: 120px; }
  .stat .n { font-size: 20px; font-weight: 600; color: #fbbf24; }
  .stat .label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
  pre { background: #111827; padding: 8px; border-radius: 4px; font-size: 11px; overflow-x: auto; max-width: 400px; color: #cbd5e1; }
  .flash { padding: 10px 14px; margin-bottom: 16px; border-radius: 4px; }
  .flash.ok { background: #064e3b; color: #d1fae5; border: 1px solid #047857; }
  .flash.err { background: #7f1d1d; color: #fecaca; border: 1px solid #991b1b; }
</style>
</head>
<body>
<header>
  <h1>MANGAL admin</h1>
  <nav>
    <a href="/admin/excluded" class="${current === "excluded" ? "active" : ""}">Excluded</a>
    <a href="/admin/audit"    class="${current === "audit"    ? "active" : ""}">Audit log</a>
  </nav>
</header>
<main>${body}</main>
</body>
</html>`;
}

function flashFromQuery(url: URL): string {
  const ok = url.searchParams.get("ok");
  const err = url.searchParams.get("err");
  if (ok) return `<div class="flash ok">${esc(ok)}</div>`;
  if (err) return `<div class="flash err">${esc(err)}</div>`;
  return "";
}

// -------------------------------------------------------------- Page: excluded

function pageExcluded(db: DB, url: URL): string {
  const reasonFilter = url.searchParams.get("reason") ?? null;
  const limit = Math.max(
    1,
    Math.min(500, Number(url.searchParams.get("limit") ?? "50")),
  );
  const offset = Math.max(0, Number(url.searchParams.get("offset") ?? "0"));

  const total = countExcluded(db, reasonFilter ?? undefined);
  const reasons = excludedReasonCounts(db);
  const rows = listExcluded(db, {
    limit,
    offset,
    reason: reasonFilter ?? undefined,
  });

  const filterLinks = [
    `<a href="/admin/excluded" class="${reasonFilter === null ? "active" : ""}">all (${reasons.reduce((a, b) => a + b.n, 0)})</a>`,
    ...reasons.map(
      (r) =>
        `<a href="/admin/excluded?reason=${encodeURIComponent(r.reason)}" class="${reasonFilter === r.reason ? "active" : ""}">${esc(r.reason)} (${r.n})</a>`,
    ),
  ].join("");

  const stats = `
    <div class="stats">
      <div class="stat"><div class="n">${total}</div><div class="label">${reasonFilter ? `excluded (${esc(reasonFilter)})` : "total excluded"}</div></div>
      ${reasons
        .slice(0, 4)
        .map(
          (r) =>
            `<div class="stat"><div class="n">${r.n}</div><div class="label">${esc(r.reason)}</div></div>`,
        )
        .join("")}
    </div>`;

  const tableRows = rows
    .map((r: ExcludedRow) => {
      const sigs = r.signalsJson
        ? (JSON.parse(r.signalsJson) as string[])
            .map((s) => `<span class="pill">${esc(s)}</span>`)
            .join("")
        : "";
      const yr = `${r.yearStarted ?? "????"}–${r.yearEnded ?? ""}`;
      return `<tr>
        <td>${r.archiveId}</td>
        <td><span class="pill ${esc(r.reason)}">${esc(r.reason)}</span></td>
        <td>${esc(r.title)}<div class="meta">${esc(r.seriesKey)}</div></td>
        <td>${esc(yr)}</td>
        <td>${esc(r.publisherKey)}</td>
        <td>${r.adultScore}</td>
        <td><div class="signals">${sigs}</div><div class="meta">${esc(r.excludedAt.replace("T", " ").replace("Z", ""))} by ${esc(r.excludedBy)}</div></td>
        <td>
          <form class="inline" method="POST" action="/admin/api/reinstate?id=${r.archiveId}" onsubmit="return confirm('「${esc(r.title)}」を公開に戻します。 よろしいですか?');">
            <button class="primary" type="submit">復帰</button>
          </form>
          <form class="inline" method="POST" action="/admin/api/delete?id=${r.archiveId}" onsubmit="return confirm('「${esc(r.title)}」を完全削除します。 archive にだけ残り、 公開・excluded 双方から消えます。 よろしいですか?');">
            <button class="danger" type="submit">完全削除</button>
          </form>
        </td>
      </tr>`;
    })
    .join("");

  const baseQuery = reasonFilter
    ? `?reason=${encodeURIComponent(reasonFilter)}&limit=${limit}`
    : `?limit=${limit}`;
  const prevOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;
  const prevHref = `/admin/excluded${baseQuery}&offset=${prevOffset}`;
  const nextHref = `/admin/excluded${baseQuery}&offset=${nextOffset}`;

  const body = `
${flashFromQuery(url)}
${stats}
<div class="filters">${filterLinks}</div>
<table>
  <thead>
    <tr>
      <th>arc.id</th>
      <th>reason</th>
      <th>title</th>
      <th>year</th>
      <th>publisher</th>
      <th>score</th>
      <th>signals / excluded</th>
      <th>actions</th>
    </tr>
  </thead>
  <tbody>${tableRows || `<tr><td colspan="8" style="padding: 20px; text-align:center; color:#94a3b8;">なし</td></tr>`}</tbody>
</table>
<div class="pager">
  ${offset > 0 ? `<a href="${prevHref}">← prev</a>` : ""}
  <span>${offset + 1}–${Math.min(offset + limit, total)} / ${total}</span>
  ${nextOffset < total ? `<a href="${nextHref}">next →</a>` : ""}
</div>
`;
  return layout("Excluded series", body, "excluded");
}

// -------------------------------------------------------------- Page: audit

function pageAudit(db: DB, url: URL): string {
  const limit = Math.max(
    1,
    Math.min(500, Number(url.searchParams.get("limit") ?? "100")),
  );
  const offset = Math.max(0, Number(url.searchParams.get("offset") ?? "0"));

  const rows = listAudit(db, { limit, offset });

  const tableRows = rows
    .map((r: AdminAuditRow) => {
      let metaPretty = "";
      if (r.metadataJson) {
        try {
          metaPretty = `<pre>${esc(JSON.stringify(JSON.parse(r.metadataJson), null, 2))}</pre>`;
        } catch {
          metaPretty = `<pre>${esc(r.metadataJson)}</pre>`;
        }
      }
      return `<tr>
        <td>${r.id}</td>
        <td>${esc(r.performedAt.replace("T", " ").replace("Z", ""))}</td>
        <td><span class="pill ${esc(r.action)}">${esc(r.action)}</span></td>
        <td>${esc(r.targetTable)} #${r.targetId}</td>
        <td>${esc(r.performedBy)}</td>
        <td>${esc(r.reason)}</td>
        <td>${metaPretty}</td>
      </tr>`;
    })
    .join("");

  const baseQuery = `?limit=${limit}`;
  const prevOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;
  const prevHref = `/admin/audit${baseQuery}&offset=${prevOffset}`;
  const nextHref = `/admin/audit${baseQuery}&offset=${nextOffset}`;

  const body = `
${flashFromQuery(url)}
<table>
  <thead>
    <tr>
      <th>id</th>
      <th>at</th>
      <th>action</th>
      <th>target</th>
      <th>by</th>
      <th>reason</th>
      <th>metadata</th>
    </tr>
  </thead>
  <tbody>${tableRows || `<tr><td colspan="7" style="padding: 20px; text-align:center; color:#94a3b8;">なし</td></tr>`}</tbody>
</table>
<div class="pager">
  ${offset > 0 ? `<a href="${prevHref}">← prev</a>` : ""}
  <span>showing ${rows.length} from offset ${offset}</span>
  ${rows.length === limit ? `<a href="${nextHref}">next →</a>` : ""}
</div>
`;
  return layout("Audit log", body, "audit");
}

// -------------------------------------------------------------- Auth

function checkBasicAuth(req: http.IncomingMessage): boolean {
  const h = req.headers["authorization"];
  if (!h || !h.startsWith("Basic ")) return false;
  let decoded: string;
  try {
    decoded = Buffer.from(h.slice(6), "base64").toString("utf-8");
  } catch {
    return false;
  }
  const idx = decoded.indexOf(":");
  if (idx < 0) return false;
  const user = decoded.slice(0, idx);
  const pass = decoded.slice(idx + 1);
  // 定数時間比較。 user/pass の長さがバラついても side channel を露出させない。
  return safeEq(user, USER) && safeEq(pass, PASS);
}

function safeEq(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let acc = 0;
  for (let i = 0; i < a.length; i++) acc |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return acc === 0;
}

// -------------------------------------------------------------- Server

function send(
  res: http.ServerResponse,
  status: number,
  body: string,
  type = "text/html; charset=utf-8",
): void {
  res.writeHead(status, { "Content-Type": type });
  res.end(body);
}

function redirect(res: http.ServerResponse, location: string): void {
  res.writeHead(303, { Location: location });
  res.end();
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c as Buffer));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    req.on("error", reject);
  });
}

async function handle(
  db: DB,
  req: http.IncomingMessage,
  res: http.ServerResponse,
): Promise<void> {
  if (!checkBasicAuth(req)) {
    res.writeHead(401, {
      "WWW-Authenticate": 'Basic realm="MANGAL admin"',
      "Content-Type": "text/plain; charset=utf-8",
    });
    res.end("auth required");
    return;
  }

  const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
  const path = url.pathname;

  // GET pages
  if (req.method === "GET") {
    if (path === "/" || path === "/admin" || path === "/admin/")
      return redirect(res, "/admin/excluded");
    if (path === "/admin/excluded") return send(res, 200, pageExcluded(db, url));
    if (path === "/admin/audit") return send(res, 200, pageAudit(db, url));
    return send(res, 404, "<h1>not found</h1>");
  }

  // POST actions
  if (req.method === "POST") {
    const id = Number(url.searchParams.get("id") ?? "");
    const sid = Number(url.searchParams.get("seriesId") ?? "");
    // body 解析 (= reason 入力等)。 form-urlencoded のみサポート。
    let bodyParams = new URLSearchParams();
    if ((req.headers["content-type"] ?? "").includes("urlencoded")) {
      bodyParams = new URLSearchParams(await readBody(req));
    }
    const reason = bodyParams.get("reason") ?? null;
    const performedBy = USER;

    try {
      if (path === "/admin/api/reinstate") {
        const r = reinstate(db, id, {
          performedBy,
          reason: reason ?? undefined,
        });
        return redirect(
          res,
          `/admin/excluded?ok=${encodeURIComponent(`復帰しました (archive#${r.archiveId} → series#${r.seriesId}${r.created ? " new" : ""}). 巻情報を埋めるには fetch:madb を再実行してください。`)}`,
        );
      }
      if (path === "/admin/api/delete") {
        const r = permanentDelete(db, id, {
          performedBy,
          reason: reason ?? undefined,
        });
        return redirect(
          res,
          `/admin/excluded?ok=${encodeURIComponent(`完全削除しました (archive#${r.archiveId}, deleted series#${r.deletedSeriesId ?? "none"})`)}`,
        );
      }
      if (path === "/admin/api/exclude-series") {
        const r = manualExcludeSeries(db, sid, {
          performedBy,
          reason: reason ?? undefined,
        });
        return redirect(
          res,
          `/admin/excluded?ok=${encodeURIComponent(`手動除外しました (archive#${r.archiveId})`)}`,
        );
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return redirect(
        res,
        `/admin/excluded?err=${encodeURIComponent(`error: ${msg}`)}`,
      );
    }

    return send(res, 404, "<h1>not found</h1>");
  }

  return send(res, 405, "<h1>method not allowed</h1>");
}

function main(): void {
  const db = openDb();
  const server = http.createServer((req, res) => {
    handle(db, req, res).catch((e) => {
      console.error("[admin-server]", e);
      try {
        send(res, 500, "internal error", "text/plain; charset=utf-8");
      } catch {
        // ignore
      }
    });
  });
  server.listen(PORT, HOST, () => {
    console.log(
      `[admin-server] listening on http://${HOST}:${PORT}/admin/excluded`,
    );
    console.log(`[admin-server] Basic Auth user=${USER} (pass set via env)`);
  });
}

main();
