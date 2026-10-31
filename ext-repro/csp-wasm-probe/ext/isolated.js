const bytes = new Uint8Array([0,97,115,109,1,0,0,0,1,5,1,96,0,1,127,3,2,1,0,7,5,1,1,102,0,0,10,6,1,4,0,65,42,11]);
window.postMessage({ cspProbeError: 'isolated started' }, '*');
let m;
try { m = new WebAssembly.Module(bytes); window.postMessage({ cspProbeError: 'isolated sync compile ok' }, '*'); }
catch (e) { window.postMessage({ cspProbeError: 'isolated sync compile: ' + e }, '*'); }
if (m) {
  try { window.postMessage({ cspProbeModule: m }, '*'); window.postMessage({ cspProbeError: 'posted module' }, '*'); }
  catch (e) { window.postMessage({ cspProbeError: 'post module: ' + e }, '*'); }
}
