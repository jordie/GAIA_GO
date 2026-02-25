#!/usr/bin/env python3
"""
Prompt Deduplicator for GAIA

Prevents duplicate prompts from being queued by:
1. Checking for existing similar prompts in queue
2. Matching by content hash
3. Preventing concurrent duplicates of same work
4. Auto-cleanup of stale duplicates
"""

import hashlib
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class PromptDeduplicator:
    """Manages prompt deduplication and prevents queue congestion"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize deduplication tracking table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prompt_dedup_history (
                id INTEGER PRIMARY KEY,
                content_hash TEXT UNIQUE,
                prompt_id INTEGER,
                content TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT,
                reason TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_content_hash(self, content: str) -> str:
        """Generate hash of prompt content for deduplication"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def check_duplicate(self, content: str, lookback_hours: int = 2) -> Optional[Dict]:
        """
        Check if similar prompt exists in recent history
        
        Returns:
            Dict with existing prompt info if duplicate found, None otherwise
        """
        content_hash = self.get_content_hash(content)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        
        cursor.execute('''
            SELECT prompt_id, status, created_at FROM prompt_dedup_history
            WHERE content_hash = ?
            AND created_at > ?
            AND status != 'cancelled'
            LIMIT 1
        ''', (content_hash, cutoff_time))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'prompt_id': result[0],
                'status': result[1],
                'created_at': result[2],
                'reason': 'Content hash match (same work detected)',
                'action': 'Skip - use existing prompt' if result[1] != 'completed' else 'Requeue if needed'
            }
        
        return None
    
    def register_prompt(self, prompt_id: int, content: str) -> str:
        """Register a new prompt in deduplication system"""
        content_hash = self.get_content_hash(content)
        
        # Check for existing before registering
        duplicate = self.check_duplicate(content)
        if duplicate and duplicate['status'] in ['pending', 'assigned', 'in_progress']:
            return f"DUPLICATE_FOUND: Prompt {duplicate['prompt_id']} ({duplicate['status']})"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        expires_at = datetime.now() + timedelta(hours=24)
        
        try:
            cursor.execute('''
                INSERT INTO prompt_dedup_history 
                (content_hash, prompt_id, content, created_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (content_hash, prompt_id, content[:500], datetime.now(), expires_at, 'active'))
            
            conn.commit()
            return f"REGISTERED: Prompt {prompt_id}"
        except sqlite3.IntegrityError:
            return f"ERROR: Hash collision detected"
        finally:
            conn.close()
    
    def mark_duplicate(self, prompt_id: int, reason: str) -> str:
        """Mark a prompt as cancelled duplicate"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE prompt_dedup_history 
            SET status = 'cancelled', reason = ?
            WHERE prompt_id = ?
        ''', (reason, prompt_id))
        
        conn.commit()
        conn.close()
        
        return f"Marked prompt {prompt_id} as duplicate"
    
    def get_active_work(self, work_type: str) -> List[Dict]:
        """Get all active prompts of a specific type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT prompt_id, status, created_at FROM prompt_dedup_history
            WHERE content LIKE ?
            AND status IN ('pending', 'assigned', 'in_progress')
            ORDER BY created_at DESC
        ''', (f'%{work_type}%',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'prompt_id': row[0],
                'status': row[1],
                'created_at': row[2]
            })
        
        conn.close()
        return results
    
    def cleanup_expired(self) -> Tuple[int, int]:
        """Clean up expired entries from dedup history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count before
        cursor.execute('SELECT COUNT(*) FROM prompt_dedup_history WHERE expires_at < ?', (datetime.now(),))
        count_before = cursor.fetchone()[0]
        
        # Delete expired
        cursor.execute('DELETE FROM prompt_dedup_history WHERE expires_at < ?', (datetime.now(),))
        
        # Count after
        cursor.execute('SELECT COUNT(*) FROM prompt_dedup_history')
        count_after = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return (count_before, count_after)
    
    def get_stats(self) -> Dict:
        """Get deduplication statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM prompt_dedup_history WHERE status = "active"')
        active = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM prompt_dedup_history WHERE status = "cancelled"')
        cancelled = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM prompt_dedup_history WHERE status = "completed"')
        completed = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'active_tracked': active,
            'cancelled_duplicates': cancelled,
            'completed': completed,
            'total': active + cancelled + completed
        }


# Integration with Assigner Worker
def integrate_deduplicator(assigner_db_path: str, gaia_home_path: str):
    """Add deduplication checks to assigner worker"""
    dedup_db = Path(gaia_home_path) / 'orchestration' / 'prompt_dedup.db'
    deduplicator = PromptDeduplicator(str(dedup_db))
    
    return deduplicator


if __name__ == '__main__':
    # Example usage
    gaia_home = Path('/Users/jgirmay/Desktop/gitrepo/GAIA_HOME')
    dedup = PromptDeduplicator(str(gaia_home / 'orchestration' / 'prompt_dedup.db'))
    
    stats = dedup.get_stats()
    print(f"\n📊 Deduplication Stats:")
    print(f"  Active Tracked: {stats['active_tracked']}")
    print(f"  Cancelled Duplicates: {stats['cancelled_duplicates']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Total: {stats['total']}")
