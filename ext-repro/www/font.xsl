<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html"/>
<xsl:template match="/"><html><head><title>t</title><style>body { font-family: monospace; }</style></head><body><p id="t">transformed</p><table><tr><td id="td">cell</td></tr></table>
<script>document.getElementById('t').textContent += ' td font: ' + getComputedStyle(document.getElementById('td')).fontFamily;</script></body></html></xsl:template>
</xsl:stylesheet>
