package commands

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

func LogsCommand(args []string) error {
	if len(args) == 0 {
		printLogsUsage()
		return nil
	}

	subcommand := args[0]

	switch subcommand {
	case "tail", "follow":
		return logsTailCommand(args[1:])
	case "view", "cat":
		return logsViewCommand(args[1:])
	case "search", "grep":
		return logsSearchCommand(args[1:])
	case "list":
		return logsListCommand(args[1:])
	case "help", "-h", "--help":
		printLogsUsage()
		return nil
	default:
		// Default to tail if agent name is provided
		return logsTailCommand(args)
	}
}

func logsTailCommand(args []string) error {
	fs := flag.NewFlagSet("logs tail", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	_ = fs.Int("lines", 50, "Number of lines to show") // TODO: implement line limiting
	_ = fs.String("stream", "both", "Stream to tail: stdout, stderr, or both") // TODO: implement stream filtering
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	c := client.NewClient(*host, *port)

	output.PrintInfo(fmt.Sprintf("Tailing logs for agent '%s' (press Ctrl+C to stop)...\n", agentName))

	// Stream logs via SSE
	return c.StreamSSE(fmt.Sprintf("/api/agents/%s/stream", agentName), func(data string) error {
		// Parse and display the log line
		if strings.HasPrefix(data, "[") {
			// Format: [timestamp] [stream] message
			fmt.Println(data)
		} else {
			fmt.Println(data)
		}
		return nil
	})
}

func logsViewCommand(args []string) error {
	fs := flag.NewFlagSet("logs view", flag.ExitOnError)
	logsDir := fs.String("dir", "logs/agents", "Logs directory")
	lines := fs.Int("lines", 100, "Number of lines to show")
	stream := fs.String("stream", "stdout", "Stream to view: stdout or stderr")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)

	// Find latest log file for agent
	agentDir := filepath.Join(*logsDir, agentName)
	files, err := os.ReadDir(agentDir)
	if err != nil {
		return fmt.Errorf("failed to read logs directory: %w", err)
	}

	if len(files) == 0 {
		return fmt.Errorf("no logs found for agent '%s'", agentName)
	}

	// Find latest stdout or stderr log
	var latestLog string
	for i := len(files) - 1; i >= 0; i-- {
		name := files[i].Name()
		if strings.Contains(name, *stream+".log") {
			latestLog = filepath.Join(agentDir, name)
			break
		}
	}

	if latestLog == "" {
		return fmt.Errorf("no %s logs found for agent '%s'", *stream, agentName)
	}

	output.PrintInfo(fmt.Sprintf("Viewing %s", latestLog))
	fmt.Println()

	// Read and display log file
	file, err := os.Open(latestLog)
	if err != nil {
		return fmt.Errorf("failed to open log file: %w", err)
	}
	defer file.Close()

	// Count total lines
	scanner := bufio.NewScanner(file)
	totalLines := 0
	for scanner.Scan() {
		totalLines++
	}

	// Reset to beginning
	file.Seek(0, 0)
	scanner = bufio.NewScanner(file)

	// Skip to last N lines
	skipLines := 0
	if totalLines > *lines {
		skipLines = totalLines - *lines
	}

	currentLine := 0
	for scanner.Scan() {
		if currentLine >= skipLines {
			fmt.Println(scanner.Text())
		}
		currentLine++
	}

	if err := scanner.Err(); err != nil {
		return fmt.Errorf("error reading log file: %w", err)
	}

	fmt.Printf("\n%s\n", output.Colorize(output.ColorBold,
		fmt.Sprintf("Showing last %d lines of %d total",
		min(*lines, totalLines), totalLines)))

	return nil
}

