# Workflow & UI Runbook

## Mikä käynnistää mitä?

| Käyttötilanne | Mitä käyttäjä tekee | Mitä taustalla tapahtuu |
| --- | --- | --- |
| **1. Päivittäinen automaattiajo** | Orchestrator-agentti ajetaan `docker-compose up orchestrator` tai ajastetulla cron-tehtävällä. | Orchestrator lähettää `workflow_started` → Content Discovery → Fact-Checking → Content Creation. Redis ja PostgreSQL päivittyvät vaiheittain, UI saa uudet uutiset ilman selaimen uudelleenkäynnistystä. |
| **2. Manuaalinen kickstart** | a) Admin-paneelin "Run workflow" ‑painike **tai**<br>b) Komentoriviltä: `.\\venv\\Scripts\\python.exe run_full_pipeline.py --country FI` | Kummassakin tapauksessa syntyy `task-{päivämäärä}`. CLI reitti ajaa kaikki agenttipolut suoraan ilman Kafkaa; Admin reitti luottaa Kafka-jonoon. UI kysyy `/api/admin/workflows` ja näyttää statuksen reaaliajassa. |
| **3. Uusi maa uutisvirtaan** | CLI-komento `python run_full_pipeline.py --country-code SE --max-articles 8`. | Komento noutaa Perplexityltä Ruotsin artikkelit, fact checkaa, rikastaa NASA/NOAA/ClimateCheck-datalla ja tallettaa ne `articles.country_code='SE'`. UI:n maatina-haku näyttää Ruotsin, eikä workflowa tarvitse ajaa uudelleen yhtä maata varten. |
| **4. Käyttäjä selaa uutisia** | Selaimessa menetään `http://localhost:3000`. | Frontend kutsuu `/api/articles?country=FI` ja näyttää vain valitun maan. Kun fact check on vielä kesken, rivillä näkyy **"Faktantarkistus odottaa…"**, ja status vaihtuu automaattisesti kun fact-check agentti puskee tuloksen. |

## Askel-askeleelta: ensimmäinen ajo

1. **Käynnistä infra**
   ```powershell
   docker-compose up -d postgres redis kafka zookeeper
   ```
2. **Käynnistä API & frontend**
   ```powershell
   uvicorn api.main:app --reload
   cd frontend && npm run dev
   ```
3. **Lataa ensimmäinen maa**
   ```powershell
   python run_full_pipeline.py --country "Finland" --country-code FI --max-articles 6
   ```
4. **Tarkista UI**
   - Etusivu näyttää Finnish feedin heti kun pipeline on valmis.
   - Admin-paneelin workflow-historia kertoo viimeisimmän ajon vaiheet.
5. **Lisää seuraava maa (esim. Sweden)**
   ```powershell
   python run_full_pipeline.py --country "Sweden" --country-code SE --max-articles 6
   ```
   Nyt Country Selectorissa on sekä FI että SE.

## Miksi faktatarkistus voi jäädä odottamaan?

| Tilanne | Mistä tunnistaa | Korjaus |
| --- | --- | --- |
| Perplexity API avain puuttuu | `run_full_pipeline` tulostaa `Perplexity API error: 401` | Aseta `PERPLEXITY_API_KEY` `.env`-tiedostoon. |
| NOAA/NASA rikastus puuttuu | Fact-check justification on vain pari lausetta | Aseta `NOAA_API_TOKEN` ja `NASA_API_KEY` tai käytä `--skip-external-data` flagia jos haluat ilman rikastusta. |
| Kafka-reitti pysähtynyt | Admin workflow näyttää statuksen `Fact-Checking` eikä etene | Käynnistä fact_checking-agentti: `python agents/fact_checking/main.py`. |

## Luotettavuuden uusi kerrostus (preview)

Taustalla lasketaan yhdistetty `reliability_score` (0-100), jota UI alkaa käyttää kun seuraavat askeleet valmistuvat:

- Perplexity analyysi (25%)
- ClimateCheck riskiscore (25%)
- NOAA lämpötila- ja sademittarit (25%)
- NASA satelliittidata (25%)

Lisäksi tallennamme jokaiselle artikkelille `tags[]`, joita käytetään tulevassa filtrissä (esim. `"sääilmiöt"`, `"kiertotalous"`).

## Rakenteilla olevat UX-parannukset

1. **Pidemmät yhteenvedot** – Content Creator tuottaa kahden kappaleen executive summaryn ja erillisen vaikutusanalyysin. (Tulossa buildiin `content_creator_extended`.)
2. **Käyttäjäpalaute** – `/api/articles/{id}/feedback` tallentaa painikkeista annetut palautteet tauluun `article_feedback`. Frontend saa palautebadgetin ja "Oliko arvio hyödyllinen?" -kysymyksen.
3. **Tagisuodatin** – Country Selectorin viereen tulee uusi multi-select tageille.
4. **Sää-widget** – NOAA & NASA datasta muodostetaan aluekohtainen sääkortti artikkelisivulle.

Näistä on backlog-issueissa CN-102…CN-109; näiden implementointi on osittain käynnissä tässä repossa.

## Pika-FAQ

- **Pitääkö workflow ajaa jokaiselle maalle erikseen?**  Ei, `--batch FI,SE,NO` ajaa ne yhdellä komennolla. UI päivittää maat automaattisesti.
- **Voinko käyttää vain UI:ta ilman CLI:tä?**  Kyllä, kun orchestrator + agentit pyörivät. Admin "Run workflow" laukaisee saman prosessin.
- **Miksi NASA-/NOAA-avaimia tarvitaan, jos Perplexity jo antaa lähteet?**  Perplexity on ensisijainen lähteiden kerääjä; NASA/NOAA mittaavat raakadataa, jolla varmistetaan että väitteet vastaavat todellista mittausdataa → parempi luotettavuuspiste.
- **Miten usein workflow kannattaa ajastaa?**  Suositus: vähintään 2× päivässä (aamu/ilta). Cron-esimerkki löytyy `scripts/schedule-workflows.md`.

---

Lisää kehityksestä: seuraa `docs/MVP_EUROPE_ROADMAP.md` ja GitHub-issueita tunnisteella `ux`.
