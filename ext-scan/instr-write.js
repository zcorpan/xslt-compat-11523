(() => {
  if (window.__caseLog) return;
  const log = window.__caseLog = [];
  const up = (s) => typeof s === 'string' && /[A-Z]/.test(s);
  const summarize = (r) => r == null ? null : typeof r === 'string' ? 'value' : typeof r === 'boolean' ? r : typeof r.length === 'number' ? r.length : 1;
  const wrap = (proto, name) => {
    const orig = proto && proto[name];
    if (typeof orig !== 'function') return;
    proto[name] = function (...args) {
      const r = orig.apply(this, args);
      if (up(args[0]) && log.length < 200) {
        const frame = (new Error().stack || '').split('\n').slice(2).find((l) => /https?:/.test(l)) || '';
        log.push({ api: name, arg: String(args[0]).slice(0, 100), result: summarize(r), at: frame.trim().slice(0, 200) });
      }
      return r;
    };
  };
  for (const n of ['write', 'writeln']) {
    const orig = Document.prototype[n];
    Document.prototype[n] = function (...args) {
      if (log.length < 200) {
        const frame = (new Error().stack || '').split('\n').slice(2).find((l) => /https?:/.test(l)) || '';
        log.push({ api: n, arg: String(args[0]).slice(0, 100), result: 1, at: frame.trim().slice(0, 200) });
      }
      return orig.apply(this, args);
    };
  }
  for (const p of [Document.prototype, Element.prototype]) wrap(p, 'getElementsByTagName');
  for (const n of ['getAttribute', 'hasAttribute', 'setAttribute', 'removeAttribute', 'getAttributeNode', 'matches', 'closest']) wrap(Element.prototype, n);
  for (const p of [Document.prototype, Element.prototype, DocumentFragment.prototype]) { wrap(p, 'querySelector'); wrap(p, 'querySelectorAll'); }
})();
