<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# \U0001F680 Pikaopas - Climate News Multi-Agent System

Tämä opas auttaa sinua käynnistämään järjestelmän 5 minuutissa.

## Vaihe 1: Kloonaa ja konfiguroi (2 min)

```bash
# 1. Kloonaa repositorio
git clone <repo-url>
cd climatenews

# 2. Kopioi ympäristömuuttujat
# Huom: .env.example ei ole versionhallinnassa, luo se itse tai pyydä tiimiltä
# cp .env.example .env

# 3. Muokkaa .env ja lisää vaaditut API-avaimet:
#    - ANTHROPIC_API_KEY (Claude)
#    - OPENAI_API_KEY (GPT-4)
#    - CLIMATECHECK_API_KEY
#    - POSTGRES_PASSWORD
```

## Vaihe 2: Käynnistä infrastruktuuri (2 min)

```bash
# Käynnistä Kafka, Redis, PostgreSQL
chmod +x scripts/start-dev.sh
./scripts/start-dev.sh
```

Tämä skripti:
- \u2705 Käynnistää tarvittavat palvelut
- \u2705 Odottaa että ne ovat valmiita
- \u2705 Luo Kafka-aiheet automaattisesti
- \u2705 Alustaa PostgreSQL-tietokannan

## Vaihe 3: Käynnistä agentit (1 min)

```bash
# Käynnistä kaikki agentit
docker-compose up -d

# Tarkista että agentit ovat käynnissä
docker-compose ps

# Seuraa lokeja
docker-compose logs -f orchestrator
```

## ✨ Testaa järjestelmä

### Lähetä manuaalinen workflow-käsky:

```bash
chmod +x scripts/test-workflow.sh
./scripts/test-workflow.sh
```

Tämä käynnistää koko päivittäisen työnkulun manuaalisesti.

### Seuraa workflow:n etenemistä:

```bash
# Orchestrator-lokit
docker-compose logs -f orchestrator

# Redis-tila
docker exec -it climatenews-redis redis-cli
> KEYS task:*
> GET task:task-20251010-999
```

### Tarkista tietokanta:

```bash
# Avaa PostgreSQL
docker exec -it climatenews-postgres psql -U postgres -d climatenews

# Kyselyt
SELECT * FROM articles LIMIT 5;
SELECT * FROM workflow_logs ORDER BY timestamp DESC LIMIT 10;
```

## \U0001F4CA Monitorointityökalut

Kun kaikki on käynnissä, avaa:

- **Grafana:** http://localhost:3000 (admin/admin)
- **Jaeger Tracing:** http://localhost:16686
- **Prometheus:** http://localhost:9090

## \U0001F527 Hyödyllisiä komentoja

```bash
# Pysäytä kaikki
docker-compose down

# Rakenna uudelleen
docker-compose build

# Puhdista kaikki data (VAROITUS!)
docker-compose down -v

# Näytä resurssien käyttö
docker stats

# Tietyn agentin lokit
docker-compose logs -f content-discovery

# Kaikki Kafka-aiheet
docker exec climatenews-kafka kafka-topics --list --bootstrap-server localhost:9092

# Kuluta viestejä aiheesta
docker exec climatenews-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic discovery_queue \
  --from-beginning
```

## \U0001F41B Ongelmanratkaisu

### Kafka ei vastaa

```bash
# Käynnistä Kafka uudelleen
docker-compose restart kafka

# Odota 10 sekuntia
sleep 10

# Testaa yhteys
docker exec climatenews-kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

### PostgreSQL-yhteysvirhe

```bash
# Tarkista onko palvelu käynnissä
docker-compose ps postgres

# Tarkista lokit
docker-compose logs postgres

# Käynnistä uudelleen
docker-compose restart postgres
```

### Agentin virhe

```bash
# Katso agentti-spesifiset lokit
docker-compose logs --tail=100 [agent-name]

# Käynnistä agentti uudelleen
docker-compose restart [agent-name]

# Rakenna ja käynnistä uudelleen
docker-compose up -d --build [agent-name]
```

## \U0001F4DA Seuraavat askeleet

1. **Lue dokumentaatio:**
   - [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Järjestelmän arkkitehtuuri
   - [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Kehittäjän opas
   - [README.md](README.md) - Yleiskatsaus

2. **Tutustu koodiin:**
   - `agents/shared/` - Jaetut komponentit
   - `agents/orchestrator/` - Keskuskoordinaattori
   - `schemas/` - Viestintäprotokollat

3. **Kehitä ensimmäinen ominaisuus:**
   - Katso [DEVELOPMENT.md](docs/DEVELOPMENT.md) kehitystyönkulusta
   - Käytä feature-brancheja
   - Kirjoita testit
   - Tee pull request

## \U0001F4A1 Vinkit

- **Kehitystilassa** agentit voidaan ajaa myös ilman Dockeria suoraan Python:lla:
  ```bash
  cd agents
  python -m orchestrator.main
  ```

- **JSON-skeemoja** kannattaa validoida ennen lähetystä:
  ```bash
  jsonschema -i my_message.json schemas/discovery_to_factcheck.json
  ```

- **Kafka UI:ta** voi lisätä docker-compose.yml:ään helpottamaan debuggausta:
  ```yaml
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9093
  ```

## \U0001F198 Tuki

- **Slack:** #climatenews-dev
- **Email:** dev-team@climatenews.com
- **Issues:** GitHub Issues

---

**Onnea projektin parissa! \U0001F30D**
