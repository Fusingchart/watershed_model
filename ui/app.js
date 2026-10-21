const state = {meta:null, targets:{}, shown:new Set(['water_temperature','dissolved_oxygen','ecoli']), rows:[], chart:null};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const STATUS = {positive_signal:'Beats baseline', uncertain_signal:'Uncertain gain', baseline_selected:'Uses baseline', insufficient_history:'Not forecast'};

function fmt(v, target){
  if (v == null || Number.isNaN(v)) return '—';
  const big = ['ecoli','other_coliform','conductivity','alkalinity','hardness'].includes(target) || Math.abs(v) >= 100;
  return big ? Math.round(v).toLocaleString() : v.toFixed(target === 'ph' ? 2 : 1);
}
const unit = t => state.targets[t]?.unit ? ` ${state.targets[t].unit}` : '';
const siteLabel = s => s.name ? `${s.name} (${s.id})` : s.id;

async function api(path, options){
  const r = await fetch(path, options); const body = await r.json();
  if (!r.ok) throw new Error(body.error || r.statusText);
  return body;
}

// Forecast view
function renderChips(){
  $('f-targets').innerHTML = state.meta.targets.filter(t => t.status !== 'insufficient_history').map(t =>
    `<button class="chip ${state.shown.has(t.id)?'on':''}" data-t="${t.id}">${esc(t.label)}</button>`).join('');
}
$('f-targets').addEventListener('click', e => {
  const t = e.target.dataset.t; if (!t) return;
  state.shown.has(t) ? state.shown.delete(t) : state.shown.add(t);
  renderChips(); renderTable();
});

async function loadForecast(){
  const date = $('f-date').value; if (!date) return;
  const after = date > state.meta.latest_useful_date;
  $('f-hint').textContent = `Forecast issued ${state.meta.lead_days} days before the visit, using only results available by then.` +
    (after ? ` Visits after ${state.meta.latest_useful_date} are more than 120 days past the latest sample, so nothing can be forecast until newer data is loaded.` : '');
  try { state.rows = (await api(`/api/forecast?date=${date}`)).rows; } catch (e) { $('f-hint').textContent = e.message; return; }
  renderTable();
}

function renderTable(){
  const cols = state.meta.targets.filter(t => state.shown.has(t.id)).map(t => t.id);
  const bySite = {};
  for (const r of state.rows) (bySite[r.site] ??= {})[r.target] = r;
  const q = $('f-search').value.trim().toLowerCase();
  let sites = state.meta.sites.filter(s => !q || s.id.includes(q) || s.name.toLowerCase().includes(q));
  if ($('f-available').checked) sites = sites.filter(s => cols.some(t => bySite[s.id]?.[t]?.status === 'eligible'));
  const shownRows = sites.flatMap(s => cols.map(t => bySite[s.id]?.[t]).filter(Boolean));
  const eligible = shownRows.filter(r => r.status === 'eligible');
  const flagged = eligible.filter(r => r.flag);
  $('f-summary').innerHTML = [['Sites', sites.length], ['Forecasts', eligible.length], ['Unavailable', shownRows.length - eligible.length], ['Unusual (experimental)', flagged.length]]
    .map(([k,v]) => `<div class="stat"><b>${v}</b>${k}</div>`).join('');
  const head = `<thead><tr><th>Site</th>${cols.map(t => `<th class="num">${esc(state.targets[t].label)}<span class="sub">${esc(unit(t).trim() || ' ')}</span></th>`).join('')}</tr></thead>`;
  const body = sites.map(s => `<tr class="link" data-site="${s.id}"><td>${esc(s.name || '—')}<span class="sub">${s.id}</span></td>${cols.map(t => cell(bySite[s.id]?.[t], t)).join('')}</tr>`).join('');
  $('f-table').innerHTML = head + `<tbody>${body || `<tr><td colspan="${cols.length+1}" class="muted">No sites match.</td></tr>`}</tbody>`;
}

function cell(r, t){
  if (!r || r.status !== 'eligible') return `<td class="num cell-na" title="${esc(r?.reason)}">—</td>`;
  const title = `Model ${fmt(r.predicted,t)}${unit(t)} · baseline ${fmt(r.baseline,t)} · last sample ${fmt(r.last_value,t)}, ${r.age_days} days before visit` +
    (r.flag ? ' · unusual compared with history (experimental flag, not an action threshold)' : '');
  return `<td class="num ${r.flag?'cell-flag':''}" title="${esc(title)}">${fmt(r.predicted,t)}<span class="sub">last ${fmt(r.last_value,t)}</span></td>`;
}

