#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLIMATE NEWS MAS - INTERAKTIIVINEN DEMO

Näyttää järjestelmän eri osat toiminnassa vaiheittain.
"""
import json
import time
from datetime import datetime

print("=" * 80)
print("🌍 CLIMATE NEWS MULTI-AGENT SYSTEM")
print("   Interaktiivinen Demo")
print("=" * 80)

# VAIHE 1: Tarkista infrastruktuuri
print("\n" + "─" * 80)
print("VAIHE 1: INFRASTRUKTUURIN TARKISTUS")
print("─" * 80)

# Redis
print("\n🔴 Redis (lyhytaikainen muisti):")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    print("   ✅ Yhteys toimii!")
    
    # Testaa kirjoitus/luku
    test_key = f"demo_test_{int(time.time())}"
    r.set(test_key, "Climate News toimii!")
    value = r.get(test_key)
    print(f"   ✅ Testi onnistui: '{value}'")
    r.delete(test_key)
    
except Exception as e:
    print(f"   ❌ Virhe: {e}")
    print("   💡 Käynnistä Redis: docker-compose up -d redis")
    exit(1)

# Kafka
print("\n📨 Kafka (viestiväylä):")
try:
    from kafka.admin import KafkaAdminClient
    
    admin = KafkaAdminClient(
        bootstrap_servers='localhost:9092',
        request_timeout_ms=5000
    )
    topics = admin.list_topics()
    print(f"   ✅ Yhteys toimii!")
    print(f"   ✅ Löydetty {len(topics)} aihetta:")
    
    our_topics = [t for t in topics if 'queue' in t or 'command' in t]
    for topic in sorted(our_topics):
        print(f"      • {topic}")
    
    admin.close()
    
except Exception as e:
    print(f"   ❌ Virhe: {e}")
    print("   💡 Käynnistä Kafka: docker-compose up -d zookeeper kafka")
    exit(1)

# VAIHE 2: Näytä järjestelmän tila
print("\n" + "─" * 80)
print("VAIHE 2: JÄRJESTELMÄN TILA")
print("─" * 80)

print("\n📊 Redis - Aktiiviset tehtävät:")
task_keys = r.keys("task:*")
if task_keys:
    print(f"   Löydetty {len(task_keys)} tehtävää:")
    for key in task_keys[:5]:
        task_data = r.get(key)
        if task_data:
            try:
                task = json.loads(task_data)
                print(f"   • {key}: {task.get('status', 'N/A')}")
            except:
                print(f"   • {key}: (ei JSON-dataa)")
else:
    print("   Ei aktiivisia tehtäviä (tyhjä järjestelmä)")

# VAIHE 3: Lähetä test-viesti
print("\n" + "─" * 80)
print("VAIHE 3: LÄHETÄ TEST-WORKFLOW")
print("─" * 80)

input("\n👉 Paina ENTER lähettääksesi test-käskyn järjestelmälle...")

from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Luo test-tehtävä
task_id = f"task-{datetime.now().strftime('%Y%m%d')}-demo"

test_message = {
    "command": "manual_trigger",
    "taskId": task_id,
    "timestamp": datetime.utcnow().isoformat() + "Z"
}

print(f"\n📤 Lähetetään viesti:")
print(f"   Aihe: orchestrator_commands")
print(f"   Task ID: {task_id}")
print(f"   Komento: {test_message['command']}")

producer.send('orchestrator_commands', value=test_message)
producer.flush()

print("\n✅ Viesti lähetetty!")

# Tallenna task Redisiin näyttääksemme että se toimii
task_state = {
    "taskId": task_id,
    "status": "DEMO_INITIATED",
    "createdAt": datetime.utcnow().isoformat(),
    "demo": True
}

r.set(f"task:{task_id}", json.dumps(task_state), ex=3600)
print(f"✅ Tehtävä tallennettu Redisiin")

# VAIHE 4: Näytä miten seurata
print("\n" + "─" * 80)
print("VAIHE 4: MITEN SEURATA JÄRJESTELMÄÄ")
print("─" * 80)

print("\n📺 Tässä ikkunassa:")
print("   Tarkista Redis:")
print(f"   >>> task_data = r.get('task:{task_id}')")
print(f"   >>> print(task_data)")

print("\n📺 Toisessa terminaalissa:")
print("   Seuraa Kafka-viestejä:")
print("   >>> docker exec climatenews-kafka kafka-console-consumer \\")
print("        --bootstrap-server localhost:9092 \\")
print("        --topic discovery_queue \\")
print("        --from-beginning")

print("\n📺 PostgreSQL:")
print("   >>> docker exec -it climatenews-postgres psql -U postgres -d climatenews")
print("   >>> SELECT * FROM articles LIMIT 5;")

# Kuuntele viestejä 10 sekuntia
print("\n" + "─" * 80)
print("VAIHE 5: KUUNNELLAAN VIESTEJÄ (10 sek)")
print("─" * 80)

from kafka import KafkaConsumer

print("\n🎧 Kuunnellaan Kafka-aiheita...")

try:
    consumer = KafkaConsumer(
        'discovery_queue',
        'fact_checking_queue',
        'creation_queue',
        bootstrap_servers='localhost:9092',
        auto_offset_reset='latest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=10000,
        group_id=f'demo_consumer_{int(time.time())}'
    )
    
    messages_received = []
    
    for message in consumer:
        messages_received.append(message)
        print(f"\n   📨 Viesti aiheesta: {message.topic}")
        print(f"      Task ID: {message.value.get('taskId', 'N/A')}")
        
        if len(messages_received) >= 5:
            break
    
    consumer.close()
    
    if messages_received:
        print(f"\n✅ Vastaanotettu {len(messages_received)} viestiä!")
        print("   Järjestelmä toimii ja agentit kommunikoivat!")
    else:
        print("\n⏱️  Ei viestejä vielä (normaalia jos agentit eivät ole käynnissä)")
        
except Exception as e:
    print(f"\n⚠️  Timeout tai virhe: {e}")
    print("   (Tämä on normaalia jos agentit eivät ole vielä käynnissä)")

# Tarkista Redis-tila
print("\n" + "─" * 80)
print("VAIHE 6: TARKISTA LOPPUTILANNE")
print("─" * 80)

print(f"\n🔍 Redis-tila (Task ID: {task_id}):")
final_state = r.get(f"task:{task_id}")
if final_state:
    task_obj = json.loads(final_state)
    print(json.dumps(task_obj, indent=2))
else:
    print("   Tehtävää ei löydy (normaalia demossa)")

# Yhteenveto
print("\n" + "=" * 80)
print("✅ DEMO VALMIS!")
print("=" * 80)

print("\n📚 Seuraavat askeleet:")
print("   1. Käynnistä agentit: .\start-agents.ps1")
print("   2. Seuraa lokeja avautuneissa ikkunoissa")
print("   3. Lähetä uusia tehtäviä tällä skriptillä")
print("   4. Tarkista tulokset: docker exec -it climatenews-postgres psql -U postgres -d climatenews")

print("\n💡 Järjestelmä on valmis käyttöön!\n")

producer.close()
r.close()

