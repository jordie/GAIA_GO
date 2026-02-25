# Twilio SMS Setup Guide

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Twilio Account

1. Go to: **https://www.twilio.com/try-twilio**
2. Click "Sign up"
3. Enter your information
4. Verify your email
5. **Get $15 free credit** (no credit card required initially)

### Step 2: Get Your Credentials

After signing up, you'll see your **Console Dashboard**:

1. Find your **Account SID** (starts with "AC...")
2. Find your **Auth Token** (click to reveal)
3. Get a phone number:
   - Click "Get a Twilio phone number"
   - Click "Choose this number"
   - Copy the number (format: +1XXXXXXXXXX)

### Step 3: Add Credentials to Vault

Run this command to store your Twilio credentials:

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Add Account SID
python3 << 'EOF'
import sqlite3
account_sid = input("Enter your Twilio Account SID: ")
encrypted = ''.join(chr(ord(c) ^ 42) for c in account_sid)
conn = sqlite3.connect('data/architect.db')
conn.execute("""
    INSERT INTO secrets (name, encrypted_value, service, category, description)
    VALUES ('TWILIO_ACCOUNT_SID', ?, 'twilio', 'api_key', 'Twilio Account SID')
""", (encrypted,))
conn.commit()
conn.close()
print("✓ Account SID saved!")
EOF

# Add Auth Token
python3 << 'EOF'
import sqlite3
auth_token = input("Enter your Twilio Auth Token: ")
encrypted = ''.join(chr(ord(c) ^ 42) for c in auth_token)
conn = sqlite3.connect('data/architect.db')
conn.execute("""
    INSERT INTO secrets (name, encrypted_value, service, category, description)
    VALUES ('TWILIO_AUTH_TOKEN', ?, 'twilio', 'api_key', 'Twilio Auth Token')
""", (encrypted,))
conn.commit()
conn.close()
print("✓ Auth Token saved!")
EOF

# Add Phone Number
python3 << 'EOF'
import sqlite3
phone_number = input("Enter your Twilio Phone Number (+1XXXXXXXXXX): ")
encrypted = ''.join(chr(ord(c) ^ 42) for c in phone_number)
conn = sqlite3.connect('data/architect.db')
conn.execute("""
    INSERT INTO secrets (name, encrypted_value, service, category, description)
    VALUES ('TWILIO_PHONE_NUMBER', ?, 'twilio', 'phone', 'Twilio From Number')
""", (encrypted,))
conn.commit()
conn.close()
print("✓ Phone Number saved!")
EOF
```

### Step 4: Test SMS

```bash
python3 workers/twilio_sms.py "+15103886759" "Test SMS from Architect Dashboard via Twilio!"
```

## 📊 Pricing

- **Free Trial**: $15 credit (sends ~600 messages)
- **Pay as you go**: $0.0075 per SMS (US)
- **No monthly fees**
- **No commitment**

## ✅ Twilio Advantages vs Google Voice

| Feature | Twilio | Google Voice |
|---------|--------|--------------|
| **Setup Time** | 5 minutes | 30+ minutes (manual) |
| **API** | ✅ Official API | ❌ Browser automation |
| **Reliability** | 99.95% uptime | Depends on browser |
| **Delivery Receipts** | ✅ Yes | ❌ No |
| **Two-way SMS** | ✅ Yes | Limited |
| **Production Ready** | ✅ Yes | ⚠️ Not recommended |
| **Support** | 24/7 support | Community only |

## 🔧 Integration with Architect Dashboard

Once credentials are added, you can use Twilio from:

### Python Code:
```python
from workers.twilio_sms import TwilioSMS

sms = TwilioSMS()
result = sms.send_sms("+15103886759", "Your message here")

if result['success']:
    print(f"Sent! SID: {result['sid']}")
```

### Command Line:
```bash
python3 workers/twilio_sms.py "+15103886759" "Your message"
```

### API Endpoint (Coming Soon):
```bash
curl -X POST http://localhost:8080/api/sms/send \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+15103886759",
    "message": "Test from API",
    "provider": "twilio"
  }'
```

## 📞 Next Steps After Setup

1. ✅ Test sending SMS
2. ✅ Add API endpoint for SMS
3. ✅ Set up webhooks for incoming messages
4. ✅ Add delivery status tracking
5. ✅ Create SMS templates

## 🆘 Troubleshooting

**"No credentials found"**
- Make sure you ran all 3 credential commands
- Check: `sqlite3 data/architect.db "SELECT name FROM secrets WHERE service='twilio'"`

**"Authentication Error"**
- Verify Account SID starts with "AC"
- Verify Auth Token is correct (32 characters)

**"Invalid 'From' number"**
- Make sure you got a Twilio phone number
- Use E.164 format: +1XXXXXXXXXX

**"Unverified number"**
- Free trial accounts can only send to verified numbers
- Verify +15103886759 in Twilio console
- Or upgrade account (no charge until you send messages)

## 💰 Cost Calculator

For 1000 SMS/month:
- **Cost**: $7.50/month
- **Per message**: $0.0075
- **vs Google Voice**: Free (but unreliable)
- **vs Carrier**: $10-20/month (limited)

**Recommendation**: Start with free trial, upgrade only when needed.

---

**Ready to set up?** Follow Step 1 above! 🚀
