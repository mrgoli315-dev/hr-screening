/* Stand-in for the Claude artifact runtime (window.claude.use) so the page runs unchanged on Vercel.
   db        -> Supabase table "docs" (collection, id, data), live updates + 60 s refresh
   user      -> null  (the page then shows its "Marked by" name list)
   downloads -> browser file download
   mcp       -> POST /api/sync, which starts the GitHub Actions sync                       */
(function () {
  var cfg = window.HR_CONFIG || {};
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY || !window.supabase || !window.supabase.createClient) {
    console.warn('HR page: Supabase not configured - marks and sync are switched off');
    return;
  }
  var sb = window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY);

  function fail(code, message) { var e = new Error(message || code); e.code = code; return e; }

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
            var r = await sb.from('docs').upsert({ collection: col, id: id, data: body, updated_at: new Date().toISOString() });
            if (r.error) throw fail('write_failed', r.error.message);
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
      var r;
      try { r = await fetch('/api/sync', { method: 'POST' }); }
      catch (e) { throw fail('tool_error', 'Could not reach /api/sync'); }
      if (!r.ok) { var t = ''; try { t = await r.text(); } catch (e) {} throw fail('tool_error', t.slice(0, 200) || ('HTTP ' + r.status)); }
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
