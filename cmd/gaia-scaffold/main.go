package main

import (
	"bufio"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"
)

const version = "0.1.0"

var (
	prompt        = flag.String("prompt", "", "Application specification prompt")
	outputDir     = flag.String("output-dir", "", "Directory for generated code (default: /tmp/gaia-scaffold-{uuid})")
	keepArtifacts = flag.Bool("keep-artifacts", false, "Keep generated files after tests (for inspection)")
	verbose       = flag.Bool("verbose", false, "Enable verbose logging")
	timeout       = flag.Duration("timeout", 0, "Maximum execution time (default: 5m)")
)

func main() {
	flag.Parse()

	fmt.Println("╔═════════════════════════════════════════════════════════════════╗")
	fmt.Println("║       GAIA SCAFFOLD - Build-Destroy Testing Framework            ║")
	fmt.Println("║                      Version " + version + "                                   ║")
	fmt.Println("╚═════════════════════════════════════════════════════════════════╝")
	fmt.Println()

	// Get specification
	specification := getSpecification()
	if specification == "" {
		fmt.Println("Error: No specification provided")
		flag.Usage()
		os.Exit(1)
	}

	if *verbose {
		fmt.Println("[VERBOSE] Specification:")
		fmt.Println(specification)
		fmt.Println()
	}

	// Create executor
	executor := NewExecutor(&ExecutorConfig{
		Specification: specification,
		OutputDir:     *outputDir,
		KeepArtifacts: *keepArtifacts,
		Verbose:       *verbose,
		Timeout:       *timeout,
	})

	// Run the build-destroy cycle
	if err := executor.Execute(); err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println()
	fmt.Println("✓ GAIA scaffold tool completed successfully")
}

// getSpecification retrieves the specification from command line or stdin
func getSpecification() string {
	if *prompt != "" {
		return *prompt
	}

	// Check if stdin has data
	stat, _ := os.Stdin.Stat()
	if (stat.Mode() & os.ModeCharDevice) == 0 {
		// stdin is piped
		scanner := bufio.NewScanner(os.Stdin)
		var lines []string
		for scanner.Scan() {
			lines = append(lines, scanner.Text())
		}
		return strings.Join(lines, "\n")
	}

	// Interactive mode
	fmt.Print("Enter application specification (press Enter twice when done):\n> ")
	reader := bufio.NewReader(os.Stdin)
	var lines []string
	var emptyCount int

	for {
		line, err := reader.ReadString('\n')
		if err != nil && err != io.EOF {
			return ""
		}

		line = strings.TrimSpace(line)
		if line == "" {
			emptyCount++
			if emptyCount >= 1 {
				break
			}
		} else {
			emptyCount = 0
			lines = append(lines, line)
		}

		if err == io.EOF {
			break
		}
	}

	return strings.Join(lines, " ")
}
