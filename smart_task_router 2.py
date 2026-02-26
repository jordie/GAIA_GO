#!/usr/bin/env python3
"""
Smart Task Router - Automatically route tasks to the best AI/tool

Routes tasks based on analysis of:
- Task type (research, coding, web automation, facts)
- Complexity level
- Time sensitivity
- Quality requirements

Routing Strategy (based on user feedback):
- Claude (tmux): Deep research, analysis, coding, high-quality content
- Perplexity: Quick facts, current events, simple searches
- Comet: Web automation, browser tasks

Usage:
    router = SmartTaskRouter()
    target, confidence, reasoning = router.route("Research Ethiopia travel tips")
    # Returns: ('claude', 0.95, 'Complex research task requiring deep analysis')
"""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, List


class SmartTaskRouter:
    """Intelligent task routing based on task characteristics."""

    def __init__(self):
        self.stats_file = Path('data/routing_stats.json')
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_stats()

        # Routing patterns based on user feedback
        self.patterns = {
            'claude': {
                'keywords': [
                    # Research & analysis
                    'research', 'analyze', 'compare', 'evaluate', 'assess',
                    'investigate', 'study', 'examine', 'review', 'summarize',
                    # Deep thinking
                    'explain', 'understand', 'why', 'how does', 'strategy',
                    'plan', 'design', 'architect', 'structure',
                    # Coding & technical
                    'code', 'implement', 'develop', 'build', 'create function',
                    'debug', 'fix bug', 'refactor', 'optimize',
                    # Writing & content
                    'write', 'draft', 'compose', 'create content', 'documentation',
                    # Complex questions
                    'implications', 'consequences', 'trade-offs', 'considerations',
                ],
                'patterns': [
                    r'why .+',
                    r'how (does|do|can|should) .+',
                    r'what (are|is) the (best|difference|implications)',
                    r'compare .+ (to|with|and) .+',
                    r'create .+ (system|framework|architecture)',
                ],
                'quality_threshold': 0.7,  # Use Claude when quality matters
                'description': 'Deep research, analysis, coding, high-quality content'
            },

            'perplexity': {
                'keywords': [
                    # Quick facts
                    'what is', 'when did', 'who is', 'where is', 'define',
                    'list', 'find', 'search', 'lookup', 'check',
                    # Current events
                    'current', 'latest', 'recent', 'today', 'now', 'news',
                    'price', 'cost', 'weather', 'schedule', 'hours',
                    # Simple queries
                    'address', 'phone', 'email', 'location', 'directions',
                ],
                'patterns': [
                    r'what (is|are) .+\?',
                    r'when (is|did|will) .+\?',
                    r'(find|list|show) .+',
                    r'how much .+',
                    r'price of .+',
                ],
                'quality_threshold': 0.3,  # OK for quick facts
                'description': 'Quick facts, current events, simple searches'
            },

            'comet': {
                'keywords': [
                    # Web automation
                    'open', 'click', 'fill form', 'submit', 'navigate',
                    'browse', 'scrape', 'extract from web', 'download from',
                    'login to', 'screenshot', 'test website',
                    # Browser tasks
                    'check website', 'verify page', 'monitor site',
                    'automate browser', 'web automation',
                ],
                'patterns': [
                    r'(open|navigate to|go to) .+ (website|page|url)',
                    r'(click|fill|submit|select) .+',
                    r'scrape .+ from .+',
                    r'test .+ (website|page|form)',
                ],
                'quality_threshold': 0.5,  # Good for automation
                'description': 'Web automation, browser tasks, scraping'
            }
        }

        # Quality indicators (higher = need better quality)
        self.quality_indicators = {
            'high': ['critical', 'important', 'production', 'customer', 'client',
                    'presentation', 'report', 'analysis', 'research'],
            'low': ['test', 'quick', 'draft', 'rough', 'temporary', 'experiment']
        }

    def load_stats(self):
        """Load routing statistics."""
        if self.stats_file.exists():
            with open(self.stats_file) as f:
                self.stats = json.load(f)
        else:
            self.stats = {
                'total_routes': 0,
                'by_target': {'claude': 0, 'perplexity': 0, 'comet': 0},
                'feedback': {},  # User feedback on routing decisions
                'history': []
            }

    def save_stats(self):
        """Save routing statistics."""
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def analyze_quality_requirement(self, task: str) -> float:
        """
        Analyze quality requirement (0.0 to 1.0).

        Returns:
            Quality score (higher = need better quality)
        """
        task_lower = task.lower()

        # Check high quality indicators
        high_count = sum(1 for word in self.quality_indicators['high']
                        if word in task_lower)

        # Check low quality indicators
        low_count = sum(1 for word in self.quality_indicators['low']
                       if word in task_lower)

        # Base quality (start at medium)
        quality = 0.5

        # Adjust based on indicators
        quality += (high_count * 0.15)
        quality -= (low_count * 0.15)

        # Task length suggests complexity
        if len(task.split()) > 20:
            quality += 0.1

        # Question marks suggest need for deep answers
        if task.count('?') > 1:
            quality += 0.1

        return min(1.0, max(0.0, quality))

    def score_target(self, task: str, target: str) -> Tuple[float, List[str]]:
        """
        Score how well a target matches the task.

        Returns:
            (score, matching_reasons)
        """
        task_lower = task.lower()
        patterns = self.patterns[target]
        matches = []

        # Check keyword matches (word boundary to avoid partial matches)
        keyword_score = 0.0
        keyword_matches = 0
        for keyword in patterns['keywords']:
            # Use word boundary for better matching
            if re.search(r'\b' + re.escape(keyword) + r'\b', task_lower):
                keyword_score += 1.0
                keyword_matches += 1
                if len(matches) < 5:  # Limit reasons shown
                    matches.append(f"Keyword: '{keyword}'")

        # Normalize by number of matches (not total keywords)
        if keyword_matches > 0:
            keyword_score = min(1.0, keyword_matches / 3.0)  # Cap at 3 matches = 1.0

        # Check regex patterns
        pattern_score = 0.0
        pattern_matches = 0
        for pattern in patterns['patterns']:
            if re.search(pattern, task_lower):
                pattern_score += 1.0
                pattern_matches += 1
                if len(matches) < 5:
                    matches.append(f"Pattern match")

        # Normalize by number of matches
        if pattern_matches > 0:
            pattern_score = min(1.0, pattern_matches / 2.0)  # Cap at 2 matches = 1.0

        # Combined score (favor keyword matches)
        score = (keyword_score * 0.7) + (pattern_score * 0.3)

        # If no matches at all, give small base score to avoid 0
        if score == 0 and target == 'claude':
            # Claude as default fallback for complex tasks
            score = 0.1

        return score, matches

    def route(self, task: str) -> Tuple[str, float, str]:
        """
        Route a task to the best target.

        Args:
            task: Task description

        Returns:
            (target, confidence, reasoning)
        """
        # Analyze quality requirement
        quality_needed = self.analyze_quality_requirement(task)

        # Score each target
        scores = {}
        all_matches = {}

        for target in ['claude', 'perplexity', 'comet']:
            score, matches = self.score_target(task, target)

            # Adjust score based on quality threshold
            quality_threshold = self.patterns[target]['quality_threshold']
            if quality_needed >= 0.7 and target == 'claude':
                # Boost Claude for high-quality tasks
                score *= 1.5
            elif quality_needed >= quality_threshold:
                score *= 1.2  # Boost if quality requirement matches
            elif quality_needed < 0.3 and target == 'perplexity':
                # Boost Perplexity for simple tasks
                score *= 1.3
            else:
                score *= 0.95  # Slight penalty if quality mismatch

            scores[target] = score
            all_matches[target] = matches

        # Pick best target
        best_target = max(scores, key=scores.get)
        confidence = scores[best_target]

        # Build reasoning
        reasoning_parts = []

        # Add quality assessment
        if quality_needed >= 0.7:
            reasoning_parts.append(f"High quality required ({quality_needed:.2f})")
        elif quality_needed <= 0.3:
            reasoning_parts.append(f"Simple task ({quality_needed:.2f})")

        # Add matches
        if all_matches[best_target]:
            reasoning_parts.append(f"Matches: {', '.join(all_matches[best_target][:3])}")

        # Add target description
        reasoning_parts.append(self.patterns[best_target]['description'])

        reasoning = " | ".join(reasoning_parts)

        # Log routing decision
        self.stats['total_routes'] += 1
        self.stats['by_target'][best_target] += 1
        self.stats['history'].append({
            'timestamp': datetime.now().isoformat(),
            'task': task[:100],
            'target': best_target,
            'confidence': round(confidence, 3),
            'quality_needed': round(quality_needed, 3),
            'scores': {k: round(v, 3) for k, v in scores.items()}
        })

        # Keep only last 100 history entries
        if len(self.stats['history']) > 100:
            self.stats['history'] = self.stats['history'][-100:]

        self.save_stats()

        return best_target, confidence, reasoning

    def provide_feedback(self, task: str, target: str, was_good: bool, notes: str = ''):
        """
        Provide feedback on a routing decision.

        Args:
            task: Original task
            target: Where it was routed
            was_good: Whether the routing was correct
            notes: Optional feedback notes
        """
        feedback_key = f"{task[:50]}_{target}"
        self.stats['feedback'][feedback_key] = {
            'timestamp': datetime.now().isoformat(),
            'task': task,
            'target': target,
            'was_good': was_good,
            'notes': notes
        }
        self.save_stats()

    def get_stats(self) -> Dict:
        """Get routing statistics."""
        return {
            'total_routes': self.stats['total_routes'],
            'by_target': self.stats['by_target'],
            'distribution': {
                target: f"{(count/max(1, self.stats['total_routes']))*100:.1f}%"
                for target, count in self.stats['by_target'].items()
            },
            'recent_routes': self.stats['history'][-10:],
            'feedback_count': len(self.stats['feedback'])
        }

    def batch_route(self, tasks: List[str]) -> List[Dict]:
        """
        Route multiple tasks at once.

        Returns:
            List of routing results
        """
        results = []
        for task in tasks:
            target, confidence, reasoning = self.route(task)
            results.append({
                'task': task,
                'target': target,
                'confidence': confidence,
                'reasoning': reasoning
            })
        return results


