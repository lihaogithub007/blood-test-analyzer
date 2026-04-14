let chartInstances = {}; // { indicatorName: echartsInstance }
let chartData = {};
let selectedIndicators = new Set();
let reports = [];
let reportTableColumns = new Set(); // display_name list
let patients = [];
let currentPatientId = null;
let currentTab = 'main';

const reportTypeSelect = document.getElementById('reportTypeSelect');
const dailyTypeSelect = document.getElementById('dailyTypeSelect');
const themeToggleBtn = document.getElementById('themeToggle');

const THEME_ICONS = {
  light: `
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z" stroke="currentColor" stroke-width="2" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `,
  dark: `
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M21 13.2A8 8 0 1 1 10.8 3a6.5 6.5 0 0 0 10.2 10.2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </svg>
  `,
};

function getPreferredTheme() {
  try {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch (_) {}
  return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
}

function applyTheme(theme) {
  const t = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('theme', t); } catch (_) {}
  if (themeToggleBtn) themeToggleBtn.innerHTML = THEME_ICONS[t];
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  applyTheme(cur === 'dark' ? 'light' : 'dark');
  renderChart();
}

// 血常规页面仅展示的核心字段（其余仍保存数据库，但不在页面显示）
const CBC_DISPLAY_WHITELIST = [
  "白细胞",
  "红细胞",
  "嗜中性粒细胞绝对值",
  "血红蛋白",
  "血小板",
];

// 默认展示（与白名单一致）
const DEFAULT_INDICATORS = [...CBC_DISPLAY_WHITELIST];

function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) {
    if (v === null || v === undefined || v === '') continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}

function normalizeName(name) {
  if (!name) return name;
  const m = name.split(/[-—]/);
  const base = (m[0] || "").trim();
  return base || name.trim();
}

function pickDefaultIndicatorKeys(allKeys) {
  const keys = new Set(allKeys);
  const picked = [];
  for (const want of DEFAULT_INDICATORS) {
    if (keys.has(want)) picked.push(want);
  }
  if (picked.length === 0) return allKeys.slice(0, 3);
  return picked;
}

function isCbcAllowedIndicator(name) {
  return CBC_DISPLAY_WHITELIST.includes(name);
}

function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 3000);
}

// 上传相关
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const chooseFileBtn = document.getElementById('chooseFileBtn');

uploadZone.addEventListener('click', () => fileInput.click());
if (chooseFileBtn) chooseFileBtn.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', e => { if (e.target.files.length) handleFile(e.target.files[0]); });

async function handleFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('请上传 PDF 文件', 'error');
    return;
  }
  if (!currentPatientId) {
    showToast('请先选择病人', 'error');
    return;
  }

  const progress = document.getElementById('uploadProgress');
  const bar = document.getElementById('progressBar');
  const status = document.getElementById('progressStatus');

  progress.style.display = 'block';
  bar.style.width = '30%';
  status.textContent = '正在上传 PDF...';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('patient_id', String(currentPatientId));
  formData.append('report_type', reportTypeSelect.value || 'cbc');

  try {
    bar.style.width = '60%';
    status.textContent = '正在用 AI 解析报告...';

    const resp = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '上传失败');

    bar.style.width = '100%';
    status.textContent = `解析完成！识别到 ${data.item_count} 项指标`;
    showToast(`成功解析 ${data.item_count} 项指标`);

    if (currentTab === 'daily') {
      await Promise.all([loadReports(), loadChartData()]);
    } else if (currentTab === 'main') {
      await loadMainTimelines();
    } else {
      await loadOtherTimelines();
    }

    setTimeout(() => { progress.style.display = 'none'; bar.style.width = '0'; }, 2000);
  } catch (err) {
    bar.style.width = '100%';
    bar.style.background = '#ef4444';
    status.textContent = `解析失败: ${err.message}`;
    showToast(err.message, 'error');
    setTimeout(() => { progress.style.display = 'none'; bar.style.background = ''; bar.style.width = '0'; }, 3000);
  }

  fileInput.value = '';
}

