// Chat panel for the catalog agent (product/agent): a launcher button and a right-hand drawer on every OM page.
// Talks to /agent/* on the same origin, sending the signed-in user's OM token, so the agent acts with their rights.
(function () {
  var SUGGESTIONS = [
    'How do we decide a contract is overdue, and how are its days past due counted?',
    'Where does the 91–180 days figure in September’s Overdue Loans Report come from, and did it pass its checks?',
    'I need customers’ PINFL with their overdue status — where is it, and may I use it?',
    'Document this table.'
  ];
  var STORE = 'agi-chat';

  // The token OM's own API calls carry: always current, and the only copy when the browser refuses OM's service
  // worker (OM then keeps the token in memory only).
  var seenToken = null;
  var setHeader = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
    if (/^authorization$/i.test(name) && /^Bearer \S+/.test(value)) seenToken = value.slice(7);
    return setHeader.apply(this, arguments);
  };

  // Otherwise OM keeps the session token in IndexedDB AppDataStore/keyValueStore/app_state (written by its service
  // worker). Read it fresh on every request and never refresh it ourselves (OM rotates the refresh token).
  function getToken() {
    if (seenToken) return Promise.resolve(seenToken);
    return new Promise(function (resolve) {
      var req;
      try { req = indexedDB.open('AppDataStore'); } catch (e) { return resolve(null); }
      req.onerror = function () { resolve(null); };
      req.onupgradeneeded = function () { req.transaction.abort(); resolve(null); };
      req.onsuccess = function () {
        var db = req.result;
        try {
          var get = db.transaction('keyValueStore', 'readonly').objectStore('keyValueStore').get('app_state');
          get.onsuccess = function () {
            db.close();
            try { resolve((JSON.parse(get.result || '{}') || {}).primary || null); } catch (e) { resolve(null); }
          };
          get.onerror = function () { db.close(); resolve(null); };
        } catch (e) { db.close(); resolve(null); }
      };
    });
  }

  // ---- minimal markdown: escape first, then a small safe subset (headings, lists, code, bold, italics, links) ----
  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Small highlighter: SQL keywords and functions; strings, numbers and comments for any language. Every piece is
  // escaped, so model output cannot inject markup.
  var SQL_KW = ('select from where and or not in is null as on join left right inner outer full cross group by order ' +
    'having limit offset union all distinct case when then else end with over partition window asc desc between like ' +
    'ilike exists insert into values update set delete create table view drop alter coalesce nullif cast date ' +
    'interval true false filter lateral using any some').split(' ');
  var SQL_SET = {};
  SQL_KW.forEach(function (k) { SQL_SET[k] = 1; });

  function highlight(code, lang) {
    var sql = /^(sql|pgsql|postgres(ql)?|greenplum|)$/i.test(lang) && /\b(select|with|from)\b/i.test(code);
    var re = sql
      ? /(--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^']|'')*')|("(?:[^"])*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()|([A-Za-z_][A-Za-z0-9_]*)|(::?|[<>=!]=?|[-+*\/%|])/g
      : /(#[^\n]*|\/\/[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^'\\]|\\.)*')|("(?:[^"\\]|\\.)*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()|([A-Za-z_][A-Za-z0-9_]*)|(\0)/g;
    var out = '', last = 0, m;
    while ((m = re.exec(code))) {
      out += esc(code.slice(last, m.index));
      var t = esc(m[0]), cls = m[1] ? 'c' : (m[2] || m[3]) ? 's' : m[4] ? 'n' : m[5] ? 'f' : m[7] ? 'o'
        : (m[6] && sql && SQL_SET[m[6].toLowerCase()]) ? 'k' : '';
      if (cls === 'f' && sql && SQL_SET[m[5].toLowerCase()]) cls = 'k';
      out += cls ? '<span class="agi-hl-' + cls + '">' + t + '</span>' : t;
      last = re.lastIndex;
    }
    return out + esc(code.slice(last));
  }

  function catalogHref(name) {
    var m = /^(\w+\.\w+\.\w+\.\w+)(\.\w+)?$/.exec(name);  // service.database.schema.table[.column]
    if (m && /^greenplum\.|^iabs\.|^tranzaxis\.|^mobile\./.test(name)) return '/table/' + encodeURIComponent(m[1]);
    if (/^banking\.[^.]+$/.test(name)) return '/glossary/' + encodeURIComponent(name);
    return null;
  }

  function inline(s) {
    var codes = [];
    s = s.replace(/`([^`]+)`/g, function (_, c) {
      var href = catalogHref(c);
      codes.push(href ? '<a class="agi-ent" href="' + href + '"><code>' + esc(c) + '</code></a>' : '<code>' + esc(c) + '</code>');
      return '\u0000' + (codes.length - 1) + '\u0000';
    });
    s = esc(s)
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>')
      .replace(/(^|[^\w])_([^_\n]+)_(?!\w)/g, '$1<em>$2</em>')
      .replace(/\[([^\]]+)\]\((\/[^)\s]*|https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s.replace(/\u0000(\d+)\u0000/g, function (_, i) { return codes[+i]; });
  }

  function markdown(src) {
    var out = [], lines = src.replace(/\r/g, '').split('\n'), i = 0, list = null;
    function closeList() { if (list) { out.push('</' + list + '>'); list = null; } }
    while (i < lines.length) {
      var line = lines[i], m;
      if (/^```/.test(line)) {
        closeList();
        var lang = line.slice(3).trim(), code = [];
        for (i++; i < lines.length && !/^```/.test(lines[i]); i++) code.push(lines[i]);
        i++;
        out.push('<div class="agi-code"><button class="agi-copy" type="button">Copy</button><pre data-lang="' + esc(lang) +
          '"><code>' + highlight(code.join('\n'), lang) + '</code></pre></div>');
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        closeList();
        var row = function (l) { return l.trim().replace(/^\||\|$/g, '').split('|').map(function (c) { return inline(c.trim()); }); };
        var head = row(line), body = [];
        for (i += 2; i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i]); i++) body.push(row(lines[i]));
        out.push('<div class="agi-table"><table><thead><tr><th>' + head.join('</th><th>') + '</th></tr></thead><tbody>' +
          body.map(function (r) { return '<tr><td>' + r.join('</td><td>') + '</td></tr>'; }).join('') + '</tbody></table></div>');
        continue;
      }
      if ((m = /^(#{1,4})\s+(.*)$/.exec(line))) { closeList(); out.push('<h4>' + inline(m[2]) + '</h4>'); i++; continue; }
      if ((m = /^\s*[-*]\s+(.*)$/.exec(line)) || (m = /^\s*\d+[.)]\s+(.*)$/.exec(line))) {
        var kind = /^\s*\d/.test(line) ? 'ol' : 'ul';
        if (list !== kind) { closeList(); out.push('<' + kind + '>'); list = kind; }
        out.push('<li>' + inline(m[1]) + '</li>'); i++; continue;
      }
      if (!line.trim()) { closeList(); i++; continue; }
      closeList();
      var para = [line];
      for (i++; i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|\s*[-*]\s|\s*\d+[.)]\s|\s*\|)/.test(lines[i]); i++) para.push(lines[i]);
      out.push('<p>' + inline(para.join('\n')).replace(/\n/g, '<br>') + '</p>');
    }
    closeList();
    return out.join('');
  }

  // ---- UI ----
  var root, log, input, sendBtn, busy = false;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function state() {
    try { return JSON.parse(sessionStorage.getItem(STORE)) || {}; } catch (e) { return {}; }
  }

  function save(patch) {
    var s = state();
    for (var k in patch) s[k] = patch[k];
    try { sessionStorage.setItem(STORE, JSON.stringify(s)); } catch (e) {}
  }

  function conversationId() {
    var s = state();
    if (!s.conversation) {
      s.conversation = 'c-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      save({ conversation: s.conversation });
    }
    return s.conversation;
  }

  function persist() { save({ html: log.innerHTML }); }

  function scroll() { log.scrollTop = log.scrollHeight; }

  function build() {
    root = el('div', 'agi-chat');
    root.innerHTML =
      '<button class="agi-launch" type="button" title="Ask the data assistant">' +
      '<span class="agi-spark">✦</span><span>Ask AI</span></button>' +
      '<aside class="agi-drawer" aria-label="Data assistant"><div class="agi-resize" title="Drag to resize"></div>' +
      '<header><span class="agi-avatar">✦</span><div><strong>Data Assistant</strong>' +
      '<small>AI over the bank’s catalog · acts with your access rights</small></div>' +
      '<button class="agi-new" type="button" title="New conversation">New chat</button>' +
      '<button class="agi-close" type="button" title="Close">✕</button></header>' +
      '<div class="agi-log"></div>' +
      '<form class="agi-form"><textarea rows="2" placeholder="Ask about the bank’s data…"></textarea>' +
      '<button type="submit">Send</button></form></aside>';
    document.body.appendChild(root);
    log = root.querySelector('.agi-log');
    input = root.querySelector('textarea');
    sendBtn = root.querySelector('.agi-form button');

    root.querySelector('.agi-launch').onclick = function () { open(true); };
    root.querySelector('.agi-close').onclick = function () { open(false); };
    resizable(root.querySelector('.agi-drawer'), root.querySelector('.agi-resize'));
    root.querySelector('.agi-new').onclick = function () {
      if (busy) return;
      save({ conversation: null, html: '' });
      log.innerHTML = '';
      welcome();
    };
    root.querySelector('.agi-form').onsubmit = function (e) { e.preventDefault(); send(input.value); };
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
    });
    log.addEventListener('click', onLogClick);

    var s = state();
    if (s.html) { log.innerHTML = s.html; } else { welcome(); }
    open(!!s.open);
  }

  // Drag the drawer's left edge; the width is remembered in this browser.
  var WIDTH_KEY = 'agi-chat-width';

  function resizable(drawer, handle) {
    function clamp(w) { return Math.max(360, Math.min(w, window.innerWidth - 72)); }
    function apply(w) { drawer.style.width = clamp(w) + 'px'; }
    try { var saved = +localStorage.getItem(WIDTH_KEY); if (saved) apply(saved); } catch (e) {}
    handle.addEventListener('pointerdown', function (e) {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      root.classList.add('agi-resizing');
      function move(ev) { apply(window.innerWidth - ev.clientX); }
      function up() {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        root.classList.remove('agi-resizing');
        try { localStorage.setItem(WIDTH_KEY, parseInt(drawer.style.width, 10)); } catch (e) {}
      }
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });
    handle.addEventListener('dblclick', function () {
      drawer.style.width = '';
      try { localStorage.removeItem(WIDTH_KEY); } catch (e) {}
    });
    window.addEventListener('resize', function () { if (drawer.style.width) apply(parseInt(drawer.style.width, 10)); });
  }

  function open(on) {
    root.classList.toggle('agi-open', on);
    save({ open: on });
    if (on) { setTimeout(function () { input.focus(); }, 50); scroll(); }
  }

  function welcome() {
    var w = el('div', 'agi-welcome', '<div class="agi-hero"><span class="agi-avatar agi-big">✦</span>' +
      '<h3>Ask anything about the bank’s data</h3><p>How a figure is computed, where it comes from, whether it ' +
      'passed its checks, whether you may use it — or open a table and ask me to document it.</p></div>');
    SUGGESTIONS.forEach(function (q) {
      var b = el('button', 'agi-suggest');
      b.type = 'button';
      b.textContent = q;
      w.appendChild(b);
    });
    log.appendChild(w);
  }

  function onLogClick(e) {
    var t = e.target;
    if (t.classList.contains('agi-suggest')) { send(t.textContent); return; }
    if (t.classList.contains('agi-copy')) {
      var code = t.parentNode.querySelector('code').textContent;
      navigator.clipboard && navigator.clipboard.writeText(code).then(function () {
        t.textContent = 'Copied'; setTimeout(function () { t.textContent = 'Copy'; }, 1500);
      });
      return;
    }
    if (t.dataset && t.dataset.decide) { decide(t.closest('.agi-proposal'), t.dataset.decide); }
  }

  function addUser(text) {
    var welcomeBox = log.querySelector('.agi-welcome');
    if (welcomeBox) welcomeBox.remove();
    log.appendChild(el('div', 'agi-msg agi-user', esc(text).replace(/\n/g, '<br>')));
  }

  function proposalCard(p) {
    var card = el('div', 'agi-proposal');
    card.dataset.id = p.id;
    var rows = (p.changes || []).map(function (c) {
      return '<li><code>' + esc(c.column || '(table)') + '</code>' + markdown(c.description || '') + '</li>';
    }).join('');
    card.innerHTML = '<div class="agi-p-head"><span class="agi-badge">Proposed change ' + esc(p.id) + '</span>' +
      '<a class="agi-ent" href="' + (catalogHref(p.fqn) || '#') + '"><code>' + esc(p.fqn) + '</code></a></div>' +
      '<p>' + esc(p.summary || '') + '</p><details open><summary>' + (p.changes || []).length +
      ' description(s)</summary><ul>' + rows + '</ul></details>' +
      '<div class="agi-p-actions"><button type="button" data-decide="apply">Apply</button>' +
      '<button type="button" class="agi-secondary" data-decide="discard">Discard</button>' +
      '<span class="agi-p-status"></span></div>';
    return card;
  }

  function decide(card, action) {
    var status = card.querySelector('.agi-p-status');
    card.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
    status.textContent = action === 'apply' ? 'Applying…' : 'Discarding…';
    getToken().then(function (token) {
      if (!token) throw new Error('Sign in to the catalog first.');
      return fetch('/agent/proposals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ proposal_id: card.dataset.id, action: action })
      });
    }).then(function (r) {
      if (r.status === 401) seenToken = null;
      return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail || ('HTTP ' + r.status)); return j; });
    }).then(function (j) {
      card.classList.add('agi-' + j.status);
      status.textContent = j.status === 'applied' ? '✓ Applied — reload the page to see it' : j.message;
      card.querySelector('.agi-p-actions').querySelectorAll('button').forEach(function (b) { b.remove(); });
      persist();
    }).catch(function (err) {
      status.textContent = err.message;
      card.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
    });
  }

  function send(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    busy = true;
    sendBtn.disabled = true;
    input.value = '';
    addUser(text);

    var reply = el('div', 'agi-msg agi-bot');
    var steps = el('div', 'agi-steps');
    var body = el('div', 'agi-body');
    var meta = el('div', 'agi-meta');
    reply.appendChild(steps);
    reply.appendChild(body);
    reply.appendChild(meta);
    log.appendChild(reply);
    var thinking = el('div', 'agi-step agi-live', 'Thinking…');
    steps.appendChild(thinking);
    scroll();

    var answer = '', pending = 0;
    function render() { body.innerHTML = markdown(answer); }
    function frame() { if (!pending) pending = requestAnimationFrame(function () { pending = 0; render(); scroll(); }); }
    function liveDone() { steps.querySelectorAll('.agi-live').forEach(function (s) { s.classList.remove('agi-live'); }); }

    function handle(type, d) {
      if (type === 'text') {
        if (thinking) { thinking.remove(); thinking = null; }
        liveDone();
        answer += d.text;
        frame();
      } else if (type === 'tool') {
        if (thinking) { thinking.remove(); thinking = null; }
        steps.appendChild(el('div', 'agi-step agi-live', esc(d.label)));
        scroll();
      } else if (type === 'proposal') {
        liveDone();
        reply.insertBefore(proposalCard(d), body);
        scroll();
      } else if (type === 'error') {
        liveDone();
        body.appendChild(el('div', 'agi-error', esc(d.message)));
      } else if (type === 'done') {
        liveDone();
        var n = (d.tool_calls || []).length;
        meta.textContent = n + ' catalog lookup' + (n === 1 ? '' : 's') + ' · ' + d.seconds.toFixed(1) + ' s · $' +
          d.cost_usd.toFixed(4) + ' · ' + d.model;
      }
    }

    getToken().then(function (token) {
      if (!token) throw new Error('Sign in to the catalog first.');
      return fetch('/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ conversation_id: conversationId(), message: text, page: location.pathname })
      });
    }).then(function (r) {
      if (r.status === 401) seenToken = null;
      if (!r.ok || !r.body) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          throw new Error(j.detail || ('The assistant is unavailable (HTTP ' + r.status + ').'));
        });
      }
      var reader = r.body.getReader(), decoder = new TextDecoder(), buf = '';
      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) return;
          buf += decoder.decode(chunk.value, { stream: true });
          var parts = buf.split('\n\n');
          buf = parts.pop();
          parts.forEach(function (part) {
            var type = 'message', data = '';
            part.split('\n').forEach(function (l) {
              if (l.indexOf('event: ') === 0) type = l.slice(7);
              else if (l.indexOf('data: ') === 0) data += l.slice(6);
            });
            if (data) { try { handle(type, JSON.parse(data)); } catch (e) {} }
          });
          return pump();
        });
      }
      return pump();
    }).catch(function (err) {
      if (thinking) { thinking.remove(); thinking = null; }
      liveDone();
      body.appendChild(el('div', 'agi-error', esc(err.message)));
    }).then(function () {
      if (pending) { cancelAnimationFrame(pending); pending = 0; }
      if (answer) render();
      busy = false;
      sendBtn.disabled = false;
      persist();
      scroll();
    });
  }

  // ---- OM's search box (#searchBox: the navbar's, or the big one on the home page) as the assistant's entry point ----
  // Its suggestions get a first row "✦ Ask AI: <text>". Enter asks the AI when the text reads as a question, else
  // OM's keyword search runs as usual; Ctrl/⌘+Enter always asks the AI.
  var QUESTION = /\?\s*$|^(how|where|what|why|which|who|whom|when|can|could|may|should|is|are|does|do|did|show|explain|document|describe|list|find|give|tell|compare|draft|write|help)\b/i;
  var OVERLAY = '.global-search-overlay, .customise-search-overlay';
  var row = null, rowQueued = false;

  function isSearchBox(t) { return t && t.id === 'searchBox' && t.tagName === 'INPUT'; }

  function asksAi(text) { return QUESTION.test(text) || text.split(/\s+/).length >= 5; }

  function askFromSearch(box, text) {
    // clear OM's controlled input the way React notices (its onChange also closes the suggestions)
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(box, '');
    box.dispatchEvent(new Event('input', { bubbles: true }));
    box.blur();
    if (!root) build();
    open(true);
    if (busy) { input.value = text; input.focus(); } else { send(text); }
  }

  function syncRow() {
    rowQueued = false;
    var box = document.getElementById('searchBox');
    var overlay = document.querySelector(OVERLAY);
    var text = box ? box.value.trim() : '';
    if (!overlay || !text) { if (row) row.remove(); return; }
    var card = overlay.querySelector('.ant-popover-inner-content') || overlay;  // inside OM's white card
    if (!row) {
      row = el('div', 'agi-search-row');
      row.setAttribute('role', 'button');
      row.addEventListener('mousedown', function (e) { e.preventDefault(); });  // keep the input focused
      row.addEventListener('click', function () {
        var b = document.getElementById('searchBox');
        if (b && b.value.trim()) askFromSearch(b, b.value.trim());
      });
    }
    if (row.dataset.text !== text) {  // redraw only on change: our own DOM writes wake the observer too
      var primary = asksAi(text);
      row.dataset.text = text;
      row.classList.toggle('agi-primary', primary);
      overlay.classList.toggle('agi-ask-first', primary);  // CSS hides OM's "Press Enter to find…" line then
      row.innerHTML = '<span class="agi-avatar">✦</span><span class="agi-sr-text"><b>Ask AI:</b> ' + esc(text) +
        '</span><kbd>' + (primary ? 'Enter ↵' : (/Mac/.test(navigator.platform) ? '⌘' : 'Ctrl') + ' + ↵') + '</kbd>';
    }
    overlay.classList.toggle('agi-ask-first', row.classList.contains('agi-primary'));
    if (card.firstChild !== row) card.insertBefore(row, card.firstChild);
  }

  function queueRow() { if (!rowQueued) { rowQueued = true; requestAnimationFrame(syncRow); } }

  document.addEventListener('keydown', function (e) {
    if (!isSearchBox(e.target) || e.key !== 'Enter' || e.isComposing) return;
    var text = e.target.value.trim();
    if (!text || !(e.ctrlKey || e.metaKey || asksAi(text))) return;
    e.preventDefault();
    e.stopPropagation();  // capture phase on document: OM's React onKeyDown never sees it, so no jump to Explore
    askFromSearch(e.target, text);
  }, true);
  document.addEventListener('input', function (e) { if (isSearchBox(e.target)) queueRow(); }, true);
  new MutationObserver(queueRow).observe(document.body, { childList: true, subtree: true });

  // OM's sign-in page has no session: show the launcher only once a token exists.
  function start() {
    if (root) return;
    getToken().then(function (token) { if (token && !root) build(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  setInterval(function () {
    if (!root) { start(); return; }
    getToken().then(function (token) { root.style.display = token ? '' : 'none'; });
  }, 3000);
})();
