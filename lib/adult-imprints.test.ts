import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { loadAdultImprintsFile } from "./adult-imprints";

function writeTmp(content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adult-imprints-test-"));
  const file = path.join(dir, "adult-imprints.yml");
  fs.writeFileSync(file, content, "utf8");
  return file;
}

describe("loadAdultImprintsFile", () => {
  it("loads a minimal valid file", () => {
    const file = writeTmp(`
schema_version: 1
imprints:
  - imprint: COMIC LO
    publisher: 茜新社
    count: 440
`);
    const data = loadAdultImprintsFile(file);
    expect(data.schema_version).toBe(1);
    expect(data.imprints).toHaveLength(1);
    expect(data.imprints[0]).toEqual({
      imprint: "COMIC LO",
      publisher: "茜新社",
      count: 440,
    });
  });

  it("loads optional sections (distribution_channels, ambiguous)", () => {
    const file = writeTmp(`
schema_version: 1
imprints: []
distribution_channels:
  - imprint: DLwolf18
    notes: 配信プラットフォーム複数
ambiguous:
  - imprint: アクションコミックス
    publishers:
      - 双葉社
      - 双葉社（アクションピザッツ）
    note: collision
`);
    const data = loadAdultImprintsFile(file);
    expect(data.distribution_channels).toHaveLength(1);
    expect(data.distribution_channels?.[0].imprint).toBe("DLwolf18");
    expect(data.ambiguous).toHaveLength(1);
    expect(data.ambiguous?.[0].publishers).toHaveLength(2);
  });

  it("rejects entries with missing required fields", () => {
    const file = writeTmp(`
schema_version: 1
imprints:
  - imprint: COMIC LO
`);
    expect(() => loadAdultImprintsFile(file)).toThrow(/検証エラー/);
  });

  it("rejects negative count", () => {
    const file = writeTmp(`
schema_version: 1
imprints:
  - imprint: X
    publisher: Y
    count: -1
`);
    expect(() => loadAdultImprintsFile(file)).toThrow(/検証エラー/);
  });

  it("rejects missing schema_version", () => {
    const file = writeTmp(`
imprints: []
`);
    expect(() => loadAdultImprintsFile(file)).toThrow(/検証エラー/);
  });

  it("throws when file does not exist", () => {
    expect(() => loadAdultImprintsFile("/nonexistent/path.yml")).toThrow(
      /not found/,
    );
  });

  it("loads the actual project seed file (sanity check)", () => {
    const projectFile = path.join(
      process.cwd(),
      "data",
      "seeds",
      "adult-imprints.yml",
    );
    if (!fs.existsSync(projectFile)) {
      // ローカル CI で seed yaml が無い環境ではスキップ
      return;
    }
    const data = loadAdultImprintsFile(projectFile);
    expect(data.schema_version).toBe(1);
    expect(data.imprints.length).toBeGreaterThan(100);
    // 代表的な adult imprint がいることを確認
    const names = new Set(data.imprints.map((i) => i.imprint));
    expect(names.has("COMIC LO")).toBe(true);
    expect(names.has("クリベロン")).toBe(true);
    // ambiguous には載るが imprints には載らないものを確認
    expect(names.has("アクションコミックス")).toBe(false);
  });
});
