package main

import (
	"fmt"
	"strings"

	"github.com/architect/go_wrapper/stream"
)

func main() {
	extractor := stream.NewExtractor()

	codeBlockSample := `Here's a Python function:

` + "```python" + `
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
` + "```" + `

Done!`

	lines := strings.Split(codeBlockSample, "\n")
	fmt.Printf("Processing %d lines:\n", len(lines))

	for i, line := range lines {
		fmt.Printf("Line %d: %q\n", i+1, line)
		matches := extractor.Extract(line)
		if len(matches) > 0 {
			fmt.Printf("  Matches: %d\n", len(matches))
			for _, m := range matches {
				fmt.Printf("    - [%s] %s: %s\n", m.Type, m.Pattern, m.Value)
			}
		}
	}

	fmt.Println("\nFinal stats:")
	stats := extractor.GetStats()
	for k, v := range stats {
		fmt.Printf("  %s: %v\n", k, v)
	}

	fmt.Println("\nAll code block matches:")
	codeBlocks := extractor.GetMatchesByType(stream.PatternTypeCodeBlock)
	fmt.Printf("Found %d code block matches\n", len(codeBlocks))
	for _, m := range codeBlocks {
		fmt.Printf("  - %s: %s\n", m.Pattern, m.Value)
		if m.Metadata != nil {
			for k, v := range m.Metadata {
				fmt.Printf("    %s: %v\n", k, v)
			}
		}
	}
}
