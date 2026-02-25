#!/usr/bin/env python3
"""
Setup Ethiopia Trip Project with tab groups and initial prompts
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
import json

def main():
    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"

    # Connect to Google Sheets
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(sheet_id)

    # Initial prompt
    initial_prompt = """Plan a trip to Ethiopia. Its for a trip for the whole family (Yordanos Girmay, Helen Atsibha, Sara Girmay, Ezana Girmay, Eden Girmay, Eden Girmay) ages 47, 46, 13, 12, 11, 6 respectively and flying to Ethiopia in mid to late June with best price. Find hotels to stay for the 1 month duration of the trip and some activities also plan a trip to tigray to visit Axum, Adigrat, and Mekele for one week"""

    # Family details
    family_members = [
        {"name": "Yordanos Girmay", "age": 47},
        {"name": "Helen Atsibha", "age": 46},
        {"name": "Sara Girmay", "age": 13},
        {"name": "Ezana Girmay", "age": 12},
        {"name": "Eden Girmay", "age": 11},
        {"name": "Eden Girmay", "age": 6}
    ]

    print("=" * 80)
    print("SETTING UP ETHIOPIA TRIP PROJECT")
    print("=" * 80)
    print()

    # 1. Create project in Projects worksheet
    ws_projects = spreadsheet.worksheet("Projects")

    project_row = [
        "P002",  # Project ID
        "Ethiopia Family Trip - June 2026",  # Project Name
        initial_prompt,  # Description
        "in-progress",  # Status
        0,  # Progress %
        7,  # Tab Groups Count (will be created)
        0,  # Total Tabs (will be filled as we add)
        0,  # Completed Tabs
        "",  # Perplexity Conversations (will add)
        datetime.now().strftime('%Y-%m-%d'),  # Created Date
        datetime.now().strftime('%Y-%m-%d %H:%M'),  # Last Updated
        f"Family: {', '.join([m['name'] for m in family_members])} | June 2026 | Duration: 1 month"  # Notes
    ]

    # Find next available row in Projects
    projects_data = ws_projects.get_all_values()
    next_row = len(projects_data) + 1

    ws_projects.update(f'A{next_row}', [project_row], value_input_option='USER_ENTERED')
    print(f"✓ Created project 'Ethiopia Family Trip - June 2026' in Projects worksheet")
    print()

    # 2. Create tab groups with prompts
    ws_tab_groups = spreadsheet.worksheet("Tab Groups")

    tab_groups = [
        {
            "id": "ETH-G001",
            "name": "Flights - Family of 6 to Ethiopia",
            "color": "blue",
            "prompt": f"""Find the best flight prices for a family of 6 traveling to Ethiopia in mid-to-late June 2026:
- Departure: Bay Area (SFO/OAK) or nearest major airport
- Destination: Addis Ababa, Ethiopia (ADD)
- Travel dates: Mid to late June 2026 (flexible within this range)
- Return: Late July 2026 (1 month trip)
- Passengers: 2 adults (ages 47, 46), 4 children (ages 13, 12, 11, 6)
- Priority: Best price while maintaining reasonable comfort and safety
- Preferences: Direct flights if possible, or minimal layovers
- Budget considerations: Compare airlines, check for family discounts
Output: Top 3-5 flight options with prices, airlines, layovers, and booking links"""
        },
        {
            "id": "ETH-G002",
            "name": "Hotels - 1 Month Accommodation",
            "prompt": """Find suitable hotels/accommodations in Ethiopia for a 1-month stay (June-July 2026):
- Location: Addis Ababa (main base)
- Duration: Approximately 1 month
- Guests: Family of 6 (2 adults, 4 children ages 6-13)
- Requirements:
  * Family-friendly (kid-safe, activities for children)
  * Kitchen or kitchenette preferred (long stay)
  * 2-3 bedrooms or family suites
  * Safe neighborhood
  * WiFi, air conditioning
- Budget: Mid-range to budget-friendly
- Options: Hotels, serviced apartments, Airbnb, or vacation rentals
Output: Top 5 accommodation options with prices, amenities, location, and booking info"""
        },
        {
            "id": "ETH-G003",
            "name": "Tigray Trip - Axum, Adigrat, Mekele",
            "prompt": """Plan a 1-week trip to Tigray region visiting Axum, Adigrat, and Mekele:
- Duration: 1 week during the 1-month Ethiopia stay
- Travelers: Family of 6 (2 adults, 4 children ages 6-13)
- Cities to visit:
  * Axum - Ancient obelisks, historical sites
  * Adigrat - Cultural experiences
  * Mekele - Capital of Tigray
- Requirements:
  * Transportation options (rental car, driver, tours)
  * Family-friendly hotels in each city
  * Safety considerations and current travel advisories
  * Key attractions and activities for families
  * Estimated costs
