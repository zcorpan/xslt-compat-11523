const results = [];
const show = () => { const t = document.getElementById('t'); if (t) t.textContent = results.join(' | '); else setTimeout(show, 50); };
try { new WebAssembly.Module(new Uint8Array([0,97,115,109,1,0,0,0])); results.push('main compile ok'); } catch (e) { results.push('main compile: ' + e.name); }
window.addEventListener('messageerror', (e) => { results.push('messageerror'); show(); });
window.addEventListener('message', async (e) => {
  if (e.data && e.data.cspProbeError) { results.push(e.data.cspProbeError); show(); }
  if (e.data && 'cspProbeModule' in e.data) {
    results.push('got ' + Object.prototype.toString.call(e.data.cspProbeModule)); show();
    try { const inst = await WebAssembly.instantiate(e.data.cspProbeModule); results.push('instantiate passed module: ' + inst.exports.f()); }
    catch (err) { results.push('instantiate passed module: ' + err.name + ' ' + err.message.slice(0, 60)); }
    show();
  }
});
show();
