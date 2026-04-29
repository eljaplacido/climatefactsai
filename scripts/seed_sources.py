#!/usr/bin/env python3
"""
Seed reliable climate news sources into the rss_feed_registry table.

Adds 120+ new sources across six categories:
  - news_outlet:   Major climate/environment news outlets
  - government:    Government climate agencies and reports
  - research:      Universities and research institutions
  - ngo:           NGOs and think tanks
  - weather_data:  Weather/climate data providers
  - industry:      Industry reports, ESG, clean energy data

Usage:
    python scripts/seed_sources.py
    DB_PORT=5433 python scripts/seed_sources.py
"""

import os
import sys

import psycopg2

# ---------------------------------------------------------------------------
# Database connection — honours environment variables, falls back to defaults
# matching docker-compose.yml (external port 5433).
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "climatenews"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

# ---------------------------------------------------------------------------
# Source definitions — every entry is a tuple of:
#   (feed_name, feed_url, source_domain, country_code, region,
#    reliability_tier, source_type)
# ---------------------------------------------------------------------------

NEWS_OUTLET_SOURCES = [
    # North America
    ("Washington Post Climate", "https://feeds.washingtonpost.com/rss/climate-environment", "washingtonpost.com", "US", "north_america", "public", "news_outlet"),
    ("Bloomberg Green", "https://feeds.bloomberg.com/green/sitemap_news.xml", "bloomberg.com", "US", "north_america", "public", "news_outlet"),
    ("CNN Climate", "https://rss.cnn.com/rss/edition_climate.rss", "cnn.com", "US", "north_america", "public", "news_outlet"),
    ("Axios Climate", "https://www.axios.com/feeds/tag/climate", "axios.com", "US", "north_america", "public", "news_outlet"),
    ("The Hill Energy & Environment", "https://thehill.com/feed/?topic=energy-environment", "thehill.com", "US", "north_america", "public", "news_outlet"),
    ("Canary Media", "https://www.canarymedia.com/feed", "canarymedia.com", "US", "north_america", "research", "news_outlet"),
    ("Heated Newsletter", "https://heated.world/feed", "heated.world", "US", "north_america", "public", "news_outlet"),
    ("DeSmog", "https://www.desmog.com/feed/", "desmog.com", "US", "north_america", "research", "news_outlet"),
    ("E&E News", "https://www.eenews.net/feed/", "eenews.net", "US", "north_america", "public", "news_outlet"),
    ("CBC Climate (CA)", "https://www.cbc.ca/cmlink/rss-science", "cbc.ca", "CA", "north_america", "public", "news_outlet"),
    ("Toronto Star Climate (CA)", "https://www.thestar.com/search/?contenttype=articles&q=climate&output=rss", "thestar.com", "CA", "north_america", "public", "news_outlet"),
    # Europe
    ("Euronews Green", "https://www.euronews.com/rss?level=theme&name=green", "euronews.com", "XX", "europe", "public", "news_outlet"),
    ("Deutsche Welle Environment", "https://rss.dw.com/xml/rss-en-environment", "dw.com", "DE", "europe", "public", "news_outlet"),
    ("Politico Europe Energy", "https://www.politico.eu/section/energy/feed/", "politico.eu", "XX", "europe", "public", "news_outlet"),
    ("The Conversation Environment", "https://theconversation.com/environment/articles.atom", "theconversation.com", "XX", "global", "research", "news_outlet"),
    ("Al Jazeera Climate", "https://www.aljazeera.com/xml/rss/all.xml", "aljazeera.com", "QA", "global", "public", "news_outlet"),
    # Asia-Pacific
    ("Japan Times Environment", "https://www.japantimes.co.jp/feed/environment/", "japantimes.co.jp", "JP", "asia_pacific", "public", "news_outlet"),
    ("South China Morning Post Climate", "https://www.scmp.com/rss/5/feed", "scmp.com", "HK", "asia_pacific", "public", "news_outlet"),
    ("Eco-Business Asia", "https://www.eco-business.com/feeds/news/", "eco-business.com", "SG", "asia_pacific", "research", "news_outlet"),
    ("The Third Pole", "https://www.thethirdpole.net/feed/", "thethirdpole.net", "XX", "asia_pacific", "research", "news_outlet"),
    # Latin America
    ("Climate Tracker Latam", "https://climatetrackerlatam.org/feed/", "climatetrackerlatam.org", "XX", "latin_america", "research", "news_outlet"),
    # Africa
    ("The Continent Africa", "https://www.thecontinent.org/feed/", "thecontinent.org", "XX", "africa", "public", "news_outlet"),
    ("Climate Tracker Africa", "https://climatetrackerafrica.org/feed/", "climatetrackerafrica.org", "XX", "africa", "research", "news_outlet"),
]