// 病人
const patientSelect = document.getElementById('patientSelect');
const patientModalMask = document.getElementById('patientModalMask');
const addPatientBtn = document.getElementById('addPatientBtn');
const patientCancelBtn = document.getElementById('patientCancelBtn');
const patientCreateBtn = document.getElementById('patientCreateBtn');

function openPatientModal() {
  document.getElementById('patientName').value = '';
  document.getElementById('patientSex').value = '';
  document.getElementById('patientBirthday').value = '';
  patientModalMask.style.display = 'flex';
}
function closePatientModal() {
  patientModalMask.style.display = 'none';
}

addPatientBtn.addEventListener('click', openPatientModal);
patientCancelBtn.addEventListener('click', closePatientModal);
patientModalMask.addEventListener('click', (e) => {
  if (e.target === patientModalMask) closePatientModal();
});

patientCreateBtn.addEventListener('click', async () => {
  const name = (document.getElementById('patientName').value || '').trim();
  const sex = document.getElementById('patientSex').value || '';
  const birthday = document.getElementById('patientBirthday').value || '';
  if (!name) {
    showToast('病人姓名不能为空', 'error');
    return;
  }
  const formData = new FormData();
  formData.append('name', name);
  if (sex) formData.append('sex', sex);
  if (birthday) formData.append('birthday', birthday);

  try {
    const resp = await fetch('/api/patients', { method: 'POST', body: formData });
    let data = null;
    let text = '';
    try {
      data = await resp.json();
    } catch (_) {
      try { text = await resp.text(); } catch (_) {}
    }
    if (!resp.ok) throw new Error((data && data.detail) || text || '创建失败');
    closePatientModal();
    await loadPatients();
    currentPatientId = data.id;
    patientSelect.value = String(currentPatientId);
    onPatientChanged(true);
    showToast('已创建病人');
  } catch (e) {
    showToast(e.message, 'error');
  }
});

patientSelect.addEventListener('change', () => {
  const v = patientSelect.value;
  currentPatientId = v ? Number(v) : null;
  onPatientChanged(true);
});

function renderPatientSelect() {
  if (!patients || patients.length === 0) {
    patientSelect.innerHTML = '<option value="">（无）</option>';
    currentPatientId = null;
    return;
  }
  patientSelect.innerHTML = patients.map(p => {
    const meta = [p.sex, p.birthday].filter(Boolean).join(' ');
    const label = meta ? `${p.name}（${meta}）` : p.name;
    return `<option value="${p.id}">${label}</option>`;
  }).join('');
  if (!currentPatientId) {
    const preferred = patients.find(p => (p.name || '').trim() === '刘晨曦');
    currentPatientId = (preferred ? preferred.id : patients[0].id);
  }
  patientSelect.value = String(currentPatientId);
}

async function loadPatients() {
  const resp = await fetch('/api/patients');
  patients = await resp.json();
  renderPatientSelect();
}

async function onPatientChanged(reset = false) {
  if (reset) {
    selectedIndicators = new Set();
    reportTableColumns = new Set();
  }
  if (currentTab === 'daily') {
    await Promise.all([loadReports(), loadChartData()]);
  } else if (currentTab === 'main') {
    await loadMainTimelines();
  } else {
    await loadOtherTimelines();
  }
}

// 报告列表
async function loadReports() {
  const rt = dailyTypeSelect ? dailyTypeSelect.value : 'cbc';
  const resp = await fetch('/api/reports' + qs({ patient_id: currentPatientId, report_type: rt }));
  reports = await resp.json();
  renderReports();
}