$('f-table').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-site]'); if (!tr) return;
  $('s-site').value = tr.dataset.site; $('w-date').value = $('f-date').value; show('site');
});
['f-search','f-available'].forEach(id => $(id).addEventListener('input', renderTable));
$('f-date').addEventListener('change', loadForecast);

// Site explorer
async function loadSite(){
  const site = $('s-site').value, target = $('s-target').value;
  let d; try { d = await api(`/api/site/${site}?target=${target}`); } catch (e) { $('s-title').textContent = e.message; return; }
  const s = state.meta.sites.find(x => x.id === site);
  $('s-title').textContent = `${siteLabel(s)} · ${state.targets[target].label}`;
  // Skewed measurements are modelled on a log scale; zeros sit on the floor of the axis.
  const log = state.targets[target].log, y = v => log ? Math.max(v, 1) : v;
  const pts = d.observations.map(o => ({x:Date.parse(o.date), y:y(o.value)}));
  const css = getComputedStyle(document.documentElement), c = n => css.getPropertyValue(n).trim();
  state.chart?.destroy();
  state.chart = new Chart($('s-chart'), {
    data:{datasets:[
      {type:'scatter', label:'Measured', data:pts, backgroundColor:c('--muted'), pointRadius:3},
      {type:'line', label:'Model forecast', data:d.tested.map(r => ({x:Date.parse(r.date), y:y(r.predicted)})), borderColor:c('--accent'), backgroundColor:c('--accent'), pointRadius:2, borderWidth:2},
      {type:'line', label:'Baseline forecast', data:d.tested.map(r => ({x:Date.parse(r.date), y:y(r.baseline)})), borderColor:c('--warn'), backgroundColor:c('--warn'), borderDash:[5,4], pointRadius:0, borderWidth:1.5}]},
    options:{responsive:true, maintainAspectRatio:false, animation:false,
      scales:{x:{type:'linear', ticks:{color:c('--muted'), callback:v => new Date(v).toISOString().slice(0,7)}, grid:{color:c('--line')}},
              y:{type:log?'logarithmic':'linear', ticks:{color:c('--muted')}, grid:{color:c('--line')}, title:{display:!!unit(target)||log, text:[unit(target).trim(), log?'log scale, zeros shown at 1':''].filter(Boolean).join(', '), color:c('--muted')}}},
      plugins:{legend:{labels:{color:c('--text')}}, tooltip:{callbacks:{title:items => new Date(items[0].parsed.x).toISOString().slice(0,10)}}}}
  });
  if (d.tested.length) {
    const mae = k => d.tested.reduce((a,r) => a + Math.abs(r.actual - r[k]), 0) / d.tested.length;
    $('s-stats').textContent = `${d.tested.length} test forecasts at this site: average miss ${fmt(mae('predicted'),target)}${unit(target)} for the model, ${fmt(mae('baseline'),target)}${unit(target)} for the baseline. Single-site results are noisy.`;
  } else $('s-stats').textContent = `${pts.length} measurements; no test forecasts for this site and measurement.`;
}
['s-site','s-target'].forEach(id => $(id).addEventListener('change', loadSite));

function addMeasurement(){
  const row = document.createElement('div'); row.className = 'wrow';
  const opts = state.meta.targets.map(t => `<option value="${t.id}">${esc(t.label)}</option>`).join('');
  const day = new Date(Date.parse($('w-date').value || state.meta.last_sample) - 14*864e5).toISOString().slice(0,10);
  row.innerHTML = `<label>Measurement <select class="w-t">${opts}</select></label><label>Sample date <input type="date" class="w-d" value="${day}"></label>` +
    `<label>Value <input type="number" step="any" class="w-v" style="width:110px"></label><button class="icon" title="Remove">✕</button>`;
  row.querySelector('.w-t').value = $('s-target').value;
  row.querySelector('button').onclick = () => row.remove();
  $('w-rows').append(row);
}
$('w-add').addEventListener('click', addMeasurement);

