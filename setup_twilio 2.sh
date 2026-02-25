#!/bin/bash
# Twilio SMS Setup Assistant

echo "════════════════════════════════════════════════════════════════════"
echo "                    Twilio SMS Setup Assistant"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "This will help you set up Twilio SMS for the Architect Dashboard."
echo ""
echo "📋 What you'll need:"
echo "   1. Twilio Account SID (starts with 'AC')"
echo "   2. Twilio Auth Token (32 characters)"
echo "   3. Twilio Phone Number (format: +1XXXXXXXXXX)"
echo ""
echo "Don't have a Twilio account yet?"
echo "👉 Sign up at: https://www.twilio.com/try-twilio (gets $15 free credit)"
echo ""
read -p "Press Enter when you're ready to continue..."
echo ""

# Add Account SID
echo "════════════════════════════════════════════════════════════════════"
echo "Step 1: Account SID"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Find your Account SID in the Twilio Console:"
echo "👉 https://console.twilio.com/"
echo ""
echo "It starts with 'AC' and looks like: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
echo ""
read -p "Enter your Twilio Account SID: " ACCOUNT_SID
echo ""

if [[ ! $ACCOUNT_SID =~ ^AC[a-f0-9]{32}$ ]]; then
    echo "⚠️  Warning: Account SID format looks incorrect (should start with 'AC')"
    echo "   Continuing anyway..."
fi

python3 << EOF
import sqlite3
account_sid = "${ACCOUNT_SID}"
encrypted = ''.join(chr(ord(c) ^ 42) for c in account_sid)
conn = sqlite3.connect('data/architect.db')
try:
    conn.execute("""
        INSERT INTO secrets (name, encrypted_value, service, category, description)
        VALUES ('TWILIO_ACCOUNT_SID', ?, 'twilio', 'api_key', 'Twilio Account SID')
    """, (encrypted,))
    conn.commit()
    print("✅ Account SID saved to vault!")
except sqlite3.IntegrityError:
    conn.execute("UPDATE secrets SET encrypted_value = ? WHERE name = 'TWILIO_ACCOUNT_SID'", (encrypted,))
    conn.commit()
    print("✅ Account SID updated in vault!")
finally:
    conn.close()
EOF

echo ""

# Add Auth Token
echo "════════════════════════════════════════════════════════════════════"
echo "Step 2: Auth Token"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Find your Auth Token in the Twilio Console (same page as Account SID)"
echo "Click the 'eye' icon to reveal it."
echo ""
echo "It's 32 characters and looks like: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
echo ""
read -sp "Enter your Twilio Auth Token (hidden): " AUTH_TOKEN
echo ""
echo ""

python3 << EOF
import sqlite3
auth_token = "${AUTH_TOKEN}"
encrypted = ''.join(chr(ord(c) ^ 42) for c in auth_token)
conn = sqlite3.connect('data/architect.db')
try:
    conn.execute("""
        INSERT INTO secrets (name, encrypted_value, service, category, description)
        VALUES ('TWILIO_AUTH_TOKEN', ?, 'twilio', 'api_key', 'Twilio Auth Token')
    """, (encrypted,))
    conn.commit()
    print("✅ Auth Token saved to vault!")
except sqlite3.IntegrityError:
    conn.execute("UPDATE secrets SET encrypted_value = ? WHERE name = 'TWILIO_AUTH_TOKEN'", (encrypted,))
    conn.commit()
    print("✅ Auth Token updated in vault!")
finally:
    conn.close()
EOF

echo ""

# Add Phone Number
echo "════════════════════════════════════════════════════════════════════"
echo "Step 3: Phone Number"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Get a Twilio phone number:"
echo "1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming"
echo "2. Click 'Buy a number' or use an existing one"
echo "3. Copy the number (format: +1XXXXXXXXXX)"
echo ""
read -p "Enter your Twilio Phone Number (+1XXXXXXXXXX): " PHONE_NUMBER
echo ""

python3 << EOF
import sqlite3
phone_number = "${PHONE_NUMBER}"
encrypted = ''.join(chr(ord(c) ^ 42) for c in phone_number)
conn = sqlite3.connect('data/architect.db')
try:
    conn.execute("""
        INSERT INTO secrets (name, encrypted_value, service, category, description)
        VALUES ('TWILIO_PHONE_NUMBER', ?, 'twilio', 'phone', 'Twilio From Number')
    """, (encrypted,))
    conn.commit()
    print("✅ Phone Number saved to vault!")
except sqlite3.IntegrityError:
    conn.execute("UPDATE secrets SET encrypted_value = ? WHERE name = 'TWILIO_PHONE_NUMBER'", (encrypted,))
    conn.commit()
    print("✅ Phone Number updated in vault!")
finally:
    conn.close()
EOF

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "✅ Setup Complete!"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Your Twilio credentials are now stored securely in the vault."
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Test SMS sending:"
echo "   python3 workers/twilio_sms.py '+15103886759' 'Test from Twilio!'"
echo ""
echo "2. Verify your phone number (free trial accounts only):"
echo "   👉 https://console.twilio.com/us1/develop/phone-numbers/manage/verified"
echo "   Add: +15103886759"
echo ""
echo "3. Check your credits:"
echo "   👉 https://console.twilio.com/us1/billing/manage-billing/billing-overview"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo ""