# CLI interface
if __name__ == '__main__':
    import sys

    router = SmartTaskRouter()

    if '--stats' in sys.argv:
        # Show statistics
        stats = router.get_stats()
        print("\n" + "="*80)
        print("SMART TASK ROUTER - STATISTICS")
        print("="*80 + "\n")
        print(f"Total Routes: {stats['total_routes']}")
        print(f"\nDistribution:")
        for target, pct in stats['distribution'].items():
            count = stats['by_target'][target]
            print(f"  {target:12} {count:4} routes ({pct})")

        if stats['recent_routes']:
            print(f"\nRecent Routes:")
            for route in stats['recent_routes'][-5:]:
                print(f"  → {route['target']:10} ({route['confidence']:.2f}) {route['task'][:60]}")

        print("\n" + "="*80)

    elif '--test' in sys.argv:
        # Test routing with sample tasks
        test_tasks = [
            "Research the best hotels in Addis Ababa for families",
            "What is the capital of Ethiopia?",
            "Open Perplexity and search for flight prices",
            "Analyze the implications of the new tax policy",
            "Find the phone number for Ethiopian Airlines",
            "Create a Python function to calculate compound interest",
            "Click the submit button on the registration form",
            "Compare PostgreSQL vs MySQL for our use case",
            "What's the current weather in Addis Ababa?",
            "Design a scalable architecture for the payment system",
        ]

        print("\n" + "="*80)
        print("SMART TASK ROUTER - TEST ROUTING")
        print("="*80 + "\n")

        for task in test_tasks:
            target, confidence, reasoning = router.route(task)
            print(f"Task: {task}")
            print(f"→ Route to: {target.upper()} (confidence: {confidence:.2f})")
            print(f"  Reasoning: {reasoning}")
            print()

    elif len(sys.argv) > 1:
        # Route a specific task
        task = ' '.join(sys.argv[1:])
        target, confidence, reasoning = router.route(task)

        print(f"\nTask: {task}")
        print(f"→ Route to: {target.upper()}")
        print(f"  Confidence: {confidence:.2f}")
        print(f"  Reasoning: {reasoning}\n")

    else:
        print("""
Smart Task Router - Intelligent task routing

Usage:
    python3 smart_task_router.py "your task here"   # Route a task
    python3 smart_task_router.py --test              # Test with examples
    python3 smart_task_router.py --stats             # Show statistics

Examples:
    python3 smart_task_router.py "Research Ethiopia travel tips"
    → Route to: CLAUDE (Deep research task)

    python3 smart_task_router.py "What is the capital of Ethiopia?"
    → Route to: PERPLEXITY (Quick fact lookup)

    python3 smart_task_router.py "Open website and click submit"
    → Route to: COMET (Web automation task)
""")
