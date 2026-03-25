#!/bin/bash

# =============================================================================
# Climate News MAS - Kehitysympäristön käynnistysskripti
# =============================================================================

set -e

echo "========================================="
echo "Climate News Multi-Agent System"
echo "Development Environment Startup"
echo "========================================="
echo ""

# Tarkista että .env-tiedosto on olemassa
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please create .env file from .env.example:"
    echo "  cp .env.example .env"
    echo ""
    echo "Then fill in your API keys and configuration."
    exit 1
fi

echo "✓ .env file found"

# Käynnistä infrastruktuuripalvelut
echo ""
echo "Starting infrastructure services (Kafka, Redis, PostgreSQL)..."
docker-compose up -d zookeeper kafka schema-registry redis postgres

# Odota että palvelut ovat valmiita
echo ""
echo "Waiting for services to be ready..."
sleep 10

# Tarkista palveluiden tila
echo ""
echo "Checking service health..."

# Tarkista Kafka
echo -n "  Kafka: "
if docker exec climatenews-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "❌ Not responding"
fi

# Tarkista Redis
echo -n "  Redis: "
if docker exec climatenews-redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "❌ Not responding"
fi

# Tarkista PostgreSQL
echo -n "  PostgreSQL: "
if docker exec climatenews-postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "❌ Not responding"
fi

# Luo Kafka-aiheet (jos eivät ole olemassa)
echo ""
echo "Creating Kafka topics..."

KAFKA_TOPICS=(
    "discovery_queue"
    "fact_checking_queue"
    "creation_queue"
    "video_queue"
    "publication_queue"
    "orchestrator_commands"
)

for topic in "${KAFKA_TOPICS[@]}"; do
    echo -n "  $topic: "
    if docker exec climatenews-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic "$topic" --partitions 3 --replication-factor 1 --if-not-exists > /dev/null 2>&1; then
        echo "✓ Created/Exists"
    else
        echo "❌ Failed"
    fi
done

echo ""
echo "========================================="
echo "Infrastructure is ready!"
echo "========================================="
echo ""
echo "Services running:"
echo "  • Kafka: localhost:9092"
echo "  • Redis: localhost:6379"
echo "  • PostgreSQL: localhost:5432"
echo "  • Schema Registry: localhost:8081"
echo ""
echo "To start agents, run:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f [service-name]"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
echo ""

