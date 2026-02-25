#!/usr/bin/env python3
"""
Route Ethiopia research tasks to appropriate AI systems via assigner_worker
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Add workers directory to path
workers_dir = Path(__file__).parent.parent
sys.path.insert(0, str(workers_dir))


class EthiopiaTaskRouter:
    def __init__(self):
        self.prompts_file = Path("ethiopia_prompts.json")
        self.results_dir = Path("ethiopia_results")
        self.results_dir.mkdir(exist_ok=True)

        # Route different topics to different providers
        # Rotate to distribute load
        self.provider_rotation = ['ollama', 'codex', 'comet', 'claude']
        self.current_provider = 0

        # Delay between tasks (3-5 minutes)
        self.min_delay = 180  # 3 minutes
        self.max_delay = 300  # 5 minutes

    def get_next_provider(self):
        """Get next provider in rotation."""
        provider = self.provider_rotation[self.current_provider % len(self.provider_rotation)]
        self.current_provider += 1
        return provider

    def submit_task(self, topic_name, prompt, provider='auto'):
        """Submit task to assigner_worker."""

        print(f"\n{'='*80}")
        print(f"SUBMITTING: {topic_name}")
        print(f"Provider: {provider}")
        print(f"{'='*80}\n")

        # Create task file
        task_data = {
            'topic': topic_name,
            'prompt': prompt,
            'provider': provider,
            'timestamp': datetime.now().isoformat(),
            'project': 'ethiopia-trip'
        }

        task_file = self.results_dir / f"task_{topic_name.replace(' ', '_')}.json"
        with open(task_file, 'w') as f:
            json.dump(task_data, f, indent=2)

        # Submit via assigner_worker
        try:
            assigner_path = workers_dir / 'assigner_worker.py'

            if provider == 'auto':
                # Auto-assign based on task
                cmd = [
                    'python3',
                    str(assigner_path),
                    '--auto',
                    prompt[:200]  # Shortened for command line
                ]
            else:
                # Target specific provider
                cmd = [
                    'python3',
                    str(assigner_path),
                    '--target',
                    provider,
                    prompt[:200]
                ]

            print(f"Running: {' '.join(cmd[:4])}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print(f"✓ Task submitted to {provider}")
                return True
            else:
                print(f"⚠️  Assigner warning: {result.stderr}")
                # Continue anyway - task may still be queued
                return True

        except Exception as e:
            print(f"Error submitting task: {e}")
            # Save prompt for manual processing
            manual_file = self.results_dir / f"manual_{topic_name.replace(' ', '_')}.txt"
            with open(manual_file, 'w') as f:
                f.write(f"TOPIC: {topic_name}\n\n")
                f.write(f"PROMPT:\n{prompt}\n")

            print(f"Saved to {manual_file} for manual processing")
            return False

    def route_all_topics(self):
        """Route all Ethiopia topics to appropriate systems."""

        if not self.prompts_file.exists():
            print("Error: ethiopia_prompts.json not found")
            return

        with open(self.prompts_file) as f:
            data = json.load(f)

        topics = data['tab_groups']

        print("="*80)
        print("ETHIOPIA TASK ROUTING")
        print("="*80)
        print()
        print(f"Total topics: {len(topics)}")
        print(f"Provider rotation: {', '.join(self.provider_rotation)}")
        print(f"Rate limit: {self.min_delay//60}-{self.max_delay//60} minutes between tasks")
        print()
        print("Estimated completion: {:.1f} hours".format(
            (len(topics) * (self.min_delay + self.max_delay) / 2) / 3600
        ))
        print()

        submitted = 0

        for i, topic in enumerate(topics, 1):
            topic_name = topic['name']
            prompt = topic['prompt']

            # Get provider for this topic
            provider = self.get_next_provider()

            # Submit task
            success = self.submit_task(topic_name, prompt, provider)

            if success:
                submitted += 1

            # Rate limiting delay (except for last one)
            if i < len(topics):
                import random
                delay = random.randint(self.min_delay, self.max_delay)

                print(f"\n⏱️  Rate limiting: {delay//60}m {delay%60}s")
                print(f"   Next: [{i+1}/{len(topics)}] {topics[i]['name']}\n")

                time.sleep(delay)

        print("\n" + "="*80)
        print("TASK ROUTING COMPLETE")
        print("="*80)
        print()
        print(f"Submitted: {submitted}/{len(topics)}")
        print(f"Results will be collected in: {self.results_dir}/")
        print()
        print("Tasks are now being processed by AI systems.")
        print("Monitor progress via the task assignment system.")
        print()


def main():
    router = EthiopiaTaskRouter()
    router.route_all_topics()


if __name__ == "__main__":
    main()
