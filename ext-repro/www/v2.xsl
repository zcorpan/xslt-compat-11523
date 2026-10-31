<?xml version="1.0"?>
<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html"/>
<xsl:template match="/"><xsl:message>hello from xsl:message</xsl:message><html><head><title>t</title></head><body><p id="t">transformed: <xsl:value-of select="root/item"/></p></body></html></xsl:template>
</xsl:stylesheet>