GOVERNMENT_SOURCES = [
    ("EPA News (US)", "https://www.epa.gov/newsreleases/search/rss", "epa.gov", "US", "north_america", "government", "government"),
    ("US DOE News", "https://www.energy.gov/rss.xml", "energy.gov", "US", "north_america", "government", "government"),
    ("White House Climate", "https://www.whitehouse.gov/feed/", "whitehouse.gov", "US", "north_america", "government", "government"),
    ("DEFRA UK", "https://www.gov.uk/government/organisations/department-for-environment-food-rural-affairs.atom", "gov.uk", "GB", "europe", "government", "government"),
    ("UK CCC", "https://www.theccc.org.uk/feed/", "theccc.org.uk", "GB", "europe", "government", "government"),
    ("Umweltbundesamt (DE)", "https://www.umweltbundesamt.de/rss/presse", "umweltbundesamt.de", "DE", "europe", "government", "government"),
    ("BMUV Germany", "https://www.bmuv.de/presse/rss-feed", "bmuv.de", "DE", "europe", "government", "government"),
    ("Ministere Transition Ecologique (FR)", "https://www.ecologie.gouv.fr/rss_actualites.xml", "ecologie.gouv.fr", "FR", "europe", "government", "government"),
    ("MITECO Spain", "https://www.miteco.gob.es/es/prensa/rss.aspx", "miteco.gob.es", "ES", "europe", "government", "government"),
    ("ISPRA Italy", "https://www.isprambiente.gov.it/it/news/RSS", "isprambiente.gov.it", "IT", "europe", "government", "government"),
    ("Environment Canada", "https://www.canada.ca/en/environment-climate-change.atom.xml", "canada.ca", "CA", "north_america", "government", "government"),
    ("Environment Ministry Japan", "https://www.env.go.jp/en/rss/index.xml", "env.go.jp", "JP", "asia_pacific", "government", "government"),
    ("MoEFCC India", "https://moef.gov.in/en/feed/", "moef.gov.in", "IN", "asia_pacific", "government", "government"),
    ("DCCEEW Australia", "https://www.dcceew.gov.au/rss.xml", "dcceew.gov.au", "AU", "asia_pacific", "government", "government"),
    ("UNEP News", "https://www.unep.org/news-and-stories/rss.xml", "unep.org", "XX", "global", "government", "government"),
    ("UNFCCC News", "https://unfccc.int/news/feed", "unfccc.int", "XX", "global", "government", "government"),
    ("EU Climate Action", "https://ec.europa.eu/clima/news/rss_en", "ec.europa.eu", "XX", "europe", "government", "government"),
    ("European Commission Environment", "https://ec.europa.eu/environment/news/rss_en", "ec.europa.eu", "XX", "europe", "government", "government"),
    ("World Bank Climate", "https://www.worldbank.org/en/topic/climatechange/rss.xml", "worldbank.org", "XX", "global", "government", "government"),
    ("Green Climate Fund", "https://www.greenclimate.fund/feed", "greenclimate.fund", "XX", "global", "government", "government"),
    ("MEE China", "https://english.mee.gov.cn/rss/index.shtml", "mee.gov.cn", "CN", "asia_pacific", "government", "government"),
    ("DFFE South Africa", "https://www.dffe.gov.za/rss.xml", "dffe.gov.za", "ZA", "africa", "government", "government"),
]

