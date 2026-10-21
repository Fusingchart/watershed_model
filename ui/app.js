const state = {meta:null, targets:{}, shown:new Set(['water_temperature','dissolved_oxygen','ecoli']), rows:[], chart:null};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const RESULT = {positive_signal:'Better than baseline', uncertain_signal:'No clear gain', baseline_selected:'Baseline used', insufficient_history:'Not forecast'};

function fmt(v, target){
  if (v == null || Number.isNaN(v)) return '–';
  const whole = ['ecoli','other_coliform','conductivity','alkalinity','hardness'].includes(target) || Math.abs(v) >= 100;
  return whole ? Math.round(v).toLocaleString() : v.toFixed(target === 'ph' ? 2 : 1);
}
const unit = t => state.targets[t]?.unit ? ` ${state.targets[t].unit}` : '';
const siteLabel = s => s.name ? `${s.name} (${s.id})` : s.id;
const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;

async function api(path, options){
  const r = await fetch(path, options); const body = await r.json();
  if (!r.ok) throw new Error(body.error || r.statusText);
  return body;
}

// Forecast
function renderColumns(){
  const boxes = state.meta.targets.filter(t => t.status !== 'insufficient_history').map(t =>
    `<label><input type="checkbox" value="${t.id}" ${state.shown.has(t.id)?'checked':''}> ${esc(t.label)}</label>`).join('');
  $('f-targets').innerHTML = '<legend>Columns</legend>' + boxes;
}
$('f-targets').addEventListener('change', e => {
  e.target.checked ? state.shown.add(e.target.value) : state.shown.delete(e.target.value);
  renderTable();
});

async function loadForecast(){
  const date = $('f-date').value; if (!date) return;
  try { state.rows = (await api(`/api/forecast?date=${date}`)).rows; } catch (e) { $('f-summary').textContent = e.message; return; }
  renderTable();
}

function renderTable(){
  const cols = state.meta.targets.filter(t => state.shown.has(t.id)).map(t => t.id);
  const bySite = {};
  for (const r of state.rows) (bySite[r.site] ??= {})[r.target] = r;
  const q = $('f-search').value.trim().toLowerCase();
  let sites = state.meta.sites.filter(s => !q || s.id.includes(q) || s.name.toLowerCase().includes(q));
  if ($('f-available').checked) sites = sites.filter(s => cols.some(t => bySite[s.id]?.[t]?.status === 'eligible'));
  const cells = sites.flatMap(s => cols.map(t => bySite[s.id]?.[t]).filter(Boolean));
  const ok = cells.filter(r => r.status === 'eligible'), flagged = ok.filter(r => r.flag).length;
  let text = `${plural(ok.length, 'forecast')} across ${plural(sites.length, 'site')}; ${cells.length - ok.length} unavailable` + (flagged ? `; ${flagged} marked †.` : '.');
  if ($('f-date').value > state.meta.latest_useful_date)
    text = `Nothing can be forecast for visits after ${state.meta.latest_useful_date}: the newest data is from ${state.meta.last_sample}, and forecasts need a measurement from the previous 120 days. Load a newer export to forecast later dates.`;
  $('f-summary').textContent = text;
  const head = `<thead><tr><th>Site</th>${cols.map(t => `<th class="n">${esc(state.targets[t].label)}<small>${esc(unit(t).trim()) || '&nbsp;'}</small></th>`).join('')}</tr></thead>`;
  const body = sites.map(s => `<tr data-site="${s.id}"><td>${esc(s.name || 'Unnamed')}<small>${s.id}</small></td>${cols.map(t => cell(bySite[s.id]?.[t], t)).join('')}</tr>`).join('');
  $('f-table').innerHTML = head + `<tbody>${body || `<tr><td colspan="${cols.length+1}" class="na">No sites match.</td></tr>`}</tbody>`;
}

function cell(r, t){
  if (!r || r.status !== 'eligible') return `<td class="n na" title="${esc(r?.reason)}">–</td>`;
  const title = `Forecast ${fmt(r.predicted,t)}${unit(t)}; baseline ${fmt(r.baseline,t)}; last measured ${fmt(r.last_value,t)}, ${r.age_days} days before the visit`;
  return `<td class="n${r.flag?' flag':''}" title="${esc(title)}">${fmt(r.predicted,t)}${r.flag?' †':''}<small>last ${fmt(r.last_value,t)}</small></td>`;
}

