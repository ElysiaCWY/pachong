import sys
import os

# Ensure the current directory is in python path
sys.path.append(os.getcwd())

from news_crawlers.thsi_unlisted import crawl_thsi_unlisted

print("Starting debug run for THSI...")
items = crawl_thsi_unlisted()
print(f"Debug run finished. items found: {len(items)}")
for item in items:
    print(item)