RESEARCH_SOURCES = [
    ("MIT Climate Portal", "https://climate.mit.edu/feed", "climate.mit.edu", "US", "north_america", "scientific", "research"),
    ("Stanford Earth", "https://earth.stanford.edu/news/feed", "earth.stanford.edu", "US", "north_america", "scientific", "research"),
    ("Columbia Climate School", "https://news.climate.columbia.edu/feed/", "climate.columbia.edu", "US", "north_america", "scientific", "research"),
    ("Yale Environment 360", "https://e360.yale.edu/feed", "e360.yale.edu", "US", "north_america", "scientific", "research"),
    ("Woods Hole Oceanographic", "https://www.whoi.edu/feed/", "whoi.edu", "US", "north_america", "scientific", "research"),
    ("NCAR Climate", "https://news.ucar.edu/rss.xml", "ucar.edu", "US", "north_america", "scientific", "research"),
    ("PIK Potsdam (DE)", "https://www.pik-potsdam.de/en/news/rss", "pik-potsdam.de", "DE", "europe", "scientific", "research"),
    ("Oxford Smith School", "https://www.smithschool.ox.ac.uk/news/feed", "ox.ac.uk", "GB", "europe", "scientific", "research"),
    ("Grantham Institute Imperial", "https://www.imperial.ac.uk/grantham/news/feed/", "imperial.ac.uk", "GB", "europe", "scientific", "research"),
    ("ETH Zurich Climate", "https://ethz.ch/en/news-and-events/eth-news/news.rss.xml", "ethz.ch", "CH", "europe", "scientific", "research"),
    ("Wageningen Climate (NL)", "https://www.wur.nl/en/newsarticle/rss.xml", "wur.nl", "NL", "europe", "scientific", "research"),
    ("CICERO Norway", "https://cicero.oslo.no/en/feed", "cicero.oslo.no", "NO", "europe", "scientific", "research"),
    ("Science Daily Climate", "https://www.sciencedaily.com/rss/earth_climate/climate.xml", "sciencedaily.com", "US", "north_america", "scientific", "research"),
    ("Phys.org Climate", "https://phys.org/rss-feed/earth-news/climate-change/", "phys.org", "XX", "global", "scientific", "research"),
    ("Environmental Research Letters", "https://iopscience.iop.org/journal/rss/1748-9326", "iopscience.iop.org", "XX", "global", "scientific", "research"),
    ("AGU Eos Climate", "https://eos.org/feed", "eos.org", "US", "north_america", "scientific", "research"),
    ("RealClimate", "https://www.realclimate.org/index.php/feed/", "realclimate.org", "US", "north_america", "scientific", "research"),
    ("Climate Feedback", "https://climatefeedback.org/feed/", "climatefeedback.org", "US", "north_america", "scientific", "research"),
    ("IIASA Austria", "https://iiasa.ac.at/rss.xml", "iiasa.ac.at", "AT", "europe", "scientific", "research"),
    ("Tyndall Centre UK", "https://tyndall.ac.uk/feed/", "tyndall.ac.uk", "GB", "europe", "scientific", "research"),
    ("TERI India", "https://www.teriin.org/feed", "teriin.org", "IN", "asia_pacific", "scientific", "research"),
]

