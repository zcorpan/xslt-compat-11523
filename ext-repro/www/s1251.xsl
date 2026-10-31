<?xml version="1.0" encoding="windows-1251"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"><xsl:output method="html"/>
<xsl:template match="/"><html><head><title>t</title></head><body><p id="t">привет <xsl:value-of select="root/item"/></p></body></html></xsl:template></xsl:stylesheet>
