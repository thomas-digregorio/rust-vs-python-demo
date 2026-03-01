import { describe, expect, it } from "vitest";
import { summarize } from "./index";

describe("summarize", () => {
  it("groups python and rust runtimes by benchmark", () => {
    const map = summarize([
      {
        benchmark_id: "cpu",
        category: "performance",
        language: "python",
        metrics: { runtime_seconds: { value: 1.2, unit: "s" } }
      },
      {
        benchmark_id: "cpu",
        category: "performance",
        language: "rust",
        metrics: { runtime_seconds: { value: 0.6, unit: "s" } }
      }
    ]);
    expect(map.get("cpu")).toEqual({ python: 1.2, rust: 0.6 });
  });
});
