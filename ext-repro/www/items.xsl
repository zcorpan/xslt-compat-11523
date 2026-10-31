<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html"/>
<xsl:template match="/"><html><head><title>t</title></head><body><p id="t">items: <xsl:for-each select="//item"><xsl:value-of select="."/>, </xsl:for-each></p>
<script>document.getElementById('t').textContent += 'source script ran: ' + (sessionStorage.ran || 'no');</script></body></html></xsl:template>
</xsl:stylesheet>