NGO_SOURCES = [
    ("Greenpeace International", "https://www.greenpeace.org/international/feed/", "greenpeace.org", "XX", "global", "public", "ngo"),
    ("WWF News", "https://www.worldwildlife.org/rss/news.xml", "worldwildlife.org", "US", "global", "public", "ngo"),
    ("350.org", "https://350.org/feed/", "350.org", "US", "global", "public", "ngo"),
    ("Climate Action Network", "https://climatenetwork.org/feed/", "climatenetwork.org", "XX", "global", "public", "ngo"),
    ("WRI Stories", "https://www.wri.org/feed", "wri.org", "US", "north_america", "research", "ngo"),
    ("Resources for the Future", "https://www.rff.org/feed/", "rff.org", "US", "north_america", "research", "ngo"),
    ("Brookings Climate", "https://www.brookings.edu/topic/climate-change/feed/", "brookings.edu", "US", "north_america", "research", "ngo"),
    ("CSIS Energy & Sustainability", "https://www.csis.org/programs/energy-security-and-climate-change-program/feed", "csis.org", "US", "north_america", "research", "ngo"),
    ("Chatham House Environment", "https://www.chathamhouse.org/topics/environment-and-society/feed", "chathamhouse.org", "GB", "europe", "research", "ngo"),
    ("E3G", "https://www.e3g.org/feed/", "e3g.org", "GB", "europe", "research", "ngo"),
    ("Climate Analytics", "https://climateanalytics.org/feed/", "climateanalytics.org", "DE", "europe", "research", "ngo"),
    ("Germanwatch", "https://www.germanwatch.org/en/feed", "germanwatch.org", "DE", "europe", "research", "ngo"),
    ("IDDRI France", "https://www.iddri.org/en/feed", "iddri.org", "FR", "europe", "research", "ngo"),
    ("Stockholm Environment Institute", "https://www.sei.org/feed/", "sei.org", "SE", "europe", "research", "ngo"),
    ("IIED", "https://www.iied.org/rss.xml", "iied.org", "GB", "europe", "research", "ngo"),
    ("ClimateWorks Foundation", "https://www.climateworks.org/feed/", "climateworks.org", "US", "north_america", "research", "ngo"),
    ("C40 Cities", "https://www.c40.org/feed/", "c40.org", "XX", "global", "public", "ngo"),
    ("Global Witness", "https://www.globalwitness.org/en/feed/", "globalwitness.org", "GB", "global", "public", "ngo"),
    ("Union of Concerned Scientists", "https://blog.ucsusa.org/feed/", "ucsusa.org", "US", "north_america", "research", "ngo"),
    ("Natural Resources Defense Council", "https://www.nrdc.org/rss.xml", "nrdc.org", "US", "north_america", "public", "ngo"),
    ("Oxfam Climate", "https://www.oxfam.org/en/tags/climate-change/rss.xml", "oxfam.org", "XX", "global", "public", "ngo"),
    ("Sierra Club", "https://www.sierraclub.org/rss.xml", "sierraclub.org", "US", "north_america", "public", "ngo"),
]