function renderReports() {
  const legacy = document.getElementById('reportsList');
  legacy.innerHTML = '';

  const colsPanel = document.getElementById('reportColsPanel');
  const table = document.getElementById('reportsTable');

  if (!reports || reports.length === 0) {
    colsPanel.innerHTML = '';
    table.innerHTML = `<thead><tr><th>日期</th><th>文件</th></tr></thead>
      <tbody><tr><td class="cell-muted" colspan="2">暂无报告记录</td></tr></tbody>`;
    return;
  }

  const indicatorSet = new Set();
  for (const r of reports) {
    for (const item of (r.items || [])) {
      const dn = (item.display_name || normalizeName(item.name));
      if (!dn) continue;
      if (dailyTypeSelect && dailyTypeSelect.value === 'cbc') {
        if (isCbcAllowedIndicator(dn)) indicatorSet.add(dn);
      } else {
        indicatorSet.add(dn);
      }
    }
  }
  const allIndicators = Array.from(indicatorSet).sort((a, b) => a.localeCompare(b, 'zh-CN'));

  if (reportTableColumns.size === 0) {
    const defaults = pickDefaultIndicatorKeys(allIndicators);
    defaults.forEach(n => reportTableColumns.add(n));
    if (reportTableColumns.size === 0) {
      allIndicators.slice(0, 5).forEach(n => reportTableColumns.add(n));
    }
  } else {
    for (const c of Array.from(reportTableColumns)) {
      if (!indicatorSet.has(c)) reportTableColumns.delete(c);
    }
  }

  colsPanel.innerHTML = allIndicators.map(name => {
    const checked = reportTableColumns.has(name) ? 'checked' : '';
    return `<label class="col-chip"><input type="checkbox" data-col="${name}" ${checked}/> ${name}</label>`;
  }).join('');

  colsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', () => {
      const col = cb.dataset.col;
      if (cb.checked) reportTableColumns.add(col);
      else reportTableColumns.delete(col);
      renderReportsTable();
    });
  });

  function renderReportsTable() {
    const cols = Array.from(reportTableColumns);
    const thead = `
      <thead>
        <tr>
          <th style="min-width:120px;">日期</th>
          ${cols.map(c => `<th>${c}</th>`).join('')}
          <th style="min-width:80px;">操作</th>
        </tr>
      </thead>
    `;

    const rowsHtml = reports.map(r => {
      const map = {};
      for (const item of (r.items || [])) {
        const dn = (item.display_name || normalizeName(item.name));
        if (!dn) continue;
        if (!map[dn] || (map[dn].value == null && item.value != null)) map[dn] = item;
      }

      // 仅按“当前显示的列”判断是否需要整行标红
      const rowAbnormal = cols.some(c => {
        const it = map[c];
        if (!it || it.value == null) return false;
        if (it.ref_low == null || it.ref_high == null) return false;
        return it.value < it.ref_low || it.value > it.ref_high;
      });

      const tds = cols.map(c => {
        const it = map[c];
        if (!it || it.value == null) return `<td class="cell-muted">-</td>`;
        const abnormal = it.ref_low != null && it.ref_high != null && (it.value < it.ref_low || it.value > it.ref_high);
        const arrow = it.ref_low != null && it.value < it.ref_low ? '↓' :
          it.ref_high != null && it.value > it.ref_high ? '↑' : '';
        const cls = abnormal ? 'cell-abnormal' : '';
        const unit = it.unit ? `<span class="cell-unit">${it.unit}</span>` : '';
        return `<td class="cell-num ${cls}">${it.value}${arrow}${unit}</td>`;
      }).join('');

      return `
        <tr class="${rowAbnormal ? 'report-row-abnormal' : ''}">
          <td>${r.report_date || '-'}</td>
          ${tds}
          <td><button class="report-delete" onclick="deleteReport(${r.id})">删除</button></td>
        </tr>
      `;
    }).join('');

    table.innerHTML = `${thead}<tbody>${rowsHtml}</tbody>`;
  }

  renderReportsTable();
}

async function deleteReport(id) {
  if (!confirm('确定删除该报告？')) return;
  await fetch(`/api/reports/${id}`, { method: 'DELETE' });
  showToast('已删除');
  await Promise.all([loadReports(), loadChartData()]);
}

// 图表
async function loadChartData() {
  const rt = dailyTypeSelect ? dailyTypeSelect.value : 'cbc';
  const resp = await fetch('/api/chart-data' + qs({ patient_id: currentPatientId, report_type: rt }));
  chartData = await resp.json();
  renderIndicatorSelector();
  renderChart();
}