$('f-table').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-site]'); if (!tr) return;
  $('s-site').value = tr.dataset.site; $('w-date').value = $('f-date').value; location.hash = 'site';
});
['f-search','f-available'].forEach(id => $(id).addEventListener('input', renderTable));
$('f-date').addEventListener('change', loadForecast);

// Site history
async function loadSite(){
  const site = $('s-site').value, target = $('s-target').value;
  let d; try { d = await api(`/api/site/${site}?target=${target}`); } catch (e) { $('s-title').textContent = e.message; return; }
  const s = state.meta.sites.find(x => x.id === site);
  $('s-title').textContent = `${siteLabel(s)}: ${state.targets[target].label}`;
  // Skewed measurements are modelled on a log scale; zeros sit on the floor of the axis.
  const log = state.targets[target].log, y = v => log ? Math.max(v, 1) : v;
  const css = getComputedStyle(document.documentElement), c = n => css.getPropertyValue(n).trim();
  state.chart?.destroy();
  state.chart = new Chart($('s-chart'), {
    data:{datasets:[
      {type:'scatter', label:'Measured', data:d.observations.map(o => ({x:Date.parse(o.date), y:y(o.value)})), backgroundColor:c('--soft'), pointRadius:2.5},
      {type:'line', label:'Model', data:d.tested.map(r => ({x:Date.parse(r.date), y:y(r.predicted)})), borderColor:c('--blue'), backgroundColor:c('--blue'), pointRadius:0, borderWidth:2},
      {type:'line', label:'Baseline', data:d.tested.map(r => ({x:Date.parse(r.date), y:y(r.baseline)})), borderColor:c('--ink'), borderDash:[4,3], pointRadius:0, borderWidth:1}]},
    options:{responsive:true, maintainAspectRatio:false, animation:false,
      scales:{x:{type:'linear', ticks:{color:c('--soft'), callback:v => new Date(v).getUTCFullYear()}, grid:{display:false}, border:{color:c('--ink')},
                 afterBuildTicks:axis => { const ticks = [];
                   for (let y = new Date(axis.min).getUTCFullYear() + 1; Date.UTC(y,0,1) <= axis.max; y++) ticks.push({value:Date.UTC(y,0,1)});
                   axis.ticks = ticks; }},
              y:{type:log?'logarithmic':'linear', ticks:{color:c('--soft')}, grid:{color:c('--faint')}, border:{display:false},
                 title:{display:!!unit(target)||log, text:[unit(target).trim(), log?'log scale; zeros plotted at 1':''].filter(Boolean).join(', '), color:c('--soft')}}},
      plugins:{legend:{position:'top', align:'start', labels:{color:c('--ink'), boxWidth:18, boxHeight:2, useBorderRadius:false}},
               tooltip:{callbacks:{title:items => new Date(items[0].parsed.x).toISOString().slice(0,10)}}}}
  });
  if (d.tested.length) {
    const miss = k => d.tested.reduce((a,r) => a + Math.abs(r.actual - r[k]), 0) / d.tested.length;
    $('s-stats').textContent = `Over ${plural(d.tested.length, 'test forecast')} here, the model missed by ${fmt(miss('predicted'),target)}${unit(target)} on average and the baseline by ${fmt(miss('baseline'),target)}${unit(target)}. One site is a small sample.`;
  } else $('s-stats').textContent = `${plural(d.observations.length, 'measurement')}; this site had no test forecasts for this measurement.`;
}
['s-site','s-target'].forEach(id => $(id).addEventListener('change', loadSite));

function addMeasurement(){
  const row = document.createElement('div'); row.className = 'wrow';
  const opts = state.meta.targets.map(t => `<option value="${t.id}">${esc(t.label)}</option>`).join('');
  const day = new Date(Date.parse($('w-date').value || state.meta.last_sample) - 14*864e5).toISOString().slice(0,10);
  row.innerHTML = `<label>Measurement<select class="w-t">${opts}</select></label><label>Sampled<input type="date" class="w-d" value="${day}"></label>` +
    `<label>Value<input type="number" step="any" class="w-v" style="width:100px"></label><button type="button" class="plain">remove</button>`;
  row.querySelector('.w-t').value = $('s-target').value;
  row.querySelector('button').onclick = () => row.remove();
  $('w-rows').append(row);
}
$('w-add').addEventListener('click', addMeasurement);