WEATHER_DATA_SOURCES = [
    # US
    ("NOAA Climate Data", "https://www.ncei.noaa.gov/news/feed", "ncei.noaa.gov", "US", "north_america", "scientific", "weather_data"),
    ("NOAA National Weather Service", "https://www.weather.gov/rss/", "weather.gov", "US", "north_america", "scientific", "weather_data"),
    ("NASA GISS", "https://www.giss.nasa.gov/research/news/feed.rss", "giss.nasa.gov", "US", "north_america", "scientific", "weather_data"),
    ("NASA Earth Observatory", "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss", "earthobservatory.nasa.gov", "US", "north_america", "scientific", "weather_data"),
    ("NSIDC Arctic News", "https://nsidc.org/news/rss.xml", "nsidc.org", "US", "north_america", "scientific", "weather_data"),
    ("Arctic Data Center", "https://arcticdata.io/feed/", "arcticdata.io", "US", "north_america", "scientific", "weather_data"),
    # Europe
    ("Met Office UK", "https://blog.metoffice.gov.uk/feed/", "metoffice.gov.uk", "GB", "europe", "scientific", "weather_data"),
    ("DWD Germany", "https://www.dwd.de/rss/presse", "dwd.de", "DE", "europe", "scientific", "weather_data"),
    ("Meteo-France News", "https://meteofrance.com/rss.xml", "meteofrance.com", "FR", "europe", "scientific", "weather_data"),
    ("AEMET Spain", "https://www.aemet.es/es/noticias/rss", "aemet.es", "ES", "europe", "scientific", "weather_data"),
    ("SMHI Sweden", "https://www.smhi.se/rss/nyheter", "smhi.se", "SE", "europe", "scientific", "weather_data"),
    ("FMI Finland", "https://www.ilmatieteenlaitos.fi/rss/uutiset", "ilmatieteenlaitos.fi", "FI", "europe", "scientific", "weather_data"),
    ("DMI Denmark", "https://www.dmi.dk/feed/", "dmi.dk", "DK", "europe", "scientific", "weather_data"),
    ("KNMI Netherlands", "https://www.knmi.nl/rss/nieuws", "knmi.nl", "NL", "europe", "scientific", "weather_data"),
    ("IPMA Portugal", "https://www.ipma.pt/en/rss/", "ipma.pt", "PT", "europe", "scientific", "weather_data"),
    ("GeoSphere Austria (ZAMG)", "https://www.zamg.ac.at/cms/de/wetter/rss", "zamg.ac.at", "AT", "europe", "scientific", "weather_data"),
    ("MeteoSwiss", "https://www.meteoswiss.admin.ch/services-and-publications/service/news.rss", "meteoswiss.admin.ch", "CH", "europe", "scientific", "weather_data"),
    ("Met Eireann Ireland", "https://www.met.ie/rss/warnings.xml", "met.ie", "IE", "europe", "scientific", "weather_data"),
    # Global / International
    ("ECMWF Forecasts", "https://www.ecmwf.int/en/forecasts/rss", "ecmwf.int", "XX", "europe", "scientific", "weather_data"),
    ("Copernicus Climate Change Service", "https://climate.copernicus.eu/rss-feed", "climate.copernicus.eu", "XX", "europe", "scientific", "weather_data"),
    ("WMO News", "https://wmo.int/news/feed", "wmo.int", "XX", "global", "scientific", "weather_data"),
    # Asia-Pacific
    ("IMD India", "https://mausam.imd.gov.in/rss/imd_rss.xml", "mausam.imd.gov.in", "IN", "asia_pacific", "scientific", "weather_data"),
    ("JMA Japan", "https://www.jma.go.jp/jma/en/news.rss", "jma.go.jp", "JP", "asia_pacific", "scientific", "weather_data"),
    ("BoM Australia", "https://media.bom.gov.au/releases/feed/", "bom.gov.au", "AU", "asia_pacific", "scientific", "weather_data"),
    ("KMA South Korea", "https://web.kma.go.kr/eng/rss/rss.jsp", "kma.go.kr", "KR", "asia_pacific", "scientific", "weather_data"),
    # Canada
    ("Environment Canada Weather", "https://weather.gc.ca/rss/city/on-143_e.xml", "weather.gc.ca", "CA", "north_america", "scientific", "weather_data"),
    # Southern Hemisphere
    ("NIWA New Zealand", "https://niwa.co.nz/news/feed", "niwa.co.nz", "NZ", "asia_pacific", "scientific", "weather_data"),
    ("SAWS South Africa", "https://www.weathersa.co.za/feed/", "weathersa.co.za", "ZA", "africa", "scientific", "weather_data"),
]