$('w-run').addEventListener('click', async () => {
  $('w-error').textContent = '';
  const measurements = [...document.querySelectorAll('#w-rows .wrow')].map(r => ({target:r.querySelector('.w-t').value, sample_date:r.querySelector('.w-d').value, value:r.querySelector('.w-v').value}));
  if (measurements.some(m => m.value === '' || !m.sample_date)) { $('w-error').textContent = 'Fill in a date and value for each measurement.'; return; }
  let d; try { d = await api('/api/whatif', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({site:$('s-site').value, date:$('w-date').value, measurements})}); }
  catch (e) { $('w-error').textContent = e.message; return; }
  const before = Object.fromEntries(d.before.map(r => [r.target, r]));
  const rows = d.after.filter(r => r.status === 'eligible' || before[r.target].status === 'eligible').map(a => {
    const b = before[a.target], t = a.target, ok = r => r.status === 'eligible';
    const delta = ok(a) && ok(b) ? a.predicted - b.predicted : null;
    return `<tr><td>${esc(state.targets[t].label)}</td><td class="num">${ok(b)?fmt(b.predicted,t):'—'}</td><td class="num">${ok(a)?fmt(a.predicted,t):'—'}</td>` +
      `<td class="num">${delta==null?'':(delta>=0?'+':'')+fmt(delta,t)}</td><td>${esc(unit(t).trim())}</td><td class="muted">${ok(a)?(a.flag?'Unusual (experimental)':''):esc(a.reason)}</td></tr>`;
  }).join('');
  $('w-table').innerHTML = `<thead><tr><th>Measurement</th><th class="num">Current</th><th class="num">With your data</th><th class="num">Change</th><th>Unit</th><th>Note</th></tr></thead><tbody>${rows || '<tr><td colspan="6" class="muted">No forecasts available for this visit date.</td></tr>'}</tbody>`;
});

// Scorecard
function renderCards(){
  $('cards').innerHTML = state.meta.targets.map(t => {
    const model = t.status === 'positive_signal' || t.status === 'uncertain_signal';
    const big = t.status === 'insufficient_history' ? 'Not forecast' : !model ? 'Baseline' :
      `${Math.abs(t.improvement).toFixed(1)}% ${t.improvement >= 0 ? 'less' : 'more'} error`;
    const vs = t.status === 'insufficient_history' ? 'Too little history under the current requirements' : !model ?
      `The forecast is the ${esc(t.baseline.replaceAll('_',' '))}; no model beat it on earlier data` : `than the ${esc(t.baseline.replaceAll('_',' '))} baseline`;
    const iv = model && t.interval ? `Site interval for gain: ${t.interval.map(v => v.toFixed(3)).join(' to ')} (transformed units)` : '';
    return `<div class="card"><span class="badge b-${t.status}">${STATUS[t.status] || t.status}</span><h2 style="margin-top:8px">${esc(t.label)}</h2>` +
      `<div class="big">${big}</div><div class="muted small">${vs}${t.test?` · ${t.test} test samples`:''}</div>` +
      `<p class="small">${t.source_MAE!=null?`Average miss ${fmt(t.source_MAE,t.id)}${esc(unit(t.id))}. `:''}${esc(iv)}</p>` +
      (t.note ? `<p class="small">${esc(t.note)}</p>` : '') + (t.caution ? `<p class="small muted">${esc(t.caution)}</p>` : '') + `</div>`;
  }).join('');
}

function show(view){
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));
  history.replaceState(null, '', `#${view}`);
  if (view === 'site') loadSite();
}
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => show(b.dataset.view)));

(async () => {
  state.meta = await api('/api/meta');
  state.meta.targets.forEach(t => state.targets[t.id] = t);
  $('dataline').textContent = `Data through ${state.meta.last_sample} · ${state.meta.sites.length} sites · frozen models trained through 2024`;
  $('f-date').value = '2026-04-20'; $('w-date').value = '2026-04-20';
  $('s-site').innerHTML = state.meta.sites.map(s => `<option value="${s.id}">${esc(siteLabel(s))}</option>`).join('');
  $('s-target').innerHTML = state.meta.targets.map(t => `<option value="${t.id}">${esc(t.label)}</option>`).join('');
  const busiest = state.meta.sites.reduce((a,b) => b.samples > a.samples ? b : a);
  $('s-site').value = busiest.id;
  renderChips(); renderCards(); await loadForecast();
  const view = location.hash.slice(1);
  if (['site','scorecard'].includes(view)) show(view);
})();
