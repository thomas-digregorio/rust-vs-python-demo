function asRuntime(record) {
  return record?.metrics?.runtime_seconds?.value;
}

function groupByBenchmark(records) {
  const map = new Map();
  for (const record of records) {
    const key = record.benchmark_id;
    const current = map.get(key) || { benchmark: key };
    const runtime = asRuntime(record);
    if (runtime !== undefined) {
      if (record.language === 'python') current.python = runtime;
      if (record.language === 'rust') current.rust = runtime;
    }
    map.set(key, current);
  }
  return [...map.values()];
}

function winner(row) {
  if (row.python == null || row.rust == null) return { name: 'n/a', speedup: 'n/a' };
  if (row.python === row.rust) return { name: 'tie', speedup: '1.00x' };
  if (row.rust < row.python) return { name: 'rust', speedup: `${(row.python / row.rust).toFixed(2)}x` };
  return { name: 'python', speedup: `${(row.rust / row.python).toFixed(2)}x` };
}

function renderSummary(rows) {
  const summary = document.getElementById('summary');
  const withBoth = rows.filter((row) => row.python != null && row.rust != null);
  const rustWins = withBoth.filter((row) => row.rust < row.python).length;
  const pythonWins = withBoth.filter((row) => row.python < row.rust).length;

  summary.innerHTML = `
    <div class="metric-box"><div class="label">Benchmarks Compared</div><div class="value">${withBoth.length}</div></div>
    <div class="metric-box"><div class="label">Rust Wins</div><div class="value">${rustWins}</div></div>
    <div class="metric-box"><div class="label">Python Wins</div><div class="value">${pythonWins}</div></div>
  `;
}

function renderTable(rows) {
  const tbody = document.getElementById('benchmark-table');
  tbody.innerHTML = rows
    .map((row) => {
      const result = winner(row);
      const cls = result.name === 'rust' ? 'winner-rust' : result.name === 'python' ? 'winner-python' : '';
      return `
        <tr>
          <td>${row.benchmark}</td>
          <td>${row.python?.toFixed(6) ?? 'n/a'}</td>
          <td>${row.rust?.toFixed(6) ?? 'n/a'}</td>
          <td class="${cls}">${result.name}</td>
          <td>${result.speedup}</td>
        </tr>
      `;
    })
    .join('');
}

async function loadData() {
  const output = document.getElementById('raw-output');
  try {
    const response = await fetch('/results/normalized/latest.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const records = await response.json();
    output.textContent = JSON.stringify(records, null, 2);

    const rows = groupByBenchmark(records);
    renderSummary(rows);
    renderTable(rows);
  } catch (error) {
    output.textContent = `Unable to load /results/normalized/latest.json.\n${error}`;
  }
}

loadData();