INDUSTRY_SOURCES = [
    ("IRENA News", "https://www.irena.org/news/rss", "irena.org", "XX", "global", "research", "industry"),
    ("IEA News", "https://www.iea.org/rss/news.xml", "iea.org", "XX", "global", "research", "industry"),
    ("BloombergNEF", "https://about.bnef.com/feed/", "bnef.com", "US", "global", "public", "industry"),
    ("S&P Global ESG", "https://www.spglobal.com/esg/rss/", "spglobal.com", "US", "global", "public", "industry"),
    ("Renewable Energy World", "https://www.renewableenergyworld.com/feed/", "renewableenergyworld.com", "US", "north_america", "public", "industry"),
    ("PV Magazine", "https://www.pv-magazine.com/feed/", "pv-magazine.com", "DE", "global", "public", "industry"),
    ("WindPower Monthly", "https://www.windpowermonthly.com/rss", "windpowermonthly.com", "GB", "global", "public", "industry"),
    ("Recharge News", "https://www.rechargenews.com/rss", "rechargenews.com", "NO", "global", "public", "industry"),
    ("GreenTech Media", "https://www.greentechmedia.com/feed", "greentechmedia.com", "US", "north_america", "public", "industry"),
    ("Energy Monitor", "https://www.energymonitor.ai/feed/", "energymonitor.ai", "GB", "global", "public", "industry"),
    ("Carbon Tracker", "https://carbontracker.org/feed/", "carbontracker.org", "GB", "global", "research", "industry"),
    ("CDP", "https://www.cdp.net/en/articles/feed", "cdp.net", "XX", "global", "research", "industry"),
    ("Rocky Mountain Institute", "https://rmi.org/feed/", "rmi.org", "US", "north_america", "research", "industry"),
    ("Energy Transitions Commission", "https://www.energy-transitions.org/feed/", "energy-transitions.org", "XX", "global", "research", "industry"),
    ("Climate Bonds Initiative", "https://www.climatebonds.net/feed", "climatebonds.net", "GB", "global", "research", "industry"),
    ("Global CCS Institute", "https://www.globalccsinstitute.com/feed/", "globalccsinstitute.com", "AU", "global", "research", "industry"),
    ("Ember Climate", "https://ember-climate.org/feed/", "ember-climate.org", "GB", "global", "research", "industry"),
    ("Clean Technica", "https://cleantechnica.com/feed/", "cleantechnica.com", "US", "north_america", "public", "industry"),
    ("Utility Dive", "https://www.utilitydive.com/feeds/news/", "utilitydive.com", "US", "north_america", "public", "industry"),
    ("Power Technology", "https://www.power-technology.com/feed/", "power-technology.com", "GB", "global", "public", "industry"),
    ("Hydrogen Insight", "https://www.hydrogeninsight.com/rss", "hydrogeninsight.com", "NO", "global", "public", "industry"),
    ("Energy Storage News", "https://www.energy-storage.news/feed/", "energy-storage.news", "GB", "global", "public", "industry"),
]

# Collect everything into a single ordered list
ALL_SOURCES = (
    NEWS_OUTLET_SOURCES
    + GOVERNMENT_SOURCES
    + RESEARCH_SOURCES
    + NGO_SOURCES
    + WEATHER_DATA_SOURCES
    + INDUSTRY_SOURCES
)

# ---------------------------------------------------------------------------
# Mapping used to back-fill source_type for rows that already exist but lack
# the column.  We infer category from reliability_tier as a reasonable default.
# ---------------------------------------------------------------------------
TIER_TO_SOURCE_TYPE = {
    "scientific": "research",
    "research": "research",
    "government": "government",
    "public": "news_outlet",
}