if (dailyTypeSelect) {
  dailyTypeSelect.addEventListener('change', () => {
    selectedIndicators = new Set();
    reportTableColumns = new Set();
    Promise.all([loadReports(), loadChartData()]);
  });
}

// Tabs
document.getElementById('tabs').addEventListener('click', (e) => {
  const btn = e.target && e.target.closest ? e.target.closest('.tab') : null;
  if (!btn) return;
  const tab = btn.dataset.tab;
  switchTab(tab);
});

function resizeAllCharts() {
  try {
    Object.values(chartInstances).forEach(ins => ins && ins.resize && ins.resize());
  } catch (_) {}
}

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.getElementById('pane_main').classList.toggle('active', tab === 'main');
  document.getElementById('pane_daily').classList.toggle('active', tab === 'daily');
  document.getElementById('pane_other').classList.toggle('active', tab === 'other');

  if (!currentPatientId) return;
  if (tab === 'daily') {
    Promise.all([loadReports(), loadChartData()]).then(() => {
      requestAnimationFrame(() => resizeAllCharts());
      setTimeout(resizeAllCharts, 80);
      setTimeout(resizeAllCharts, 180);
    });
  }
  if (tab === 'main') loadMainTimelines();
  if (tab === 'other') loadOtherTimelines();
}

function formatFactValue(f) {
  if (!f) return '-';
  if (f.value_text != null && String(f.value_text).trim() !== '') return String(f.value_text).trim();
  if (f.value_num != null) {
    const u = f.unit ? ` ${f.unit}` : '';
    return `${f.value_num}${u}`;
  }
  return '-';
}

function pickBadge(reportType, facts) {
  const byKey = {};
  (facts || []).forEach(f => { if (f.key && !(f.key in byKey)) byKey[f.key] = f; });
  const get = (k) => byKey[k] ? formatFactValue(byKey[k]) : null;
  if (reportType === 'bm_smear') return get('结论') || '骨穿';
  if (reportType === 'lp') return get('结论') || '腰穿';
  if (reportType === 'flow') return get('结论') || '流式';
  if (reportType === 'molecular') return get('项目') || '分子';
  if (reportType === 'ct_chest') return get('检查部位') || '影像';
  return reportType;
}

function isBadBadge(text) {
  const s = (text || '').toString();
  return /阳性|复发|未缓解|CNS3|可疑|异常|检出/i.test(s);
}

async function loadTimeline(reportType) {
  const resp = await fetch('/api/timeline' + qs({ patient_id: currentPatientId, report_type: reportType }));
  return await resp.json();
}

