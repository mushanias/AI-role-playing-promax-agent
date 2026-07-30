import { parseBackup, serializeBackup } from "./backup";

describe("学习数据备份", () => {
  it("导出格式不包含 API Key", () => {
    const serialized = serializeBackup([]);

    expect(serialized).not.toContain("api_key");
    expect(parseBackup(serialized).goals).toEqual([]);
  });

  it("拒绝导入带有密钥字段的文件", () => {
    expect(() =>
      parseBackup(
        JSON.stringify({
          schema_version: 1,
          exported_at: new Date().toISOString(),
          goals: [],
          api_key: "不应出现",
        }),
      ),
    ).toThrow("API Key");
  });
});
