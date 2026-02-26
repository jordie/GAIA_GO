#!/usr/bin/env python3
"""
Unified Messaging System - Always deliver messages, one way or another

Priority: WhatsApp → Email → File → Console
Each backend tries in order until one succeeds.
"""
import json
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime


class MessagingBackend:
    """Base class for messaging backends."""
    def send(self, message, recipient):
        raise NotImplementedError


class WhatsAppBackend(MessagingBackend):
    """WhatsApp via OpenClaw."""
    def send(self, message, recipient):
        try:
            result = subprocess.run(
                ['openclaw', 'message', 'send', '--channel', 'whatsapp', 
                 '--target', recipient, '--message', message, '--json'],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and 'messageId' in result.stdout:
                return True, f"WhatsApp sent (ID: {json.loads(result.stdout).get('payload', {}).get('result', {}).get('messageId', 'unknown')})"
            
            return False, f"WhatsApp failed: {result.stderr}"
        except Exception as e:
            return False, f"WhatsApp error: {e}"


class EmailBackend(MessagingBackend):
    """Email via localhost or external SMTP."""
    def send(self, message, recipient):
        try:
            msg = MIMEMultipart()
            msg['From'] = 'automation@localhost'
            msg['To'] = recipient
            msg['Subject'] = 'Automation Update'
            msg.attach(MIMEText(message, 'plain'))
            
            # Try localhost SMTP
            try:
                with smtplib.SMTP('localhost', timeout=5) as server:
                    server.send_message(msg)
                    return True, "Email sent via localhost SMTP"
            except:
                pass
            
            # Fallback: macOS mail command
            try:
                with open('/tmp/email_message.txt', 'w') as f:
                    f.write(message)
                
                subprocess.run(
                    ['mail', '-s', 'Automation Update', recipient],
                    stdin=open('/tmp/email_message.txt'),
                    timeout=10,
                    check=True
                )
                return True, "Email sent via mail command"
            except Exception as e:
                return False, f"Email failed: {e}"
                
        except Exception as e:
            return False, f"Email error: {e}"


class FileBackend(MessagingBackend):
    """Save to file as last resort."""
    def send(self, message, recipient):
        try:
            messages_dir = Path('data/messages')
            messages_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = messages_dir / f"message_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(f"To: {recipient}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write(f"\n{message}\n")
            
            return True, f"Saved to: {filename}"
        except Exception as e:
            return False, f"File error: {e}"


class ConsoleBackend(MessagingBackend):
    """Print to console - always works."""
    def send(self, message, recipient):
        print("=" * 80)
        print(f"MESSAGE TO: {recipient}")
        print(f"TIME: {datetime.now().isoformat()}")
        print("-" * 80)
        print(message)
        print("=" * 80)
        return True, "Printed to console"


class UnifiedMessenger:
    """Unified messaging with automatic fallback."""
    
    def __init__(self):
        self.backends = [
            ('WhatsApp', WhatsAppBackend()),
            ('Email', EmailBackend()),
            ('File', FileBackend()),
            ('Console', ConsoleBackend()),
        ]
        
        # Track stats
        self.stats_file = Path('data/messaging_stats.json')
        self.load_stats()
    
    def load_stats(self):
        """Load messaging statistics."""
        if self.stats_file.exists():
            with open(self.stats_file) as f:
                self.stats = json.load(f)
        else:
            self.stats = {
                'total_messages': 0,
                'by_backend': {},
                'failures': []
            }
    
    def save_stats(self):
        """Save messaging statistics."""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def send(self, message, recipient, preferred_backend=None):
        """
        Send message with automatic fallback.
        
        Args:
            message: Message text
            recipient: Phone/email/username
            preferred_backend: Try this first (optional)
        
        Returns:
            (success, backend_used, details)
        """
        backends = self.backends.copy()
        
        # If preferred backend specified, try it first
        if preferred_backend:
            for i, (name, backend) in enumerate(backends):
                if name.lower() == preferred_backend.lower():
                    backends.insert(0, backends.pop(i))
                    break
        
        # Try each backend in order
        for backend_name, backend in backends:
            try:
                success, details = backend.send(message, recipient)
                
                if success:
                    # Update stats
                    self.stats['total_messages'] += 1
                    self.stats['by_backend'][backend_name] = \
                        self.stats['by_backend'].get(backend_name, 0) + 1
                    self.save_stats()
                    
                    return True, backend_name, details
                else:
                    print(f"  ⚠️  {backend_name} failed: {details}")
            
            except Exception as e:
                print(f"  ❌ {backend_name} error: {e}")
        
        # Should never reach here (Console always succeeds)
        return False, None, "All backends failed"
    
    def get_stats(self):
        """Get messaging statistics."""
        return self.stats


# Test the unified messenger
if __name__ == '__main__':
    messenger = UnifiedMessenger()
    
    test_message = """
🎯 Test Message from Unified Messenger

This is a test of the unified messaging system.
It will try backends in order until one succeeds:

1. WhatsApp
2. Email
3. File
4. Console (always works)

Timestamp: """ + datetime.now().isoformat()
    
    print("Testing Unified Messenger...")
    print()
    
    success, backend, details = messenger.send(
        test_message,
        '+15103886759'
    )
    
    print()
    print(f"✅ Delivered via: {backend}")
    print(f"Details: {details}")
    print()
    print("Stats:")
    print(json.dumps(messenger.get_stats(), indent=2))
