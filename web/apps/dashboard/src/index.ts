export type Metric = { value: number; unit: string };
export type Category = "performance" | "security" | "quality";
export type RecordItem = {
  benchmark_id: string;
  category: Category;
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

export function summarizeByCategory(
  records: RecordItem[],
): Map<Category, Map<string, { python?: number; rust?: number }>> {
  const output = new Map<Category, Map<string, { python?: number; rust?: number }>>();
  for (const record of records) {
    const categoryMap = output.get(record.category) ?? new Map<string, { python?: number; rust?: number }>();
    const current = categoryMap.get(record.benchmark_id) ?? {};
    const runtime = record.metrics.runtime_seconds?.value;
    if (runtime !== undefined) {
      if (record.language === "python") current.python = runtime;
      if (record.language === "rust") current.rust = runtime;
    }
    categoryMap.set(record.benchmark_id, current);
    output.set(record.category, categoryMap);
  }
  return output;
}
