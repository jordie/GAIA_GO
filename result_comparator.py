#!/usr/bin/env python3
"""
Result Comparator - Compare Claude vs Perplexity vs Comet results

Integrates with:
- claude_auto_integration.py
- perplexity_scraper.py
- quality_scorer.py

Provides side-by-side comparison and quality scoring.

Usage:
    from result_comparator import ResultComparator

    comparator = ResultComparator()
    comparison = comparator.compare_all("What is machine learning?")
    print(comparison['winner'])
"""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from claude_auto_integration import ClaudeIntegration
from comet_auto_integration import CometIntegration
from perplexity_scraper import PerplexityScraper
from quality_scorer import QualityScorer

# Database setup
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "comparisons"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "comparisons.db"


class ResultComparator:
    """Compare results from multiple AI sources."""

    def __init__(self):
        self.claude = ClaudeIntegration()
        self.perplexity = PerplexityScraper()
        self.comet = CometIntegration()
        self.scorer = QualityScorer()
        self.db_path = DB_PATH
        self.init_database()

    def init_database(self):
        """Initialize comparison database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                claude_result_id INTEGER,
                perplexity_search_id TEXT,
                comet_result_id INTEGER,
                claude_score REAL,
                perplexity_score REAL,
                comet_score REAL,
                winner TEXT,
                comparison_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS side_by_side (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comparison_id INTEGER,
                source TEXT,
                response TEXT,
                score_breakdown TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (comparison_id) REFERENCES comparisons(id)
            )
        """)

        conn.commit()
        conn.close()

    def compare_all(self, query: str, timeout: int = 120) -> Dict:
        """
        Execute query on all sources and compare results.

        Args:
            query: The question/task to compare
            timeout: Maximum seconds to wait per source

        Returns:
            Comparison dictionary with scores and winner
        """
        print(f"\n{'='*80}")
        print(f"COMPARING: {query}")
        print(f"{'='*80}\n")

        results = {}
        scores = {}

        # Execute on Claude
        print("📤 Executing on Claude...")
        claude_start = time.time()
        claude_result = self.claude.execute_task(query, timeout=timeout)
        claude_time = time.time() - claude_start

        if claude_result and claude_result['status'] == 'success':
            results['claude'] = {
                'response': claude_result['response'],
                'execution_time': claude_time,
                'result_id': claude_result.get('result_id'),
                'parsed': claude_result.get('parsed')
            }

            # Score Claude result
            claude_score = self.scorer.score_result({
                'source': 'claude',
                'query': query,
                'answer': claude_result['response'],
                'sources': [],  # Claude doesn't provide external sources
                'response_time': claude_time,
                'word_count': len(claude_result['response'].split())
            })
            scores['claude'] = claude_score
            print(f"✅ Claude: {claude_score['total']:.3f} ({claude_score['grade']})")
        else:
            print(f"❌ Claude failed: {claude_result.get('error', 'Unknown') if claude_result else 'No result'}")
            results['claude'] = None
            scores['claude'] = None

        # Execute on Perplexity (via scraping)
        print("\n📤 Executing on Perplexity...")
        perplexity_start = time.time()
        # Note: This would need actual Perplexity search execution
        # For now, we'll check if there are recent results
        perplexity_time = time.time() - perplexity_start

        # Try to get a recent Perplexity result for this query
        perplexity_results = self.perplexity.get_recent_results(limit=10)
        perplexity_match = None

        for pr in perplexity_results:
            if pr.get('query', '').lower() == query.lower():
                perplexity_match = pr
                break

        if perplexity_match:
            results['perplexity'] = {
                'response': perplexity_match.get('answer', ''),
                'execution_time': perplexity_time,
                'search_id': perplexity_match.get('search_id'),
                'sources': perplexity_match.get('sources', [])
            }

            # Score Perplexity result
            perplexity_score = self.scorer.score_result({
                'source': 'perplexity',
                'query': query,
                'answer': perplexity_match.get('answer', ''),
                'sources': perplexity_match.get('sources', []),
                'response_time': perplexity_time,
                'word_count': len(perplexity_match.get('answer', '').split())
            })
            scores['perplexity'] = perplexity_score
            print(f"✅ Perplexity: {perplexity_score['total']:.3f} ({perplexity_score['grade']})")
        else:
            print("⚠️  No matching Perplexity result found (would need live search)")
            results['perplexity'] = None
            scores['perplexity'] = None

        # Execute on Comet
        print("\n📤 Executing on Comet...")
        comet_start = time.time()
        comet_result = self.comet.execute_task(query, timeout=timeout)
        comet_time = time.time() - comet_start

        if comet_result and comet_result['status'] == 'success':
            results['comet'] = {
                'response': comet_result['response'],
                'execution_time': comet_time,
                'result_id': comet_result.get('result_id')
            }

            # Score Comet result
            comet_score = self.scorer.score_result({
                'source': 'comet',
                'query': query,
                'answer': comet_result['response'],
                'sources': [],  # Comet doesn't provide external sources
                'response_time': comet_time,
                'word_count': len(comet_result['response'].split())
            })
            scores['comet'] = comet_score
            print(f"✅ Comet: {comet_score['total']:.3f} ({comet_score['grade']})")
        else:
            print(f"❌ Comet failed: {comet_result.get('error', 'Unknown') if comet_result else 'No result'}")
            results['comet'] = None
            scores['comet'] = None

        # Determine winner
        winner = self._determine_winner(scores)

        # Save comparison
        comparison_id = self._save_comparison(
            query=query,
            results=results,
            scores=scores,
            winner=winner
        )

        print(f"\n{'='*80}")
        print(f"🏆 WINNER: {winner.upper()}")
        print(f"{'='*80}\n")

        return {
            'comparison_id': comparison_id,
            'query': query,
            'results': results,
            'scores': scores,
            'winner': winner,
            'summary': self._generate_summary(results, scores, winner)
        }

    def _determine_winner(self, scores: Dict) -> str:
        """Determine which source had the best score."""
        valid_scores = {
            source: score['total']
            for source, score in scores.items()
            if score is not None
        }

        if not valid_scores:
            return 'none'

        winner = max(valid_scores, key=valid_scores.get)
        return winner

    def _generate_summary(self, results: Dict, scores: Dict, winner: str) -> Dict:
        """Generate comparison summary."""
        summary = {
            'sources_compared': sum(1 for r in results.values() if r is not None),
            'scores': {},
            'winner': winner,
            'margin': None
        }

        # Extract scores
        for source, score in scores.items():
            if score:
                summary['scores'][source] = {
                    'total': score['total'],
                    'grade': score['grade']
                }

        # Calculate winning margin
        valid_scores = [s['total'] for s in scores.values() if s]
        if len(valid_scores) >= 2:
            sorted_scores = sorted(valid_scores, reverse=True)
            summary['margin'] = sorted_scores[0] - sorted_scores[1]

        return summary

    def _save_comparison(self, query: str, results: Dict, scores: Dict,
                         winner: str) -> int:
        """Save comparison to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Extract IDs
        claude_id = results.get('claude', {}).get('result_id') if results.get('claude') else None
        perplexity_id = results.get('perplexity', {}).get('search_id') if results.get('perplexity') else None
        comet_id = results.get('comet', {}).get('result_id') if results.get('comet') else None

        # Extract scores
        claude_score = scores.get('claude', {}).get('total_score') if scores.get('claude') else None
        perplexity_score = scores.get('perplexity', {}).get('total_score') if scores.get('perplexity') else None
        comet_score = scores.get('comet', {}).get('total_score') if scores.get('comet') else None

        cursor.execute("""
            INSERT INTO comparisons
            (query, claude_result_id, perplexity_search_id, comet_result_id,
             claude_score, perplexity_score, comet_score, winner,
             comparison_details, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            query,
            claude_id,
            perplexity_id,
            comet_id,
            claude_score,
            perplexity_score,
            comet_score,
            winner,
            json.dumps(scores),
            json.dumps({'version': '1.0'})
        ))

        comparison_id = cursor.lastrowid

        # Save side-by-side details
        for source, result in results.items():
            if result:
                cursor.execute("""
                    INSERT INTO side_by_side
                    (comparison_id, source, response, score_breakdown)
                    VALUES (?, ?, ?, ?)
                """, (
                    comparison_id,
                    source,
                    result.get('response', ''),
                    json.dumps(scores.get(source))
                ))

        conn.commit()
        conn.close()

        return comparison_id

    def get_recent_comparisons(self, limit: int = 10) -> List[Dict]:
        """Get recent comparisons from database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM comparisons
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        comparisons = []
        for row in rows:
            comp = dict(row)
            # Parse JSON fields
            if comp['comparison_details']:
                comp['comparison_details'] = json.loads(comp['comparison_details'])
            if comp['metadata']:
                comp['metadata'] = json.loads(comp['metadata'])
            comparisons.append(comp)

        return comparisons

    def get_comparison_stats(self) -> Dict:
        """Get statistics about comparisons."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM comparisons")
        total_comparisons = cursor.fetchone()[0]

        cursor.execute("""
            SELECT winner, COUNT(*) as count
            FROM comparisons
            GROUP BY winner
        """)
        winner_counts = dict(cursor.fetchall())

        cursor.execute("""
            SELECT AVG(claude_score), AVG(perplexity_score), AVG(comet_score)
            FROM comparisons
        """)
        avg_scores = cursor.fetchone()

        conn.close()

        return {
            'total_comparisons': total_comparisons,
            'winner_counts': winner_counts,
            'average_scores': {
                'claude': round(avg_scores[0], 3) if avg_scores[0] else None,
                'perplexity': round(avg_scores[1], 3) if avg_scores[1] else None,
                'comet': round(avg_scores[2], 3) if avg_scores[2] else None
            }
        }


