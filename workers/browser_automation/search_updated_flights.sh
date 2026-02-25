#!/bin/bash
# Search for flights with updated dates: Aug 20 - Sep 20, 2026

# Google Flights URL for SFO to ADD, family of 6
# Outbound: Aug 20, 2026
# Return: Sep 20, 2026
# 6 passengers (2 adults, 4 children)

FLIGHT_URL='https://www.google.com/travel/flights?tfs=CBwQAhoeEgoyMDI2LTA4LTIwagcIARIDU0ZPcgcIARIDQUREGh4SCjIwMjYtMDktMjBqBwgBEgNBRERyBwgBEgNTRk9AAUABQAJAAkACQAJIAXABggELCP___________wGYAQGyAQIYBg&tfu=EgYIABAAGAA'

echo "Opening Google Flights search..."
echo "Dates: August 20 - September 20, 2026"
echo "Route: SFO → ADD (round trip)"
echo "Passengers: 6 (2 adults, 4 children)"
echo ""

open "$FLIGHT_URL"

echo "✅ Flight search opened in browser"
