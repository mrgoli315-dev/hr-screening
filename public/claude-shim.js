/* Stand-in for the Claude artifact runtime (window.claude.use) so the page runs unchanged on Vercel.
   db        -> Supabase table "docs" (collection, id, data), live updates + 60 s refresh
                collections: "verdicts" (Fit/Unfit marks), "runs" (sync status), "overrides" (v1.7: Unsuitable -> dashboard transfers);
                every mark, transfer and undo also adds one Activity log row
   user      -> null  (the page then shows its "Marked by" name list)
   downloads -> browser file download
   mcp       -> POST /api/sync, which starts the GitHub Actions sync                       */
(function () {
  var cfg = window.HR_CONFIG || {};
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY || !window.supabase || !window.supabase.createClient) {
    console.warn('HR page: Supabase not configured - marks and sync are switched off');
    return;
  }
  // Accept the Project URL with or without a trailing "/rest/v1/" (supabase-js adds it itself).
  var baseUrl = String(cfg.SUPABASE_URL).trim().replace(/\/+$/, '').replace(/\/rest\/v1$/, '');
  var sb = window.supabase.createClient(baseUrl, cfg.SUPABASE_ANON_KEY);

  window.HR_SB = sb; // used by activity-log.js

  function fail(code, message) { var e = new Error(message || code); e.code = code; return e; }

  // Activity log (v1.3): one row per action. A failed log write never blocks the action itself.
  async function logAction(row) {
    try {
      var r = await sb.from('activity_log').insert(row);
      if (r.error) console.warn('activity log:', r.error.message);
    } catch (e) { console.warn('activity log:', e && e.message); }
  }
  function myName() {
    try { return localStorage.getItem('hf_hr') || ''; } catch (e) { return ''; }
  }

  async function logVerdict(id, before, body) {
    var action = !before ? 'mark'
      : before.verdict !== body.verdict ? 'mark_changed'
      : 'mark_edited';
    await logAction({
      who: body.hr || '', action: action,
      cand: body.cand || '', phone: body.phone || '', pos: body.pos || '',
      old_value: before ? (before.verdict || '') : '', new_value: body.verdict || '',
      reason: body.reason || '',
      detail: { doc_id: id, src: body.src || '', level: body.level || '',
                old_reason: before ? (before.reason || '') : '', old_by: before ? (before.hr || '') : '' }
    });
  }

  // v1.7 transfers (Unsuitable page -> dashboard): one log row per transfer / change / undo
  async function logTransfer(id, before, body) {
    await logAction({
      who: body.hr || '', action: before ? 'transfer_changed' : 'transfer',
      cand: body.cand || '', phone: body.phone || '', pos: (body.ro || []).join(', '),
      old_value: before ? (before.lv || '') : 'unsuitable', new_value: body.lv || '',
      reason: body.reason || '',
      detail: { doc_id: id, src: body.src || '', form: body.form || '', st: body.st || '', why: body.why || '',
                old_roles: before ? (before.ro || []) : [], old_reason: before ? (before.reason || '') : '', old_by: before ? (before.hr || '') : '' }
    });
  }
  async function logUndo(id, before) {
    await logAction({
      who: myName() || 'Unknown (no name chosen yet)', action: 'transfer_undo',
      cand: before.cand || '', phone: before.phone || '', pos: (before.ro || []).join(', '),
      old_value: before.lv || '', new_value: 'unsuitable', reason: before.reason || '',
      detail: { doc_id: id, src: before.src || '', transferred_by: before.hr || '', transferred_at: before.at || '' }
    });
  }
  var LOGGED = { verdicts: true, overrides: true };
  async function readBefore(col, id) {
    if (!LOGGED[col]) return null;
    try {
      var o = await sb.from('docs').select('data').eq('collection', col).eq('id', id).maybeSingle();
      return o.data ? o.data.data : null;
    } catch (e) { return null; }
  }

  async function loadAll(col) {
    var rows = [], from = 0, size = 1000;
    for (;;) {
      var r = await sb.from('docs').select('id,data').eq('collection', col).order('id').range(from, from + size - 1);
      if (r.error) throw fail('read_failed', r.error.message);
      rows = rows.concat(r.data || []);
      if (!r.data || r.data.length < size) break;
      from += size;
    }
    return rows;
  }

  function snapshot(rows) {
    return { docs: rows.map(function (row) { return { id: row.id, data: function () { return row.data; } }; }) };
  }

  function collection(col) {
    return {
      doc: function (id) {
        return {
          set: async function (body) {
            var before = await readBefore(col, id);
            var r = await sb.from('docs').upsert({ collection: col, id: id, data: body, updated_at: new Date().toISOString() });
            if (r.error) throw fail('write_failed', r.error.message);
            if (col === 'verdicts') await logVerdict(id, before, body);
            if (col === 'overrides') await logTransfer(id, before, body);
          },
          delete: async function () {
            var before = await readBefore(col, id);
            var r = await sb.from('docs').delete().eq('collection', col).eq('id', id);
            if (r.error) throw fail('write_failed', r.error.message);
            if (col === 'overrides' && before) await logUndo(id, before);
          },
          get: async function () {
            var r = await sb.from('docs').select('id,data').eq('collection', col).eq('id', id).maybeSingle();
            if (r.error) throw fail('read_failed', r.error.message);
            return { id: id, exists: !!r.data, data: function () { return r.data ? r.data.data : undefined; } };
          }
        };
      },
      onSnapshot: function (onNext, onError) {
        var stopped = false, busy = false, again = false;
        function refresh() {
          if (busy) { again = true; return; }
          busy = true;
          loadAll(col).then(function (rows) { if (!stopped) onNext(snapshot(rows)); })
            .catch(function (e) { if (onError) onError(e); })
            .finally(function () { busy = false; if (again) { again = false; refresh(); } });
        }
        refresh();
        var ch = sb.channel('docs-' + col + '-' + Math.random().toString(36).slice(2))
          .on('postgres_changes', { event: '*', schema: 'public', table: 'docs', filter: 'collection=eq.' + col }, refresh)
          .subscribe();
        var timer = setInterval(refresh, 60000);
        return function () { stopped = true; clearInterval(timer); sb.removeChannel(ch); };
      }
    };
  }

  var db = { collection: collection };

  var downloads = {
    save: async function (o) {
      var blob = new Blob([o.data], { type: o.mimeType || 'text/csv;charset=utf-8' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = o.filename || 'download.csv';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
    }
  };

  var mcp = {
    callTool: async function () {
      var r, who = myName() || 'Unknown (no name chosen yet)';
      try { r = await fetch('/api/sync', { method: 'POST' }); }
      catch (e) {
        await logAction({ who: who, action: 'sync_button', new_value: 'failed', reason: 'Could not reach /api/sync' });
        throw fail('tool_error', 'Could not reach /api/sync');
      }
      if (!r.ok) {
        var t = ''; try { t = await r.text(); } catch (e) {}
        await logAction({ who: who, action: 'sync_button', new_value: 'failed', reason: (t.slice(0, 200) || ('HTTP ' + r.status)) });
        throw fail('tool_error', t.slice(0, 200) || ('HTTP ' + r.status));
      }
      await logAction({ who: who, action: 'sync_button', new_value: 'started' });
      return { ok: true };
    }
  };

  window.claude = {
    use: async function (name) {
      if (name === 'db') return db;
      if (name === 'downloads') return downloads;
      if (name === 'mcp') return mcp;
      return null; // user and anything else
    }
  };
})();
