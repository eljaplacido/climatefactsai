"""
Global Climate News Feed Registry — European coverage + sample global sources.

Provides RSS feed configurations for climate, environment, and weather news
across ALL European countries, EU-wide institutions, and sample sources from
the US, Africa, and Latin America for global reach evaluation.
"""

from typing import Dict, List, Any

EU_CLIMATE_FEEDS: Dict[str, List[Dict[str, Any]]] = {
    # ─── Nordic ───
    "FI": [
        {"name": "YLE Climate", "url": "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET&concepts=18-220107", "tier": "public", "domain": "yle.fi", "language": "fi"},
        {"name": "Finnish Met Institute", "url": "https://www.ilmatieteenlaitos.fi/rss/uutiset", "tier": "scientific", "domain": "ilmatieteenlaitos.fi", "language": "fi"},
        {"name": "Helsinki Times Environment", "url": "https://www.helsinkitimes.fi/finland/finland-news/domestic/rss.html", "tier": "public", "domain": "helsinkitimes.fi", "language": "en"},
    ],
    "SE": [
        {"name": "SVT Climate", "url": "https://www.svt.se/nyheter/rss.xml", "tier": "public", "domain": "svt.se", "language": "sv"},
        {"name": "SMHI News", "url": "https://www.smhi.se/rss/nyheter", "tier": "scientific", "domain": "smhi.se", "language": "sv"},
        {"name": "Stockholm Resilience Centre", "url": "https://www.stockholmresilience.org/news-and-media/rss.xml", "tier": "research", "domain": "stockholmresilience.org", "language": "en"},
    ],
    "NO": [
        {"name": "NRK Climate", "url": "https://www.nrk.no/toppsaker.rss", "tier": "public", "domain": "nrk.no", "language": "no"},
        {"name": "CICERO Climate Research", "url": "https://cicero.oslo.no/en/feed", "tier": "research", "domain": "cicero.oslo.no", "language": "en"},
    ],
    "DK": [
        {"name": "DR Climate", "url": "https://www.dr.dk/nyheder/service/feeds/senestenyt/", "tier": "public", "domain": "dr.dk", "language": "da"},
        {"name": "CONCITO", "url": "https://concito.dk/feed", "tier": "research", "domain": "concito.dk", "language": "da"},
    ],
    "IS": [{"name": "RUV Iceland", "url": "https://www.ruv.is/rss/frettir", "tier": "public", "domain": "ruv.is", "language": "is"}],
    # ─── Western Europe ───
    "GB": [
        {"name": "BBC Environment", "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "tier": "public", "domain": "bbc.co.uk", "language": "en"},
        {"name": "Met Office Blog", "url": "https://blog.metoffice.gov.uk/feed/", "tier": "scientific", "domain": "metoffice.gov.uk", "language": "en"},
        {"name": "Carbon Brief", "url": "https://www.carbonbrief.org/feed/", "tier": "research", "domain": "carbonbrief.org", "language": "en"},
        {"name": "The Guardian Climate", "url": "https://www.theguardian.com/environment/climate-crisis/rss", "tier": "public", "domain": "theguardian.com", "language": "en"},
        {"name": "Climate Change News", "url": "https://www.climatechangenews.com/feed/", "tier": "public", "domain": "climatechangenews.com", "language": "en"},
    ],
    "IE": [{"name": "RTE Environment", "url": "https://www.rte.ie/rss/news.xml", "tier": "public", "domain": "rte.ie", "language": "en"}],
    "FR": [
        {"name": "France24 Environment", "url": "https://www.france24.com/en/environment/rss", "tier": "public", "domain": "france24.com", "language": "en"},
        {"name": "Le Monde Climat", "url": "https://www.lemonde.fr/climat/rss_full.xml", "tier": "public", "domain": "lemonde.fr", "language": "fr"},
        {"name": "IDDRI", "url": "https://www.iddri.org/en.rss", "tier": "research", "domain": "iddri.org", "language": "en"},
    ],
    "DE": [
        {"name": "DW Environment", "url": "https://rss.dw.com/xml/rss-en-environment", "tier": "public", "domain": "dw.com", "language": "en"},
        {"name": "PIK Potsdam", "url": "https://www.pik-potsdam.de/en/news/latest-news/RSS", "tier": "research", "domain": "pik-potsdam.de", "language": "en"},
        {"name": "Clean Energy Wire", "url": "https://www.cleanenergywire.org/rss.xml", "tier": "research", "domain": "cleanenergywire.org", "language": "en"},
    ],
    "NL": [
        {"name": "NOS Science", "url": "https://feeds.nos.nl/nosnieuwswetenschap", "tier": "public", "domain": "nos.nl", "language": "nl"},
        {"name": "Deltares", "url": "https://www.deltares.nl/en/news/rss", "tier": "research", "domain": "deltares.nl", "language": "en"},
    ],
    "BE": [{"name": "VRT NWS", "url": "https://www.vrt.be/vrtnws/nl.rss.articles.xml", "tier": "public", "domain": "vrt.be", "language": "nl"}],
    "LU": [{"name": "Luxembourg Times", "url": "https://www.luxtimes.lu/rss", "tier": "public", "domain": "luxtimes.lu", "language": "en"}],
    "CH": [{"name": "SWI Environment", "url": "https://www.swissinfo.ch/eng/environment/rss", "tier": "public", "domain": "swissinfo.ch", "language": "en"}],
    "AT": [{"name": "ORF Science", "url": "https://rss.orf.at/science.xml", "tier": "public", "domain": "orf.at", "language": "de"}],
    "LI": [{"name": "Liechtenstein News", "url": "https://www.lie-zeit.li/feed/", "tier": "public", "domain": "lie-zeit.li", "language": "de"}],
    # ─── Southern Europe ───
    "ES": [
        {"name": "EFE Verde", "url": "https://efeverde.com/feed/", "tier": "public", "domain": "efeverde.com", "language": "es"},
        {"name": "El Pais Climate", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/clima-y-medio-ambiente/portada", "tier": "public", "domain": "elpais.com", "language": "es"},
    ],
    "PT": [{"name": "Observador Ambiente", "url": "https://observador.pt/seccao/ambiente/feed/", "tier": "public", "domain": "observador.pt", "language": "pt"}],
    "IT": [
        {"name": "ANSA Environment", "url": "https://www.ansa.it/sito/notizie/cronaca/rss_cronaca.xml", "tier": "public", "domain": "ansa.it", "language": "it"},
        {"name": "CMCC Italy", "url": "https://www.cmcc.it/feed", "tier": "research", "domain": "cmcc.it", "language": "en"},
    ],
    "MT": [{"name": "Times of Malta", "url": "https://timesofmalta.com/rss/environment", "tier": "public", "domain": "timesofmalta.com", "language": "en"}],
    "GR": [{"name": "Kathimerini English", "url": "https://www.ekathimerini.com/rss/", "tier": "public", "domain": "ekathimerini.com", "language": "en"}],
    "CY": [{"name": "Cyprus Mail", "url": "https://cyprus-mail.com/feed/", "tier": "public", "domain": "cyprus-mail.com", "language": "en"}],
    "TR": [{"name": "Daily Sabah Environment", "url": "https://www.dailysabah.com/rssFeed/environment", "tier": "public", "domain": "dailysabah.com", "language": "en"}],
    # ─── Central Europe ───
    "PL": [{"name": "TVN24", "url": "https://tvn24.pl/najnowsze.xml", "tier": "public", "domain": "tvn24.pl", "language": "pl"}],
    "CZ": [{"name": "Czech Radio", "url": "https://www.irozhlas.cz/rss/irozhlas", "tier": "public", "domain": "irozhlas.cz", "language": "cs"}],
    "SK": [{"name": "TASR News", "url": "https://www.tasr.sk/rss/rss.ashx", "tier": "public", "domain": "tasr.sk", "language": "sk"}],
    "HU": [{"name": "Hungary Today", "url": "https://hungarytoday.hu/feed/", "tier": "public", "domain": "hungarytoday.hu", "language": "en"}],
    "SI": [{"name": "Slovenia Times", "url": "https://sloveniatimes.com/feed/", "tier": "public", "domain": "sloveniatimes.com", "language": "en"}],
    # ─── Eastern Europe ───
    "RO": [{"name": "Romania Insider", "url": "https://www.romania-insider.com/feed/", "tier": "public", "domain": "romania-insider.com", "language": "en"}],
    "BG": [{"name": "Sofia Globe", "url": "https://sofiaglobe.com/feed/", "tier": "public", "domain": "sofiaglobe.com", "language": "en"}],
    "HR": [{"name": "Croatia Week", "url": "https://www.croatiaweek.com/feed/", "tier": "public", "domain": "croatiaweek.com", "language": "en"}],
    "RS": [{"name": "Balkan Green Energy", "url": "https://balkangreenenergynews.com/feed/", "tier": "research", "domain": "balkangreenenergynews.com", "language": "en"}],
    "BA": [{"name": "Sarajevo Times", "url": "https://sarajevotimes.com/feed/", "tier": "public", "domain": "sarajevotimes.com", "language": "en"}],
    "ME": [{"name": "Montenegro Gov", "url": "https://www.gov.me/en/rss", "tier": "government", "domain": "gov.me", "language": "en"}],
    "MK": [{"name": "MIA N. Macedonia", "url": "https://mia.mk/en/rss", "tier": "public", "domain": "mia.mk", "language": "en"}],
    "AL": [{"name": "Albanian Daily News", "url": "https://albaniandailynews.com/feed/", "tier": "public", "domain": "albaniandailynews.com", "language": "en"}],
    "XK": [{"name": "Kosovo Online", "url": "https://www.kosovoonline.com/rss", "tier": "public", "domain": "kosovoonline.com", "language": "en"}],
    # ─── Baltic States ───
    "EE": [{"name": "ERR News Estonia", "url": "https://news.err.ee/rss", "tier": "public", "domain": "err.ee", "language": "en"}],
    "LV": [{"name": "LSM Latvia", "url": "https://eng.lsm.lv/rss/", "tier": "public", "domain": "lsm.lv", "language": "en"}],
    "LT": [{"name": "LRT English", "url": "https://www.lrt.lt/en/rss", "tier": "public", "domain": "lrt.lt", "language": "en"}],
    # ─── Eastern (non-EU) ───
    "UA": [{"name": "Kyiv Independent", "url": "https://kyivindependent.com/feed/", "tier": "public", "domain": "kyivindependent.com", "language": "en"}],
    "MD": [{"name": "Moldova.org", "url": "https://www.moldova.org/en/feed/", "tier": "public", "domain": "moldova.org", "language": "en"}],
    "BY": [{"name": "BelTA", "url": "https://eng.belta.by/rss", "tier": "public", "domain": "belta.by", "language": "en"}],
    "GE": [{"name": "Agenda.ge", "url": "https://agenda.ge/en/news/rss", "tier": "public", "domain": "agenda.ge", "language": "en"}],
    "AM": [{"name": "Armenpress", "url": "https://armenpress.am/eng/rss/", "tier": "public", "domain": "armenpress.am", "language": "en"}],
    "AZ": [{"name": "APA Azerbaijan", "url": "https://apa.az/en/rss/", "tier": "public", "domain": "apa.az", "language": "en"}],
}

EU_WIDE_FEEDS: List[Dict[str, Any]] = [
    {"name": "EEA News", "url": "https://www.eea.europa.eu/api/rss", "country_code": "EU", "tier": "scientific", "domain": "eea.europa.eu", "language": "en"},
    {"name": "EU Climate Action", "url": "https://ec.europa.eu/clima/news/rss_en", "country_code": "EU", "tier": "government", "domain": "ec.europa.eu", "language": "en"},
    {"name": "Euractiv Environment", "url": "https://www.euractiv.com/sections/energy-environment/feed/", "country_code": "EU", "tier": "public", "domain": "euractiv.com", "language": "en"},
    {"name": "ECMWF News", "url": "https://www.ecmwf.int/en/about/media-centre/rss", "country_code": "EU", "tier": "scientific", "domain": "ecmwf.int", "language": "en"},
    {"name": "Copernicus News", "url": "https://climate.copernicus.eu/news/rss", "country_code": "EU", "tier": "scientific", "domain": "climate.copernicus.eu", "language": "en"},
    {"name": "EUMETSAT News", "url": "https://www.eumetsat.int/rss-feed", "country_code": "EU", "tier": "scientific", "domain": "eumetsat.int", "language": "en"},
    {"name": "JRC Science Hub", "url": "https://joint-research-centre.ec.europa.eu/rss_en", "country_code": "EU", "tier": "research", "domain": "ec.europa.eu", "language": "en"},
    {"name": "European Climate Foundation", "url": "https://europeanclimate.org/feed/", "country_code": "EU", "tier": "research", "domain": "europeanclimate.org", "language": "en"},
]

INTERNATIONAL_CLIMATE_FEEDS: List[Dict[str, Any]] = [
    {"name": "Nature Climate Change", "url": "https://www.nature.com/nclimate.rss", "country_code": "XX", "tier": "scientific", "domain": "nature.com", "language": "en"},
    {"name": "AGU Climate", "url": "https://news.agu.org/feed/", "country_code": "XX", "tier": "scientific", "domain": "agu.org", "language": "en"},
    {"name": "IPCC", "url": "https://www.ipcc.ch/feed/", "country_code": "XX", "tier": "scientific", "domain": "ipcc.ch", "language": "en"},
    {"name": "WMO News", "url": "https://wmo.int/media/news/rss", "country_code": "XX", "tier": "scientific", "domain": "wmo.int", "language": "en"},
    {"name": "UN Climate News", "url": "https://news.un.org/feed/subscribe/en/topic/climate-change/feed/rss.xml", "country_code": "XX", "tier": "scientific", "domain": "news.un.org", "language": "en"},
    {"name": "UNEP News", "url": "https://www.unep.org/rss.xml", "country_code": "XX", "tier": "scientific", "domain": "unep.org", "language": "en"},
    {"name": "World Bank Climate", "url": "https://blogs.worldbank.org/en/climatechange/rss.xml", "country_code": "XX", "tier": "research", "domain": "worldbank.org", "language": "en"},
    {"name": "IEA News", "url": "https://www.iea.org/rss/news.xml", "country_code": "XX", "tier": "research", "domain": "iea.org", "language": "en"},
    {"name": "IRENA", "url": "https://www.irena.org/rss", "country_code": "XX", "tier": "research", "domain": "irena.org", "language": "en"},
    {"name": "NOAA Climate", "url": "https://www.climate.gov/rss.xml", "country_code": "US", "tier": "scientific", "domain": "climate.gov", "language": "en"},
    {"name": "NASA Climate", "url": "https://climate.nasa.gov/news/rss.xml", "country_code": "US", "tier": "scientific", "domain": "climate.nasa.gov", "language": "en"},
    {"name": "NYT Climate", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml", "country_code": "US", "tier": "public", "domain": "nytimes.com", "language": "en"},
    {"name": "Inside Climate News", "url": "https://insideclimatenews.org/feed/", "country_code": "US", "tier": "research", "domain": "insideclimatenews.org", "language": "en"},
    {"name": "Climate Central", "url": "https://www.climatecentral.org/feed", "country_code": "US", "tier": "research", "domain": "climatecentral.org", "language": "en"},
    {"name": "Grist", "url": "https://grist.org/feed/", "country_code": "US", "tier": "public", "domain": "grist.org", "language": "en"},
    {"name": "Reuters Environment", "url": "https://www.reuters.com/arc/outboundfeeds/v3/all/section/environment/?outputType=xml", "country_code": "XX", "tier": "public", "domain": "reuters.com", "language": "en"},
    {"name": "Earth.org", "url": "https://earth.org/feed/", "country_code": "XX", "tier": "research", "domain": "earth.org", "language": "en"},
    {"name": "Carbon Tracker", "url": "https://carbontracker.org/feed/", "country_code": "XX", "tier": "research", "domain": "carbontracker.org", "language": "en"},
    {"name": "World Resources Institute", "url": "https://www.wri.org/rss.xml", "country_code": "XX", "tier": "research", "domain": "wri.org", "language": "en"},
]

# ─── US (comprehensive — news, research, government, industry) ───
US_CLIMATE_FEEDS: List[Dict[str, Any]] = [
    {"name": "AP Climate", "url": "https://apnews.com/hub/climate-and-environment.rss", "country_code": "US", "tier": "public", "domain": "apnews.com", "language": "en"},
    {"name": "Washington Post Climate", "url": "https://feeds.washingtonpost.com/rss/climate-environment", "country_code": "US", "tier": "public", "domain": "washingtonpost.com", "language": "en"},
    {"name": "NPR Climate", "url": "https://feeds.npr.org/1025/rss.xml", "country_code": "US", "tier": "public", "domain": "npr.org", "language": "en"},
    {"name": "Yale Climate Connections", "url": "https://yaleclimateconnections.org/feed/", "country_code": "US", "tier": "research", "domain": "yaleclimateconnections.org", "language": "en"},
    {"name": "MIT Climate Portal", "url": "https://climate.mit.edu/feed", "country_code": "US", "tier": "research", "domain": "climate.mit.edu", "language": "en"},
    {"name": "Brookings Climate", "url": "https://www.brookings.edu/topic/climate-change/feed/", "country_code": "US", "tier": "research", "domain": "brookings.edu", "language": "en"},
    {"name": "RFF Resources for the Future", "url": "https://www.rff.org/feed/", "country_code": "US", "tier": "research", "domain": "rff.org", "language": "en"},
    {"name": "E&E News Climate", "url": "https://www.eenews.net/feed/", "country_code": "US", "tier": "public", "domain": "eenews.net", "language": "en"},
    {"name": "DeSmog", "url": "https://www.desmog.com/feed/", "country_code": "US", "tier": "research", "domain": "desmog.com", "language": "en"},
    {"name": "Canary Media", "url": "https://www.canarymedia.com/feed", "country_code": "US", "tier": "research", "domain": "canarymedia.com", "language": "en"},
    {"name": "NRDC Blog", "url": "https://www.nrdc.org/rss.xml", "country_code": "US", "tier": "research", "domain": "nrdc.org", "language": "en"},
    {"name": "Union of Concerned Scientists", "url": "https://blog.ucsusa.org/feed/", "country_code": "US", "tier": "research", "domain": "ucsusa.org", "language": "en"},
    {"name": "DOE Energy News", "url": "https://www.energy.gov/rss/articles.xml", "country_code": "US", "tier": "government", "domain": "energy.gov", "language": "en"},
    {"name": "EPA News", "url": "https://www.epa.gov/rss/epa-news.xml", "country_code": "US", "tier": "government", "domain": "epa.gov", "language": "en"},
    {"name": "NCAR Climate", "url": "https://news.ucar.edu/rss.xml", "country_code": "US", "tier": "scientific", "domain": "ucar.edu", "language": "en"},
    {"name": "Woods Hole Oceanographic", "url": "https://www.whoi.edu/feed/", "country_code": "US", "tier": "scientific", "domain": "whoi.edu", "language": "en"},
    {"name": "Scripps Oceanography News", "url": "https://scripps.ucsd.edu/news/rss.xml", "country_code": "US", "tier": "scientific", "domain": "scripps.ucsd.edu", "language": "en"},
    {"name": "EDF Climate", "url": "https://www.edf.org/rss.xml", "country_code": "US", "tier": "research", "domain": "edf.org", "language": "en"},
    {"name": "Sierra Club", "url": "https://www.sierraclub.org/rss.xml", "country_code": "US", "tier": "public", "domain": "sierraclub.org", "language": "en"},
    {"name": "Heatmap News", "url": "https://heatmap.news/feed", "country_code": "US", "tier": "public", "domain": "heatmap.news", "language": "en"},
]

# ─── Africa (comprehensive — every major region) ───
AFRICA_CLIMATE_FEEDS: List[Dict[str, Any]] = [
    # East Africa
    {"name": "Daily Nation Environment", "url": "https://nation.africa/kenya/news/rss", "country_code": "KE", "tier": "public", "domain": "nation.africa", "language": "en"},
    {"name": "The East African", "url": "https://www.theeastafrican.co.ke/tea/science-health/rss", "country_code": "KE", "tier": "public", "domain": "theeastafrican.co.ke", "language": "en"},
    {"name": "The Citizen Tanzania", "url": "https://www.thecitizen.co.tz/rss", "country_code": "TZ", "tier": "public", "domain": "thecitizen.co.tz", "language": "en"},
    {"name": "New Vision Uganda", "url": "https://www.newvision.co.ug/rss", "country_code": "UG", "tier": "public", "domain": "newvision.co.ug", "language": "en"},
    {"name": "The New Times Rwanda", "url": "https://www.newtimes.co.rw/rssfeed/all", "country_code": "RW", "tier": "public", "domain": "newtimes.co.rw", "language": "en"},
    {"name": "Capital FM Ethiopia", "url": "https://www.capitalethiopia.com/feed/", "country_code": "ET", "tier": "public", "domain": "capitalethiopia.com", "language": "en"},
    # West Africa
    {"name": "Punch Nigeria", "url": "https://punchng.com/topics/environment/feed/", "country_code": "NG", "tier": "public", "domain": "punchng.com", "language": "en"},
    {"name": "Premium Times Nigeria", "url": "https://www.premiumtimesng.com/category/news/top-news/feed", "country_code": "NG", "tier": "public", "domain": "premiumtimesng.com", "language": "en"},
    {"name": "Guardian Nigeria", "url": "https://guardian.ng/feed/", "country_code": "NG", "tier": "public", "domain": "guardian.ng", "language": "en"},
    {"name": "Ghana Web", "url": "https://www.ghanaweb.com/GhanaHomePage/rss/", "country_code": "GH", "tier": "public", "domain": "ghanaweb.com", "language": "en"},
    {"name": "Joy Online Ghana", "url": "https://www.myjoyonline.com/feed/", "country_code": "GH", "tier": "public", "domain": "myjoyonline.com", "language": "en"},
    {"name": "Dakar Actu Senegal", "url": "https://www.dakaractu.com/xml/syndication.rss", "country_code": "SN", "tier": "public", "domain": "dakaractu.com", "language": "fr"},
    # Southern Africa
    {"name": "News24 South Africa", "url": "https://feeds.news24.com/articles/news24/green/rss", "country_code": "ZA", "tier": "public", "domain": "news24.com", "language": "en"},
    {"name": "Daily Maverick", "url": "https://www.dailymaverick.co.za/section/our-burning-planet/feed/", "country_code": "ZA", "tier": "research", "domain": "dailymaverick.co.za", "language": "en"},
    {"name": "IOL South Africa", "url": "https://www.iol.co.za/rss", "country_code": "ZA", "tier": "public", "domain": "iol.co.za", "language": "en"},
    {"name": "Lusaka Times Zambia", "url": "https://www.lusakatimes.com/feed/", "country_code": "ZM", "tier": "public", "domain": "lusakatimes.com", "language": "en"},
    {"name": "Nyasa Times Malawi", "url": "https://www.nyasatimes.com/feed/", "country_code": "MW", "tier": "public", "domain": "nyasatimes.com", "language": "en"},
    # North Africa
    {"name": "Egypt Independent", "url": "https://www.egyptindependent.com/feed/", "country_code": "EG", "tier": "public", "domain": "egyptindependent.com", "language": "en"},
    {"name": "Morocco World News", "url": "https://www.moroccoworldnews.com/feed/", "country_code": "MA", "tier": "public", "domain": "moroccoworldnews.com", "language": "en"},
    # Pan-Africa / Research.
    # NOTE: 'XX-AF' (and XX-LA/XX-AS/XX-ME below) are PAN-REGIONAL markers, not
    # ISO codes. The articles.country_code column is CHAR(2) and would truncate
    # them to AF/LA/AS/ME (Afghanistan/Laos/American-Samoa/Montenegro), so they
    # are normalized to 'XX' (global/unattributed) at insert by
    # ingestion._normalize_country_code (P0 — mig 067). Per-article geo-tagging
    # of these multi-country feeds is a follow-up.
    {"name": "African Arguments", "url": "https://africanarguments.org/feed/", "country_code": "XX-AF", "tier": "research", "domain": "africanarguments.org", "language": "en"},
    {"name": "Africa Climate Summit", "url": "https://africaclimatesummit.org/feed/", "country_code": "XX-AF", "tier": "government", "domain": "africaclimatesummit.org", "language": "en"},
    {"name": "AllAfrica Environment", "url": "https://allafrica.com/tools/headlines/rdf/environment/headlines.rdf", "country_code": "XX-AF", "tier": "public", "domain": "allafrica.com", "language": "en"},
    {"name": "IISD Africa Climate", "url": "https://sdg.iisd.org/feed/", "country_code": "XX-AF", "tier": "research", "domain": "sdg.iisd.org", "language": "en"},
    {"name": "Climate Home Africa", "url": "https://www.climatechangenews.com/regions/africa/feed/", "country_code": "XX-AF", "tier": "public", "domain": "climatechangenews.com", "language": "en"},
    {"name": "ACPC UNECA", "url": "https://www.uneca.org/rss.xml", "country_code": "XX-AF", "tier": "scientific", "domain": "uneca.org", "language": "en"},
]

# ─── Latin America (comprehensive) ───
LATAM_CLIMATE_FEEDS: List[Dict[str, Any]] = [
    # Brazil
    {"name": "Folha de Sao Paulo Ambiente", "url": "https://feeds.folha.uol.com.br/ambiente/rss091.xml", "country_code": "BR", "tier": "public", "domain": "folha.uol.com.br", "language": "pt"},
    {"name": "O Globo Sociedade", "url": "https://oglobo.globo.com/rss/oglobo/sociedade/", "country_code": "BR", "tier": "public", "domain": "oglobo.globo.com", "language": "pt"},
    {"name": "INPE Brazil", "url": "https://www.gov.br/inpe/pt-br/RSS", "country_code": "BR", "tier": "scientific", "domain": "gov.br", "language": "pt"},
    {"name": "Observatorio do Clima", "url": "https://www.oc.eco.br/feed/", "country_code": "BR", "tier": "research", "domain": "oc.eco.br", "language": "pt"},
    # Mexico
    {"name": "Mexico News Daily Environment", "url": "https://mexiconewsdaily.com/category/news/environment/feed/", "country_code": "MX", "tier": "public", "domain": "mexiconewsdaily.com", "language": "en"},
    {"name": "El Universal Ciencia", "url": "https://www.eluniversal.com.mx/rss/ciencia.xml", "country_code": "MX", "tier": "public", "domain": "eluniversal.com.mx", "language": "es"},
    {"name": "CONABIO Mexico", "url": "https://www.gob.mx/conabio/rss", "country_code": "MX", "tier": "government", "domain": "gob.mx", "language": "es"},
    # Argentina
    {"name": "Buenos Aires Times", "url": "https://www.batimes.com.ar/feed", "country_code": "AR", "tier": "public", "domain": "batimes.com.ar", "language": "en"},
    {"name": "Clarin Sociedad", "url": "https://www.clarin.com/rss/sociedad/", "country_code": "AR", "tier": "public", "domain": "clarin.com", "language": "es"},
    # Colombia
    {"name": "Colombia Reports", "url": "https://colombiareports.com/feed/", "country_code": "CO", "tier": "public", "domain": "colombiareports.com", "language": "en"},
    {"name": "El Tiempo Medio Ambiente", "url": "https://www.eltiempo.com/rss/vida.xml", "country_code": "CO", "tier": "public", "domain": "eltiempo.com", "language": "es"},
    # Chile
    {"name": "Santiago Times", "url": "https://santiagotimes.cl/feed/", "country_code": "CL", "tier": "public", "domain": "santiagotimes.cl", "language": "en"},
    {"name": "BioBio Chile", "url": "https://www.biobiochile.cl/feed/rss.xml", "country_code": "CL", "tier": "public", "domain": "biobiochile.cl", "language": "es"},
    # Peru
    {"name": "Andina Peru", "url": "https://andina.pe/agencia/rss/noticia-3.aspx", "country_code": "PE", "tier": "public", "domain": "andina.pe", "language": "es"},
    # Pan-LATAM / Research
    {"name": "Mongabay LATAM", "url": "https://es.mongabay.com/feed/", "country_code": "XX-LA", "tier": "research", "domain": "es.mongabay.com", "language": "es"},
    {"name": "Dialogo Chino", "url": "https://dialogochino.net/en/feed/", "country_code": "XX-LA", "tier": "research", "domain": "dialogochino.net", "language": "en"},
    {"name": "Prensa Latina Environment", "url": "https://www.plenglish.com/news/environment/feed/", "country_code": "XX-LA", "tier": "public", "domain": "plenglish.com", "language": "en"},
    {"name": "ECLAC Climate", "url": "https://www.cepal.org/en/rss.xml", "country_code": "XX-LA", "tier": "research", "domain": "cepal.org", "language": "en"},
    {"name": "IDB Sustainability", "url": "https://blogs.iadb.org/sostenibilidad/en/feed/", "country_code": "XX-LA", "tier": "research", "domain": "iadb.org", "language": "en"},
    {"name": "Climate Tracker LATAM", "url": "https://climatetracker.org/feed/", "country_code": "XX-LA", "tier": "research", "domain": "climatetracker.org", "language": "en"},
]

# ─── Asia (comprehensive) ───
ASIA_CLIMATE_FEEDS: List[Dict[str, Any]] = [
    # China
    {"name": "China Dialogue", "url": "https://www.chinadialogue.net/feed/", "country_code": "CN", "tier": "research", "domain": "chinadialogue.net", "language": "en"},
    {"name": "Caixin Environment", "url": "https://www.caixinglobal.com/rss/environment.xml", "country_code": "CN", "tier": "public", "domain": "caixinglobal.com", "language": "en"},
    {"name": "SCMP Climate", "url": "https://www.scmp.com/rss/5/feed", "country_code": "CN", "tier": "public", "domain": "scmp.com", "language": "en"},
    # India
    {"name": "Down to Earth India", "url": "https://www.downtoearth.org.in/rss/environment", "country_code": "IN", "tier": "research", "domain": "downtoearth.org.in", "language": "en"},
    {"name": "Scroll.in Environment", "url": "https://scroll.in/rss/feed/section/environment", "country_code": "IN", "tier": "public", "domain": "scroll.in", "language": "en"},
    {"name": "The Hindu Climate", "url": "https://www.thehindu.com/sci-tech/energy-and-environment/feeder/default.rss", "country_code": "IN", "tier": "public", "domain": "thehindu.com", "language": "en"},
    {"name": "Mongabay India", "url": "https://india.mongabay.com/feed/", "country_code": "IN", "tier": "research", "domain": "india.mongabay.com", "language": "en"},
    {"name": "India Met Department News", "url": "https://mausam.imd.gov.in/rss/rss_feed.xml", "country_code": "IN", "tier": "scientific", "domain": "imd.gov.in", "language": "en"},
    # Japan
    {"name": "Japan Times Environment", "url": "https://www.japantimes.co.jp/environment/feed/", "country_code": "JP", "tier": "public", "domain": "japantimes.co.jp", "language": "en"},
    {"name": "JMA Climate News", "url": "https://www.jma.go.jp/jma/en/news.rss", "country_code": "JP", "tier": "scientific", "domain": "jma.go.jp", "language": "en"},
    {"name": "Nikkei Asia Environment", "url": "https://asia.nikkei.com/rss/feed/environment", "country_code": "JP", "tier": "public", "domain": "asia.nikkei.com", "language": "en"},
    # South Korea
    {"name": "Korea Herald Environment", "url": "https://www.koreaherald.com/rss/020200040000.xml", "country_code": "KR", "tier": "public", "domain": "koreaherald.com", "language": "en"},
    {"name": "KMA Korea Meteorological", "url": "https://www.kma.go.kr/rss.jsp", "country_code": "KR", "tier": "scientific", "domain": "kma.go.kr", "language": "en"},
    # Southeast Asia
    {"name": "Eco-Business", "url": "https://www.eco-business.com/rss/", "country_code": "SG", "tier": "research", "domain": "eco-business.com", "language": "en"},
    {"name": "CNA Green Singapore", "url": "https://www.channelnewsasia.com/rss/sustainability.xml", "country_code": "SG", "tier": "public", "domain": "channelnewsasia.com", "language": "en"},
    {"name": "Bangkok Post Environment", "url": "https://www.bangkokpost.com/rss/data/environment.xml", "country_code": "TH", "tier": "public", "domain": "bangkokpost.com", "language": "en"},
    {"name": "Jakarta Globe", "url": "https://jakartaglobe.id/feed", "country_code": "ID", "tier": "public", "domain": "jakartaglobe.id", "language": "en"},
    {"name": "Mongabay Indonesia", "url": "https://news.mongabay.com/feed/", "country_code": "ID", "tier": "research", "domain": "mongabay.com", "language": "en"},
    {"name": "Rappler Philippines", "url": "https://www.rappler.com/environment/feed/", "country_code": "PH", "tier": "public", "domain": "rappler.com", "language": "en"},
    {"name": "VnExpress Vietnam", "url": "https://e.vnexpress.net/rss/environment.rss", "country_code": "VN", "tier": "public", "domain": "vnexpress.net", "language": "en"},
    # Central / South Asia
    {"name": "The Third Pole", "url": "https://www.thethirdpole.net/feed/", "country_code": "XX-AS", "tier": "research", "domain": "thethirdpole.net", "language": "en"},
    {"name": "Pakistan Dawn", "url": "https://www.dawn.com/feed", "country_code": "PK", "tier": "public", "domain": "dawn.com", "language": "en"},
    {"name": "Dhaka Tribune Bangladesh", "url": "https://www.dhakatribune.com/feed", "country_code": "BD", "tier": "public", "domain": "dhakatribune.com", "language": "en"},
    # Australia / Oceania
    {"name": "ABC Australia Environment", "url": "https://www.abc.net.au/news/feed/2942460/rss.xml", "country_code": "AU", "tier": "public", "domain": "abc.net.au", "language": "en"},
    {"name": "The Conversation Climate AU", "url": "https://theconversation.com/au/environment/feed", "country_code": "AU", "tier": "research", "domain": "theconversation.com", "language": "en"},
    {"name": "Bureau of Meteorology AU", "url": "https://www.bom.gov.au/rss/alerts/rss_warning_all.xml", "country_code": "AU", "tier": "scientific", "domain": "bom.gov.au", "language": "en"},
    {"name": "RNZ New Zealand", "url": "https://www.rnz.co.nz/rss/environment.xml", "country_code": "NZ", "tier": "public", "domain": "rnz.co.nz", "language": "en"},
    # Pan-Asia research
    {"name": "ADB Climate Blog", "url": "https://blogs.adb.org/feed", "country_code": "XX-AS", "tier": "research", "domain": "adb.org", "language": "en"},
    {"name": "IGES Japan Research", "url": "https://www.iges.or.jp/en/feed", "country_code": "JP", "tier": "research", "domain": "iges.or.jp", "language": "en"},
]

# ─── Middle East (comprehensive) ───
MIDDLE_EAST_CLIMATE_FEEDS: List[Dict[str, Any]] = [
    # UAE
    {"name": "The National UAE Climate", "url": "https://www.thenationalnews.com/rss/climate.xml", "country_code": "AE", "tier": "public", "domain": "thenationalnews.com", "language": "en"},
    {"name": "Gulf News Environment", "url": "https://gulfnews.com/rss/environment.xml", "country_code": "AE", "tier": "public", "domain": "gulfnews.com", "language": "en"},
    {"name": "Masdar News", "url": "https://masdar.ae/en/news/feed", "country_code": "AE", "tier": "research", "domain": "masdar.ae", "language": "en"},
    # Saudi Arabia
    {"name": "Arab News Environment", "url": "https://www.arabnews.com/rss.xml", "country_code": "SA", "tier": "public", "domain": "arabnews.com", "language": "en"},
    {"name": "Saudi Gazette", "url": "https://www.saudigazette.com.sa/rss", "country_code": "SA", "tier": "public", "domain": "saudigazette.com.sa", "language": "en"},
    # Israel
    {"name": "Times of Israel Environment", "url": "https://www.timesofisrael.com/feed/", "country_code": "IL", "tier": "public", "domain": "timesofisrael.com", "language": "en"},
    {"name": "Haaretz Climate", "url": "https://www.haaretz.com/rss", "country_code": "IL", "tier": "public", "domain": "haaretz.com", "language": "en"},
    # Jordan / Lebanon / Iraq
    {"name": "Jordan Times", "url": "https://www.jordantimes.com/rss.xml", "country_code": "JO", "tier": "public", "domain": "jordantimes.com", "language": "en"},
    {"name": "Daily Star Lebanon", "url": "https://www.dailystar.com.lb/rss.aspx", "country_code": "LB", "tier": "public", "domain": "dailystar.com.lb", "language": "en"},
    {"name": "Kurdistan24 Iraq", "url": "https://www.kurdistan24.net/en/rss", "country_code": "IQ", "tier": "public", "domain": "kurdistan24.net", "language": "en"},
    # Iran
    {"name": "Tehran Times", "url": "https://www.tehrantimes.com/rss", "country_code": "IR", "tier": "public", "domain": "tehrantimes.com", "language": "en"},
    # Qatar / Kuwait
    {"name": "Al Jazeera Climate", "url": "https://www.aljazeera.com/xml/rss/all.xml", "country_code": "QA", "tier": "public", "domain": "aljazeera.com", "language": "en"},
    {"name": "Gulf Times Qatar", "url": "https://www.gulf-times.com/rss", "country_code": "QA", "tier": "public", "domain": "gulf-times.com", "language": "en"},
    {"name": "Kuwait Times", "url": "https://www.kuwaittimes.com/feed/", "country_code": "KW", "tier": "public", "domain": "kuwaittimes.com", "language": "en"},
    # Pan-ME research
    {"name": "UNDP Arab States", "url": "https://www.undp.org/arab-states/rss.xml", "country_code": "XX-ME", "tier": "research", "domain": "undp.org", "language": "en"},
    {"name": "IRENA Middle East", "url": "https://www.irena.org/rss", "country_code": "XX-ME", "tier": "research", "domain": "irena.org", "language": "en"},
    {"name": "ICARDA Drylands Research", "url": "https://www.icarda.org/feed", "country_code": "XX-ME", "tier": "scientific", "domain": "icarda.org", "language": "en"},
]

# ─── Research Reports & Industry Analysis feeds (cross-cutting) ───
RESEARCH_INDUSTRY_FEEDS: List[Dict[str, Any]] = [
    {"name": "Nature Climate Change", "url": "https://www.nature.com/nclimate.rss", "country_code": "XX", "tier": "scientific", "domain": "nature.com", "language": "en"},
    {"name": "Science Climate", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science", "country_code": "XX", "tier": "scientific", "domain": "science.org", "language": "en"},
    {"name": "Environmental Research Letters", "url": "https://iopscience.iop.org/journal/rss/1748-9326", "country_code": "XX", "tier": "scientific", "domain": "iopscience.iop.org", "language": "en"},
    {"name": "Annual Review of Environment", "url": "https://www.annualreviews.org/action/showFeed?jc=environ&type=etoc&feed=rss", "country_code": "XX", "tier": "scientific", "domain": "annualreviews.org", "language": "en"},
    {"name": "PNAS Environmental Sciences", "url": "https://www.pnas.org/action/showFeed?type=searchTopic&taxonomyCode=resid-environ", "country_code": "XX", "tier": "scientific", "domain": "pnas.org", "language": "en"},
    {"name": "McKinsey Sustainability", "url": "https://www.mckinsey.com/capabilities/sustainability/rss.xml", "country_code": "XX", "tier": "research", "domain": "mckinsey.com", "language": "en"},
    {"name": "BloombergNEF", "url": "https://about.bnef.com/feed/", "country_code": "XX", "tier": "research", "domain": "bnef.com", "language": "en"},
    {"name": "S&P Global Sustainable", "url": "https://www.spglobal.com/esg/insights/rss", "country_code": "XX", "tier": "research", "domain": "spglobal.com", "language": "en"},
    {"name": "Rocky Mountain Institute", "url": "https://rmi.org/feed/", "country_code": "US", "tier": "research", "domain": "rmi.org", "language": "en"},
    {"name": "Climate Policy Initiative", "url": "https://www.climatepolicyinitiative.org/feed/", "country_code": "XX", "tier": "research", "domain": "climatepolicyinitiative.org", "language": "en"},
    {"name": "Global CCS Institute", "url": "https://www.globalccsinstitute.com/feed/", "country_code": "XX", "tier": "research", "domain": "globalccsinstitute.com", "language": "en"},
    {"name": "Ember Climate", "url": "https://ember-climate.org/feed/", "country_code": "XX", "tier": "research", "domain": "ember-climate.org", "language": "en"},
    {"name": "Energy Transitions Commission", "url": "https://www.energy-transitions.org/feed/", "country_code": "XX", "tier": "research", "domain": "energy-transitions.org", "language": "en"},
    {"name": "Chatham House Climate", "url": "https://www.chathamhouse.org/rss/research/topics/climate-change", "country_code": "GB", "tier": "research", "domain": "chathamhouse.org", "language": "en"},
    {"name": "ODI Climate", "url": "https://odi.org/en/publications/feed/", "country_code": "GB", "tier": "research", "domain": "odi.org", "language": "en"},
]


def _flat_feeds(feeds: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
    """Normalize a regional feed list to the common flat format."""
    return [
        {
            "name": f["name"], "url": f["url"],
            "country_code": f.get("country_code", "XX"),
            "reliability_tier": f.get("tier", "public"),
            "source_domain": f.get("domain", ""),
            "language": f.get("language", "en"),
            "region": region,
        }
        for f in feeds
    ]


def get_all_feeds() -> List[Dict[str, Any]]:
    """Return all feeds as flat list across all regions."""
    all_feeds = []
    for cc, feeds in EU_CLIMATE_FEEDS.items():
        for f in feeds:
            all_feeds.append({"name": f["name"], "url": f["url"], "country_code": cc,
                              "reliability_tier": f.get("tier", "public"), "source_domain": f.get("domain", ""),
                              "language": f.get("language", "en"), "region": "europe"})
    for f in EU_WIDE_FEEDS:
        all_feeds.append({"name": f["name"], "url": f["url"], "country_code": f.get("country_code", "EU"),
                          "reliability_tier": f.get("tier", "public"), "source_domain": f.get("domain", ""),
                          "language": f.get("language", "en"), "region": "europe"})
    for f in INTERNATIONAL_CLIMATE_FEEDS:
        all_feeds.append({"name": f["name"], "url": f["url"], "country_code": f.get("country_code", "XX"),
                          "reliability_tier": f.get("tier", "public"), "source_domain": f.get("domain", ""),
                          "language": f.get("language", "en"), "region": "global"})
    all_feeds.extend(_flat_feeds(US_CLIMATE_FEEDS, "north_america"))
    all_feeds.extend(_flat_feeds(AFRICA_CLIMATE_FEEDS, "africa"))
    all_feeds.extend(_flat_feeds(LATAM_CLIMATE_FEEDS, "latin_america"))
    all_feeds.extend(_flat_feeds(ASIA_CLIMATE_FEEDS, "asia"))
    all_feeds.extend(_flat_feeds(MIDDLE_EAST_CLIMATE_FEEDS, "middle_east"))
    all_feeds.extend(_flat_feeds(RESEARCH_INDUSTRY_FEEDS, "research"))
    return all_feeds


def get_feeds_by_country(country_code: str) -> List[Dict[str, Any]]:
    cc = country_code.upper()
    feeds = EU_CLIMATE_FEEDS.get(cc, [])
    result = [{"name": f["name"], "url": f["url"], "country_code": cc,
               "reliability_tier": f.get("tier", "public"), "source_domain": f.get("domain", ""),
               "language": f.get("language", "en")} for f in feeds]
    # Also check regional lists
    for regional_list in [US_CLIMATE_FEEDS, AFRICA_CLIMATE_FEEDS, LATAM_CLIMATE_FEEDS,
                          ASIA_CLIMATE_FEEDS, MIDDLE_EAST_CLIMATE_FEEDS,
                          INTERNATIONAL_CLIMATE_FEEDS, RESEARCH_INDUSTRY_FEEDS]:
        for f in regional_list:
            if f.get("country_code", "").upper() == cc:
                result.append({"name": f["name"], "url": f["url"], "country_code": cc,
                               "reliability_tier": f.get("tier", "public"),
                               "source_domain": f.get("domain", ""),
                               "language": f.get("language", "en")})
    return result


def get_feeds_by_region(region: str) -> List[Dict[str, Any]]:
    """Return feeds filtered by region: europe, global, africa, latin_america."""
    return [f for f in get_all_feeds() if f["region"] == region]


def get_feeds_by_tier(tier: str) -> List[Dict[str, Any]]:
    return [f for f in get_all_feeds() if f["reliability_tier"] == tier]


def get_european_country_codes() -> List[str]:
    return sorted(EU_CLIMATE_FEEDS.keys())


def get_all_regions() -> Dict[str, int]:
    """Return a summary of feed counts per region."""
    feeds = get_all_feeds()
    counts: Dict[str, int] = {}
    for f in feeds:
        r = f.get("region", "unknown")
        counts[r] = counts.get(r, 0) + 1
    return counts
