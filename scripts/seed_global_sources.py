"""
Seed RSS/data sources for ALL underrepresented regions.
Focus: Africa, Latin America, Middle East, Central/South Asia, Pacific.
Topics: green transition, cleantech, circular economy, renewables, resource efficiency.
"""
import os, sys
try:
    import psycopg2, psycopg2.extras
except ImportError:
    sys.exit("pip install psycopg2-binary")

conn = psycopg2.connect(
    host=os.getenv("DB_HOST","localhost"), port=int(os.getenv("DB_PORT","5432")),
    dbname=os.getenv("DB_NAME","climatenews"), user=os.getenv("DB_USER","postgres"),
    password=os.getenv("POSTGRES_PASSWORD","postgres"),
)
conn.autocommit = True
cur = conn.cursor()

SOURCES = [
    # ── AFRICA news + research ───────────────────────────────────────
    ("Africa Renewal (UN)", "https://www.un.org/africarenewal/rss.xml", "XX", "africa", "research", "news_outlet"),
    ("Greenpeace Africa", "https://www.greenpeace.org/africa/en/feed/", "XX", "africa", "research", "ngo"),
    ("AFDB Green Growth", "https://www.afdb.org/en/topics-and-sectors/sectors/climate-change/rss", "XX", "africa", "research", "ngo"),
    ("Climate Scorecard Africa", "https://www.climatescorecard.org/feed/", "XX", "africa", "research", "research"),
    ("Mongabay Africa News", "https://news.mongabay.com/feed/?topics=africa", "XX", "africa", "research", "news_outlet"),
    ("AllAfrica Environment", "https://allafrica.com/tools/headlines/rdf/environment/headlines.rdf", "XX", "africa", "public", "news_outlet"),
    ("Sahara Reporters Green", "https://saharareporters.com/rss.xml", "NG", "africa", "public", "news_outlet"),
    ("Business Day NG", "https://businessday.ng/feed/", "NG", "africa", "public", "news_outlet"),
    ("Mail & Guardian Green", "https://mg.co.za/environment/rss/", "ZA", "africa", "public", "news_outlet"),
    ("Ground Up SA", "https://www.groundup.org.za/rss/", "ZA", "africa", "public", "news_outlet"),
    ("Kenya Climate Innovation", "https://www.kenyacic.org/feed/", "KE", "africa", "research", "research"),
    ("AIMS Africa Research", "https://www.aims.ac.za/feed/", "ZA", "africa", "scientific", "research"),
    ("ENDA Energy Senegal", "https://www.endaenergie.org/feed/", "SN", "africa", "research", "ngo"),
    ("Power Africa (USAID)", "https://www.usaid.gov/powerafrica/rss.xml", "XX", "africa", "government", "government"),
    ("GET.invest Africa", "https://www.get-invest.eu/feed/", "XX", "africa", "research", "industry"),
    ("IRENA Africa Hub", "https://www.irena.org/rss/africa", "XX", "africa", "scientific", "research"),
    ("African Energy Chamber", "https://energychamber.org/feed/", "XX", "africa", "public", "industry"),
    ("Ethiopia EPA", "https://www.epa.gov.et/feed/", "ET", "africa", "government", "government"),
    ("Ghana EPA", "https://www.epa.gov.gh/epa/feed/", "GH", "africa", "government", "government"),
    ("Tanzania NEMC", "https://www.nemc.or.tz/feed/", "TZ", "africa", "government", "government"),

    # ── LATIN AMERICA ────────────────────────────────────────────────
    ("Dialogo Chino Latam", "https://dialogochino.net/es/feed/", "XX", "latin_america", "research", "news_outlet"),
    ("Mongabay Latam ES", "https://es.mongabay.com/feed/", "XX", "latin_america", "research", "news_outlet"),
    ("Agencia EFE Verde", "https://efeverde.com/feed/", "XX", "latin_america", "public", "news_outlet"),
    ("SciDev Latin America", "https://www.scidev.net/america-latina/feed/", "XX", "latin_america", "research", "research"),
    ("BNAmericas Energy", "https://www.bnamericas.com/en/rss/energy", "XX", "latin_america", "public", "industry"),
    ("Climate Reality Latam", "https://www.climaterealityproject.org/feed", "XX", "latin_america", "research", "ngo"),
    ("ECLAC Sustainability", "https://www.cepal.org/en/rss.xml", "XX", "latin_america", "scientific", "research"),
    ("IDB Climate LAC", "https://blogs.iadb.org/sostenibilidad/feed/", "XX", "latin_america", "research", "ngo"),
    ("El Espectador Colombia Env", "https://www.elespectador.com/ambiente/rss/", "CO", "latin_america", "public", "news_outlet"),
    ("La Tercera Chile Env", "https://www.latercera.com/medio-ambiente/feed/", "CL", "latin_america", "public", "news_outlet"),
    ("Folha de SP Ambiente BR", "https://feeds.folha.uol.com.br/ambiente/rss091.xml", "BR", "latin_america", "public", "news_outlet"),
    ("Argentina Ministerio Amb", "https://www.argentina.gob.ar/ambiente/rss", "AR", "latin_america", "government", "government"),
    ("Bolivia Min Medio Ambiente", "https://www.mmaya.gob.bo/feed/", "BO", "latin_america", "government", "government"),
    ("Peru MINAM Noticias", "https://www.gob.pe/minam/noticias/rss", "PE", "latin_america", "government", "government"),
    ("Observatorio do Clima BR", "https://www.oc.eco.br/feed/", "BR", "latin_america", "research", "ngo"),
    ("WWF Latin America", "https://www.worldwildlife.org/blogs/sustainability-works/feed", "XX", "latin_america", "research", "ngo"),
    ("CIER Energy Latam", "https://www.cier.org/feed/", "XX", "latin_america", "research", "industry"),
    ("Caribbean Climate Blog", "https://caribbeanclimateblog.com/feed/", "XX", "latin_america", "research", "research"),
    ("Venezuela Observatory", "https://observatoriodeecologia.org/feed/", "VE", "latin_america", "research", "ngo"),
    ("Ecuador MAE", "https://www.ambiente.gob.ec/feed/", "EC", "latin_america", "government", "government"),

    # ── MIDDLE EAST ──────────────────────────────────────────────────
    ("Middle East Eye Climate", "https://www.middleeasteye.net/rss", "XX", "middle_east", "public", "news_outlet"),
    ("Arab News Green", "https://www.arabnews.com/rss.xml", "SA", "middle_east", "public", "news_outlet"),
    ("Gulf News Environment", "https://gulfnews.com/rss/environment", "AE", "middle_east", "public", "news_outlet"),
    ("Jordan Times Env", "https://jordantimes.com/feed", "JO", "middle_east", "public", "news_outlet"),
    ("Daily Star Lebanon", "https://www.dailystar.com.lb/RSS.aspx", "LB", "middle_east", "public", "news_outlet"),
    ("Khaleej Times Green", "https://www.khaleejtimes.com/rss", "AE", "middle_east", "public", "news_outlet"),
    ("KAPSARC Saudi Energy", "https://www.kapsarc.org/feed/", "SA", "middle_east", "research", "research"),
    ("Masdar UAE Clean Energy", "https://masdar.ae/rss", "AE", "middle_east", "research", "industry"),
    ("RCREEE Arab Renewables", "https://rcreee.org/feed/", "XX", "middle_east", "research", "research"),
    ("Qatar Foundation Green", "https://www.qf.org.qa/rss", "QA", "middle_east", "research", "ngo"),
    ("IRENA Abu Dhabi", "https://www.irena.org/rss/news", "AE", "middle_east", "scientific", "research"),
    ("Kuwait EPA", "https://epa.org.kw/feed/", "KW", "middle_east", "government", "government"),
    ("Oman Env Authority", "https://ea.gov.om/feed/", "OM", "middle_east", "government", "government"),
    ("Iraq Green Belt", "https://www.moen.gov.iq/feed/", "IQ", "middle_east", "government", "government"),
    ("Iran DOE", "https://www.doe.ir/feed/", "IR", "middle_east", "government", "government"),
    ("ACWA Power", "https://www.acwapower.com/rss/", "SA", "middle_east", "public", "industry"),
    ("MESIA Solar ME", "https://mesia.com/feed/", "AE", "middle_east", "research", "industry"),
    ("Emirates Green Building", "https://emiratesgbc.org/feed/", "AE", "middle_east", "research", "industry"),
    ("Bahrain EWA", "https://www.ewa.bh/feed/", "BH", "middle_east", "government", "government"),
    ("Yemen Environmental Prot", "https://www.epa.gov.ye/feed/", "YE", "middle_east", "government", "government"),

    # ── CENTRAL & SOUTH ASIA ────────────────────────────────────────
    ("Down To Earth India", "https://www.downtoearth.org.in/rss", "IN", "asia_pacific", "research", "news_outlet"),
    ("Scroll.in Environment", "https://scroll.in/rss/environment", "IN", "asia_pacific", "public", "news_outlet"),
    ("Pakistan Tribune Green", "https://tribune.com.pk/rss/environment", "PK", "asia_pacific", "public", "news_outlet"),
    ("Daily Star BD Climate", "https://www.thedailystar.net/environment/rss.xml", "BD", "asia_pacific", "public", "news_outlet"),
    ("Nepali Times Climate", "https://www.nepalitimes.com/feed/", "NP", "asia_pacific", "public", "news_outlet"),
    ("Central Asia Energy", "https://cabar.asia/en/feed/", "XX", "asia_pacific", "research", "news_outlet"),
    ("Eurasianet Central Asia", "https://eurasianet.org/feed", "XX", "asia_pacific", "research", "news_outlet"),
    ("AKDN Central Asia", "https://www.akdn.org/rss", "XX", "asia_pacific", "research", "ngo"),
    ("ADB Central Asia", "https://www.adb.org/rss/central-asia", "XX", "asia_pacific", "research", "ngo"),
    ("CAREC Energy", "https://www.carecprogram.org/feed/", "XX", "asia_pacific", "research", "research"),
    ("Kazakhstan Green Economy", "https://igep.kz/feed/", "KZ", "asia_pacific", "government", "government"),
    ("Uzbekistan Ecology", "https://ecology.uz/feed/", "UZ", "asia_pacific", "government", "government"),

    # ── SOUTHEAST ASIA & PACIFIC ─────────────────────────────────────
    ("Channel News Asia Green", "https://www.channelnewsasia.com/rss/sustainability", "SG", "asia_pacific", "public", "news_outlet"),
    ("Frontier Myanmar", "https://www.frontiermyanmar.net/feed/", "MM", "asia_pacific", "public", "news_outlet"),
    ("Mekong Eye", "https://www.mekongeye.com/feed/", "XX", "asia_pacific", "research", "news_outlet"),
    ("Pacific Islands News", "https://www.pina.com.fj/rss/", "FJ", "asia_pacific", "public", "news_outlet"),
    ("Devex Asia Climate", "https://www.devex.com/news/rss", "XX", "asia_pacific", "research", "news_outlet"),
    ("SPREP Pacific Env", "https://www.sprep.org/rss.xml", "XX", "asia_pacific", "scientific", "research"),
    ("SPC Pacific Community", "https://www.spc.int/feed/", "XX", "asia_pacific", "research", "research"),
    ("Pacific Energy", "https://prdrse4all.spc.int/feed/", "XX", "asia_pacific", "research", "industry"),
    ("PNG Post Courier", "https://postcourier.com.pg/feed/", "PG", "asia_pacific", "public", "news_outlet"),
    ("Samoa Observer", "https://www.samoaobserver.ws/rss", "WS", "asia_pacific", "public", "news_outlet"),
    ("Fiji Sun Climate", "https://fijisun.com.fj/feed/", "FJ", "asia_pacific", "public", "news_outlet"),
    ("Philippines Star Green", "https://www.philstar.com/rss/science", "PH", "asia_pacific", "public", "news_outlet"),

    # ── GLOBAL sustainability/cleantech/circular economy ─────────────
    ("Circular Economy Club", "https://www.circulareconomyclub.com/feed/", "XX", "global", "research", "industry"),
    ("Ellen MacArthur Found", "https://www.ellenmacarthurfoundation.org/rss", "XX", "global", "research", "ngo"),
    ("CleanTechnica", "https://cleantechnica.com/feed/", "XX", "global", "public", "industry"),
    ("GreenBiz", "https://www.greenbiz.com/rss", "XX", "global", "research", "industry"),
    ("Renewable Energy World", "https://www.renewableenergyworld.com/feed/", "XX", "global", "public", "industry"),
    ("PV Magazine Global", "https://www.pv-magazine.com/feed/", "XX", "global", "public", "industry"),
    ("Wind Power Monthly", "https://www.windpowermonthly.com/rss", "XX", "global", "public", "industry"),
    ("Energy Monitor", "https://www.energymonitor.ai/feed/", "XX", "global", "research", "industry"),
    ("Resource Efficiency EU", "https://ec.europa.eu/environment/resource_efficiency/rss.xml", "XX", "global", "government", "government"),
    ("Critical Minerals Alliance", "https://www.iea.org/rss/critmin", "XX", "global", "scientific", "research"),
    ("SYSTEMIQ Transitions", "https://www.systemiq.earth/feed/", "XX", "global", "research", "ngo"),
    ("Material Economics", "https://materialeconomics.com/feed/", "XX", "global", "research", "research"),
    ("World Circular Economy Forum", "https://wcef.world/feed/", "XX", "global", "research", "ngo"),
    ("CDP Climate Disclosure", "https://www.cdp.net/en/rss", "XX", "global", "research", "ngo"),
    ("SBTi Net Zero", "https://sciencebasedtargets.org/feed/", "XX", "global", "scientific", "ngo"),
    ("RE100 Renewables", "https://www.there100.org/feed/", "XX", "global", "research", "industry"),
    ("Global Witness Raw Minerals", "https://www.globalwitness.org/en/campaigns/oil-gas-and-mining/feed/", "XX", "global", "research", "ngo"),
    ("Cobalt Institute", "https://www.cobaltinstitute.org/feed/", "XX", "global", "research", "research"),
    ("Lithium Valley", "https://lithiumvalley.org/feed/", "XX", "global", "public", "research"),
    ("Hydrogen Council", "https://hydrogencouncil.com/feed/", "XX", "global", "research", "industry"),

    # ── AFRICA — country-specific green transition ────────────────────
    ("Rwanda FONERWA Green Fund", "https://www.fonerwa.org/feed/", "RW", "africa", "government", "government"),
    ("MASEN Morocco Solar", "https://www.masen.ma/feed/", "MA", "africa", "government", "government"),
    ("KPLC Kenya Power", "https://www.kplc.co.ke/feed/", "KE", "africa", "government", "industry"),
    ("EEHC Egypt Renewables", "https://www.eehc.gov.eg/feed/", "EG", "africa", "government", "government"),
    ("GNPC Ghana Energy", "https://www.gnpc.com.gh/feed/", "GH", "africa", "government", "industry"),
    ("TANESCO Tanzania", "https://www.tanesco.co.tz/feed/", "TZ", "africa", "government", "government"),
    ("SAPP Southern Africa Power", "https://www.sapp.co.zw/feed/", "ZA", "africa", "research", "industry"),
    ("Nigeria NERC Electricity", "https://www.nerc.gov.ng/feed/", "NG", "africa", "government", "government"),
    ("Ethiopia EEP Power", "https://www.eep.com.et/feed/", "ET", "africa", "government", "government"),
    ("Afrik21 Green Economy", "https://www.afrik21.africa/feed/", "XX", "africa", "public", "news_outlet"),
    ("Clean Cooking Alliance Africa", "https://www.cleancooking.org/feed/", "XX", "africa", "research", "ngo"),
    ("Africa Circular Economy Network", "https://acen.africa/feed/", "XX", "africa", "research", "ngo"),

    # ── ASIA — country-specific clean energy ─────────────────────────
    ("EVN Vietnam Energy", "https://www.evn.com.vn/feed/", "VN", "asia_pacific", "government", "government"),
    ("MEMR Indonesia Energy", "https://www.esdm.go.id/feed/", "ID", "asia_pacific", "government", "government"),
    ("DOE Philippines Energy", "https://www.doe.gov.ph/feed/", "PH", "asia_pacific", "government", "government"),
    ("SREDA Bangladesh Renewables", "https://www.sreda.gov.bd/feed/", "BD", "asia_pacific", "government", "government"),
    ("MNRE India Renewables", "https://mnre.gov.in/feed/", "IN", "asia_pacific", "government", "government"),
    ("KITA Korea Trade", "https://www.kita.net/rss", "KR", "asia_pacific", "research", "industry"),
    ("Vietnam MOIT Energy", "https://www.moit.gov.vn/feed/", "VN", "asia_pacific", "government", "government"),
    ("Myanmar Energy Ministry", "https://www.moee.gov.mm/feed/", "MM", "asia_pacific", "government", "government"),
    ("Thailand EPPO Energy", "https://www.eppo.go.th/feed/", "TH", "asia_pacific", "government", "government"),
    ("China NEA Renewables", "https://www.nea.gov.cn/rss/", "CN", "asia_pacific", "government", "government"),
    ("Japan ANRE Energy", "https://www.enecho.meti.go.jp/rss/", "JP", "asia_pacific", "government", "government"),
    ("Korea KEA Efficiency", "https://www.energy.or.kr/rss/", "KR", "asia_pacific", "government", "government"),
    ("Eco-Business Asia", "https://www.eco-business.com/rss/", "SG", "asia_pacific", "public", "news_outlet"),
    ("China Dialogue Ocean", "https://chinadialogueocean.net/feed/", "CN", "asia_pacific", "research", "news_outlet"),
    ("Climate Tracker Asia", "https://climatetracker.org/asia/feed/", "XX", "asia_pacific", "research", "ngo"),

    # ── LATIN AMERICA — country-specific ─────────────────────────────
    ("YLB Bolivia Lithium", "https://www.ylb.gob.bo/feed/", "BO", "latin_america", "government", "government"),
    ("Minem Peru Mining", "https://www.minem.gob.pe/feed/", "PE", "latin_america", "government", "government"),
    ("UPME Colombia Energy", "https://www1.upme.gov.co/rss/", "CO", "latin_america", "government", "government"),
    ("CNE Chile Energy", "https://www.cne.cl/rss/", "CL", "latin_america", "government", "government"),
    ("ANEEL Brazil Energy", "https://www.aneel.gov.br/rss/", "BR", "latin_america", "government", "government"),
    ("ANDE Paraguay Energy", "https://www.ande.gov.py/feed/", "PY", "latin_america", "government", "government"),
    ("UTE Uruguay Energy", "https://www.ute.com.uy/feed/", "UY", "latin_america", "government", "government"),
    ("Secretaria Ambiente Ecuador", "https://www.ambiente.gob.ec/feed/", "EC", "latin_america", "government", "government"),
    ("LitioAr Argentina", "https://www.litioar.com.ar/feed/", "AR", "latin_america", "research", "industry"),
    ("Latin America Climate Hub", "https://www.latinclimate.org/feed/", "XX", "latin_america", "research", "ngo"),
    ("Agencia EFE Desarrollo Sostenible", "https://www.efeagro.com/feed/", "XX", "latin_america", "public", "news_outlet"),

    # ── CRITICAL MINERALS & RESOURCE EFFICIENCY — global ─────────────
    ("NRGI Natural Resources", "https://resourcegovernance.org/feed/", "XX", "global", "research", "ngo"),
    ("Raw Materials EU Initiative", "https://ec.europa.eu/growth/sectors/raw-materials/rss", "XX", "global", "government", "government"),
    ("USGS Mineral Resources", "https://www.usgs.gov/rss/mineral-resources-program", "XX", "global", "scientific", "government"),
    ("Critical Minerals Monitor", "https://criticalmineral.watch/feed/", "XX", "global", "research", "research"),
    ("Mining.com Green Minerals", "https://www.mining.com/category/environment/feed/", "XX", "global", "public", "industry"),
    ("Benchmark Mineral Intelligence", "https://www.benchmarkminerals.com/feed/", "XX", "global", "research", "industry"),
    ("International Mining Green", "https://im-mining.com/feed/", "XX", "global", "public", "industry"),
    ("EEA Resource Use EU", "https://www.eea.europa.eu/rss/topics/resource-use", "XX", "global", "scientific", "government"),
    ("WEF Green Transition", "https://www.weforum.org/agenda/energy-and-utilities/rss", "XX", "global", "research", "ngo"),
    ("IISD Resource Efficiency", "https://www.iisd.org/feed/", "XX", "global", "research", "ngo"),
    ("Chatham House Resources", "https://www.chathamhouse.org/topics/energy-environment/rss", "XX", "global", "research", "research"),
    ("Transition Minerals Tracker", "https://transitionminerals.org/feed/", "XX", "global", "research", "ngo"),
    ("REN21 Global Status", "https://www.ren21.net/feed/", "XX", "global", "scientific", "research"),
    ("BNEF Energy Transition", "https://about.bnef.com/blog/feed/", "XX", "global", "research", "industry"),
    ("IEA Energy Transition", "https://www.iea.org/rss/news", "XX", "global", "scientific", "research"),
    ("Rocky Mountain Institute", "https://rmi.org/feed/", "XX", "global", "research", "ngo"),
    ("E3G Climate Policy", "https://www.e3g.org/feed/", "XX", "global", "research", "ngo"),
    ("Sandbag Carbon Policy", "https://sandbag.be/feed/", "XX", "global", "research", "ngo"),
    ("Global EV Outlook BNEF", "https://about.bnef.com/electric-vehicle-outlook/feed/", "XX", "global", "research", "research"),
    ("Just Transition Initiative", "https://www.ilo.org/global/topics/green-jobs/rss", "XX", "global", "research", "ngo"),
]

