<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html"/>
<xsl:template match="/"><html><head><title>t</title><script>var Event = function (e) { this.type = e.type; };
window.addEventListener('load', function () { document.getElementById('t').textContent += ' load fired'; });</script></head><body><p id="t">transformed: <xsl:value-of select="root/item"/></p></body></html></xsl:template>
</xsl:stylesheet>
