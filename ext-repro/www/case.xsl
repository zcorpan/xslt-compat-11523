<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html"/>
<xsl:template match="/"><html><head><title>t</title><style>BODY { font-family: monospace } P.X { color: rgb(0, 0, 255) }</style></head><body><p class="X" id="p" ALIGN="right">para</p><div id="t"></div>
<script>
var p = document.getElementById('p'), r = [];
r.push('BODY font ' + getComputedStyle(document.body).fontFamily);
r.push('P color ' + getComputedStyle(p).color);
r.push("qS('P') " + !!document.querySelector('P'));
r.push("gEBTN('P') " + document.getElementsByTagName('P').length);
r.push("getAttribute('CLASS') " + p.getAttribute('CLASS'));
r.push("getAttribute('align') " + p.getAttribute('align'));
try { document.write(''); r.push('document.write ok'); } catch (e) { r.push('document.write throws'); }
document.getElementById('t').textContent = r.join(', ');
</script></body></html></xsl:template>
</xsl:stylesheet>
