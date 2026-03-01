function asRuntime(record) {
  return record?.metrics?.runtime_seconds?.value;
}

function groupByBenchmark(records) {
  const map = new Map();
  for (const record of records) {
    const key = record.benchmark_id;
    const current = map.get(key) || { benchmark: key, category: record.category };
    const runtime = asRuntime(record);
    if (runtime !== undefined) {
      if (record.language === 'python') current.python = runtime;
      if (record.language === 'rust') current.rust = runtime;
    }
    map.set(key, current);
  }
  return [...map.values()].sort((a, b) => `${a.category}:${a.benchmark}`.localeCompare(`${b.category}:${b.benchmark}`));
}

function winner(row) {
  if (row.python == null || row.rust == null) return { name: 'n/a', speedup: 'n/a' };
  if (row.python === row.rust) return { name: 'tie', speedup: '1.00x' };
  if (row.rust < row.python) return { name: 'rust', speedup: `${(row.python / row.rust).toFixed(2)}x` };
  return { name: 'python', speedup: `${(row.rust / row.python).toFixed(2)}x` };
}

function buildStats(rows) {
  const withBoth = rows.filter((row) => row.python != null && row.rust != null);
  const rustWins = withBoth.filter((row) => row.rust < row.python).length;
  const pythonWins = withBoth.filter((row) => row.python < row.rust).length;
  const ties = withBoth.length - rustWins - pythonWins;
  return { compared: withBoth.length, rustWins, pythonWins, ties };
}

function renderSummary(rows, selectedCategory) {
  const summary = document.getElementById('summary');
  const stats = buildStats(rows);

  summary.innerHTML = `
    <div class="metric-box"><div class="label">Selected Category</div><div class="value text">${selectedCategory}</div></div>
    <div class="metric-box"><div class="label">Benchmarks Compared</div><div class="value">${stats.compared}</div></div>
    <div class="metric-box"><div class="label">Rust Wins</div><div class="value">${stats.rustWins}</div></div>
    <div class="metric-box"><div class="label">Python Wins</div><div class="value">${stats.pythonWins}</div></div>
    <div class="metric-box"><div class="label">Ties</div><div class="value">${stats.ties}</div></div>
  `;
}

function renderCategorySummary(rows) {
  const container = document.getElementById('category-summary');
  const categories = ['performance', 'security', 'quality'];
  container.innerHTML = categories
    .map((category) => {
      const stats = buildStats(rows.filter((row) => row.category === category));
      return `
        <div class="metric-box">
          <div class="label">${category}</div>
          <div class="value">${stats.compared}</div>
          <div class="subvalue">rust ${stats.rustWins} | python ${stats.pythonWins} | ties ${stats.ties}</div>
        </div>
      `;
    })
    .join('');
}

function renderTabs(categories, selected, onSelect) {
  const tabs = document.getElementById('category-tabs');
  const options = ['all', ...categories];
  tabs.innerHTML = options
    .map((option) => {
      const active = option === selected ? 'tab active' : 'tab';
      return `<button class="${active}" data-category="${option}" role="tab" aria-selected="${option === selected}">${option}</button>`;
    })
    .join('');

  for (const button of tabs.querySelectorAll('button[data-category]')) {
    button.addEventListener('click', () => onSelect(button.dataset.category || 'all'));
  }
}

function renderTable(rows) {
  const tbody = document.getElementById('benchmark-table');
  tbody.innerHTML = rows
    .map((row) => {
      const result = winner(row);
      const cls = result.name === 'rust' ? 'winner-rust' : result.name === 'python' ? 'winner-python' : '';
      return `
        <tr>
          <td>${row.category}</td>
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

function renderDashboard(records) {
  const rows = groupByBenchmark(records);
  const categories = [...new Set(rows.map((row) => row.category))].sort();
  let selectedCategory = 'all';

  const render = () => {
    const visibleRows =
      selectedCategory === 'all' ? rows : rows.filter((row) => row.category === selectedCategory);
    renderSummary(visibleRows, selectedCategory);
    renderCategorySummary(rows);
    renderTable(visibleRows);
    renderTabs(categories, selectedCategory, (nextCategory) => {
      selectedCategory = nextCategory;
      render();
    });
  };

  render();
}

async function loadData() {
  const output = document.getElementById('raw-output');
  try {
    const response = await fetch('/results/normalized/latest.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const records = await response.json();
    output.textContent = JSON.stringify(records, null, 2);
    renderDashboard(records);
  } catch (error) {
    output.textContent = `Unable to load /results/normalized/latest.json.\n${error}`;
  }
}

loadData();
