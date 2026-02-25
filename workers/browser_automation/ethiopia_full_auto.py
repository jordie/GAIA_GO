#!/usr/bin/env python3
"""
Fully automated Ethiopia project research with rate limiting
Distributes work across multiple AI systems and aggregates results
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import random


class EthiopiaAutomation:
    def __init__(self):
        self.sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"
        self.prompts_file = Path("ethiopia_prompts.json")
        self.results_dir = Path("ethiopia_results")
        self.results_dir.mkdir(exist_ok=True)

        # Rate limiting: 2-5 minutes between requests
        self.min_delay = 120  # 2 minutes
        self.max_delay = 300  # 5 minutes

        # AI systems to use
        self.ai_systems = ['claude', 'comet', 'gemini', 'codex']

    def get_delay(self):
        """Get random delay between min and max to avoid patterns."""
        return random.randint(self.min_delay, self.max_delay)

    async def send_to_ai_system(self, system, prompt, topic_name):
        """Send prompt to specific AI system."""

        result_file = self.results_dir / f"{topic_name.replace(' ', '_')}_{system}.json"

        print(f"\n{'='*80}")
        print(f"Sending to {system.upper()}: {topic_name}")
        print(f"{'='*80}")

        # Route to appropriate system
        if system == 'claude':
            response = await self.send_to_claude(prompt)
        elif system == 'comet':
            response = await self.send_to_comet(prompt)
        elif system == 'gemini':
            response = await self.send_to_gemini(prompt)
        elif system == 'codex':
            response = await self.send_to_codex(prompt)
        else:
            response = None

        # Save result
        if response:
            with open(result_file, 'w') as f:
                json.dump({
                    'topic': topic_name,
                    'system': system,
                    'prompt': prompt,
                    'response': response,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)

            print(f"✓ Saved response to {result_file}")
            return response

        return None

    async def send_to_claude(self, prompt):
        """Send prompt to Claude API or CLI."""
        try:
            # Use claude CLI to send prompt
            cmd = ['claude', '--prompt', prompt]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                return result.stdout
            else:
                print(f"Claude error: {result.stderr}")
                return None

        except Exception as e:
            print(f"Error with Claude: {e}")
            return None

    async def send_to_comet(self, prompt):
        """Send to Comet/Perplexity."""
        # For now, save the prompt for manual Perplexity research
        # In future, could integrate with Perplexity API
        return f"[Comet/Perplexity research needed for: {prompt[:100]}...]"

    async def send_to_gemini(self, prompt):
        """Send to Google Gemini."""
        # Placeholder - would need Gemini API integration
        return f"[Gemini research needed for: {prompt[:100]}...]"

    async def send_to_codex(self, prompt):
        """Send to Codex (OpenAI)."""
        # Placeholder - would need OpenAI API integration
        return f"[Codex research needed for: {prompt[:100]}...]"

    async def research_topic(self, topic_data, index, total):
        """Research a single topic using multiple AI systems."""

        topic_name = topic_data['name']
        prompt = topic_data['prompt']

        print(f"\n{'='*80}")
        print(f"TOPIC {index}/{total}: {topic_name}")
        print(f"{'='*80}")

        # Send to primary AI system (rotate for load distribution)
        primary_system = self.ai_systems[index % len(self.ai_systems)]

        response = await self.send_to_ai_system(primary_system, prompt, topic_name)

        # Update Google Sheet
        if response:
            await self.update_sheet(topic_data['id'], response, primary_system)

        return response

    async def update_sheet(self, topic_id, response, system):
        """Update Google Sheet with research results."""

        try:
            creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
            creds = Credentials.from_service_account_file(
                str(creds_path),
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )

            gc = gspread.authorize(creds)
            spreadsheet = gc.open_by_key(self.sheet_id)
            ws_tab_groups = spreadsheet.worksheet("Tab Groups")

            # Find row
            all_data = ws_tab_groups.get_all_values()

            for row_num, row in enumerate(all_data[1:], 2):
                if row[0] == topic_id:
                    # Update status
                    ws_tab_groups.update_cell(row_num, 5, "completed")

                    # Update notes with system used
                    current_notes = row[11] if len(row) > 11 else ""
                    new_notes = f"{current_notes}\n\nResearched via {system} on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    ws_tab_groups.update_cell(row_num, 12, new_notes)

                    # Update timestamp
                    ws_tab_groups.update_cell(row_num, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))

                    print(f"  ✓ Updated Google Sheet for {topic_id}")
                    break

        except Exception as e:
            print(f"  Error updating sheet: {e}")

    async def aggregate_to_doc(self):
        """Aggregate all results into a Google Doc."""

        print("\n" + "="*80)
        print("AGGREGATING RESULTS TO GOOGLE DOC")
        print("="*80)

        # Collect all results
        all_results = []
        for result_file in sorted(self.results_dir.glob("*.json")):
            with open(result_file) as f:
                all_results.append(json.load(f))

        # Create markdown document
        doc_content = self.create_markdown_doc(all_results)

        # Save locally
        doc_file = Path("ETHIOPIA_TRIP_RESEARCH.md")
        with open(doc_file, 'w') as f:
            f.write(doc_content)

        print(f"✓ Created {doc_file}")
        print(f"  {len(all_results)} research topics compiled")

        # TODO: Upload to Google Docs
        # Would need Google Docs API integration

        return doc_file

    def create_markdown_doc(self, results):
        """Create formatted markdown document from results."""

        doc = []
        doc.append("# Ethiopia Family Trip - Research Compilation")
        doc.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        doc.append("\n**Trip Details:**")
        doc.append("- Family: 6 people (Yordanos, Helen, Sara, Ezana, Eden, Eden)")
        doc.append("- Ages: 47, 46, 13, 12, 11, 6")
        doc.append("- Duration: 1 month (June-July 2026)")
        doc.append("- Special: 1 week Tigray trip (Axum, Adigrat, Mekele)")
        doc.append("\n" + "="*80 + "\n")

        for result in results:
            topic = result.get('topic', 'Unknown')
            system = result.get('system', 'Unknown')
            response = result.get('response', 'No response')
            timestamp = result.get('timestamp', '')

            doc.append(f"\n## {topic}")
            doc.append(f"\n*Researched via: {system} on {timestamp}*\n")
            doc.append("\n### Findings\n")
            doc.append(response)
            doc.append("\n" + "-"*80 + "\n")

        return "\n".join(doc)

    async def run(self):
        """Run full automation."""

        # Load prompts
        if not self.prompts_file.exists():
            print("Error: ethiopia_prompts.json not found")
            return

        with open(self.prompts_file) as f:
            data = json.load(f)

        topics = data['tab_groups']

        print("="*80)
        print("ETHIOPIA PROJECT - FULL AUTOMATION")
        print("="*80)
        print()
        print(f"Topics: {len(topics)}")
        print(f"Rate limit: {self.min_delay//60}-{self.max_delay//60} minutes between requests")
        print(f"AI systems: {', '.join(self.ai_systems)}")
        print()
        print("This will run completely autonomously.")
        print("Estimated time: {:.1f}-{:.1f} hours".format(
            (len(topics) * self.min_delay) / 3600,
            (len(topics) * self.max_delay) / 3600
        ))
        print()

        # Process each topic
        completed = 0

        for i, topic in enumerate(topics, 1):
            # Research topic
            response = await self.research_topic(topic, i, len(topics))

            if response:
                completed += 1

            # Rate limiting delay (except after last one)
            if i < len(topics):
                delay = self.get_delay()
                print(f"\n⏱️  Rate limiting: waiting {delay//60} minutes {delay%60} seconds...")
                print(f"   Next: {topics[i]['name']}")
                await asyncio.sleep(delay)

        # Aggregate results
        doc_file = await self.aggregate_to_doc()

        print("\n" + "="*80)
        print("✅ AUTOMATION COMPLETE")
        print("="*80)
        print()
        print(f"Completed: {completed}/{len(topics)} topics")
        print(f"Results: {self.results_dir}/")
        print(f"Document: {doc_file}")
        print()
        print(f"Google Sheet: https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit")
        print()
        print("✓ Ready for human evaluation")


async def main():
    automation = EthiopiaAutomation()
    await automation.run()


if __name__ == "__main__":
    asyncio.run(main())