Output: Detailed 7-day itinerary with hotels, transportation, activities, and costs"""
        },
        {
            "id": "ETH-G004",
            "name": "Activities - Family-Friendly Ethiopia",
            "prompt": """Find family-friendly activities and attractions in Ethiopia for June-July 2026:
- Travelers: 2 adults + 4 children (ages 13, 12, 11, 6)
- Location: Primarily Addis Ababa and surrounding areas
- Duration: Activities throughout 1-month stay
- Categories:
  * Cultural sites and museums (child-appropriate)
  * Outdoor activities and parks
  * Day trips from Addis Ababa
  * Educational experiences
  * Food experiences suitable for children
  * Shopping and markets
- Considerations: Age-appropriate for youngest (6 years old), educational value, safety
Output: List of 15-20 activities with descriptions, costs, duration, age suitability"""
        },
        {
            "id": "ETH-G005",
            "name": "Documents & Requirements",
            "prompt": """Research travel document requirements for US citizens traveling to Ethiopia:
- Travelers: 2 adults, 4 children (US citizens/residents)
- Travel dates: June-July 2026
- Requirements to research:
  * Passport requirements (validity period)
  * Ethiopia visa requirements and application process
  * Vaccination requirements (Yellow fever, COVID-19, etc.)
  * Health insurance recommendations
  * Minor travel requirements (parental consent forms if needed)
  * Entry/exit requirements
  * Travel advisories and safety information
Output: Checklist of all required documents and steps with deadlines and application links"""
        },
        {
            "id": "ETH-G006",
            "name": "Budget & Cost Tracking",
            "prompt": """Create a comprehensive budget for Ethiopia family trip:
- Trip details: Family of 6, 1 month, June-July 2026
- Categories to budget:
  * Flights (6 passengers)
  * Accommodation (1 month)
  * Tigray week-long trip (hotels, transport, activities)
  * Daily food and dining
  * Activities and attractions
  * Local transportation (taxis, tours)
  * Travel insurance
  * Miscellaneous (souvenirs, emergencies)
- Currency: Ethiopian Birr (ETB) and USD
- Output: Detailed budget spreadsheet with estimated costs and tracking columns"""
        },
        {
            "id": "ETH-G007",
            "name": "Packing & Preparation",
            "prompt": """Create packing list and preparation checklist for Ethiopia family trip:
- Travelers: Family of 6 (ages 6-47)
- Duration: 1 month in June-July
- Climate: Research June-July weather in Ethiopia
- Categories:
  * Clothing (adults and children)
  * Medications and first aid
  * Electronics and adapters
  * Entertainment for children (long flights)
  * Important documents (copies)
  * Toiletries and essentials
  * Special items for young children
- Cultural considerations: Modest dress codes, religious sites
Output: Comprehensive packing checklist organized by person and category"""
        }
    ]

    print("Creating tab groups...")
    tab_groups_data = ws_tab_groups.get_all_values()
    next_row = len(tab_groups_data) + 1

    for i, group in enumerate(tab_groups):
        row_data = [
            group["id"],
            "P002",  # Project ID
            group["name"],
            group.get("color", "blue"),
            "pending",  # Status
            0,  # Progress %
            0,  # Tab Count (will be filled as Perplexity conversations are added)
            0,  # Completed Tabs
            "",  # Main Perplexity URL (will be filled)
            "",  # Dependencies
            "",  # Blocked By
            group["prompt"],  # Store prompt in Notes
            datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d %H:%M'),
            "Mac Mini (Gezabase)"  # Source Computer
        ]

        ws_tab_groups.update(f'A{next_row + i}', [row_data], value_input_option='USER_ENTERED')
        print(f"  ✓ {group['name']}")

    print()
    print("=" * 80)
    print("✅ ETHIOPIA PROJECT SETUP COMPLETE!")
    print("=" * 80)
    print()
    print("Created:")
    print(f"  • 1 Project: Ethiopia Family Trip - June 2026")
    print(f"  • 7 Tab Groups with research prompts")
    print()
    print("Tab Groups:")
    for group in tab_groups:
        print(f"  • {group['name']}")
    print()
    print("Next Steps:")
    print("  1. Send each prompt to Perplexity/Comet for research")
    print("  2. Collect Perplexity conversation URLs")
    print("  3. Update tab groups with conversation URLs")
    print("  4. Aggregate findings into Google Doc")
    print()
    print("View in Google Sheet:")
    print(f"  https://docs.google.com/spreadsheets/d/{sheet_id}/edit?gid=183210330")
    print()

    # Save prompts to a file for easy access
    prompts_file = Path("ethiopia_prompts.json")
    with open(prompts_file, 'w') as f:
        json.dump({
            "project": "Ethiopia Family Trip - June 2026",
            "initial_prompt": initial_prompt,
            "family_members": family_members,
            "tab_groups": tab_groups
        }, f, indent=2)

    print(f"✓ Saved prompts to {prompts_file}")
    print()

if __name__ == "__main__":
    main()
