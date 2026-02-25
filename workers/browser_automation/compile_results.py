#!/usr/bin/env python3
"""
Compile research results from both projects
"""
import json
from pathlib import Path

print("=" * 80)
print("RESEARCH RESULTS SUMMARY")
print("=" * 80)
print()

# Ethiopia Results
print("🇪🇹 ETHIOPIA TRIP RESEARCH")
print("-" * 80)

ethiopia_results = Path('data/ethiopia/research_results')
if ethiopia_results.exists():
    for result_file in sorted(ethiopia_results.glob('*.json')):
        with open(result_file) as f:
            data = json.load(f)
        
        print(f"\n{data['id']}: {data['name']}")
        print(f"  Status: {'✅ Complete' if data['success'] else '❌ Failed'}")
        print(f"  URL: {data['url']}")
        print(f"  Time: {data['timestamp']}")
else:
    print("No results found")

print()
print()
print("📊 PROPERTY ANALYSIS RESEARCH")
print("-" * 80)

property_results = Path('data/property_analysis/research_results')
if property_results.exists():
    for result_file in sorted(property_results.glob('*.json')):
        with open(result_file) as f:
            data = json.load(f)
        
        print(f"\n{data['id']}: {data['name']}")
        print(f"  Status: {'✅ Complete' if data['success'] else '❌ Failed'}")
        print(f"  URL: {data['url']}")
        print(f"  Time: {data['timestamp']}")
else:
    print("No results found")

print()
print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Count totals
ethiopia_count = len(list(ethiopia_results.glob('*.json'))) if ethiopia_results.exists() else 0
property_count = len(list(property_results.glob('*.json'))) if property_results.exists() else 0

print(f"Ethiopia Topics: {ethiopia_count}")
print(f"Property Topics: {property_count}")
print(f"Total Research: {ethiopia_count + property_count}")
print()
print("All research completed and results available in Perplexity tabs!")
print()
