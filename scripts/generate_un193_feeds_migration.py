"""Generate migration 026 with Google News RSS feeds for UN-193 country coverage.

Writes to infrastructure/database/migrations/versions/026_un193_country_feeds.sql.
Idempotent (ON CONFLICT DO NOTHING).

Google News country-and-language-scoped climate queries surface real
publisher articles tagged by country. The resulting feed_url returns RSS
entries whose source attribution still cites the underlying publisher.
"""

from pathlib import Path

UN_193 = [
    # (iso2, lang, region, name) — UN-193 member states.
    ("DZ","ar","africa","Algeria"),("AO","pt","africa","Angola"),("BJ","fr","africa","Benin"),
    ("BW","en","africa","Botswana"),("BF","fr","africa","Burkina Faso"),("BI","fr","africa","Burundi"),
    ("CV","pt","africa","Cabo Verde"),("CM","fr","africa","Cameroon"),("CF","fr","africa","Central African Republic"),
    ("TD","fr","africa","Chad"),("KM","fr","africa","Comoros"),("CG","fr","africa","Congo"),
    ("CD","fr","africa","Democratic Republic of the Congo"),("CI","fr","africa","Cote d'Ivoire"),
    ("DJ","fr","africa","Djibouti"),("EG","ar","africa","Egypt"),("GQ","es","africa","Equatorial Guinea"),
    ("ER","en","africa","Eritrea"),("SZ","en","africa","Eswatini"),("ET","en","africa","Ethiopia"),
    ("GA","fr","africa","Gabon"),("GM","en","africa","Gambia"),("GH","en","africa","Ghana"),
    ("GN","fr","africa","Guinea"),("GW","pt","africa","Guinea-Bissau"),("KE","en","africa","Kenya"),
    ("LS","en","africa","Lesotho"),("LR","en","africa","Liberia"),("LY","ar","africa","Libya"),
    ("MG","fr","africa","Madagascar"),("MW","en","africa","Malawi"),("ML","fr","africa","Mali"),
    ("MR","ar","africa","Mauritania"),("MU","en","africa","Mauritius"),("MA","ar","africa","Morocco"),
    ("MZ","pt","africa","Mozambique"),("NA","en","africa","Namibia"),("NE","fr","africa","Niger"),
    ("NG","en","africa","Nigeria"),("RW","en","africa","Rwanda"),("ST","pt","africa","Sao Tome and Principe"),
    ("SN","fr","africa","Senegal"),("SC","en","africa","Seychelles"),("SL","en","africa","Sierra Leone"),
    ("SO","en","africa","Somalia"),("ZA","en","africa","South Africa"),("SS","en","africa","South Sudan"),
    ("SD","ar","africa","Sudan"),("TZ","en","africa","Tanzania"),("TG","fr","africa","Togo"),
    ("TN","ar","africa","Tunisia"),("UG","en","africa","Uganda"),("ZM","en","africa","Zambia"),
    ("ZW","en","africa","Zimbabwe"),
    ("AF","en","asia","Afghanistan"),("AM","en","asia","Armenia"),("AZ","en","asia","Azerbaijan"),
    ("BH","ar","asia","Bahrain"),("BD","en","asia","Bangladesh"),("BT","en","asia","Bhutan"),
    ("BN","en","asia","Brunei"),("KH","en","asia","Cambodia"),("CN","zh-CN","asia","China"),
    ("CY","en","asia","Cyprus"),("GE","en","asia","Georgia"),("IN","en","asia","India"),
    ("ID","id","asia","Indonesia"),("IR","en","asia","Iran"),("IQ","ar","asia","Iraq"),
    ("IL","en","asia","Israel"),("JP","ja","asia","Japan"),("JO","ar","asia","Jordan"),
    ("KZ","en","asia","Kazakhstan"),("KW","ar","asia","Kuwait"),("KG","en","asia","Kyrgyzstan"),
    ("LA","en","asia","Laos"),("LB","ar","asia","Lebanon"),("MY","en","asia","Malaysia"),
    ("MV","en","asia","Maldives"),("MN","en","asia","Mongolia"),("MM","en","asia","Myanmar"),
    ("NP","en","asia","Nepal"),("KP","en","asia","North Korea"),("OM","ar","asia","Oman"),
    ("PK","en","asia","Pakistan"),("PH","en","asia","Philippines"),("QA","ar","asia","Qatar"),
    ("SA","ar","asia","Saudi Arabia"),("SG","en","asia","Singapore"),("KR","ko","asia","South Korea"),
    ("LK","en","asia","Sri Lanka"),("SY","ar","asia","Syria"),("TJ","en","asia","Tajikistan"),
    ("TH","en","asia","Thailand"),("TL","en","asia","Timor-Leste"),("TR","en","asia","Turkey"),
    ("TM","en","asia","Turkmenistan"),("AE","ar","asia","United Arab Emirates"),
    ("UZ","en","asia","Uzbekistan"),("VN","en","asia","Vietnam"),("YE","ar","asia","Yemen"),
    ("AL","en","europe","Albania"),("AD","es","europe","Andorra"),("AT","de","europe","Austria"),
    ("BY","en","europe","Belarus"),("BE","en","europe","Belgium"),("BA","en","europe","Bosnia and Herzegovina"),
    ("BG","en","europe","Bulgaria"),("HR","en","europe","Croatia"),("CZ","en","europe","Czechia"),
    ("DK","en","europe","Denmark"),("EE","en","europe","Estonia"),("FI","en","europe","Finland"),
    ("FR","fr","europe","France"),("DE","de","europe","Germany"),("GR","en","europe","Greece"),
    ("HU","en","europe","Hungary"),("IS","en","europe","Iceland"),("IE","en","europe","Ireland"),
    ("IT","it","europe","Italy"),("LV","en","europe","Latvia"),("LI","de","europe","Liechtenstein"),
    ("LT","en","europe","Lithuania"),("LU","en","europe","Luxembourg"),("MT","en","europe","Malta"),
    ("MD","en","europe","Moldova"),("MC","fr","europe","Monaco"),("ME","en","europe","Montenegro"),
    ("NL","en","europe","Netherlands"),("MK","en","europe","North Macedonia"),("NO","en","europe","Norway"),
    ("PL","en","europe","Poland"),("PT","pt","europe","Portugal"),("RO","en","europe","Romania"),
    ("RU","en","europe","Russia"),("SM","it","europe","San Marino"),("RS","en","europe","Serbia"),
    ("SK","en","europe","Slovakia"),("SI","en","europe","Slovenia"),("ES","es","europe","Spain"),
    ("SE","en","europe","Sweden"),("CH","de","europe","Switzerland"),("UA","en","europe","Ukraine"),
    ("GB","en","europe","United Kingdom"),
    ("AG","en","americas","Antigua and Barbuda"),("AR","es","americas","Argentina"),("BS","en","americas","Bahamas"),
    ("BB","en","americas","Barbados"),("BZ","en","americas","Belize"),("BO","es","americas","Bolivia"),
    ("BR","pt","americas","Brazil"),("CA","en","americas","Canada"),("CL","es","americas","Chile"),
    ("CO","es","americas","Colombia"),("CR","es","americas","Costa Rica"),("CU","es","americas","Cuba"),
    ("DM","en","americas","Dominica"),("DO","es","americas","Dominican Republic"),("EC","es","americas","Ecuador"),
    ("SV","es","americas","El Salvador"),("GD","en","americas","Grenada"),("GT","es","americas","Guatemala"),
    ("GY","en","americas","Guyana"),("HT","fr","americas","Haiti"),("HN","es","americas","Honduras"),
    ("JM","en","americas","Jamaica"),("MX","es","americas","Mexico"),("NI","es","americas","Nicaragua"),
    ("PA","es","americas","Panama"),("PY","es","americas","Paraguay"),("PE","es","americas","Peru"),
    ("KN","en","americas","Saint Kitts and Nevis"),("LC","en","americas","Saint Lucia"),
    ("VC","en","americas","Saint Vincent and the Grenadines"),("SR","en","americas","Suriname"),
    ("TT","en","americas","Trinidad and Tobago"),("US","en","americas","United States"),
    ("UY","es","americas","Uruguay"),("VE","es","americas","Venezuela"),
    ("AU","en","oceania","Australia"),("FJ","en","oceania","Fiji"),("KI","en","oceania","Kiribati"),
    ("MH","en","oceania","Marshall Islands"),("FM","en","oceania","Micronesia"),("NR","en","oceania","Nauru"),
    ("NZ","en","oceania","New Zealand"),("PW","en","oceania","Palau"),("PG","en","oceania","Papua New Guinea"),
    ("WS","en","oceania","Samoa"),("SB","en","oceania","Solomon Islands"),("TO","en","oceania","Tonga"),
    ("TV","en","oceania","Tuvalu"),("VU","en","oceania","Vanuatu"),
]

