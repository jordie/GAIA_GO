#!/usr/bin/env python3
"""
Perplexity Result Scraper - Extract actual content from Perplexity searches

Extracts:
- Main answer text
- Source citations
- Related questions
- Search metadata

Methods:
1. AppleScript (Comet browser) - Get page content
2. Playwright (headless) - Full automation
3. HTML parsing - Extract structured data

Usage:
    scraper = PerplexityScraper()
    result = scraper.scrape_url("https://www.perplexity.ai/search/xyz")
"""
import subprocess
import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


class PerplexityScraper:
    """Scrape Perplexity search results."""

    def __init__(self):
        self.results_dir = Path('data/perplexity_results')
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def scrape_via_applescript(self, url: str) -> Optional[str]:
        """
        Get page content via AppleScript (Comet browser).

        Returns:
            Page HTML content or None
        """
        script = f'''
        tell application "Comet"
            set currentURL to URL of active tab of window 1
            if currentURL contains "{url}" then
                tell application "System Events"
                    keystroke "s" using {{command down}}
                end tell
                delay 1

                -- Get page source via developer console
                do JavaScript "document.documentElement.outerHTML" in active tab of window 1
            else
                return "URL mismatch"
            end if
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            print(f"AppleScript error: {e}")
            return None

    def extract_answer_from_html(self, html: str) -> Dict:
        """
        Extract structured data from Perplexity HTML.

        Returns:
            Extracted data (answer, sources, related)
        """
        data = {
            'answer': '',
            'sources': [],
            'related_questions': [],
            'timestamp': datetime.now().isoformat()
        }

        # Extract main answer
        # Perplexity typically uses specific CSS classes or data attributes
        # This is a simplified extraction - real implementation needs DOM parsing

        # Look for answer text patterns
        answer_patterns = [
            r'<div[^>]*class="[^"]*answer[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*data-testid="answer"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
        ]

        for pattern in answer_patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                # Strip HTML tags
                answer_text = re.sub(r'<[^>]+>', ' ', match.group(1))
                answer_text = re.sub(r'\s+', ' ', answer_text).strip()
                if answer_text:
                    data['answer'] = answer_text[:2000]  # Limit length
                    break

        # Extract sources (links)
        source_pattern = r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]+)</a>'
        sources = re.findall(source_pattern, html)
        data['sources'] = [
            {'url': url, 'title': title.strip()}
            for url, title in sources[:10]  # Max 10 sources
            if 'perplexity.ai' not in url  # Exclude self-references
        ]

        # Extract related questions
        question_pattern = r'<div[^>]*class="[^"]*related[^"]*"[^>]*>([^<]+)</div>'
        questions = re.findall(question_pattern, html, re.IGNORECASE)
        data['related_questions'] = [q.strip() for q in questions[:5]]

        return data

    def scrape_url(self, url: str, method: str = 'simple') -> Dict:
        """
        Scrape Perplexity result from URL.

        Args:
            url: Perplexity search URL
            method: 'simple' (metadata only), 'applescript', 'playwright'

        Returns:
            Scraped result data
        """
        result = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'success': False
        }

        if method == 'simple':
            # Extract query from URL
            match = re.search(r'/search/([^/?]+)', url)
            if match:
                search_id = match.group(1)
                result['search_id'] = search_id
                result['success'] = True

            # Extract query parameter if present
            match = re.search(r'[?&]q=([^&]+)', url)
            if match:
                import urllib.parse
                query = urllib.parse.unquote(match.group(1))
                result['query'] = query

            result['note'] = 'Simple extraction - URL only. Use applescript/playwright for content.'

        elif method == 'applescript':
            html = self.scrape_via_applescript(url)
            if html:
                extracted = self.extract_answer_from_html(html)
                result.update(extracted)
                result['success'] = bool(extracted['answer'])
            else:
                result['error'] = 'Failed to get HTML via AppleScript'

        elif method == 'playwright':
            # Future: Implement Playwright scraping
            result['error'] = 'Playwright not implemented yet'

        return result

    def scrape_and_save(self, url: str, task_id: str = None, method: str = 'simple') -> str:
        """
        Scrape result and save to file.

        Args:
            url: Perplexity search URL
            task_id: Optional task identifier
            method: Scraping method

        Returns:
            Path to saved result file
        """
        result = self.scrape_url(url, method=method)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if task_id:
            filename = f"{task_id}_{timestamp}.json"
        else:
            filename = f"result_{timestamp}.json"

        result_file = self.results_dir / filename
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)

        return str(result_file)

    def get_recent_results(self, limit: int = 10) -> list:
        """Get recent scraped results."""
        result_files = sorted(self.results_dir.glob('*.json'), reverse=True)[:limit]

        results = []
        for result_file in result_files:
            with open(result_file) as f:
                results.append(json.load(f))

        return results

    def search_results(self, query: str) -> list:
        """Search through scraped results."""
        all_results = []
        for result_file in self.results_dir.glob('*.json'):
            with open(result_file) as f:
                data = json.load(f)
                # Search in query and answer
                if query.lower() in data.get('query', '').lower():
                    all_results.append(data)
                elif query.lower() in data.get('answer', '').lower():
                    all_results.append(data)

        return all_results

    def get_stats(self) -> Dict:
        """Get scraping statistics."""
        result_files = list(self.results_dir.glob('*.json'))

        stats = {
            'total_results': len(result_files),
            'by_method': {},
            'successful': 0,
            'failed': 0,
            'with_answer': 0,
            'with_sources': 0
        }

        for result_file in result_files:
            with open(result_file) as f:
                data = json.load(f)

                # Count by method
                method = data.get('method', 'unknown')
                stats['by_method'][method] = stats['by_method'].get(method, 0) + 1

                # Count success/failure
                if data.get('success'):
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1

                # Count with answer
                if data.get('answer'):
                    stats['with_answer'] += 1

                # Count with sources
                if data.get('sources'):
                    stats['with_sources'] += 1

        return stats


# CLI interface
if __name__ == '__main__':
    import sys

    scraper = PerplexityScraper()

    if '--stats' in sys.argv:
        # Show statistics
        stats = scraper.get_stats()
        print("\n" + "="*80)
        print("PERPLEXITY SCRAPER STATISTICS")
        print("="*80 + "\n")
        print(f"Total Results: {stats['total_results']}")
        print(f"Successful: {stats['successful']}")
        print(f"Failed: {stats['failed']}")
        print(f"With Answer: {stats['with_answer']}")
        print(f"With Sources: {stats['with_sources']}")

        if stats['by_method']:
            print(f"\nBy Method:")
            for method, count in stats['by_method'].items():
                print(f"  {method:15} {count:4}")

        print("\n" + "="*80)

    elif '--recent' in sys.argv:
        # Show recent results
        results = scraper.get_recent_results(limit=10)
        print("\n" + "="*80)
        print("RECENT SCRAPED RESULTS")
        print("="*80 + "\n")

        for result in results:
            print(f"URL: {result['url']}")
            print(f"Timestamp: {result['timestamp']}")
            print(f"Method: {result['method']}")
            print(f"Success: {result['success']}")

            if result.get('query'):
                print(f"Query: {result['query']}")

            if result.get('answer'):
                print(f"Answer: {result['answer'][:200]}...")

            if result.get('sources'):
                print(f"Sources: {len(result['sources'])}")

            print()

    elif '--search' in sys.argv:
        # Search results
        query = ' '.join([arg for arg in sys.argv if arg != '--search'])
        results = scraper.search_results(query)

        print(f"\nFound {len(results)} results for: {query}\n")
        for result in results:
            print(f"URL: {result['url']}")
            if result.get('query'):
                print(f"Query: {result['query']}")
            if result.get('answer'):
                print(f"Answer: {result['answer'][:150]}...")
            print()

    elif len(sys.argv) > 1:
        # Scrape a URL
        url = sys.argv[1]
        method = sys.argv[2] if len(sys.argv) > 2 else 'simple'

        print(f"\nScraping: {url}")
        print(f"Method: {method}\n")

        result_file = scraper.scrape_and_save(url, method=method)
        result = scraper.scrape_url(url, method=method)

        print(f"Success: {result['success']}")
        if result.get('query'):
            print(f"Query: {result['query']}")
        if result.get('answer'):
            print(f"Answer: {result['answer'][:300]}...")
        if result.get('sources'):
            print(f"Sources: {len(result['sources'])}")

        print(f"\nSaved to: {result_file}\n")

    else:
        print("""
Perplexity Result Scraper - Extract search content

Usage:
    python3 perplexity_scraper.py <url> [method]     # Scrape URL
    python3 perplexity_scraper.py --stats             # Show statistics
    python3 perplexity_scraper.py --recent            # Show recent results
    python3 perplexity_scraper.py --search <query>    # Search results

Methods:
    simple      - Extract metadata from URL (fast, no content)
    applescript - Get content via Comet browser (requires active tab)
    playwright  - Full headless scraping (not implemented yet)

Examples:
    # Simple extraction (default)
    python3 perplexity_scraper.py "https://www.perplexity.ai/search/xyz"

    # Extract content via AppleScript
    python3 perplexity_scraper.py "https://www.perplexity.ai/search/xyz" applescript

    # View statistics
    python3 perplexity_scraper.py --stats

    # Search scraped results
    python3 perplexity_scraper.py --search "Ethiopia"
""")
