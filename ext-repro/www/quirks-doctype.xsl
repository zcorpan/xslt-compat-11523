<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" doctype-system="about:legacy-compat"/>
<xsl:template match="/"><html><head><title>t</title><style>body { font-size: 10px }</style></head><body><table><tr><td id="td">cell</td></tr></table><li id="stray">stray</li><ul><li id="inlist">in list</li></ul><li id="outer">outer<ul><li id="nested">nested</li></ul></li>
<p id="t"></p><script>
var g = function (id, p) { return getComputedStyle(document.getElementById(id))[p]; };
document.getElementById('t').textContent = [document.compatMode, 'td ' + g('td', 'fontSize'), 'stray ' + g('stray', 'listStylePosition'), 'inlist ' + g('inlist', 'listStylePosition'), 'nested ' + g('nested', 'listStylePosition')].join(', ');
</script></body></html></xsl:template>
</xsl:stylesheet>