$('w-run').addEventListener('click', async () => {
  $('w-error').textContent = '';
  const measurements = [...document.querySelectorAll('#w-rows .wrow')].map(r => ({target:r.querySelector('.w-t').value, sample_date:r.querySelector('.w-d').value, value:r.querySelector('.w-v').value}));
  if (measurements.some(m => m.value === '' || !m.sample_date)) { $('w-error').textContent = 'Each added measurement needs a date and a value.'; return; }
  let d; try { d = await api('/api/whatif', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({site:$('s-site').value, date:$('w-date').value, measurements})}); }
  catch (e) { $('w-error').textContent = e.message; return; }
  const before = Object.fromEntries(d.before.map(r => [r.target, r])), ok = r => r.status === 'eligible';
  const rows = d.after.filter(a => ok(a) || ok(before[a.target])).map(a => {
    const b = before[a.target], t = a.target, delta = ok(a) && ok(b) ? a.predicted - b.predicted : null;
    return `<tr><td>${esc(state.targets[t].label)}</td><td class="n">${ok(b)?fmt(b.predicted,t):'–'}</td><td class="n">${ok(a)?fmt(a.predicted,t):'–'}${ok(a)&&a.flag?' †':''}</td>` +
      `<td class="n">${delta==null?'':(delta>0?'+':delta<0?'−':'')+fmt(Math.abs(delta),t)}</td><td>${esc(unit(t).trim())}</td><td class="na">${ok(a)?'':esc(a.reason)}</td></tr>`;
  }).join('');
  $('w-table').innerHTML = `<thead><tr><th>Measurement</th><th class="n">Actual data</th><th class="n">With additions</th><th class="n">Change</th><th>Unit</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="6" class="na">Nothing can be forecast at this site for that visit date.</td></tr>'}</tbody>`;
});

// Model results
function renderResults(){
  const rows = state.meta.targets.map(t => {
    const model = t.status === 'positive_signal' || t.status === 'uncertain_signal';
    const change = model ? `${Math.abs(t.improvement).toFixed(1)}% ${t.improvement >= 0 ? 'less' : 'more'}` : '';
    const base = t.baseline ? t.baseline.replaceAll('_',' ') : '';
    const how = t.status === 'insufficient_history' ? 'Too little history to train' : model ? `vs. ${base}` : `Forecast is the ${base}`;
    const iv = model && t.interval ? t.interval.map(v => v.toFixed(3)).join(' to ') : '';
    const notes = [t.note, t.caution].filter(Boolean).map(esc).join(' ');
    return `<tr><td><b>${esc(t.label)}</b></td><td>${RESULT[t.status] || t.status}<small>${esc(how)}</small></td><td class="n">${change}</td><td class="n">${iv}</td>` +
      `<td class="n">${t.source_MAE!=null?fmt(t.source_MAE,t.id)+esc(unit(t.id)):''}</td><td class="n">${t.test ?? ''}</td><td><small>${notes}</small></td></tr>`;
  }).join('');
  $('cards').innerHTML = `<thead><tr><th>Measurement</th><th>Result</th><th class="n">Error vs. baseline</th><th class="n">Interval</th><th class="n">Average miss</th><th class="n">Samples</th><th>Notes</th></tr></thead><tbody>${rows}</tbody>`;
}

function show(){
  const view = ['site','scorecard'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'forecast';
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('on', a.dataset.view === view));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('on', v.id === `view-${view}`));
  if (view === 'site') loadSite();
}
window.addEventListener('hashchange', show);

(async () => {
  state.meta = await api('/api/meta');
  state.meta.targets.forEach(t => state.targets[t.id] = t);
  $('dataline').textContent = `Measurements through ${state.meta.last_sample} from ${state.meta.sites.length} sites. Models trained on data through 2024 and not changed since.`;
  $('f-date').value = $('w-date').value = '2026-04-20';
  $('s-site').innerHTML = state.meta.sites.map(s => `<option value="${s.id}">${esc(siteLabel(s))}</option>`).join('');
  $('s-target').innerHTML = state.meta.targets.map(t => `<option value="${t.id}">${esc(t.label)}</option>`).join('');
  $('s-site').value = state.meta.sites.reduce((a,b) => b.samples > a.samples ? b : a).id;
  renderColumns(); renderResults(); await loadForecast(); show();
})();