function renderTimeline(containerId, emptyId, rows, reportType, keysToShow) {
  const el = document.getElementById(containerId);
  const empty = document.getElementById(emptyId);
  if (!rows || rows.length === 0) {
    el.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';
  el.innerHTML = rows.map(r => {
    const facts = r.facts || [];
    const byKey = {};
    facts.forEach(f => { if (f.key && !(f.key in byKey)) byKey[f.key] = f; });
    const badgeText = pickBadge(reportType, facts);
    const badgeCls = isBadBadge(badgeText) ? 'badge red' : 'badge green';
    const showKeys = keysToShow || Object.keys(byKey).slice(0, 6);
    const factHtml = showKeys.map(k => {
      const f = byKey[k];
      return `<div class="fact-row"><div class="fact-key">${k}</div><div class="fact-val">${formatFactValue(f)}</div></div>`;
    }).join('');
    return `
      <div class="timeline-card">
        <div class="timeline-card-head">
          <div class="timeline-date">${r.report_date || '-'}</div>
          <div class="${badgeCls}">${badgeText}</div>
        </div>
        <div class="fact-list">
          ${factHtml || '<div class="fact-row"><div class="fact-key">要点</div><div class="fact-val">-</div></div>'}
        </div>
      </div>
    `;
  }).join('');
}

async function loadMainTimelines() {
  const [bm, lp, flow, mol] = await Promise.all([
    loadTimeline('bm_smear'),
    loadTimeline('lp'),
    loadTimeline('flow'),
    loadTimeline('molecular'),
  ]);
  renderTimeline('timeline_bm', 'timeline_bm_empty', bm, 'bm_smear', ['结论', '原始细胞比例', '标本质量', '备注']);
  renderTimeline('timeline_lp', 'timeline_lp_empty', lp, 'lp', ['结论', 'CSF白细胞', 'CSF红细胞', '是否见幼稚细胞', '备注']);
  renderTimeline('timeline_flow', 'timeline_flow_empty', flow, 'flow', ['用途', 'MRD', '阈值', '结论', '关键表型']);
  renderTimeline('timeline_molecular', 'timeline_molecular_empty', mol, 'molecular', ['项目', '结果', '数值', '备注']);
}

async function loadOtherTimelines() {
  const ct = await loadTimeline('ct_chest');
  renderTimeline('timeline_ct', 'timeline_ct_empty', ct, 'ct_chest', ['检查部位', '印象', '关键阳性']);
}

function renderIndicatorSelector() {
  const container = document.getElementById('indicatorSelector');
  let names = Object.keys(chartData);
  if (dailyTypeSelect && dailyTypeSelect.value === 'cbc') {
    names = names.filter(isCbcAllowedIndicator);
    for (const n of Array.from(selectedIndicators)) {
      if (!isCbcAllowedIndicator(n)) selectedIndicators.delete(n);
    }
  }

  if (names.length === 0) {
    container.innerHTML = '';
    return;
  }

  if (selectedIndicators.size === 0) {
    pickDefaultIndicatorKeys(names).forEach(n => selectedIndicators.add(n));
  }

  for (const name of selectedIndicators) {
    if (!chartData[name]) selectedIndicators.delete(name);
  }

  container.innerHTML = names.map(name => {
    const hasAbnormal = chartData[name].data.some(d =>
      d.value != null && chartData[name].ref_low != null && chartData[name].ref_high != null &&
      (d.value < chartData[name].ref_low || d.value > chartData[name].ref_high)
    );
    return `<button class="indicator-btn ${selectedIndicators.has(name) ? 'active' : ''}" data-name="${name}">
      ${name}${hasAbnormal ? '<span class="abnormal-dot"></span>' : ''}
    </button>`;
  }).join('');

  container.querySelectorAll('.indicator-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const name = btn.dataset.name;
      if (selectedIndicators.has(name)) selectedIndicators.delete(name);
      else selectedIndicators.add(name);
      renderIndicatorSelector();
      renderChart();
    });
  });
}

/** 血常规「红细胞」折线图数值展示为一位小数（Y 轴、提示框等） */
function formatDailyChartValue(name, val) {
  if (val == null || val === '') return '-';
  if (name === '红细胞') {
    const n = Number(val);
    return Number.isFinite(n) ? n.toFixed(1) : String(val);
  }
  return val;
}

