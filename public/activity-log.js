/* Activity log (v1.3): who did what, when — marks, mark changes, Sync button, sync results.
   Reads table "activity_log" in Supabase through the client that claude-shim.js puts on window.HR_SB.
   Adds an "Activity log" button next to "Sync leads now" and opens a full-height panel. */
(function () {
  var ACTIONS = {
    mark: 'Marked',
    mark_changed: 'Changed mark',
    mark_edited: 'Edited reason',
    mark_imported: 'Mark (before log)',
    sync_button: 'Pressed Sync',
    sync_done: 'Sync finished',
    sync_failed: 'Sync failed',
    transfer: 'Transferred to dashboard',
    transfer_changed: 'Transfer changed',
    transfer_undo: 'Transfer undone'
  };
  var VERDICT = { fit: 'Fit', unfit: 'Unfit' };
  var LEVEL = { unsuitable: 'Unsuitable', check: 'Check', medium: 'Medium', strong: 'Strong' };   // v1.7 transfers
  var TZ = 'Asia/Kolkata';
  var rows = [], loaded = false, loading = false, live = null, els = {};

  var css = [
    '.alog-scrim{position:fixed;inset:0;background:rgba(10,18,16,.45);z-index:30}',
    '.alog{position:fixed;top:0;right:0;bottom:0;width:min(1100px,100%);background:var(--surface);color:var(--fg);z-index:31;box-shadow:var(--shadow);display:flex;flex-direction:column;font-family:var(--body);font-size:14px}',
    '.alog[hidden],.alog-scrim[hidden]{display:none}',
    '.alog-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px 8px}',
    '.alog-head h2{font-family:var(--display);font-size:20px;margin:0}',
    '.alog-head .alog-count{color:var(--muted);font-size:12.5px;margin-left:10px;font-weight:500}',
    '.alog-x{font:inherit;font-size:22px;line-height:1;border:1px solid var(--line);background:var(--surface);color:var(--fg);border-radius:999px;width:36px;height:36px;cursor:pointer}',
    '.alog-filters{display:flex;flex-wrap:wrap;gap:8px;padding:4px 20px 12px;border-bottom:1px solid var(--line)}',
    '.alog-filters input,.alog-filters select{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--surface);color:var(--fg);border-radius:8px;padding:7px 10px;min-height:36px}',
    '.alog-filters input{flex:1 1 220px;min-width:0}',
    '.alog-filters button{font:inherit;font-weight:700;font-size:13px;border:1px solid var(--accent);background:var(--surface);color:var(--accent);border-radius:999px;padding:7px 14px;cursor:pointer}',
    '.alog-wrap{flex:1;overflow:auto;padding:0 20px 20px}',
    '.alog table{width:100%;min-width:860px;border-collapse:collapse;font-size:13px}',
    '.alog th{position:sticky;top:0;background:var(--surface);text-align:left;font-size:12px;color:var(--muted);font-weight:700;padding:10px 8px;border-bottom:1px solid var(--line)}',
    '.alog td{background:none;border-left:0;border-right:0;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}',
    '.alog td.alog-when{white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--muted)}',
    '.alog td.alog-who{font-weight:600}',
    '.alog small{display:block;color:var(--muted);font-size:12px}',
    '.alog .alog-chip{display:inline-block;white-space:nowrap;font-size:12px;font-weight:700;border-radius:999px;padding:2px 9px;background:var(--sunk);color:var(--muted)}',
    '.alog .alog-chip.alog-a-mark,.alog .alog-chip.alog-a-mark_changed,.alog .alog-chip.alog-a-mark_edited{background:var(--accent-soft);color:var(--accent)}',
    '.alog .alog-chip.alog-a-sync_done{background:var(--green-soft);color:var(--green)}',
    '.alog .alog-chip.alog-a-sync_failed{background:var(--red-soft);color:var(--red)}',
    '.alog .alog-chip.alog-a-sync_button{background:var(--yellow-soft);color:var(--yellow)}',
    '.alog .alog-v-fit{color:var(--green);font-weight:700}.alog .alog-v-unfit{color:var(--red);font-weight:700}',
    '.alog .alog-chip.alog-a-transfer,.alog .alog-chip.alog-a-transfer_changed{background:var(--accent);color:var(--on-accent)}',
    '.alog .alog-chip.alog-a-transfer_undo{background:var(--sunk);color:var(--muted);border:1px solid var(--line)}',
    '.alog .alog-lv-check{color:var(--orange);font-weight:700}.alog .alog-lv-medium{color:var(--yellow);font-weight:700}.alog .alog-lv-strong{color:var(--green);font-weight:700}.alog .alog-lv-unsuitable{color:var(--muted);font-weight:700}',
    '.alog .alog-reason{max-width:320px;overflow-wrap:anywhere}',
    '.alog-msg{color:var(--muted);padding:24px 0}',
    '@media (max-width:640px){.alog-head,.alog-filters{padding-left:16px;padding-right:16px}.alog-wrap{padding:0 16px 16px}}'
  ].join('\n');

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function when(iso) {
    try {
      return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true, timeZone: TZ });
    } catch (e) { return iso || ''; }
  }
  function dayKey(d) { return d.toLocaleDateString('en-CA', { timeZone: TZ }); } // YYYY-MM-DD in IST
  function vword(v) { return VERDICT[v] || LEVEL[v] || v || ''; }
  function change(r) {
    if (r.action === 'mark' || r.action === 'mark_imported') return '<span class="alog-v-' + esc(r.new_value) + '">' + esc(vword(r.new_value)) + '</span>';
    if (r.action === 'mark_changed') return '<span class="alog-v-' + esc(r.old_value) + '">' + esc(vword(r.old_value)) + '</span> → <span class="alog-v-' + esc(r.new_value) + '">' + esc(vword(r.new_value)) + '</span>';
    if (r.action === 'mark_edited') return '<span class="alog-v-' + esc(r.new_value) + '">' + esc(vword(r.new_value)) + '</span> <small>reason edited</small>';
    if (r.action === 'transfer' || r.action === 'transfer_changed' || r.action === 'transfer_undo') {
      return '<span class="alog-lv-' + esc(r.old_value) + '">' + esc(vword(r.old_value)) + '</span> → <span class="alog-lv-' + esc(r.new_value) + '">' + esc(vword(r.new_value)) + '</span>' +
        (r.pos && r.action !== 'transfer_undo' ? '<small>as ' + esc(r.pos) + '</small>' : '');
    }
    return esc(r.new_value);
  }

  function build() {
    var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="alog-scrim" hidden></div>' +
      '<section class="alog" role="dialog" aria-modal="true" aria-labelledby="alogTitle" hidden>' +
      '<div class="alog-head"><h2 id="alogTitle">Activity log<span class="alog-count"></span></h2>' +
      '<button type="button" class="alog-x" aria-label="Close activity log">×</button></div>' +
      '<div class="alog-filters">' +
      '<input type="search" class="alog-q" placeholder="Search candidate, phone, position, reason" aria-label="Search the log">' +
      '<select class="alog-who" aria-label="Person"><option value="">Everyone</option></select>' +
      '<select class="alog-act" aria-label="Action"><option value="">All actions</option></select>' +
      '<select class="alog-per" aria-label="Period"><option value="all">All time</option><option value="today">Today</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option></select>' +
      '<button type="button" class="alog-csv">Download CSV</button>' +
      '</div><div class="alog-wrap"><div class="alog-msg">Loading…</div></div></section>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
    els.scrim = document.querySelector('.alog-scrim');
    els.panel = document.querySelector('.alog');
    els.count = els.panel.querySelector('.alog-count');
    els.body = els.panel.querySelector('.alog-wrap');
    els.q = els.panel.querySelector('.alog-q');
    els.who = els.panel.querySelector('.alog-who');
    els.act = els.panel.querySelector('.alog-act');
    els.per = els.panel.querySelector('.alog-per');
    els.close = els.panel.querySelector('.alog-x');
    Object.keys(ACTIONS).forEach(function (k) {
      var o = document.createElement('option'); o.value = k; o.textContent = ACTIONS[k]; els.act.appendChild(o);
    });
    els.close.onclick = close;
    els.scrim.onclick = close;
    [els.q, els.who, els.act, els.per].forEach(function (el) { el.addEventListener('input', render); });
    els.panel.querySelector('.alog-csv').onclick = csv;
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !els.panel.hidden) close(); });
  }

  function filtered() {
    var q = els.q.value.trim().toLowerCase(), who = els.who.value, act = els.act.value, per = els.per.value;
    var today = dayKey(new Date()), since = per === '7' || per === '30' ? Date.now() - Number(per) * 864e5 : 0;
    return rows.filter(function (r) {
      if (who && r.who !== who) return false;
      if (act && r.action !== act) return false;
      if (per === 'today' && dayKey(new Date(r.at)) !== today) return false;
      if (since && Date.parse(r.at) < since) return false;
      if (q && [r.cand, r.phone, r.pos, r.reason, r.who, r.new_value].join(' ').toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
  }

  function fillPeople() {
    var cur = els.who.value, names = {};
    rows.forEach(function (r) { if (r.who) names[r.who] = 1; });
    els.who.innerHTML = '<option value="">Everyone</option>' + Object.keys(names).sort().map(function (n) {
      return '<option' + (n === cur ? ' selected' : '') + '>' + esc(n) + '</option>';
    }).join('');
  }

  function render() {
    if (!loaded) return;
    var list = filtered();
    els.count.textContent = ' · ' + list.length + (list.length === rows.length ? '' : ' of ' + rows.length) + ' entries';
    if (!list.length) { els.body.innerHTML = '<div class="alog-msg">' + (rows.length ? 'No entries match these filters.' : 'No activity yet. Marks and syncs will appear here.') + '</div>'; return; }
    var shown = list.slice(0, 500);
    els.body.innerHTML = '<table><thead><tr><th>When (IST)</th><th>Who</th><th>Action</th><th>Candidate</th><th>Position / roles</th><th>Change</th><th>Reason / details</th></tr></thead><tbody>' +
      shown.map(function (r) {
        var oldReason = r.action === 'mark_edited' && r.detail && r.detail.old_reason ? '<small>Before: ' + esc(r.detail.old_reason) + '</small>' : '';
        var step = r.action === 'sync_failed' && r.detail && r.detail.step ? '<small>Step: ' + esc(r.detail.step) + '</small>' : '';
        return '<tr><td class="alog-when">' + esc(when(r.at)) + '</td><td class="alog-who">' + esc(r.who || '—') + '</td>' +
          '<td><span class="alog-chip alog-a-' + esc(r.action) + '">' + esc(ACTIONS[r.action] || r.action) + '</span></td>' +
          '<td>' + esc(r.cand) + (r.phone ? '<small>' + esc(r.phone) + '</small>' : '') + '</td>' +
          '<td>' + esc(r.pos) + '</td><td>' + change(r) + '</td>' +
          '<td class="alog-reason">' + esc(r.reason) + oldReason + step + '</td></tr>';
      }).join('') + '</tbody></table>' +
      (list.length > shown.length ? '<div class="alog-msg">Showing the newest 500. Narrow the filters or download the CSV for all ' + list.length + '.</div>' : '');
  }

  async function load() {
    var sb = window.HR_SB; if (!sb || loading) return;
    loading = true;
    try {
      var all = [], from = 0, size = 1000;
      for (;;) {
        var r = await sb.from('activity_log').select('*').order('at', { ascending: false }).range(from, from + size - 1);
        if (r.error) throw r.error;
        all = all.concat(r.data || []);
        if (!r.data || r.data.length < size || all.length >= 20000) break;
        from += size;
      }
      rows = all; loaded = true; fillPeople(); render();
    } catch (e) {
      els.body.innerHTML = '<div class="alog-msg">Could not load the log: ' + esc(e && e.message) + '. If it says the table does not exist, run sql/v1.3_activity_log.sql in Supabase.</div>';
    } finally { loading = false; }
    if (!live) {
      live = sb.channel('activity-log-' + Math.random().toString(36).slice(2))
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'activity_log' }, function (p) {
          if (!p || !p.new || rows.some(function (x) { return x.id === p.new.id; })) return;
          rows.unshift(p.new); fillPeople(); render();
        }).subscribe();
    }
  }

  function csv() {
    var head = ['When (IST)', 'Who', 'Action', 'Candidate', 'Phone', 'Position / roles', 'From', 'To', 'Reason'];
    var q = function (v) { return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'; };
    var lines = [head.map(q).join(',')].concat(filtered().map(function (r) {
      return [when(r.at), r.who, ACTIONS[r.action] || r.action, r.cand, r.phone, r.pos,
              vword(r.old_value), vword(r.new_value), r.reason].map(q).join(',');
    }));
    var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'activity-log-' + dayKey(new Date()) + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
  }

  var lastFocus = null;
  function open() {
    lastFocus = document.activeElement;
    els.scrim.hidden = false; els.panel.hidden = false; els.close.focus();
    load();
  }
  function close() {
    els.scrim.hidden = true; els.panel.hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function addButton() {
    var box = document.getElementById('syncBox');
    if (!box || document.getElementById('alogBtn')) return;
    var b = document.createElement('button');
    b.type = 'button'; b.id = 'alogBtn'; b.textContent = 'Activity log';
    b.onclick = open;
    box.insertBefore(b, box.firstChild);
  }

  function start() {
    if (!window.HR_SB) return; // Supabase not configured: no log
    build(); addButton();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
