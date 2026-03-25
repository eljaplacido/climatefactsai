#!/usr/bin/env python
"""
Yksinkertainen järjestelmätesti
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("CLIMATE NEWS MAS - JÄRJESTELMÄTESTI")
print("=" * 60)

# 1. Tarkista ympäristömuuttujat
print("\n1️⃣  Tarkistetaan ympäristömuuttujat...")
anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
openai_key = os.getenv("OPENAI_API_KEY", "")

if anthropic_key and anthropic_key != "your-claude-api-key-here":
    print("   ✅ ANTHROPIC_API_KEY löydetty")
else:
    print("   ❌ ANTHROPIC_API_KEY puuttuu tai on oletus")

if openai_key and openai_key != "your-openai-api-key-here":
    print("   ✅ OPENAI_API_KEY löydetty")
else:
    print("   ❌ OPENAI_API_KEY puuttuu tai on oletus")

# 2. Testaa Redis-yhteys
print("\n2️⃣  Testataan Redis-yhteys...")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    print("   ✅ Redis toimii!")
    r.set("test_key", "Climate News MAS")
    value = r.get("test_key")
    print(f"   ✅ Redis read/write toimii: {value}")
except Exception as e:
    print(f"   ❌ Redis-virhe: {e}")

# 3. Testaa Kafka-yhteys
print("\n3️⃣  Testataan Kafka-yhteys...")
try:
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.admin import KafkaAdminClient
    
    admin = KafkaAdminClient(
        bootstrap_servers='localhost:9092',
        request_timeout_ms=5000
    )
    topics = admin.list_topics()
    print(f"   ✅ Kafka toimii! Löydetty {len(topics)} aihetta:")
    for topic in sorted(topics):
        print(f"      - {topic}")
    admin.close()
except Exception as e:
    print(f"   ❌ Kafka-virhe: {e}")

# 4. Testaa Anthropic API (jos avain on asetettu)
print("\n4️⃣  Testataan Anthropic API...")
if anthropic_key and anthropic_key != "your-claude-api-key-here":
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": "Vastaa yhteen sanaan: Mikä on pääkaupunki Suomessa?"
            }]
        )
        answer = response.content[0].text.strip()
        print(f"   ✅ Anthropic API toimii! Vastaus: {answer}")
    except Exception as e:
        print(f"   ❌ Anthropic API -virhe: {e}")
else:
    print("   ⏭️  Ohitetaan (API-avain puuttuu)")

# 5. Testaa OpenAI API (jos avain on asetettu)
print("\n5️⃣  Testataan OpenAI API...")
if openai_key and openai_key != "your-openai-api-key-here":
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": "Vastaa yhteen sanaan: Mikä on pääkaupunki Suomessa?"
            }]
        )
        answer = response.choices[0].message.content.strip()
        print(f"   ✅ OpenAI API toimii! Vastaus: {answer}")
    except Exception as e:
        print(f"   ❌ OpenAI API -virhe: {e}")
else:
    print("   ⏭️  Ohitetaan (API-avain puuttuu)")

print("\n" + "=" * 60)
print("TESTIT VALMIIT!")
print("=" * 60)

