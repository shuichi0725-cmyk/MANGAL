/**
 * 3-state model (live/excluded/archive) の admin 操作 CLI。
 *
 * 使い方:
 *   npm run admin:state list-excluded                              # 一覧 (= 最新 50 件)
 *   npm run admin:state list-excluded --reason adult_imprint
 *   npm run admin:state list-excluded --limit 200
 *   npm run admin:state counts                                       # reason 別件数
 *   npm run admin:state reinstate --archive-id 123 --by ops --reason "誤検出"
 *   npm run admin:state delete --archive-id 123 --by ops --reason "確実に成人向け"
 *   npm run admin:state exclude-series --series-id 456 --by ops --reason "重複"
 *   npm run admin:state audit                                        # 監査ログ最新 50 件
 *
 * UI が無い段階での運用 / smoke test 用。 P5 で /admin/excluded UI が整ったら
 * UI 経由がメインになるが、 復帰後の fetch:madb 起動などは CLI から。
 */
import "./_env";
import { openDb } from "./_db";
import {
  countExcluded,
  excludedReasonCounts,
  listAudit,
  listExcluded,
  manualExcludeSeries,
  permanentDelete,
  reinstate,
} from "../lib/admin-state";

type Args = {
  cmd: string | null;
  archiveId: number | null;
  seriesId: number | null;
  by: string;
  reason: string | null;
  limit: number | null;
  offset: number | null;
  reasonFilter: string | null;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    cmd: argv[0] ?? null,
    archiveId: null,
    seriesId: null,
    by: "cli",
    reason: null,
    limit: null,
    offset: null,
    reasonFilter: null,
  };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--archive-id" && next) {
      out.archiveId = Number(next);
      i++;
    } else if (a === "--series-id" && next) {
      out.seriesId = Number(next);
      i++;
    } else if (a === "--by" && next) {
      out.by = next;
      i++;
    } else if (a === "--reason" && next) {
      // list-excluded の --reason は filter、 それ以外の --reason は audit reason
      out.reason = next;
      out.reasonFilter = next;
      i++;
    } else if (a === "--limit" && next) {
      out.limit = Number(next);
      i++;
    } else if (a === "--offset" && next) {
      out.offset = Number(next);
      i++;
    }
  }
  return out;
}

function pad(s: string | number | null | undefined, n: number): string {
  const v = s === null || s === undefined ? "" : String(s);
  return v.length >= n ? v.slice(0, n) : v + " ".repeat(n - v.length);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const db = openDb();

  switch (args.cmd) {
    case "list-excluded": {
      const total = countExcluded(db, args.reasonFilter ?? undefined);
      const rows = listExcluded(db, {
        limit: args.limit ?? 50,
        offset: args.offset ?? 0,
        reason: args.reasonFilter ?? undefined,
      });
      console.log(
        `[excluded] total=${total} ${args.reasonFilter ? `(reason=${args.reasonFilter})` : ""}`,
      );
      console.log(
        `${pad("arcId", 6)} ${pad("score", 6)} ${pad("reason", 18)} ${pad("year", 11)} ${pad("title", 36)} signals`,
      );
      for (const r of rows) {
        const yr = `${r.yearStarted ?? "????"}-${r.yearEnded ?? ""}`;
        const sig = r.signalsJson ? JSON.parse(r.signalsJson).join(",") : "";
        console.log(
          `${pad(r.archiveId, 6)} ${pad(r.adultScore, 6)} ${pad(r.reason, 18)} ${pad(yr, 11)} ${pad(r.title, 36)} ${sig}`,
        );
      }
      break;
    }

    case "counts": {
      const counts = excludedReasonCounts(db);
      console.log("[excluded counts by reason]");
      for (const c of counts) {
        console.log(`  ${pad(c.reason, 24)} ${c.n}`);
      }
      console.log(`  ${pad("total", 24)} ${countExcluded(db)}`);
      break;
    }

    case "reinstate": {
      if (args.archiveId === null) {
        console.error("require --archive-id");
        process.exit(1);
      }
      const result = reinstate(db, args.archiveId, {
        performedBy: args.by,
        reason: args.reason ?? undefined,
      });
      console.log(`[reinstate] ok`);
      console.log(`  archiveId    = ${result.archiveId}`);
      console.log(`  seriesId     = ${result.seriesId}`);
      console.log(`  createdRow   = ${result.created}`);
      console.log(
        `[hint] 巻情報を復元するには次に \`npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --all\` を実行する`,
      );
      break;
    }

    case "delete": {
      if (args.archiveId === null) {
        console.error("require --archive-id");
        process.exit(1);
      }
      const result = permanentDelete(db, args.archiveId, {
        performedBy: args.by,
        reason: args.reason ?? undefined,
      });
      console.log(`[permanent_delete] ok`);
      console.log(`  archiveId       = ${result.archiveId}`);
      console.log(`  deletedSeriesId = ${result.deletedSeriesId}`);
      console.log(
        `[note] archive 行は state='deleted' で残存 (= 監査用)。 import が来ても再表示されない。`,
      );
      break;
    }

    case "exclude-series": {
      if (args.seriesId === null) {
        console.error("require --series-id");
        process.exit(1);
      }
      const result = manualExcludeSeries(db, args.seriesId, {
        performedBy: args.by,
        reason: args.reason ?? undefined,
      });
      console.log(`[manual_exclude] ok`);
      console.log(`  archiveId = ${result.archiveId}`);
      console.log(`  seriesId  = ${result.seriesId} (削除済み)`);
      break;
    }

    case "audit": {
      const rows = listAudit(db, {
        limit: args.limit ?? 50,
        offset: args.offset ?? 0,
      });
      console.log(
        `${pad("id", 6)} ${pad("action", 18)} ${pad("targetId", 8)} ${pad("by", 16)} ${pad("at", 21)} reason`,
      );
      for (const r of rows) {
        console.log(
          `${pad(r.id, 6)} ${pad(r.action, 18)} ${pad(r.targetId, 8)} ${pad(r.performedBy, 16)} ${pad(r.performedAt, 21)} ${r.reason ?? ""}`,
        );
      }
      break;
    }

    default:
      console.error(
        `usage: admin:state <list-excluded | counts | reinstate | delete | exclude-series | audit> [...flags]`,
      );
      process.exit(1);
  }

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});