function renderChart() {
  const noDataHint = document.getElementById('noDataHint');
  const grid = document.getElementById('chartsGrid');
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  const colors = {
    text: theme === 'dark' ? '#e5e7eb' : '#0f172a',
    muted: theme === 'dark' ? '#94a3b8' : '#64748b',
    border: theme === 'dark' ? 'rgba(148,163,184,0.22)' : '#e2e8f0',
    brand2: theme === 'dark' ? '#60a5fa' : '#3b82f6',
    danger: theme === 'dark' ? '#fb7185' : '#ef4444',
    okBand: theme === 'dark' ? 'rgba(52, 211, 153, 0.10)' : '#10b9811f',
    panel: theme === 'dark' ? '#0f172a' : '#ffffff',
  };

  if (selectedIndicators.size === 0 || Object.keys(chartData).length === 0) {
    grid.style.display = 'none';
    noDataHint.style.display = 'block';
    Object.values(chartInstances).forEach(ins => ins && ins.dispose && ins.dispose());
    chartInstances = {};
    grid.innerHTML = '';
    return;
  }

  grid.style.display = 'grid';
  noDataHint.style.display = 'none';

  const allDates = new Set();
  for (const name of selectedIndicators) {
    if (chartData[name]) chartData[name].data.forEach(d => allDates.add(d.date));
  }
  const dateList = [...allDates].sort();

  let selected = Array.from(selectedIndicators).filter(n => chartData[n]);
  if (dailyTypeSelect && dailyTypeSelect.value === 'cbc') {
    selected = selected.filter(isCbcAllowedIndicator);
  }

  Object.values(chartInstances).forEach(ins => ins && ins.dispose && ins.dispose());
  chartInstances = {};

  grid.innerHTML = selected.map(name => {
    const info = chartData[name];
    const unit = info?.unit ? `单位：${info.unit}` : '';
    const ref = (info?.ref_low != null && info?.ref_high != null)
      ? (name === '红细胞'
        ? `参考：${Number(info.ref_low).toFixed(1)} - ${Number(info.ref_high).toFixed(1)}`
        : `参考：${info.ref_low} - ${info.ref_high}`)
      : '';
    const sub = [unit, ref].filter(Boolean).join('  ');
    return `
      <div class="chart-card" data-ind="${name}">
        <div class="chart-card-header">
          <div class="chart-card-title">${name}</div>
          <div class="chart-card-sub">${sub}</div>
        </div>
        <div class="mini-chart" id="chart_${encodeURIComponent(name)}"></div>
      </div>
    `;
  }).join('');

  for (const name of selected) {
    const info = chartData[name];
    const dom = document.getElementById(`chart_${encodeURIComponent(name)}`);
    if (!dom) continue;

    chartInstances[name] = echarts.init(dom);

    const dataMap = {};
    info.data.forEach(d => { dataMap[d.date] = d.value; });
    const values = dateList.map(date => dataMap[date] ?? null);
    const refLow = info.ref_low;
    const refHigh = info.ref_high;

    const option = {
      textStyle: { color: colors.text },
      tooltip: {
        trigger: 'axis',
        formatter: function(params) {
          const p = params && params[0] ? params[0] : null;
          if (!p) return '';
          const val = p.value;
          let flag = '';
          if (val != null) {
            if (refLow != null && val < refLow) flag = ` <span style="color:${colors.danger}">↓偏低</span>`;
            if (refHigh != null && val > refHigh) flag = ` <span style="color:${colors.danger}">↑偏高</span>`;
          }
          const unit = info?.unit || '';
          const disp = formatDailyChartValue(name, val);
          return `<b>${p.axisValue}</b><br/>${p.marker} ${name}: ${disp} ${unit}${flag}`;
        }
      },
      grid: { top: 24, right: 18, bottom: 26, left: 52 },
      xAxis: {
        type: 'category',
        data: dateList,
        boundaryGap: false,
        axisLabel: { color: colors.muted },
        axisLine: { lineStyle: { color: colors.border } },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: colors.muted,
          ...(name === '红细胞' ? {
            formatter: (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(1) : v),
          } : {}),
        },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: colors.border, opacity: 0.7 } },
      },
      series: [{
        name,
        type: 'line',
        data: values,
        smooth: true,
        symbolSize: 7,
        itemStyle: {
          color: function(params) {
            const val = params.value;
            if (val == null) return colors.brand2;
            if (refLow != null && val < refLow) return colors.danger;
            if (refHigh != null && val > refHigh) return colors.danger;
            return colors.brand2;
          }
        },
        markArea: (refLow != null && refHigh != null) ? {
          silent: true,
          itemStyle: { color: colors.okBand },
          data: [[{ yAxis: refLow }, { yAxis: refHigh }]]
        } : undefined,
      }],
      backgroundColor: colors.panel,
    };

    chartInstances[name].setOption(option, true);
    try { chartInstances[name].resize(); } catch (_) {}
  }

  requestAnimationFrame(() => resizeAllCharts());
  setTimeout(resizeAllCharts, 80);
  setTimeout(resizeAllCharts, 180);
}

window.addEventListener('resize', () => {
  Object.values(chartInstances).forEach(ins => ins && ins.resize && ins.resize());
});

(async function init() {
  applyTheme(getPreferredTheme());
  if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);
  await loadPatients();
  await onPatientChanged(true);
  switchTab('daily');
})();