func logsSearchCommand(args []string) error {
	fs := flag.NewFlagSet("logs search", flag.ExitOnError)
	logsDir := fs.String("dir", "logs/agents", "Logs directory")
	ignoreCase := fs.Bool("i", false, "Case-insensitive search")
	count := fs.Bool("count", false, "Show only count of matches")
	stream := fs.String("stream", "both", "Stream to search: stdout, stderr, or both")
	fs.Parse(args)

	if fs.NArg() < 2 {
		return fmt.Errorf("usage: logs search <agent-name> <pattern>")
	}

	agentName := fs.Arg(0)
	pattern := fs.Arg(1)

	if *ignoreCase {
		pattern = strings.ToLower(pattern)
	}

	agentDir := filepath.Join(*logsDir, agentName)
	files, err := os.ReadDir(agentDir)
	if err != nil {
		return fmt.Errorf("failed to read logs directory: %w", err)
	}

	matchCount := 0
	for _, file := range files {
		if file.IsDir() {
			continue
		}

		// Filter by stream type
		if *stream != "both" {
			if !strings.Contains(file.Name(), *stream+".log") {
				continue
			}
		}

		logPath := filepath.Join(agentDir, file.Name())
		f, err := os.Open(logPath)
		if err != nil {
			continue
		}

		scanner := bufio.NewScanner(f)
		lineNum := 0
		for scanner.Scan() {
			lineNum++
			line := scanner.Text()
			searchLine := line
			if *ignoreCase {
				searchLine = strings.ToLower(line)
			}

			if strings.Contains(searchLine, pattern) {
				matchCount++
				if !*count {
					fmt.Printf("%s:%d: %s\n",
						output.Colorize(output.ColorCyan, file.Name()),
						lineNum,
						line)
				}
			}
		}
		f.Close()
	}

	if *count {
		fmt.Printf("Found %d match(es)\n", matchCount)
	} else if matchCount == 0 {
		output.PrintWarning(fmt.Sprintf("No matches found for pattern '%s'", pattern))
	}

	return nil
}

func logsListCommand(args []string) error {
	fs := flag.NewFlagSet("logs list", flag.ExitOnError)
	logsDir := fs.String("dir", "logs/agents", "Logs directory")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	agentDir := filepath.Join(*logsDir, agentName)

	files, err := os.ReadDir(agentDir)
	if err != nil {
		return fmt.Errorf("failed to read logs directory: %w", err)
	}

	if len(files) == 0 {
		output.PrintInfo(fmt.Sprintf("No logs found for agent '%s'", agentName))
		return nil
	}

	headers := []string{"FILE", "SIZE", "MODIFIED"}
	rows := make([][]string, 0)

	for _, file := range files {
		if file.IsDir() {
			continue
		}

		info, err := file.Info()
		if err != nil {
			continue
		}

		rows = append(rows, []string{
			file.Name(),
			output.FormatBytes(uint64(info.Size())),
			info.ModTime().Format("2006-01-02 15:04:05"),
		})
	}

	output.PrintTable(headers, rows)
	fmt.Printf("\nTotal: %d log file(s)\n", len(rows))

	return nil
}

func printLogsUsage() {
	fmt.Printf(`View and search agent logs

USAGE:
    wrapper-cli logs <subcommand> [options] <agent-name>

SUBCOMMANDS:
    tail, follow   Stream live logs from agent (SSE)
    view, cat      View recent logs from file
    search, grep   Search logs for pattern
    list           List all log files for agent

OPTIONS:
    --host         API server host (default: localhost)
    --port         API server port (default: 8151)
    --dir          Logs directory (default: logs/agents)
    --lines        Number of lines to show (default: 50)
    --stream       Stream type: stdout, stderr, both (default: both)
    --no-color     Disable colored output

SEARCH OPTIONS:
    -i             Case-insensitive search
    --count        Show only count of matches

EXAMPLES:
    # Tail live logs (SSE stream)
    wrapper-cli logs tail worker-1

    # View last 100 lines of stdout
    wrapper-cli logs view worker-1 --lines 100 --stream stdout

    # Search for errors
    wrapper-cli logs search worker-1 "ERROR"

    # Case-insensitive search
    wrapper-cli logs search worker-1 "error" -i

    # Count matches
    wrapper-cli logs search worker-1 "warning" --count

    # List all log files
    wrapper-cli logs list worker-1

`)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
