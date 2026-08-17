"""
Le XML des flux de chronométrage est parsé par defusedxml, pas par `xml.etree`
(constat ruff S314, #394) : une bombe d'entités doit être refusée, pas expansée.
"""
import pytest
from defusedxml.common import EntitiesForbidden

from app.scrapers.timepulse import parse_xml as timepulse_parse
from app.scrapers.wiclax import parse_xml as wiclax_parse

BOMBE = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
]>
<Results><E d="1" n="&lol2;" /></Results>"""

XML_SAIN = '<Results><E d="1" n="Dupont Jean" /></Results>'


@pytest.mark.parametrize("parse", [timepulse_parse, wiclax_parse])
def test_bombe_entites_refusee(parse):
    with pytest.raises(EntitiesForbidden):
        parse(BOMBE)


@pytest.mark.parametrize("parse", [timepulse_parse, wiclax_parse])
def test_xml_normal_toujours_parse(parse):
    assert parse(XML_SAIN).find("E").get("n") == "Dupont Jean"
