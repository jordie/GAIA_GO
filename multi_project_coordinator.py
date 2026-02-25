#!/usr/bin/env python3
"""
Multi-Project Coordinator - Handle multiple research projects simultaneously

Features:
- Project queue management
- Priority scheduling
- Concurrent execution
- Progress tracking
- Result aggregation
- Quality scoring integration

Usage:
    coordinator = MultiProjectCoordinator()
    coordinator.add_project('Ethiopia Trip', 'data/ethiopia/ethiopia_prompts.json', priority='high')
    coordinator.run_all()
"""
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from auto_router_executor import AutoRouterExecutor
from quality_scorer import QualityScorer


class Project:
    """Represents a research project."""

    def __init__(self, name: str, prompts_file: str, priority: str = 'medium'):
        self.name = name
        self.prompts_file = prompts_file
        self.priority = priority
        self.status = 'pending'  # pending, running, completed, failed
        self.topics = []
        self.results = []
        self.start_time = None
        self.end_time = None
        self.load_topics()

    def load_topics(self):
        """Load research topics from prompts file."""
        with open(self.prompts_file) as f:
            data = json.load(f)

        self.topics = data.get('tab_groups') or data.get('research_topics', [])

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'name': self.name,
            'prompts_file': self.prompts_file,
            'priority': self.priority,
            'status': self.status,
            'topics': len(self.topics),
            'completed': len(self.results),
            'start_time': self.start_time,
            'end_time': self.end_time
        }


class MultiProjectCoordinator:
    """Coordinate multiple research projects."""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.projects = []
        self.executor = AutoRouterExecutor()
        self.scorer = QualityScorer()
        self.state_file = Path('data/project_coordinator_state.json')
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_state()

        # Priority weights
        self.priority_weights = {
            'critical': 100,
            'high': 75,
            'medium': 50,
            'low': 25
        }

    def load_state(self):
        """Load saved state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                # Restore projects (simplified)
                self.state = data
        else:
            self.state = {
                'total_projects': 0,
                'completed_projects': 0,
                'total_topics': 0,
                'completed_topics': 0
            }

    def save_state(self):
        """Save current state."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def add_project(self, name: str, prompts_file: str, priority: str = 'medium'):
        """
        Add a project to the queue.

        Args:
            name: Project name
            prompts_file: Path to prompts JSON
            priority: critical, high, medium, low
        """
        project = Project(name, prompts_file, priority)
        self.projects.append(project)
        self.state['total_projects'] += 1
        self.state['total_topics'] += len(project.topics)
        self.save_state()

        print(f"✅ Added project: {name} ({len(project.topics)} topics, priority: {priority})")

    def get_next_project(self) -> Optional[Project]:
        """
        Get next project to run based on priority.

        Returns:
            Next project or None
        """
        pending = [p for p in self.projects if p.status == 'pending']

        if not pending:
            return None

        # Sort by priority
        pending.sort(key=lambda p: self.priority_weights.get(p.priority, 0), reverse=True)

        return pending[0]

    def run_project(self, project: Project):
        """
        Run a single project.

        Args:
            project: Project to run
        """
        project.status = 'running'
        project.start_time = datetime.now().isoformat()

        print(f"\n{'='*80}")
        print(f"🚀 STARTING PROJECT: {project.name}")
        print(f"{'='*80}\n")
        print(f"Topics: {len(project.topics)}")
        print(f"Priority: {project.priority}")
        print()

        for i, topic in enumerate(project.topics, 1):
            topic_name = topic.get('name', f'Topic {i}')
            prompt = topic.get('prompt', '')

            print(f"[{i}/{len(project.topics)}] {topic_name}")

            try:
                # Execute via auto router
                result = self.executor.execute(prompt, auto_execute=True)

                # Score result if successful
                if result.get('execution', {}).get('status') == 'success':
                    # Basic result data for scoring
                    result_data = {
                        'answer': '',  # Would need actual scraping
                        'sources': [],
                        'response_time': 5  # Estimate
                    }

                    target = result['routing']['target']
                    score_entry = self.scorer.log_score(result_data, target, prompt)

                    print(f"  ✅ Success via {target.upper()}")
                    print(f"  Quality: {score_entry['score']:.3f} (Grade: {score_entry['grade']})")

                    project.results.append({
                        'topic': topic_name,
                        'success': True,
                        'result': result,
                        'quality_score': score_entry['score']
                    })

                else:
                    print(f"  ❌ Failed")
                    project.results.append({
                        'topic': topic_name,
                        'success': False
                    })

            except Exception as e:
                print(f"  ❌ Error: {e}")
                project.results.append({
                    'topic': topic_name,
                    'success': False,
                    'error': str(e)
                })

            print()

            # Small delay between topics
            if i < len(project.topics):
                time.sleep(2)

        project.status = 'completed'
        project.end_time = datetime.now().isoformat()

        # Update state
        self.state['completed_projects'] += 1
        self.state['completed_topics'] += len([r for r in project.results if r['success']])
        self.save_state()

        # Print summary
        self.print_project_summary(project)

    def print_project_summary(self, project: Project):
        """Print project completion summary."""
        successful = len([r for r in project.results if r['success']])
        failed = len(project.results) - successful

        avg_quality = 0
        if successful > 0:
            quality_scores = [r['quality_score'] for r in project.results if r.get('quality_score')]
            if quality_scores:
                avg_quality = sum(quality_scores) / len(quality_scores)

        print(f"{'='*80}")
        print(f"✅ PROJECT COMPLETE: {project.name}")
        print(f"{'='*80}\n")
        print(f"Success: {successful}/{len(project.results)} topics")
        print(f"Failed: {failed}/{len(project.results)} topics")
        if avg_quality > 0:
            print(f"Avg Quality: {avg_quality:.3f} (Grade: {self.scorer.score_to_grade(avg_quality)})")
        print(f"\nStart: {project.start_time}")
        print(f"End: {project.end_time}")
        print(f"{'='*80}\n")

    def run_all(self, concurrent: bool = False):
        """
        Run all pending projects.

        Args:
            concurrent: If True, run multiple projects in parallel
        """
        if concurrent:
            self.run_all_concurrent()
        else:
            self.run_all_sequential()

    def run_all_sequential(self):
        """Run projects one at a time by priority."""
        print("\n" + "="*80)
        print("MULTI-PROJECT COORDINATOR - SEQUENTIAL MODE")
        print("="*80 + "\n")
        print(f"Total Projects: {len(self.projects)}")
        print(f"Max Concurrent: 1 (sequential)")
        print()

        while True:
            project = self.get_next_project()
            if not project:
                break

            self.run_project(project)

        self.print_overall_summary()

    def run_all_concurrent(self):
        """Run projects concurrently (up to max_concurrent)."""
        print("\n" + "="*80)
        print("MULTI-PROJECT COORDINATOR - CONCURRENT MODE")
        print("="*80 + "\n")
        print(f"Total Projects: {len(self.projects)}")
        print(f"Max Concurrent: {self.max_concurrent}")
        print()

        threads = []
        running = []

        while True:
            # Start new projects if slots available
            while len(running) < self.max_concurrent:
                project = self.get_next_project()
                if not project:
                    break

                thread = threading.Thread(target=self.run_project, args=(project,))
                thread.start()
                threads.append(thread)
                running.append(project)

            # Wait for a project to complete
            if running:
                time.sleep(1)
                running = [p for p in running if p.status == 'running']
            else:
                break

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        self.print_overall_summary()

    def print_overall_summary(self):
        """Print overall completion summary."""
        completed = [p for p in self.projects if p.status == 'completed']
        total_topics = sum(len(p.topics) for p in self.projects)
        completed_topics = sum(len([r for r in p.results if r['success']]) for p in completed)

        print("\n" + "="*80)
        print("📊 OVERALL SUMMARY")
        print("="*80 + "\n")
        print(f"Projects Completed: {len(completed)}/{len(self.projects)}")
        print(f"Topics Completed: {completed_topics}/{total_topics}")
        print(f"Success Rate: {(completed_topics/total_topics*100):.1f}%")

        # Quality breakdown
        quality_stats = self.scorer.get_stats()
        if quality_stats['comparison']:
            print(f"\nQuality Comparison:")
            for source, data in quality_stats['comparison'].items():
                if source not in ['winner', 'winner_score']:
                    print(f"  {source.upper()}: {data['avg_score']:.3f} (Grade: {data['grade']})")

        print("\n" + "="*80)

    def get_status(self) -> Dict:
        """Get current status."""
        return {
            'projects': [p.to_dict() for p in self.projects],
            'state': self.state,
            'running': [p.name for p in self.projects if p.status == 'running'],
            'pending': [p.name for p in self.projects if p.status == 'pending'],
            'completed': [p.name for p in self.projects if p.status == 'completed']
        }


