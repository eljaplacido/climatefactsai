import feedparser

print("\nTestataan YLE RSS...")
feed = feedparser.parse("https://yle.fi/rss/uutiset.rss")

print(f"Feed title: {feed.feed.get('title', 'N/A')}")
print(f"Entries: {len(feed.entries)}")
print(f"Status: {feed.get('status', 'N/A')}")

if feed.entries:
    print("\nEnsimmäiset 5 uutista:")
    for i, entry in enumerate(feed.entries[:5], 1):
        print(f"{i}. {entry.get('title', 'No title')}")
else:
    print("\n❌ Ei uutisia löytynyt")
    print("Syy:", feed.get('bozo_exception', 'Unknown'))