inserted = 0
for name, url, cc, region, tier, stype in SOURCES:
    try:
        cur.execute("""
            INSERT INTO rss_feed_registry (feed_name, feed_url, country_code, region, reliability_tier, source_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (feed_url) DO NOTHING
        """, (name, url, cc, region, tier, stype))
        if cur.rowcount > 0:
            inserted += 1
    except Exception as e:
        # Likely duplicate feed_name
        conn.rollback()
        conn.autocommit = True
        try:
            cur.execute("""
                INSERT INTO rss_feed_registry (feed_name, feed_url, country_code, region, reliability_tier, source_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (feed_url) DO NOTHING
            """, (name + " Feed", url, cc, region, tier, stype))
            if cur.rowcount > 0:
                inserted += 1
        except:
            pass

cur.execute("SELECT region, count(*) as cnt FROM rss_feed_registry GROUP BY region ORDER BY cnt DESC")
regions = cur.fetchall()
cur.execute("SELECT source_type, count(*) as cnt FROM rss_feed_registry GROUP BY source_type ORDER BY cnt DESC")
types = cur.fetchall()
cur.execute("SELECT count(*) FROM rss_feed_registry")
total = cur.fetchone()[0]
cur.execute("SELECT count(DISTINCT country_code) FROM rss_feed_registry WHERE country_code IS NOT NULL AND country_code <> 'XX'")
countries = cur.fetchone()[0]

print(f"Inserted: {inserted} new sources")
print(f"Total sources: {total}")
print(f"Countries with sources: {countries}")
print("By region:")
for r in regions:
    print(f"  {r[0]}: {r[1]}")
print("By type:")
for t in types:
    print(f"  {t[0]}: {t[1]}")

cur.close()
conn.close()