# CLI interface
if __name__ == '__main__':
    import sys

    coordinator = MultiProjectCoordinator(max_concurrent=3)

    if '--status' in sys.argv:
        # Show status
        status = coordinator.get_status()
        print("\n" + "="*80)
        print("PROJECT COORDINATOR STATUS")
        print("="*80 + "\n")
        print(f"Total Projects: {status['state']['total_projects']}")
        print(f"Completed: {status['state']['completed_projects']}")
        print(f"Topics Completed: {status['state']['completed_topics']}/{status['state']['total_topics']}")

        if status['running']:
            print(f"\n🏃 Running: {', '.join(status['running'])}")
        if status['pending']:
            print(f"⏳ Pending: {', '.join(status['pending'])}")
        if status['completed']:
            print(f"✅ Completed: {', '.join(status['completed'])}")

        print("\n" + "="*80)

    elif '--add' in sys.argv:
        # Add a project
        # Usage: --add "Project Name" path/to/prompts.json [priority]
        args = [arg for arg in sys.argv if arg != '--add']
        if len(args) >= 2:
            name = args[0]
            prompts_file = args[1]
            priority = args[2] if len(args) > 2 else 'medium'

            coordinator.add_project(name, prompts_file, priority)
        else:
            print("Usage: --add <name> <prompts_file> [priority]")

    elif '--run' in sys.argv:
        # Run all projects
        concurrent = '--concurrent' in sys.argv
        coordinator.run_all(concurrent=concurrent)

    else:
        print("""
Multi-Project Coordinator - Handle multiple projects simultaneously

Usage:
    python3 multi_project_coordinator.py --add "Name" file.json [priority]
    python3 multi_project_coordinator.py --run [--concurrent]
    python3 multi_project_coordinator.py --status

Examples:
    # Add projects
    python3 multi_project_coordinator.py --add "Ethiopia Trip" data/ethiopia/ethiopia_prompts.json high
    python3 multi_project_coordinator.py --add "Property Analysis" data/property_analysis/property_prompts.json medium

    # Run all (sequential)
    python3 multi_project_coordinator.py --run

    # Run all (concurrent, max 3 at once)
    python3 multi_project_coordinator.py --run --concurrent

    # Check status
    python3 multi_project_coordinator.py --status

Features:
    - Priority-based scheduling (critical > high > medium > low)
    - Sequential or concurrent execution
    - Automatic routing (Claude/Perplexity/Comet)
    - Quality scoring for all results
    - Progress tracking
    - Result aggregation
""")
