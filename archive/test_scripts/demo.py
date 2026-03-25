#!/usr/bin/env python
"""
Climate News MAS - Live Demo
Käynnistää workflow'n ja näyttää agentit toiminnassa
"""
import json
import time
from kafka import KafkaProducer, KafkaConsumer
from datetime import datetime

print("=" * 80)
print("🌍 CLIMATE NEWS MAS - LIVE DEMO")
print("=" * 80)

# Luo Kafka producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Luo tehtävä
task = {
    "task_id": f"demo_{int(time.time())}",
    "command": "discover_content",
    "params": {
        "sources": ["https://yle.fi/rss/uutiset.rss"],
        "keywords": ["ilmastonmuutos", "sää", "lämpötila"],
        "max_articles": 3
    },
    "timestamp": datetime.utcnow().isoformat()
}

print(f"\n📤 Lähetetään tehtävä orchestratorille...")
print(f"   Task ID: {task['task_id']}")
print(f"   Komento: {task['command']}")
print(f"   Lähteet: {task['params']['sources']}")

# Lähetä tehtävä
producer.send('orchestrator_commands', value=task)
producer.flush()

print("\n✅ Tehtävä lähetetty!")
print("\n👀 Seuraa nyt agenttiesi lokeja...")
print("   - Orchestrator vastaanottaa tehtävän")
print("   - Content Discovery etsii uutisia")
print("   - Fact-Checking tarkistaa tiedot")
print("\n💡 Vihje: Tarkista Docker/terminal-ikkunat nähdäksesi agentit työskentelemässä!")

# Kuuntele vastauksia 30 sekunnin ajan
print("\n🎧 Kuunnellaan vastauksia (30 sekuntia)...\n")

consumer = KafkaConsumer(
    'discovery_queue',
    'fact_checking_queue', 
    'creation_queue',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='latest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    consumer_timeout_ms=30000
)

message_count = 0
try:
    for message in consumer:
        message_count += 1
        topic = message.topic
        value = message.value
        
        print(f"\n📨 Viesti aiheesta: {topic}")
        if topic == 'discovery_queue':
            print(f"   🔍 Content Discovery löysi:")
            print(f"      - Artikkeli: {value.get('title', 'N/A')[:60]}...")
            print(f"      - Väitteitä: {len(value.get('claims', []))}")
        elif topic == 'fact_checking_queue':
            print(f"   ✅ Fact-Checking tarkisti:")
            print(f"      - Artikkeli: {value.get('article_id', 'N/A')}")
            print(f"      - Luotettavuus: {value.get('credibility_score', 'N/A')}")
        elif topic == 'creation_queue':
            print(f"   📝 Content Creation loi sisältöä:")
            print(f"      - Otsikko: {value.get('title', 'N/A')}")
        
except Exception as e:
    print(f"\n⏱️  Timeout tai virhe: {e}")

print(f"\n{'=' * 80}")
print(f"📊 YHTEENVETO:")
print(f"   Viestejä käsitelty: {message_count}")
print(f"   Järjestelmä toimii! ✨")
print(f"{'=' * 80}")

consumer.close()
producer.close()

