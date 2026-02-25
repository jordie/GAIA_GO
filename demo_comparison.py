#!/usr/bin/env python3
"""
Demo: Result Comparison System

Shows how the comparison system scores and compares results from different AI sources.
"""

from quality_scorer import QualityScorer

def demo_comparison():
    """Demonstrate the comparison system with sample results."""

    scorer = QualityScorer()

    # Sample query
    query = "What are the key benefits of using Python for machine learning?"

    print("\n" + "="*80)
    print(f"DEMO: Comparing AI Sources")
    print("="*80)
    print(f"\nQuery: {query}\n")

    # Sample responses from different sources
    claude_response = {
        'source': 'claude',
        'query': query,
        'answer': '''Python offers several key benefits for machine learning:

1. **Rich Ecosystem**: Libraries like NumPy, pandas, scikit-learn, TensorFlow, and PyTorch provide comprehensive ML tools
2. **Easy Syntax**: Clean, readable code makes it accessible for beginners and efficient for experts
3. **Data Handling**: Excellent tools for data preprocessing, cleaning, and visualization
4. **Community Support**: Large community means abundant resources, tutorials, and pre-trained models
5. **Integration**: Easy integration with other languages and tools, plus deployment flexibility

These factors make Python the de facto standard for ML development.''',
        'sources': [],
        'response_time': 3.2,
        'word_count': 85
    }

    perplexity_response = {
        'source': 'perplexity',
        'query': query,
        'answer': '''Python's advantages for machine learning include:

- Extensive libraries (scikit-learn, TensorFlow, PyTorch, Keras)
- Simple syntax and rapid prototyping
- Strong data science ecosystem (NumPy, pandas, Matplotlib)
- Active community and resources
- Cross-platform compatibility

Sources cited: official documentation and industry standards.''',
        'sources': [
            {'url': 'https://tensorflow.org', 'title': 'TensorFlow Docs'},
            {'url': 'https://scikit-learn.org', 'title': 'Scikit-learn'},
            {'url': 'https://pytorch.org', 'title': 'PyTorch'},
        ],
        'response_time': 2.1,
        'word_count': 48
    }

    comet_response = {
        'source': 'comet',
        'query': query,
        'answer': '''Python is popular for machine learning because:

1. Lots of ML libraries available
2. Easy to learn and use
3. Good for working with data
4. Many people use it so lots of help available

It's the most common language for AI and ML projects.''',
        'sources': [],
        'response_time': 4.5,
        'word_count': 42
    }

    # Score each response
    print("📊 SCORING RESULTS:")
    print("-" * 80)

    results = {}

    for response in [claude_response, perplexity_response, comet_response]:
        source = response['source']
        score = scorer.score_result(response)
        results[source] = score

        print(f"\n{source.upper()}:")
        print(f"  Total Score: {score['total']:.3f} ({score['grade']})")
        print(f"  Breakdown:")
        for dim, val in score['breakdown'].items():
            weight = scorer.weights[dim]
            print(f"    - {dim.capitalize():15s}: {val:.3f} (weight: {weight:.0%})")

    # Determine winner
    winner = max(results.items(), key=lambda x: x[1]['total'])

    print("\n" + "="*80)
    print(f"🏆 WINNER: {winner[0].upper()}")
    print(f"   Score: {winner[1]['total']:.3f} ({winner[1]['grade']})")
    print("="*80)

    # Show detailed comparison
    print("\n📈 DETAILED COMPARISON:")
    print("-" * 80)
    print(f"{'Dimension':<15s} {'Claude':<10s} {'Perplexity':<12s} {'Comet':<10s}")
    print("-" * 80)

    for dim in ['completeness', 'sources', 'speed', 'depth', 'accuracy']:
        values = [results[source]['breakdown'][dim] for source in ['claude', 'perplexity', 'comet']]
        print(f"{dim.capitalize():<15s} {values[0]:<10.3f} {values[1]:<12.3f} {values[2]:<10.3f}")

    print("-" * 80)
    totals = [results[source]['total'] for source in ['claude', 'perplexity', 'comet']]
    grades = [results[source]['grade'] for source in ['claude', 'perplexity', 'comet']]
    print(f"{'TOTAL':<15s} {totals[0]:<10.3f} {totals[1]:<12.3f} {totals[2]:<10.3f}")
    print(f"{'GRADE':<15s} {grades[0]:<10s} {grades[1]:<12s} {grades[2]:<10s}")

    # Analysis
    print("\n💡 ANALYSIS:")
    print("-" * 80)

    if winner[0] == 'claude':
        print("Claude won due to:")
        print("  ✓ Most complete answer (detailed explanations)")
        print("  ✓ Better structure and formatting")
        print("  ✓ More comprehensive coverage")
    elif winner[0] == 'perplexity':
        print("Perplexity won due to:")
        print("  ✓ Cited external sources (higher source score)")
        print("  ✓ Fastest response time")
        print("  ✓ Good balance of detail and conciseness")
    else:
        print("Comet won due to:")
        print("  ✓ Simplicity and clarity")
        print("  ✓ Easy to understand")

    # Show weaknesses
    print("\n⚠️  WEAKNESSES:")
    for source, score in results.items():
        weak_dims = [dim for dim, val in score['breakdown'].items() if val < 0.3]
        if weak_dims:
            print(f"  {source.capitalize()}: {', '.join(weak_dims)}")

    print("\n" + "="*80)
    print("Demo complete! This shows how the comparison system works.")
    print("="*80 + "\n")


if __name__ == "__main__":
    demo_comparison()