def run_seed():
    conn = None
    try:
        print(f"Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']} ...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cur = conn.cursor()

        # ------------------------------------------------------------------
        # 1. Add source_type column if it does not exist
        # ------------------------------------------------------------------
        print("\n[1/4] Ensuring source_type column exists ...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'rss_feed_registry'
                      AND column_name = 'source_type'
                ) THEN
                    ALTER TABLE rss_feed_registry
                        ADD COLUMN source_type VARCHAR(50) DEFAULT 'news_outlet';
                    RAISE NOTICE 'Column source_type added.';
                ELSE
                    RAISE NOTICE 'Column source_type already exists.';
                END IF;
            END
            $$;
        """)
        conn.commit()
        print("       source_type column: OK")

        # ------------------------------------------------------------------
        # 2. Back-fill existing rows that still have the default source_type
        # ------------------------------------------------------------------
        print("\n[2/4] Back-filling source_type on existing rows ...")
        updated_rows = 0
        for tier, stype in TIER_TO_SOURCE_TYPE.items():
            cur.execute("""
                UPDATE rss_feed_registry
                SET source_type = %s
                WHERE reliability_tier = %s
                  AND (source_type IS NULL OR source_type = 'news_outlet')
                  AND reliability_tier != 'public'
            """, (stype, tier))
            updated_rows += cur.rowcount
        conn.commit()
        print(f"       Updated {updated_rows} existing row(s) with inferred source_type.")

        # ------------------------------------------------------------------
        # 3. Count existing sources before insert
        # ------------------------------------------------------------------
        cur.execute("SELECT COUNT(*) FROM rss_feed_registry")
        count_before = cur.fetchone()[0]
        print(f"\n       Existing sources in registry: {count_before}")

        # ------------------------------------------------------------------
        # 4. Insert new sources — ON CONFLICT (feed_url) DO NOTHING
        # ------------------------------------------------------------------
        print(f"\n[3/4] Inserting up to {len(ALL_SOURCES)} new sources ...")

        insert_sql = """
            INSERT INTO rss_feed_registry
                (feed_name, feed_url, source_domain, country_code, region,
                 reliability_tier, source_type, is_active, is_system_feed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true, true)
            ON CONFLICT (feed_url) DO NOTHING
        """

        category_counts = {}
        for src in ALL_SOURCES:
            cur.execute(insert_sql, src)
            cat = src[6]  # source_type is the 7th element
            category_counts.setdefault(cat, {"attempted": 0, "inserted": 0})
            category_counts[cat]["attempted"] += 1
            if cur.rowcount > 0:
                category_counts[cat]["inserted"] += 1

        conn.commit()

        # ------------------------------------------------------------------
        # 5. Summary
        # ------------------------------------------------------------------
        cur.execute("SELECT COUNT(*) FROM rss_feed_registry")
        count_after = cur.fetchone()[0]
        actually_added = count_after - count_before

        print(f"\n[4/4] Summary")
        print(f"       {'Category':<20} {'Attempted':>10} {'Inserted':>10}")
        print(f"       {'-'*20} {'-'*10} {'-'*10}")
        total_attempted = 0
        total_inserted = 0
        for cat in ["news_outlet", "government", "research", "ngo", "weather_data", "industry"]:
            info = category_counts.get(cat, {"attempted": 0, "inserted": 0})
            print(f"       {cat:<20} {info['attempted']:>10} {info['inserted']:>10}")
            total_attempted += info["attempted"]
            total_inserted += info["inserted"]
        print(f"       {'-'*20} {'-'*10} {'-'*10}")
        print(f"       {'TOTAL':<20} {total_attempted:>10} {total_inserted:>10}")
        print()
        print(f"       Sources before: {count_before}")
        print(f"       Sources after:  {count_after}")
        print(f"       Net new:        {actually_added}")

        # Breakdown by source_type in the database
        print("\n       Counts by source_type in database:")
        cur.execute("""
            SELECT source_type, COUNT(*) AS cnt
            FROM rss_feed_registry
            GROUP BY source_type
            ORDER BY cnt DESC
        """)
        for row in cur.fetchall():
            print(f"         {row[0] or 'NULL':<20} {row[1]:>5}")

        # Breakdown by region
        print("\n       Counts by region in database:")
        cur.execute("""
            SELECT region, COUNT(*) AS cnt
            FROM rss_feed_registry
            GROUP BY region
            ORDER BY cnt DESC
        """)
        for row in cur.fetchall():
            print(f"         {row[0] or 'NULL':<20} {row[1]:>5}")

        print("\n       Done.")
        return True

    except psycopg2.OperationalError as exc:
        print(f"\nERROR: Could not connect to the database.")
        print(f"       {exc}")
        print(f"\n       Hints:")
        print(f"         - Is the Docker container 'climatenews-postgres' running?")
        print(f"         - Port mapping in docker-compose.yml uses 5433:5432.")
        print(f"           Try: DB_PORT=5433 python scripts/seed_sources.py")
        print(f"         - Set POSTGRES_PASSWORD if the default does not work.")
        return False

    except Exception as exc:
        print(f"\nERROR: {exc}")
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()
            print("       Connection closed.")


if __name__ == "__main__":
    print("=" * 70)
    print("  CliLens.AI  --  Seed Climate News Sources")
    print("=" * 70)
    success = run_seed()
    sys.exit(0 if success else 1)