def main():
    """CLI interface."""
    import sys

    comparator = ResultComparator()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == '--compare':
            if len(sys.argv) < 3:
                print("Usage: --compare '<query>'")
                sys.exit(1)

            query = sys.argv[2]
            comparison = comparator.compare_all(query)

            # Print detailed results
            print("\nDETAILED RESULTS:")
            print("="*80)

            for source in ['claude', 'perplexity', 'comet']:
                result = comparison['results'].get(source)
                score = comparison['scores'].get(source)

                print(f"\n{source.upper()}:")
                print("-" * 80)

                if result and score:
                    print(f"Response: {result['response'][:200]}...")
                    print(f"Score: {score['total_score']:.3f} ({score['letter_grade']})")
                    print(f"Time: {result.get('execution_time', 0):.1f}s")
                else:
                    print("Not available")

        elif command == '--stats':
            stats = comparator.get_comparison_stats()
            print(json.dumps(stats, indent=2))

        elif command == '--recent':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            comparisons = comparator.get_recent_comparisons(limit=limit)

            for comp in comparisons:
                print(f"\n{'='*80}")
                print(f"Comparison ID: {comp['id']}")
                print(f"Query: {comp['query']}")
                print(f"Winner: {comp['winner']}")
                print(f"Scores: Claude={comp['claude_score']:.3f if comp['claude_score'] else 'N/A'}, "
                      f"Perplexity={comp['perplexity_score']:.3f if comp['perplexity_score'] else 'N/A'}")
                print(f"Created: {comp['created_at']}")

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Result Comparator - Compare AI sources")
        print("\nUsage:")
        print("  python3 result_comparator.py --compare '<query>'")
        print("  python3 result_comparator.py --stats")
        print("  python3 result_comparator.py --recent [N]")


if __name__ == "__main__":
    main()
