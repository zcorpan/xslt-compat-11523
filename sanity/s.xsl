<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/"><html><body><p id="t">transformed: <xsl:value-of select="root/item"/></p></body></html></xsl:template>
</xsl:stylesheet>
