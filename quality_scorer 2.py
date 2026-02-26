#!/usr/bin/env python3
"""
Quality Scorer - Measure and compare AI result quality

Scores based on:
- Answer completeness
- Source quality and quantity
- Response time
- User feedback
- Content depth

Compares:
- Claude vs Perplexity
- Different routing strategies
- Manual vs automated results

Usage:
    scorer = QualityScorer()
    score = scorer.score_result(result_data)
    comparison = scorer.compare_sources('claude', 'perplexity')
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class QualityScorer:
    """Score and compare AI result quality."""

    def __init__(self):
        self.scores_file = Path('data/quality_scores.json')
        self.scores_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_scores()

        # Scoring weights
        self.weights = {
            'completeness': 0.30,      # Is answer complete?
            'sources': 0.20,            # Quality/quantity of sources
            'speed': 0.15,              # Response time
            'depth': 0.20,              # Content depth
            'accuracy': 0.15,           # User-verified accuracy
        }

    def load_scores(self):
        """Load quality scores."""
        if self.scores_file.exists():
            with open(self.scores_file) as f:
                self.scores = json.load(f)
        else:
            self.scores = {
                'results': [],
                'by_source': {
                    'claude': {'total': 0, 'avg_score': 0, 'scores': []},
                    'perplexity': {'total': 0, 'avg_score': 0, 'scores': []},
                    'comet': {'total': 0, 'avg_score': 0, 'scores': []}
                },
                'feedback': []
            }

    def save_scores(self):
        """Save quality scores."""
        with open(self.scores_file, 'w') as f:
            json.dump(self.scores, f, indent=2)

    def score_completeness(self, result: Dict) -> float:
        """
        Score answer completeness (0.0 to 1.0).

        Factors:
        - Has answer text
        - Answer length
        - Multiple perspectives
        - Covers key aspects
        """
        score = 0.0

        answer = result.get('answer', '')
        if not answer:
            return 0.0

        # Base score for having an answer
        score += 0.3

        # Length-based scoring
        answer_length = len(answer)
        if answer_length > 1000:
            score += 0.3
        elif answer_length > 500:
            score += 0.2
        elif answer_length > 200:
            score += 0.1

        # Check for completeness indicators
        completeness_indicators = [
            r'\d+\.',                    # Numbered lists
            r'•',                        # Bullet points
            r'however|although|but',     # Balanced perspectives
            r'additionally|furthermore', # Depth
            r'because|since|therefore',  # Reasoning
        ]

        for pattern in completeness_indicators:
            if re.search(pattern, answer, re.IGNORECASE):
                score += 0.08

        return min(1.0, score)

    def score_sources(self, result: Dict) -> float:
        """
        Score source quality (0.0 to 1.0).

        Factors:
        - Number of sources
        - Source diversity
        - Source authority
        """
        score = 0.0

        sources = result.get('sources', [])
        if not sources:
            return 0.0

        # Number of sources
        num_sources = len(sources)
        if num_sources >= 5:
            score += 0.5
        elif num_sources >= 3:
            score += 0.3
        elif num_sources >= 1:
            score += 0.1

        # Source diversity (different domains)
        domains = set()
        for source in sources:
            url = source.get('url', '')
            match = re.search(r'https?://([^/]+)', url)
            if match:
                domain = match.group(1)
                domains.add(domain)

        diversity_score = min(0.3, len(domains) * 0.1)
        score += diversity_score

        # Authority indicators
        authority_domains = [
            '.gov', '.edu', '.org',
            'wikipedia.org', 'reuters.com', 'bbc.com'
        ]

        authority_count = sum(
            1 for source in sources
            if any(domain in source.get('url', '') for domain in authority_domains)
        )

        score += min(0.2, authority_count * 0.1)

        return min(1.0, score)

    def score_speed(self, result: Dict) -> float:
        """
        Score response speed (0.0 to 1.0).

        Faster is better, but quality matters more.
        """
        response_time = result.get('response_time', 10)  # Default 10 seconds

        # Perfect score < 2 seconds
        if response_time < 2:
            return 1.0
        # Good score < 5 seconds
        elif response_time < 5:
            return 0.8
        # Acceptable < 10 seconds
        elif response_time < 10:
            return 0.6
        # Slow < 20 seconds
        elif response_time < 20:
            return 0.4
        # Very slow
        else:
            return 0.2

    def score_depth(self, result: Dict) -> float:
        """
        Score content depth (0.0 to 1.0).

        Factors:
        - Technical terms
        - Specific details
        - Examples
        - Explanations
        """
        score = 0.0

        answer = result.get('answer', '')
        if not answer:
            return 0.0

        # Check for depth indicators
        depth_patterns = [
            r'\d+%',                     # Statistics
            r'\$\d+',                    # Money/numbers
            r'for example|such as',      # Examples
            r'specifically|particularly', # Specificity
            r'according to|research shows', # Citations
            r'\d{4}',                    # Years/dates
        ]

        for pattern in depth_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                score += 0.15

        # Related questions suggest depth
        if result.get('related_questions'):
            score += 0.2

        return min(1.0, score)

    def score_accuracy(self, result: Dict) -> float:
        """
        Score accuracy based on user feedback (0.0 to 1.0).

        Default: 0.5 (neutral, no feedback yet)
        """
        # Check for user feedback
        result_id = result.get('id')
        if result_id:
            for feedback in self.scores.get('feedback', []):
                if feedback.get('result_id') == result_id:
                    return feedback.get('accuracy_score', 0.5)

        # No feedback yet - neutral score
        return 0.5

    def score_result(self, result: Dict) -> Dict:
        """
        Score a result across all dimensions.

        Returns:
            Score breakdown and total
        """
        scores = {
            'completeness': self.score_completeness(result),
            'sources': self.score_sources(result),
            'speed': self.score_speed(result),
            'depth': self.score_depth(result),
            'accuracy': self.score_accuracy(result),
        }

        # Calculate weighted total
        total = sum(
            scores[dim] * self.weights[dim]
            for dim in scores
        )

        return {
            'total': round(total, 3),
            'breakdown': {k: round(v, 3) for k, v in scores.items()},
            'grade': self.score_to_grade(total)
        }

    def score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 0.9:
            return 'A+'
        elif score >= 0.85:
            return 'A'
        elif score >= 0.8:
            return 'A-'
        elif score >= 0.75:
            return 'B+'
        elif score >= 0.7:
            return 'B'
        elif score >= 0.65:
            return 'B-'
        elif score >= 0.6:
            return 'C+'
        elif score >= 0.55:
            return 'C'
        elif score >= 0.5:
            return 'C-'
        else:
            return 'D'

    def log_score(self, result: Dict, source: str, task: str):
        """
        Log a quality score.

        Args:
            result: Result data with answer, sources, etc.
            source: claude, perplexity, comet
            task: Original task description
        """
        score_data = self.score_result(result)

        entry = {
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'task': task[:100],
            'score': score_data['total'],
            'breakdown': score_data['breakdown'],
            'grade': score_data['grade']
        }

        self.scores['results'].append(entry)

        # Update source statistics
        source_stats = self.scores['by_source'][source]
        source_stats['total'] += 1
        source_stats['scores'].append(score_data['total'])

        # Calculate average
        if source_stats['scores']:
            source_stats['avg_score'] = round(
                sum(source_stats['scores']) / len(source_stats['scores']),
                3
            )

        # Keep only last 100 scores per source
        if len(source_stats['scores']) > 100:
            source_stats['scores'] = source_stats['scores'][-100:]

        self.save_scores()

        return entry

    def add_feedback(self, result_id: str, accuracy_score: float, notes: str = ''):
        """
        Add user feedback on result accuracy.

        Args:
            result_id: ID of the result
            accuracy_score: 0.0 to 1.0
            notes: Optional feedback notes
        """
        self.scores['feedback'].append({
            'timestamp': datetime.now().isoformat(),
            'result_id': result_id,
            'accuracy_score': accuracy_score,
            'notes': notes
        })

        self.save_scores()

    def compare_sources(self) -> Dict:
        """
        Compare quality across sources.

        Returns:
            Comparison statistics
        """
        comparison = {}

        for source, stats in self.scores['by_source'].items():
            if stats['total'] > 0:
                comparison[source] = {
                    'avg_score': stats['avg_score'],
                    'grade': self.score_to_grade(stats['avg_score']),
                    'total_results': stats['total'],
                    'recent_scores': stats['scores'][-10:]
                }

        # Determine winner
        if comparison:
            winner = max(comparison, key=lambda x: comparison[x]['avg_score'])
            comparison['winner'] = winner
            comparison['winner_score'] = comparison[winner]['avg_score']

        return comparison

    def get_stats(self) -> Dict:
        """Get quality statistics."""
        return {
            'total_results': len(self.scores['results']),
            'by_source': self.scores['by_source'],
            'comparison': self.compare_sources(),
            'recent_scores': self.scores['results'][-10:]
        }


# CLI interface
if __name__ == '__main__':
    import sys

    scorer = QualityScorer()

    if '--stats' in sys.argv:
        # Show statistics
        stats = scorer.get_stats()
        print("\n" + "="*80)
        print("QUALITY SCORER STATISTICS")
        print("="*80 + "\n")
        print(f"Total Results Scored: {stats['total_results']}")

        if stats['comparison']:
            print("\nSource Comparison:")
            for source, data in stats['comparison'].items():
                if source != 'winner' and source != 'winner_score':
                    print(f"\n{source.upper()}:")
                    print(f"  Average Score: {data['avg_score']:.3f} (Grade: {data['grade']})")
                    print(f"  Total Results: {data['total_results']}")

            if 'winner' in stats['comparison']:
                print(f"\n🏆 Winner: {stats['comparison']['winner'].upper()}")
                print(f"   Score: {stats['comparison']['winner_score']:.3f}")

        print("\n" + "="*80)

    elif '--test' in sys.argv:
        # Test scoring
        test_results = [
            {
                'answer': 'Ethiopia is a country in East Africa. The best time to visit is October to March during the dry season. You can see historical sites, beautiful landscapes, and unique culture. Prices are moderate.',
                'sources': [
                    {'url': 'https://wikipedia.org/ethiopia', 'title': 'Ethiopia'},
                    {'url': 'https://lonelyplanet.com/ethiopia', 'title': 'Lonely Planet'}
                ],
                'response_time': 3
            },
            {
                'answer': 'Ethiopia',
                'sources': [],
                'response_time': 1
            }
        ]

        print("\nTesting Quality Scorer:\n")
        for i, result in enumerate(test_results, 1):
            score_data = scorer.score_result(result)
            print(f"Result {i}:")
            print(f"  Total Score: {score_data['total']:.3f} (Grade: {score_data['grade']})")
            print(f"  Breakdown:")
            for dim, score in score_data['breakdown'].items():
                print(f"    {dim:15} {score:.3f}")
            print()

    else:
        print("""
Quality Scorer - Measure AI result quality

Usage:
    python3 quality_scorer.py --stats    # Show statistics
    python3 quality_scorer.py --test     # Test scorer

Scoring Dimensions:
    - Completeness (30%): Answer completeness
    - Sources (20%): Quality and quantity of sources
    - Speed (15%): Response time
    - Depth (20%): Content depth and detail
    - Accuracy (15%): User-verified accuracy

Grades:
    A+ (0.9+), A (0.85+), A- (0.8+)
    B+ (0.75+), B (0.7+), B- (0.65+)
    C+ (0.6+), C (0.55+), C- (0.5+)
    D (< 0.5)

Integration:
    scorer = QualityScorer()
    score = scorer.score_result(result_data)
    scorer.log_score(result_data, source='perplexity', task='Research Ethiopia')
""")
