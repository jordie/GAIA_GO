#!/usr/bin/env python3
"""
Send WhatsApp message directly using authenticated session
"""
import requests
import json

# OpenClaw gateway API
gateway_url = "http://127.0.0.1:18789"
phone = "+15103886759"

# Try gateway RPC endpoint
payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "channels.send",
    "params": {
        "channel": "whatsapp",
        "account": "default",
        "to": phone,
        "text": "🦞 Test from OpenClaw!\n\nYour automation systems are connected:\n✅ WhatsApp integrated\n✅ Property analysis ready\n✅ Ethiopia research running\n\nEverything is working! 🚀"
    }
}

print(f"Attempting to send WhatsApp message to {phone}...")
print()

try:
    response = requests.post(
        f"{gateway_url}/rpc",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        if "error" not in result:
            print("\n✅ Message sent successfully!")
        else:
            print(f"\n❌ Error: {result['error']}")
    else:
        print(f"\n❌ Failed with status {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nNote: Direct RPC may not be available.")
    print("Trying alternative method...")

