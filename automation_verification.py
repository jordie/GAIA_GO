#!/usr/bin/env python3
"""
Automation Verification Layer - Never trust "success", always verify

Wraps automation operations with verification checks.
"""
import subprocess
import time
from pathlib import Path
from datetime import datetime
import json


class VerificationError(Exception):
    """Raised when verification fails."""
    pass


class AutomationVerifier:
    """Verification wrapper for automation operations."""
    
    def __init__(self, screenshots_dir='data/screenshots'):
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.verification_log = Path('data/verification_log.json')
        self.load_log()
    
    def load_log(self):
        """Load verification history."""
        if self.verification_log.exists():
            with open(self.verification_log) as f:
                self.log = json.load(f)
        else:
            self.log = {
                'total_operations': 0,
                'verified': 0,
                'failed': 0,
                'history': []
            }
    
    def save_log(self):
        """Save verification history."""
        with open(self.verification_log, 'w') as f:
            json.dump(self.log, f, indent=2)
    
    def verify_perplexity_submission(self, url, expected_pattern='/search/'):
        """
        Verify Perplexity search was created.
        
        Args:
            url: URL returned from submission
            expected_pattern: Pattern that should be in URL
        
        Returns:
            True if verified
        
        Raises:
            VerificationError if verification fails
        """
        self.log['total_operations'] += 1
        
        verification = {
            'timestamp': datetime.now().isoformat(),
            'operation': 'perplexity_submission',
            'url': url,
            'expected': expected_pattern,
            'verified': False
        }
        
        if expected_pattern in url:
            verification['verified'] = True
            self.log['verified'] += 1
            self.log['history'].append(verification)
            self.save_log()
            return True
        else:
            verification['error'] = f"URL missing '{expected_pattern}'"
            self.log['failed'] += 1
            self.log['history'].append(verification)
            self.save_log()
            
            # Take screenshot for debugging
            screenshot_file = self.take_screenshot('perplexity_failed')
            verification['screenshot'] = str(screenshot_file)
            
            raise VerificationError(
                f"Perplexity submission failed verification: {verification['error']}"
            )
    
    def verify_file_exists(self, filepath):
        """Verify file was created."""
        self.log['total_operations'] += 1
        
        verification = {
            'timestamp': datetime.now().isoformat(),
            'operation': 'file_creation',
            'filepath': str(filepath),
            'verified': False
        }
        
        if Path(filepath).exists():
            verification['verified'] = True
            verification['size'] = Path(filepath).stat().st_size
            self.log['verified'] += 1
            self.log['history'].append(verification)
            self.save_log()
            return True
        else:
            verification['error'] = 'File not found'
            self.log['failed'] += 1
            self.log['history'].append(verification)
            self.save_log()
            
            raise VerificationError(f"File creation failed: {filepath}")
    
    def verify_url_accessible(self, url, timeout=5):
        """Verify URL is accessible."""
        try:
            import urllib.request
            urllib.request.urlopen(url, timeout=timeout)
            return True
        except Exception as e:
            raise VerificationError(f"URL not accessible: {e}")
    
    def take_screenshot(self, prefix='screenshot'):
        """Take screenshot for debugging."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshot_file = self.screenshots_dir / f"{prefix}_{timestamp}.png"
        
        try:
            # macOS screenshot command
            subprocess.run(
                ['screencapture', '-x', str(screenshot_file)],
                timeout=5,
                check=True
            )
            return screenshot_file
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return None
    
    def get_stats(self):
        """Get verification statistics."""
        if self.log['total_operations'] > 0:
            success_rate = (self.log['verified'] / self.log['total_operations']) * 100
        else:
            success_rate = 0
        
        return {
            'total_operations': self.log['total_operations'],
            'verified': self.log['verified'],
            'failed': self.log['failed'],
            'success_rate': f"{success_rate:.1f}%",
            'recent_failures': [
                h for h in self.log['history'][-10:]
                if not h['verified']
            ]
        }


# Example usage
if __name__ == '__main__':
    verifier = AutomationVerifier()
    
    print("Testing Verification Layer...")
    print()
    
    # Test 1: Verify good Perplexity URL
    try:
        good_url = "https://www.perplexity.ai/search/test-query-abc123"
        verifier.verify_perplexity_submission(good_url)
        print("✅ Test 1: Good URL verified")
    except VerificationError as e:
        print(f"❌ Test 1 failed: {e}")
    
    # Test 2: Verify bad Perplexity URL (should fail)
    try:
        bad_url = "https://www.perplexity.ai/"
        verifier.verify_perplexity_submission(bad_url)
        print("✅ Test 2: Should not reach here")
    except VerificationError as e:
        print(f"✅ Test 2: Correctly caught bad URL: {e}")
    
    # Test 3: Verify file exists
    test_file = Path('/tmp/test_verification.txt')
    test_file.write_text('test')
    try:
        verifier.verify_file_exists(test_file)
        print("✅ Test 3: File existence verified")
    except VerificationError as e:
        print(f"❌ Test 3 failed: {e}")
    
    print()
    print("Verification Stats:")
    print(json.dumps(verifier.get_stats(), indent=2))