# Countries already in rss_feed_registry as of 2026-05-18 (queried from local DB).
COVERED = {"AE","AR","AT","AU","BD","BG","BH","BO","BR","CA","CH","CL","CN","CO","CR","CZ","DE","DK","EC",
           "EG","ES","ET","FI","FJ","FR","GB","GH","GR","HR","HU","ID","IE","IN","IQ","IR","IS","IT","JO",
           "JP","KE","KR","KW","KZ","LB","LK","MA","MM","MX","NG","NL","NO","NP","NZ","OM","PE","PG","PH",
           "PK","PL","PT","QA","RO","SA","SE","SG","SI","SK","SN","TH","TZ","US","UZ","VE","VN","WS","YE","ZA"}

OUT = Path(__file__).resolve().parents[1] / "infrastructure" / "database" / "migrations" / "versions" / "026_un193_country_feeds.sql"


def main():
    missing = [c for c in UN_193 if c[0] not in COVERED]
    lines = [
        "-- Migration 026: UN-193 country coverage to 95% via Google News RSS feeds",
        "--",
        "-- Adds Google News country-and-language-scoped climate feeds for the",
        f"-- {len(missing)} UN-193 members not yet in rss_feed_registry as of 2026-05-18.",
        "-- Google News aggregates from local publishers; resulting article rows",
        "-- carry the underlying publisher in feedparser's source attribution.",
        "-- Reliability tier is 'public' (aggregator); downstream source_credibility",
        "-- scoring is applied per individual publisher when the article is parsed.",
        "--",
        "-- Idempotent: ON CONFLICT DO NOTHING respects existing rows.",
        "",
    ]
    for cc, lang, region, name in missing:
        safe = name.replace("'", "''")
        feed_url = (
            f"https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22"
            f"&hl={lang}&gl={cc}&ceid={cc}:{lang}"
        )
        feed_name = f"Google News Climate - {safe}"
        lines.extend([
            "INSERT INTO rss_feed_registry "
            "(feed_name, feed_url, source_domain, country_code, region, reliability_tier, "
            "is_active, is_system_feed, source_type)",
            f"  VALUES ('{feed_name}', '{feed_url}', 'news.google.com', '{cc}', "
            f"'{region}', 'public', TRUE, TRUE, 'news_outlet')",
            "  ON CONFLICT DO NOTHING;",
        ])
    lines.extend([
        "",
        "-- Coverage tally after insert:",
        "-- SELECT COUNT(DISTINCT country_code) FROM rss_feed_registry WHERE is_active = TRUE;",
    ])
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(Path(__file__).resolve().parents[1])} ({len(missing)} feeds)")


if __name__ == "__main__":
    main()
