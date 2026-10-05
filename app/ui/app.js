const content = document.querySelector('#content');
const cache = new Map();
const replayView = {day: 142, search: '', filter: 'pending', sort: 'risk-desc'};
const engineView = {search: ''};
let timer = null;
let generation = 0;
const routes = ['fleet', 'engine', 'policies', 'calibration', 'audits'];
const policies = {HT: {name: 'Fixed interval', color: '#B3C0CB'}, CT: {name: 'Condition threshold', color: '#79B8D8'}, FC: {name: 'Predictive', color: '#B7A9D1'}, OR: {name: 'Perfect foresight (reference only)', color: '#93BBA7'}};
const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
const number = (value, digits = 0) => value == null || !Number.isFinite(Number(value)) ? 'Unavailable' : Number(value).toFixed(digits);
const pct = (value, digits = 1) => value == null ? 'Unavailable' : `${number(value * 100, digits)}%`;
const interval = (values, digits = 2) => Array.isArray(values) ? `${number(values[0], digits)} to ${number(values[1], digits)}` : 'Unavailable';
const tail = aircraft => aircraft == null || aircraft < 0 ? 'Stores / spare pool' : `AF-${String(aircraft + 1).padStart(2, '0')}`;
const eventDay = day => day == null ? 'Unavailable' : day === -1 ? 'Initial state — before Day 1' : day < 0 ? `Before Day 1 (exported day ${esc(day)})` : `Day ${number(day + 1)}`;
const replacementDetail = event => event.detail?.new_serial == null ? '' : `Replacement lifecycle ID: <code>${esc(event.detail.new_serial)}</code>`;
const stateName = status => ({serviceable: 'Serviceable', maintenance: 'Engine change', AOG: 'Grounded by failure'}[status] ?? 'Unavailable');
const eventName = event => ({init_installed: 'Initially installed', init_stock: 'Initial shelf stock', request: 'Removal request', start: 'Engine-change start', complete: 'Engine-change complete', serviceable: 'Serviceable', failure: 'Recorded failure', shop_return: 'Overhaul return'}[event] ?? event ?? 'Unavailable');
const recorded = value => value === true ? 'Recorded pass' : value === false ? 'Recorded fail' : 'Unavailable';
const table = (headers, rows, label) => `<div class="table-wrap"><table aria-label="${esc(label)}"><thead><tr>${headers.map(header => `<th scope="col">${header}</th>`).join('')}</tr></thead><tbody>${rows.length ? rows.join('') : `<tr><td colspan="${headers.length}">No exported records available.</td></tr>`}</tbody></table></div>`;
const row = cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join('')}</tr>`;
const head = (title, description) => `<div class="page-head"><h1>${title}</h1><p class="lede">${description}</p></div>`;
const jumpLink = (target, label) => `<a href="${esc(location.hash || '#/fleet')}" data-jump="${esc(target)}">${esc(label)}</a>`;
const workspace = (entity, scope, sections, returnLabel = 'Return to Fleet replay', returnHook = '') => `<div class="workspace-context" aria-label="Workspace context"><div class="scope-row"><strong>${esc(entity)}</strong><span id="workspace-scope">${esc(scope)}</span><a class="context-return" href="#/fleet" ${returnHook ? `data-testid="${returnHook}"` : ''}>${esc(returnLabel)}</a></div><nav class="section-jumps" aria-label="Page sections">${sections.map(([target, label]) => jumpLink(target, label)).join('')}</nav></div>`;
const provenance = () => '';
const policyParameter = (code, value) => code === 'HT' ? `<span class="parameter-label">Removal interval</span>${value == null ? 'Unavailable' : `${number(value)} cycles`}` : code === 'CT' ? `<span class="parameter-label">Health-index threshold</span>${number(value, 4)}<small> · units not specified</small>` : code === 'FC' ? `<span class="parameter-label">Failure-risk threshold</span>${number(value, 4)}<small> probability${value == null ? '' : ` (${pct(value, 2)})`}</small>` : `<span class="parameter-label">Parameter · scale unspecified</span>${number(value, 4)}`;
const selectionMode = mode => mode === 'fewest_failures_fallback' ? 'Fewest-failures fallback' : mode ?? 'Unavailable';
const provenanceFull = data => `<details class="provenance"><summary>${data.scenario ? 'Scenario provenance' : 'Run provenance'}</summary><dl><dt>Run</dt><dd><code>${esc(data.run_id ?? 'Unavailable')}</code></dd><dt>Data</dt><dd>${esc(data.data_label ?? data.data_labels?.join('; ') ?? 'Unavailable')}</dd>${data.scenario ? `<dt>Policy / parameter / seed</dt><dd>${esc(data.scenario.policy ?? 'Unavailable')} / ${number(data.scenario.parameter, 4)} / ${number(data.scenario.seed)}</dd><dt>Initial aircraft / spares / starts per day</dt><dd>${number(data.scenario.aircraft)} / ${number(data.scenario.spares)} / ${number(data.scenario.capacity)}</dd><dt>Flying demand (cycles / aircraft-day)</dt><dd>${number(data.scenario.cell?.rate, 1)}</dd><dt>Planned / unplanned downtime / overhaul (days)</dt><dd>${number(data.scenario.planned_downtime)} / ${number(data.scenario.unplanned_downtime)} / ${number(data.scenario.turnaround)}</dd>` : ''}</dl></details>`;

async function load(name) {
  if (!cache.has(name)) cache.set(name, fetch(`/data/${name}.json`, {cache: 'no-store'}).then(response => {
    if (!response.ok) throw new Error(`${name} export is unavailable (${response.status}).`);
    return response.json();
  }));
  try { return await cache.get(name); } catch (error) { cache.delete(name); throw error; }
}

function plot(id, traces, layout = {}) {
  const element = document.getElementById(id);
  if (!element) return Promise.resolve();
  const axis = {gridcolor: '#344655', zerolinecolor: '#344655', tickfont: {size: 14}, automargin: true};
  return Plotly.react(element, traces, {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family: 'Barlow, sans-serif', color: '#B3C0CB', size: 14},
    margin: {l: 60, r: 20, t: 44, b: 58}, legend: {orientation: 'h', y: 1.2},
    ...layout, xaxis: {...axis, ...layout.xaxis}, yaxis: {...axis, ...layout.yaxis}
  }, {displayModeBar: false, responsive: true});
}

function requestsByDay(replay) {
  const pending = new Map();
  return replay.days.map(frame => {
    for (const event of replay.events.filter(event => event.day === frame.day)) {
      if (event.event === 'request') pending.set(event.serial, event);
      if (event.event === 'start' && event.detail?.removed) pending.delete(event.detail.removed);
      if (event.event === 'failure') pending.delete(event.serial);
    }
    return new Map(pending);
  });
}

function replayHistory(replay, index) {
  const frames = replay.days.slice(0, index + 1);
  const total = replay.scenario.aircraft;
  const firstDay = replay.days[0].day;
  const lastDay = replay.days.at(-1).day;
  const position = day => 48 + (day - firstDay) / Math.max(1, lastDay - firstDay) * 940;
  const counts = frames.map(frame => frame.aircraft.filter(aircraft => aircraft.status === 'serviceable').length);
  const minimum = Math.max(0, Math.min(...counts) - 1);
  const height = value => 76 - (value - minimum) / Math.max(1, total - minimum) * 56;
  let path = '';
  frames.forEach((frame, offset) => {
    const count = frame.aircraft.filter(aircraft => aircraft.status === 'serviceable').length;
    path += `${offset ? 'H' : 'M'}${position(frame.day).toFixed(2)}${offset ? 'V' : ','}${height(count).toFixed(2)} `;
  });
  const countTicks = [...new Set([minimum, Math.floor((total + minimum) / 2), total])];
  const dayTicks = [...new Set([firstDay, ...[59, 119, 179, 239, 299].filter(day => day > firstDay && day < lastDay), lastDay])];
  return `<div class="history-frame"><div class="history-canvas"><svg class="history" viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" aria-label="Recorded daily serviceable aircraft through Day ${frames.at(-1).day + 1}; full replay day axis, not a forecast">
    ${countTicks.map(value => `<path d="M48 ${height(value)}H988" class="gridline"/>`).join('')}
    <path d="${path}" class="history-line"/><path d="M${position(frames.at(-1).day)} 15V80" class="cursor-line"/></svg>
    ${countTicks.map(value => `<span class="history-count" style="top:${height(value)}%">${value}</span>`).join('')}</div>
    <div class="history-ticks">${dayTicks.map(day => `<span class="${day !== firstDay && day !== lastDay ? 'intermediate-tick' : day === firstDay ? 'first-tick' : 'last-tick'}" style="left:${position(day) / 10}%">Day ${day + 1}</span>`).join('')}</div></div>`;
}

async function fleetPage(current) {
  const [replay, summary] = await Promise.all([load('replay'), load('summary')]);
  if (current !== generation) return;
  if (!replay.days?.length || !Array.isArray(replay.events)) throw new Error('Replay history or events are unavailable.');
  const pendingDays = requestsByDay(replay);
  const last = replay.days.length - 1;
  replayView.day = Math.min(replayView.day, last);
  content.innerHTML = `<article data-testid="page-fleet">
    ${head('Fleet replay', `${number(replay.scenario.aircraft)}-airframe squadron · predictive engine removal · one simulated year`)}
    ${provenance(replay)}
    <div class="task-banner"><strong id="task-summary"></strong><span>Removals wait for a free engine-change slot and a spare engine on the shelf.</span></div>
    <section class="panel replay" aria-label="Replay controls">
      <div class="replay-controls"><h2 id="fleet-title"></h2><button id="previous" aria-label="Previous day">Previous</button><button id="play" data-testid="replay-play" aria-label="Play replay" aria-pressed="false">Play</button><button id="next" aria-label="Next day">Next</button><label for="day-number">Go to day</label><input id="day-number" data-testid="replay-day-number" type="number" min="1" max="${replay.days.at(-1).day + 1}" step="1"></div>
      <input id="day" class="scrub" data-testid="replay-day" type="range" min="0" max="${last}" step="1" aria-label="Selected replay day">
      <div class="panel-head"><h2 id="history-title"></h2><span>Mission-capable aircraft each day</span></div><div id="strip" data-testid="chart-replay"></div>
      <div class="summary-line" id="kpis" aria-live="polite"></div>
    </section>
    <div class="fleet-grid"><section class="panel fleet-evidence"><div class="panel-head"><h2>Request and engine evidence</h2><span></span></div><p class="muted">Risk is each engine's calibrated probability of failing within its next 20 cycles; FleetSense requests removal above ${pct(replay.scenario.parameter, 0)}.</p>
      <div class="filters"><label class="search-label"><span class="sr-only">Search aircraft or engine</span><input id="fleet-search" data-testid="fleet-search" type="search" placeholder="Aircraft or engine serial" value="${esc(replayView.search)}"></label>
      <label>View<select id="fleet-filter" data-testid="fleet-filter"><option value="pending">Pending requests</option><option value="all">All aircraft</option><option value="serviceable">Serviceable</option><option value="maintenance">Engine change</option><option value="AOG">Grounded by failure</option></select></label>
      <label>Sort<select id="fleet-sort" data-testid="fleet-sort"><option value="risk-desc">Risk descending</option><option value="risk-asc">Risk ascending</option><option value="aircraft">Airframe ID</option><option value="cycles">Cycles descending</option><option value="request">Oldest request</option></select></label></div>
      <div id="board"></div><p class="muted" id="row-count" aria-live="polite"></p><p class="evidence-note">Inspect opens the engine's health record; returning keeps your place in the replay.</p></section>
      <aside class="side"><section class="panel"><h2>Resource context</h2><div id="stock"></div><details class="resource-note"><summary>Capacity and stock meaning</summary><p class="muted">One engine change can start per day. The squadron holds ${number(replay.scenario.spares)} spare engines; removed engines return to the shelf after overhaul.</p></details></section>
      <section class="panel"><div class="panel-head"><h2>Recent events</h2></div><div id="log" data-testid="replay-events"></div><p class="muted">Latest four events, not all pending requests.</p></section></aside></div></article>`;
  const slider = document.querySelector('#day');
  const dayNumber = document.querySelector('#day-number');
  const playButton = document.querySelector('#play');
  document.querySelector('#fleet-filter').value = replayView.filter;
  document.querySelector('#fleet-sort').value = replayView.sort;
  function render() {
    const frame = replay.days[replayView.day];
    const pending = pendingDays[replayView.day];
    const humanDay = frame.day + 1;
    slider.value = replayView.day;
    slider.setAttribute('aria-valuetext', `Day ${humanDay}`);
    dayNumber.value = humanDay;
    document.querySelector('#previous').disabled = replayView.day === 0;
    document.querySelector('#next').disabled = replayView.day === last;
    document.querySelector('#fleet-title').textContent = `Day ${humanDay} of ${replay.days.at(-1).day + 1}`;
    document.querySelector('#history-title').textContent = `Fleet serviceability through Day ${humanDay}`;
    document.querySelector('#strip').innerHTML = replayHistory(replay, replayView.day);
    const capable = frame.aircraft.filter(aircraft => aircraft.status === 'serviceable').length;
    const availability = replay.days.slice(0, replayView.day + 1).reduce((sum, daily) => sum + daily.aircraft.filter(aircraft => aircraft.status === 'serviceable').length, 0) / ((replayView.day + 1) * replay.scenario.aircraft);
    document.querySelector('#task-summary').textContent = `${pending.size} pending ${pending.size === 1 ? 'request' : 'requests'}. ${frame.stock == null ? 'Shelf stock unavailable.' : frame.stock === 0 ? 'No shelf spare available.' : `${frame.stock} shelf ${frame.stock === 1 ? 'spare' : 'spares'} available.`}`;
    document.querySelector('#kpis').innerHTML = `<span>Serviceable: <strong>${capable} / ${frame.aircraft.length}</strong></span><span>Availability through Day ${humanDay}: <strong>${pct(availability)}</strong></span><span>Pending removals: <strong>${pending.size}</strong></span>`;
    const selected = frame.aircraft.filter(aircraft => {
      const matchesSearch = `${tail(aircraft.aircraft)} ${aircraft.serial}`.toLowerCase().includes(replayView.search.trim().toLowerCase());
      return matchesSearch && (replayView.filter === 'all' || (replayView.filter === 'pending' ? pending.has(aircraft.serial) : aircraft.status === replayView.filter));
    }).sort((first, second) => {
      let order = 0;
      if (replayView.sort.startsWith('risk')) order = first.risk == null ? (second.risk == null ? 0 : 1) : second.risk == null ? -1 : (first.risk - second.risk) * (replayView.sort === 'risk-desc' ? -1 : 1);
      if (replayView.sort === 'cycles') order = first.cycle == null ? (second.cycle == null ? 0 : 1) : second.cycle == null ? -1 : second.cycle - first.cycle;
      if (replayView.sort === 'request') order = (pending.get(first.serial)?.day ?? Infinity) - (pending.get(second.serial)?.day ?? Infinity);
      return order || first.aircraft - second.aircraft;
    });
    document.querySelector('#board').innerHTML = selected.length ? table(['Airframe / engine', 'State', 'Request', 'Observed cycles', `Model risk · Day ${humanDay}<br><small>Next 20 cycles</small>`, 'Evidence'], selected.map(aircraft => {
      const request = pending.get(aircraft.serial);
      return `<tr data-testid="fleet-row" data-aircraft="${aircraft.aircraft}" data-risk="${aircraft.risk ?? ''}"><td><strong>${tail(aircraft.aircraft)}</strong><br><code>${esc(aircraft.serial)}</code></td><td><span class="state ${esc(aircraft.status)}">${stateName(aircraft.status)}</span></td><td>${request ? `Day ${request.day + 1}, pending ${frame.day - request.day} ${frame.day - request.day === 1 ? 'day' : 'days'}<details><summary>Trigger evidence</summary><span>Request-time score: ${pct(request.detail?.urgency)}<br>Policy ${esc(replay.scenario.policy)}; parameter ${number(replay.scenario.parameter, 4)}</span></details>` : 'No pending request'}</td><td class="num">${number(aircraft.cycle)}</td><td><span class="risk-value"><span class="risk-bar" aria-hidden="true"><i style="width:${aircraft.risk == null ? 0 : Math.max(0, Math.min(100, aircraft.risk * 100))}%"></i></span>${pct(aircraft.risk)}</span></td><td><a class="btn inspect" data-testid="aircraft-${aircraft.aircraft}" href="#/engine/${encodeURIComponent(aircraft.serial)}" aria-label="Inspect engine ${esc(aircraft.serial)}">Inspect</a></td></tr>`;
    }), 'Selected-day aircraft evidence') : '<div class="empty">No aircraft match this day and view. <button id="show-all">Show all aircraft</button></div>';
    document.querySelector('#show-all')?.addEventListener('click', () => { replayView.filter = 'all'; replayView.search = ''; document.querySelector('#fleet-filter').value = 'all'; document.querySelector('#fleet-search').value = ''; render(); });
    document.querySelector('#row-count').textContent = `${selected.length} shown of ${frame.aircraft.length} aircraft. A request is separate from operational state.`;
    document.querySelector('#stock').innerHTML = `<dl class="resource"><dt>Current shelf spares</dt><dd>${number(frame.stock)}</dd><dt>In overhaul</dt><dd>${number(frame.in_shop)}</dd><dt>Starts at most</dt><dd>${number(replay.scenario.capacity)}/day</dd></dl>`;
    const events = replay.events.filter(event => event.day <= frame.day && ['request', 'start', 'failure', 'shop_return'].includes(event.event)).slice(-4).reverse();
    document.querySelector('#log').innerHTML = events.length ? events.map(event => {
      const stores = event.aircraft == null || event.aircraft < 0;
      return `<div class="log-row"><span class="event-identity"><time>${eventDay(event.day)}</time> · ${tail(event.aircraft)}${stores ? '' : ` / <code>${esc(event.serial)}</code>`}</span><strong class="${event.event === 'failure' ? 'failure' : event.event === 'request' ? 'request' : ''}">${esc(eventName(event.event))}${stores ? ` · <code>${esc(event.serial)}</code>` : ''}${event.detail?.removed ? ` · removed ${esc(event.detail.removed)}` : ''}</strong>${event.detail?.new_serial == null ? '' : `<span class="replacement-detail">${replacementDetail(event)}</span>`}</div>`;
    }).join('') : '<p class="empty">No recorded events through this day.</p>';
  }
  function pause() { clearInterval(timer); timer = null; playButton.textContent = 'Play'; playButton.setAttribute('aria-label', 'Play replay'); playButton.setAttribute('aria-pressed', 'false'); }
  function selectDay(index) { pause(); replayView.day = Math.max(0, Math.min(last, index)); render(); }
  slider.addEventListener('input', () => selectDay(Number(slider.value)));
  function applyDayEntry(commit) {
    pause();
    if (!dayNumber.validity.valid || dayNumber.value === '') {
      if (commit) { dayNumber.reportValidity(); dayNumber.value = replay.days[replayView.day].day + 1; }
      return;
    }
    const index = replay.days.findIndex(frame => frame.day + 1 === Number(dayNumber.value));
    if (index >= 0) {
      if (index !== replayView.day) selectDay(index);
      else dayNumber.value = replay.days[index].day + 1;
    }
    else if (commit) dayNumber.value = replay.days[replayView.day].day + 1;
  }
  dayNumber.addEventListener('input', () => applyDayEntry(false));
  dayNumber.addEventListener('change', () => applyDayEntry(true));
  dayNumber.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); applyDayEntry(true); } });
  document.querySelector('#previous').addEventListener('click', () => selectDay(replayView.day - 1));
  document.querySelector('#next').addEventListener('click', () => selectDay(replayView.day + 1));
  playButton.addEventListener('click', () => {
    if (timer) { pause(); return; }
    if (replayView.day === last) replayView.day = 0;
    playButton.textContent = 'Pause'; playButton.setAttribute('aria-label', 'Pause replay'); playButton.setAttribute('aria-pressed', 'true'); render();
    timer = setInterval(() => { if (current !== generation) { pause(); return; } replayView.day = Math.min(last, replayView.day + 1); render(); if (replayView.day === last) pause(); }, 250);
  });
  for (const [selector, key, eventName] of [['#fleet-search', 'search', 'input'], ['#fleet-filter', 'filter', 'change'], ['#fleet-sort', 'sort', 'change']]) document.querySelector(selector).addEventListener(eventName, event => { replayView[key] = event.target.value; render(); });
  render();
}

async function enginePage(current, serial) {
  const [data, replay] = await Promise.all([load('engine'), load('replay')]);
  if (current !== generation) return;
  const engines = data.engines ?? [];
  const engine = serial ? engines.find(record => record.serial === serial) : engines[0];
  if (!engine) {
    content.innerHTML = `<article data-testid="page-engine">${head(serial ? 'Unknown engine ID' : 'No engine records', serial ? `No exported record matches ${esc(serial)}. No substitute engine is shown.` : 'Engine evidence is unavailable.')}<a class="btn" href="#/fleet">Return to Fleet replay</a><a class="btn" href="#/engine">Browse exported engines</a></article>`;
    return;
  }
  const selectedFrame = replay.days[Math.min(replayView.day, replay.days.length - 1)];
  const observation = selectedFrame?.aircraft.find(aircraft => aircraft.serial === engine.serial);
  const appearances = replay.days.filter(frame => frame.aircraft.some(aircraft => aircraft.serial === engine.serial));
  const lastFrame = appearances.at(-1);
  const events = replay.events.filter(event => event.serial === engine.serial || event.detail?.removed === engine.serial || event.detail?.new_serial === engine.serial);
  content.innerHTML = `<article data-testid="page-engine">${head(`Engine ${esc(engine.serial)}`, `Health record · sensor ${esc(engine.sensor)} against same-age fleet norm`)}${provenance(data)}
    ${workspace(`Engine ${engine.serial}`, `Selected replay: ${selectedFrame ? `Day ${selectedFrame.day + 1}` : 'unavailable'}; terminal export: cycle ${number(engine.cycle)}, last appearance ${lastFrame ? `Day ${lastFrame.day + 1}` : 'unavailable'}.`, [['engine-context', 'Replay / terminal context'], ['engine-history', 'Sensor history'], ['engine-horizons', 'Horizon probabilities'], ['engine-lifecycle', 'Lifecycle evidence']], `Return to Fleet replay · Day ${selectedFrame ? selectedFrame.day + 1 : 'unavailable'}`, 'engine-return')}
    <div class="engine-layout"><aside class="engine-finder"><h2>Engines</h2><label for="engine-search">Find engine by serial or source</label><input id="engine-search" type="search" data-testid="engine-search" value="${esc(engineView.search)}" placeholder="Serial or source trajectory"><button id="clear-engine-search" type="button">Clear engine search</button><p id="engine-matches" aria-live="polite"></p><nav id="engine-list" class="engine-list" aria-label="Exported engines"></nav></aside><div class="engine-main">
    <div class="two context" id="engine-context"><section class="panel" data-testid="selected-engine-context"><h2>Selected replay context · Day ${selectedFrame ? selectedFrame.day + 1 : 'unavailable'}</h2>${observation ? `<p>${tail(observation.aircraft)} · ${stateName(observation.status)}</p><p><strong>${number(observation.cycle)} observed cycles</strong> · next-20-cycle risk <strong>${pct(observation.risk)}</strong></p>` : '<p>This engine does not appear in the selected replay day. Selected-day evidence is unavailable.</p>'}</section>
    <section class="panel" data-testid="terminal-engine-context"><h2>Latest health snapshot</h2><p><strong>${number(engine.cycle)} observed cycles</strong></p><p>Last replay appearance: ${lastFrame ? `Day ${lastFrame.day + 1}` : 'Unavailable'}.</p></section></div>
    <section class="panel" id="engine-history"><div class="panel-head"><h2>Sensor ${esc(engine.sensor)} history</h2><span>Band: 5–95% range of fleet engines at the same age</span></div><div id="engine-sensor" class="chart" data-testid="chart-engine"></div>${jumpLink('engine-sensor-values', 'View sensor values')}<details id="engine-sensor-values" class="numeric-disclosure"><summary>Exported sensor and reference values</summary>${table(['Engine cycle', 'Sensor reading · units unspecified'], (engine.cycles ?? []).map((cycle, index) => row([number(cycle), number(engine.values?.[index], 4)])), 'Engine sensor readings')}${table(['Training-engine cycle', 'P05 reference', 'P95 reference'], (engine.band?.age ?? []).map((cycle, index) => row([number(cycle), number(engine.band?.low?.[index], 4), number(engine.band?.high?.[index], 4)])), 'Training-engine reference quantiles')}</details></section>
    <div class="two"><section class="panel" id="engine-horizons"><h2>Failure risk by horizon</h2><div id="engine-risk" class="chart short" data-testid="chart-engine-risk"></div>${jumpLink('engine-horizon-values', 'View horizon values')}<div id="engine-horizon-values">${table(['Within next cycles', 'Failure probability'], (engine.horizons ?? []).map((horizon, index) => row([number(horizon), pct(engine.probabilities?.[index], 2)])), 'Terminal horizon probabilities')}</div></section>
    <section class="panel" id="engine-lifecycle"><h2>Maintenance history</h2>${table(['Day', 'Event', 'Entity / exported detail'], events.map(event => row([eventDay(event.day), `<span data-event="${esc(event.event)}" title="Exported event: ${esc(event.event)}">${esc(eventName(event.event))}</span>`, `${tail(event.aircraft)} · lifecycle <code>${esc(event.serial)}</code>${event.detail?.removed ? ` · removed ${esc(event.detail.removed)}` : ''}${event.detail?.new_serial == null ? '' : ` · ${replacementDetail(event)}`}`])), 'Engine lifecycle events')}</section></div></div></div></article>`;
  function renderFinder() {
    const query = engineView.search.trim().toLowerCase();
    const matches = engines.filter(record => `${record.serial} ${record.trajectory ?? ''}`.toLowerCase().includes(query));
    document.querySelector('#engine-list').innerHTML = matches.length ? matches.map(record => `<a href="#/engine/${encodeURIComponent(record.serial)}" ${record.serial === engine.serial ? 'aria-current="page" class="active"' : ''}><code>${esc(record.serial)}</code><span>${esc(record.trajectory ?? 'Source unavailable')} · ${number(record.cycle)} cycles</span></a>`).join('') : '<p class="empty">No exported engines match. Clear the search to browse all engines.</p>';
    document.querySelector('#engine-matches').textContent = `${matches.length} of ${engines.length} exported engines`;
  }
  document.querySelector('#engine-search').addEventListener('input', event => { engineView.search = event.target.value; renderFinder(); });
  document.querySelector('#clear-engine-search').addEventListener('click', () => { engineView.search = ''; document.querySelector('#engine-search').value = ''; renderFinder(); document.querySelector('#engine-search').focus(); });
  renderFinder();
  await Promise.all([
    plot('engine-sensor', [
      {x: [...(engine.band?.age ?? []), ...[...(engine.band?.age ?? [])].reverse()], y: [...(engine.band?.high ?? []), ...[...(engine.band?.low ?? [])].reverse()], mode: 'lines', fill: 'toself', fillcolor: 'rgba(121,184,216,.15)', line: {width: 0}, name: 'Fleet norm (5–95%)', hoverinfo: 'skip'},
      {x: engine.cycles, y: engine.values, mode: 'lines', line: {color: '#79B8D8', width: 2}, name: engine.serial, hovertemplate: 'Cycle %{x}<br>Reading %{y:.3f}<extra></extra>'}
    ], {xaxis: {title: {text: 'Engine cycle'}}, yaxis: {title: {text: `${engine.sensor} reading`}}}),
    plot('engine-risk', [{x: engine.horizons, y: engine.probabilities, type: 'bar', marker: {color: '#79B8D8'}, hovertemplate: 'Next %{x} cycles: %{y:.2%}<extra></extra>'}], {xaxis: {title: {text: 'Next cycles'}, type: 'category'}, yaxis: {range: [0, 1], tickformat: '.0%', title: {text: 'Failure probability'}}})
  ]);
}

async function policiesPage(current) {
  const [data, summary] = await Promise.all([load('policies'), load('summary')]);
  if (current !== generation) return;
  const primary = summary.primary ?? {};
  const study = summary.study_design ?? summary.presentation?.tuning_feasibility;
  const cells = data.cells ?? [];
  content.innerHTML = `<article data-testid="page-policies">${head('Policy comparison', 'Run fixed-interval, condition-based and predictive maintenance against the same squadron, demand and spares before adopting a rule.')} ${provenance(summary)}
    ${workspace('Policy comparison', `${number(summary.counts?.paired_scenarios ?? primary.paired_scenarios)} simulated squadron-years per strategy`, [['policy-result', 'Key finding'], ['policy-outcomes', 'Strategy outcomes'], ['policy-charts', 'Trade-off and scenarios'], ['scenario-table', 'Scenario table']])}
    <section class="panel verdict" id="policy-result"><h2>Key finding: spare engines, not forecasts, set the availability ceiling</h2><p>Predictive removal kept ${pct(data.metrics?.FC?.availability, 2)} of aircraft-days available, ${number(primary.delta_availability_pp, 2)} percentage points above ${esc((policies[summary.best_simple]?.name ?? 'the best simple rule').toLowerCase())}, and left ${number((1 - (summary.guardrails?.wasted_life?.ratio ?? 1)) * 100, 0)}% less engine life on the table. The margin is small because spare-engine supply sets the ceiling: with three spares and long overhaul turnaround, even perfect foresight cannot keep more aircraft flying. The scenario map shows where better forecasts pay off and where more spares do.</p></section>
    <section class="panel" id="policy-outcomes"><h2>Strategy outcomes</h2>${table(['Policy', 'Availability', 'Failures / aircraft-year', 'Planned changes / aircraft-year', 'Life left at removal (cycles)'], Object.entries(data.metrics ?? {}).map(([code, metric]) => row([esc(policies[code]?.name ?? code), pct(metric.availability, 3), number(metric.failures_per_aircraft_year, 4), number(metric.planned_per_aircraft_year, 4), number(metric.wasted_life_cycles, 2)])), 'Frozen policy outcomes')}</section>
    <div class="two" id="policy-charts"><section class="panel"><h2>Availability against in-service failures</h2><div id="frontier" class="chart" data-testid="chart-frontier"></div><p class="muted">Each point is one threshold setting of a strategy.</p>${jumpLink('frontier-values', 'View frontier numeric values')}</section><section class="panel"><h2>Scenario differences</h2><div id="policies" class="chart" data-testid="chart-policies"></div><p class="dimension-key">Row key: downtime ratio = unplanned / planned downtime; overhaul turnaround is in days.</p><div class="scenario-dimensions" aria-label="Scenario row definitions">${[...new Map(cells.map(cell => [`${cell.downtime_ratio}× / ${cell.turnaround}d`, cell])).entries()].map(([label, cell]) => `<button type="button" class="dimension-label" data-jump="scenario-table" title="Unplanned / planned downtime ratio: ${number(cell.downtime_ratio)} times; overhaul turnaround: ${number(cell.turnaround)} days" aria-label="${esc(label)}: unplanned / planned downtime ratio ${number(cell.downtime_ratio)} times; overhaul turnaround ${number(cell.turnaround)} days. Open scenario table.">${esc(label)}</button>`).join('')}</div><p class="muted">Availability gain of predictive removal over the best simple rule, in percentage points.</p>${jumpLink('scenario-table', 'View scenario numeric values')}</section></div>
    <details class="panel numeric-disclosure" id="frontier-values"><summary>Numeric frontier alternatives (${(data.frontier ?? []).length} settings)</summary>${table(['Policy', 'Policy parameter', 'Availability', 'Failures / aircraft-year', 'Wasted life (cycles)'], (data.frontier ?? []).map(record => row([esc(policies[record.policy]?.name ?? record.policy), policyParameter(record.policy, record.parameter), record.availability_pct == null ? pct(record.availability, 3) : `${number(record.availability_pct, 3)}%`, number(record.failures_per_aircraft_year, 4), number(record.wasted_life_cycles, 2)])), 'Frontier alternatives')}</details>
    <section class="panel" id="scenario-table"><h2>Numeric scenario matrix</h2>${table(['Flying cycles / aircraft-day', 'Unplanned / planned downtime ratio', 'Overhaul turnaround (days)', 'Availability difference (pp)', '95% CI (pp)'], cells.map(cell => row([number(cell.rate, 1), `${number(cell.downtime_ratio)}×`, number(cell.turnaround), number(cell.delta_availability_pp, 3), interval(cell.ci95_pp, 3)])), 'Scenario matrix')}</section>
    </article>`;
  const rates = [...new Set(cells.map(cell => cell.rate))];
  const scenarios = [...new Set(cells.map(cell => `${cell.downtime_ratio}× / ${cell.turnaround}d`))];
  const dimensionDetail = document.createElement('p');
  dimensionDetail.id = 'scenario-dimension-detail';
  dimensionDetail.className = 'muted dimension-detail';
  dimensionDetail.setAttribute('role', 'status');
  dimensionDetail.textContent = 'Focus or hover a row key for its full dimension names.';
  document.querySelector('.scenario-dimensions').after(dimensionDetail);
  document.querySelectorAll('.dimension-label').forEach(button => { for (const eventName of ['focus', 'mouseenter']) button.addEventListener(eventName, () => { dimensionDetail.textContent = button.title; }); });
  await Promise.all([
    plot('frontier', ['HT', 'CT', 'FC'].map(code => { const records = (data.frontier ?? []).filter(record => record.policy === code); return {x: records.map(record => record.failures_per_aircraft_year), y: records.map(record => record.availability_pct ?? (record.availability == null ? null : record.availability * 100)), mode: 'markers', name: policies[code].name, marker: {color: policies[code].color, size: 7}}; }), {xaxis: {title: {text: 'Failures / aircraft-year'}}, yaxis: {title: {text: 'Availability (%)'}}}),
    plot('policies', [{type: 'heatmap', x: rates, y: scenarios, z: scenarios.map(scenario => rates.map(rate => cells.find(cell => cell.rate === rate && `${cell.downtime_ratio}× / ${cell.turnaround}d` === scenario)?.delta_availability_pp ?? null)), customdata: scenarios.map(scenario => rates.map(rate => { const cell = cells.find(cell => cell.rate === rate && `${cell.downtime_ratio}× / ${cell.turnaround}d` === scenario); return cell ? `Unplanned / planned downtime ratio: ${number(cell.downtime_ratio)} times<br>Overhaul turnaround: ${number(cell.turnaround)} days<br>95% CI: ${interval(cell.ci95_pp, 3)} pp` : 'Unavailable'; })), colorscale: [[0, '#B7A9D1'], [.5, '#18232D'], [1, '#79B8D8']], zmid: 0, colorbar: {thickness: 12, ticksuffix: ' pp'}, hovertemplate: '%{x} cycles / aircraft-day<br>%{customdata}<br>Difference %{z:.3f} pp<extra></extra>'}], {margin: {l: 100, r: 50, t: 20, b: 58}, xaxis: {type: 'category', title: {text: 'Flying cycles / aircraft-day'}}, yaxis: {type: 'category'}})
  ]);
}

async function calibrationPage(current) {
  const data = await load('calibration');
  if (current !== generation) return;
  const horizons = data.used_horizons ?? [];
  if (!horizons.length) {
    content.innerHTML = `<article data-testid="page-calibration">${head('Calibration unavailable', 'No calibration horizons are present in this export. Missing statistics are not zero.')}<button class="btn" id="retry-calibration">Retry local export</button></article>`;
    document.querySelector('#retry-calibration').addEventListener('click', () => { cache.delete('calibration'); route(); });
    return;
  }
  let horizon = horizons.includes(20) ? 20 : horizons[0];
  content.innerHTML = `<article data-testid="page-calibration">${head('Calibration', 'A risk score is only useful if it means what it says: on engines the model never saw, a predicted 10% risk should come true about one time in ten.')} ${provenance(data)}
    ${workspace('Calibration', `Next ${number(horizon)} cycles · engines the model never saw`, [['trust-metrics', 'Horizon scores'], ['calibration-reliability', 'Reliability chart'], ['calibration-subgroups', 'Wear-pattern subgroups'], ['calibration-values', 'Reliability values'], ['calibration-limits', 'Warning coverage']])}
    <div class="seg" role="group" aria-label="Risk horizon">${horizons.map(value => `<button data-h="${value}" aria-pressed="${value === horizon}">${value} cycles</button>`).join('')}</div><div id="trust-metrics"></div>
    <div class="two"><section class="panel" id="calibration-reliability"><h2>Predicted versus observed</h2><div id="calibration" class="chart" data-testid="chart-calibration"></div>${jumpLink('calibration-values', 'View reliability numeric values')}</section><section class="panel" id="calibration-subgroups"><h2>By wear-pattern subgroup</h2><div id="subgroups"></div></section></div>
    <details class="panel numeric-disclosure" id="calibration-values"><summary>Numeric reliability bins</summary><div id="reliability-table"></div></details><section class="panel" id="calibration-limits"><h2>Warning coverage</h2><p class="big-stat">${pct(data.missed_warnings?.assessable ? (data.missed_warnings.assessable - data.missed_warnings.missed) / data.missed_warnings.assessable : null, 1)}</p><p>of in-service failures were flagged before they happened (${number((data.missed_warnings?.assessable ?? 0) - (data.missed_warnings?.missed ?? 0))} of ${number(data.missed_warnings?.assessable)}).</p></section></article>`;
  let plotQueue = Promise.resolve();
  function render() {
    document.querySelector('#workspace-scope').textContent = `Next ${number(horizon)} cycles · engines the model never saw`;
    document.querySelectorAll('.seg button').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.h) === horizon)));
    const groups = [['All engine-cycles', data.all_cycles], ['Decision points', data.decision_points], ['Near threshold', data.near_threshold]];
    const chosen = groups.map(([label, records]) => ({label, record: records?.find(record => record.horizon === horizon)}));
    document.querySelector('#trust-metrics').innerHTML = `<section class="panel"><h2>Next ${number(horizon)} cycles · numeric scores</h2>${table(['Scope', 'Sample count', 'Brier score', 'Calibration gap (pp)'], chosen.map(({label, record}) => row([label, number(record?.count), number(record?.brier, 5), record?.ece == null ? 'Unavailable' : number(record.ece * 100, 3)])), 'Selected horizon scores')}</section>`;
    document.querySelector('#subgroups').innerHTML = table(['Wear pattern', 'Engine-cycles', 'Brier', 'Gap (pp)'], (data.subgroups ?? []).filter(record => record.horizon === horizon).map(record => row([esc({FD001: 'Compressor wear', FD003: 'Compressor + fan wear'}[record.subgroup] ?? record.subgroup), number(record.count), number(record.brier, 5), record.ece == null ? 'Unavailable' : number(record.ece * 100, 3)])), 'Subgroup calibration');
    document.querySelector('#reliability-table').innerHTML = table(['Scope / bin', 'Sample count', 'Mean prediction', 'Observed rate'], chosen.flatMap(({label, record}) => (record?.reliability ?? []).map((bin, index) => row([`${label} / ${index + 1}`, number(bin.count), pct(bin.prediction, 3), pct(bin.observed, 3)]))), 'Reliability bin values');
    const traces = [{x: [0, 1], y: [0, 1], mode: 'lines', line: {color: '#B3C0CB', dash: 'dot'}, name: 'Perfect calibration'}, ...chosen.filter(({record}) => record?.reliability?.length).map(({label, record}, index) => ({x: record.reliability.map(bin => bin.prediction), y: record.reliability.map(bin => bin.observed), mode: 'lines+markers', name: label, line: {color: ['#79B8D8', '#B7A9D1', '#93BBA7'][index]}}))];
    const selectedHorizon = horizon;
    plotQueue = plotQueue.then(() => current === generation && selectedHorizon === horizon ? plot('calibration', traces, {xaxis: {range: [0, 1], tickformat: '.0%', title: {text: 'Predicted probability'}}, yaxis: {range: [0, 1], tickformat: '.0%', title: {text: 'Observed failure rate'}}}) : undefined);
    return plotQueue;
  }
  document.querySelectorAll('.seg button').forEach(button => button.addEventListener('click', () => { horizon = Number(button.dataset.h); render().catch(error => { if (current === generation) document.querySelector('#calibration').textContent = `Chart unavailable: ${error.message}`; }); }));
  await render();
}

async function auditsPage(current) {
  const [data, summary, claims] = await Promise.all([load('audits'), load('summary'), load('claims').catch(() => null)]);
  if (current !== generation) return;
  const tests = data.tests;
  const scheduling = data.checker_violations == null ? undefined : data.checker_violations === 0;
  const mutations = data.mutations?.passed ?? (data.mutations?.caught != null && data.mutations?.total > 0 ? data.mutations.caught === data.mutations.total : undefined);
  const testStatus = tests?.failed == null || tests?.passed == null ? undefined : tests.failed === 0 && tests.passed > 0;
  content.innerHTML = `<article data-testid="page-audits">${head('Validation checks', 'Every schedule FleetSense produces is re-checked by an independent rule engine, and the model is tested against look-ahead and data leakage.')} ${provenance(data)}
    ${workspace('Validation checks', `${number(tests?.passed)} automated tests passing`, [['audit-checks', 'Checks'], ['audit-timing', 'Simulation speed']])}
    <section class="panel" id="audit-checks"><h2>Checks</h2>${table(['Check', 'Outcome', 'Evidence / scope'], [
      row(['Independent scheduling checker', recorded(scheduling), `${number(data.checker_violations)} violations; resource, duration, serial and failure-boundary checks`]),
      row(['Injected schedule mutations', recorded(mutations), `${number(data.mutations?.caught)} caught / ${number(data.mutations?.total)} total`]),
      row(['Poisoned-future decisions', recorded(data.poisoned_future?.passed), esc(data.poisoned_future?.evidence ?? 'Evidence description unavailable')]),
      row(['Engine-disjoint split', recorded(data.leakage?.disjointness_passed), `${number(data.leakage?.fitted_objects)} fitted objects; train / calibration / test separation`]),
      row(['Recorded automated suite', recorded(testStatus), `${number(tests?.passed)} passed / ${number(tests?.failed)} failed`])
    ], 'Recorded validation outcomes')}</section>
    <section class="panel" id="audit-timing"><h2>Simulation speed</h2><p class="muted">One simulated year on a laptop CPU, independent rule check included.</p>${table(['Airframes', 'Starts / day', 'Initial spares', 'Simulation / day (ms)', 'Simulation / year (s)', 'Checker (s)', 'Recorded check'], (data.scale ?? []).map(record => row([number(record.aircraft), number(record.capacity), number(record.spares), record.seconds_per_simulated_day == null ? 'Unavailable' : number(record.seconds_per_simulated_day * 1000, 4), number(record.wall_seconds, 4), number(record.checker_seconds, 4), recorded(record.passed)])), 'Recorded scale timings')}</section>
    </article>`;
  document.querySelector('#retry-claims')?.addEventListener('click', route);
}

async function route() {
  const current = ++generation;
  clearInterval(timer); timer = null;
  document.body.dataset.ready = '';
  const [slug = 'fleet', argument] = location.hash.replace(/^#\/?/, '').split('/');
  const page = routes.includes(slug) ? slug : 'fleet';
  document.querySelectorAll('[data-route]').forEach(link => { const active = link.dataset.route === page; link.classList.toggle('active', active); if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
  content.innerHTML = '<div class="loading" role="status">Loading local evidence…</div>';
  try {
    await ({fleet: () => fleetPage(current), engine: () => enginePage(current, argument ? decodeURIComponent(argument) : undefined), policies: () => policiesPage(current), calibration: () => calibrationPage(current), audits: () => auditsPage(current)}[page])();
    if (current !== generation) return;
    document.querySelector('#unit').textContent = 'Simulated squadron · 12 airframes';
    document.querySelector('#source').textContent = 'NASA C-MAPSS engine data · synthetic fleet';
    document.body.dataset.ready = page;
  } catch (error) {
    if (current !== generation) return;
    content.innerHTML = `<div class="error" data-testid="page-${page}" role="alert"><h1>Evidence unavailable</h1><p>${esc(error.message)}</p><button class="btn" id="retry">Retry local exports</button></div>`;
    document.querySelector('#retry').addEventListener('click', () => { cache.clear(); route(); });
    document.body.dataset.ready = page;
  }
}
content.addEventListener('click', event => {
  const trigger = event.target.closest('[data-jump]');
  if (!trigger) return;
  const target = document.getElementById(trigger.dataset.jump);
  if (!target) return;
  event.preventDefault();
  for (let container = target; container && container !== content; container = container.parentElement) if (container.tagName === 'DETAILS') container.open = true;
  target.setAttribute('tabindex', '-1');
  target.style.scrollMarginTop = `${(document.querySelector('.workspace-context')?.offsetHeight ?? 0) + 12}px`;
  target.focus({preventScroll: true});
  target.scrollIntoView({block: 'start', behavior: 'instant'});
});
window.addEventListener('hashchange', route);
route();
