<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" doctype-system="about:legacy-compat"/>
<xsl:template match="/"><html><head><title>t</title><style>body { font-family: monospace; font-size: 10px }</style></head><body leftmargin="0" topmargin="0" marginwidth="0" marginheight="0">
<table id="tb"><tr><td id="td">cell</td><td id="top" valign="top">top<br/>x</td></tr></table>
<div style="white-space: pre"><table><tr><td id="pre">a  b</td></tr></table></div>
<p id="t"></p><script>
var c = function (id) { return getComputedStyle(document.getElementById(id)); };
document.getElementById('t').textContent = ['body margin ' + getComputedStyle(document.body).marginTop, 'td font ' + c('td').fontFamily + ' ' + c('td').fontSize, 'td valign ' + c('td').verticalAlign, 'valign=top ' + c('top').verticalAlign, 'td padding ' + c('td').paddingTop, 'table spacing ' + c('tb').borderSpacing, 'table width ' + c('tb').width, 'pre in table ' + c('pre').whiteSpace].join(', ');
</script></body></html></xsl:template>
</xsl:stylesheet>
