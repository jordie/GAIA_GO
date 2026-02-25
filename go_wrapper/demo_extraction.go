package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"

	"github.com/architect/go_wrapper/stream"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s <log-file>\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "\nExample:\n")
		fmt.Fprintf(os.Stderr, "  %s logs/agents/codex-1/2026-02-09-*-stdout.log\n", os.Args[0])
		os.Exit(1)
	}

	logFile := os.Args[1]

	// Resolve glob pattern if needed
	matches, err := filepath.Glob(logFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	if len(matches) == 0 {
		fmt.Fprintf(os.Stderr, "Error: No log files found matching: %s\n", logFile)
		os.Exit(1)
	}

	// Use first match
	logFile = matches[0]

	fmt.Printf("Extracting from: %s\n", logFile)
	fmt.Println("=" + string(make([]byte, 60)) + "=")
	fmt.Println()

	// Open log file
	file, err := os.Open(logFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error opening file: %v\n", err)
		os.Exit(1)
	}
	defer file.Close()

	// Create extractor
	extractor := stream.NewExtractor()

	// Process line by line
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		matches := extractor.Extract(line)

		// Print matches as they're found
		for _, m := range matches {
			printMatch(m)
		}
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Error reading file: %v\n", err)
		os.Exit(1)
	}

	// Print summary
	fmt.Println()
	fmt.Println("=" + string(make([]byte, 60)) + "=")
	fmt.Println("EXTRACTION SUMMARY")
	fmt.Println("=" + string(make([]byte, 60)) + "=")

	stats := extractor.GetStats()
	fmt.Printf("Total lines processed: %d\n", stats["total_lines"])
	fmt.Printf("Total matches found: %d\n", stats["total_matches"])
	fmt.Println()

	if matchesByType, ok := stats["matches_by_type"].(map[string]int); ok {
		fmt.Println("Matches by type:")
		for typ, count := range matchesByType {
			fmt.Printf("  %-20s: %d\n", typ, count)
		}
	}

	fmt.Println()
	fmt.Println("Details by category:")
	fmt.Println()

	printCategory(extractor, stream.PatternTypeSession, "SESSION INFO")
	printCategory(extractor, stream.PatternTypeMetric, "METRICS")
	printCategory(extractor, stream.PatternTypeCodeBlock, "CODE BLOCKS")
	printCategory(extractor, stream.PatternTypeError, "ERRORS/WARNINGS")
	printCategory(extractor, stream.PatternTypeStateChange, "STATE CHANGES")
	printCategory(extractor, stream.PatternTypeFileOp, "FILE OPERATIONS")
}

func printMatch(m stream.Match) {
	icon := getIcon(m.Type)
	fmt.Printf("%s [%s] %s: %s\n", icon, m.Type, m.Pattern, m.Value)
}

func printCategory(extractor *stream.Extractor, matchType, title string) {
	matches := extractor.GetMatchesByType(matchType)
	if len(matches) == 0 {
		return
	}

	fmt.Printf("--- %s ---\n", title)
	for _, m := range matches {
		fmt.Printf("  • %s: %s", m.Pattern, m.Value)
		if m.Metadata != nil && len(m.Metadata) > 0 {
			fmt.Printf(" (")
			first := true
			for k, v := range m.Metadata {
				if !first {
					fmt.Printf(", ")
				}
				// Don't print huge content fields
				if k == "content" {
					contentStr, ok := v.(string)
					if ok && len(contentStr) > 50 {
						fmt.Printf("%s: <%.50s...>", k, contentStr)
					} else {
						fmt.Printf("%s: %v", k, v)
					}
				} else {
					fmt.Printf("%s: %v", k, v)
				}
				first = false
			}
			fmt.Printf(")")
		}
		fmt.Println()
	}
	fmt.Println()
}

func getIcon(matchType string) string {
	switch matchType {
	case stream.PatternTypeError:
		return "❌"
	case stream.PatternTypeMetric:
		return "📊"
	case stream.PatternTypeCodeBlock:
		return "💻"
	case stream.PatternTypeSession:
		return "🔧"
	case stream.PatternTypeStateChange:
		return "🔄"
	case stream.PatternTypeFileOp:
		return "📁"
	case stream.PatternTypePrompt:
		return "👤"
	case stream.PatternTypeResponse:
		return "🤖"
	default:
		return "•"
	}
}
