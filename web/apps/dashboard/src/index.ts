export type Metric = { value: number; unit: string };
export type RecordItem = {
  benchmark_id: string;
  category: "performance" | "security" | "quality";
  language: "python" | "rust";
  metrics: Record<string, Metric>;
};

export function summarize(records: RecordItem[]): Map<string, { python?: number; rust?: number }> {
  const table = new Map<string, { python?: number; rust?: number }>();
  for (const row of records) {
    const current = table.get(row.benchmark_id) ?? {};
    const runtime = row.metrics.runtime_seconds?.value;
    if (runtime !== undefined) {
      if (row.language === "python") current.python = runtime;
      if (row.language === "rust") current.rust = runtime;
    }
    table.set(row.benchmark_id, current);
  }
  return table;
}
