import { describe, expect, it } from "vitest";
import { summarize, summarizeByCategory } from "./index";

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

describe("summarizeByCategory", () => {
  it("groups benchmark runtimes by category", () => {
    const grouped = summarizeByCategory([
      {
        benchmark_id: "cpu",
        category: "performance",
        language: "python",
        metrics: { runtime_seconds: { value: 1.0, unit: "s" } }
      },
      {
        benchmark_id: "cpu",
        category: "performance",
        language: "rust",
        metrics: { runtime_seconds: { value: 0.4, unit: "s" } }
      },
      {
        benchmark_id: "lint",
        category: "security",
        language: "python",
        metrics: { runtime_seconds: { value: 0.2, unit: "s" } }
      }
    ]);

    expect(grouped.get("performance")?.get("cpu")).toEqual({ python: 1.0, rust: 0.4 });
    expect(grouped.get("security")?.get("lint")).toEqual({ python: 0.2 });
  });
});
