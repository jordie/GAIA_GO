package commands

import (
	"flag"
	"fmt"
	"os"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

func ReplayCommand(args []string) error {
	if len(args) == 0 {
		printReplayUsage()
		return nil
	}

	subcommand := args[0]

	switch subcommand {
	case "start":
		return replayStartCommand(args[1:])
	case "list":
		// Redirect to query sessions
		return querySessionsCommand(args[1:])
	case "export":
		return replayExportCommand(args[1:])
	case "control":
		return replayControlCommand(args[1:])
	case "help", "-h", "--help":
		printReplayUsage()
		return nil
	default:
		return fmt.Errorf("unknown subcommand: %s", subcommand)
	}
}

func replayStartCommand(args []string) error {
	fs := flag.NewFlagSet("replay start", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	sessionID := fs.String("session", "", "Session ID to replay (required)")
	speed := fs.Float64("speed", 1.0, "Replay speed multiplier (0.5 = half speed, 2.0 = double speed)")
	format := fs.String("format", "sse", "Output format (sse, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if *sessionID == "" {
		return fmt.Errorf("--session is required")
	}

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	// Build query string
	query := fmt.Sprintf("/api/replay/session/%s?format=%s&speed=%.1f", *sessionID, *format, *speed)

	fmt.Printf("Starting replay of session: %s (speed: %.1fx)\n\n", *sessionID, *speed)

	if *format == "sse" {
		// Stream SSE events
		err := c.StreamSSE(query, func(event string) error {
			fmt.Println(event)
			return nil
		})
		if err != nil {
			return err
		}
		fmt.Println("\nReplay completed")
	} else {
		// Get JSON response
		body, err := c.Get(query)
		if err != nil {
			return err
		}
		fmt.Println(string(body))
	}

	return nil
}

func replayExportCommand(args []string) error {
	fs := flag.NewFlagSet("replay export", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	sessionID := fs.String("session", "", "Session ID to export (required)")
	format := fs.String("format", "json", "Export format (json, csv, har, xml)")
	outputFile := fs.String("output", "", "Output file (default: stdout)")
	fs.Parse(args)

	if *sessionID == "" {
		return fmt.Errorf("--session is required")
	}

	c := client.NewClient(*host, *port)

	// Build query string
	query := fmt.Sprintf("/api/replay/export/%s?format=%s", *sessionID, *format)

	body, err := c.Get(query)
	if err != nil {
		return err
	}

	// Write to file or stdout
	if *outputFile != "" {
		err := os.WriteFile(*outputFile, body, 0644)
		if err != nil {
			return fmt.Errorf("failed to write output file: %w", err)
		}
		fmt.Printf("Session exported to: %s\n", *outputFile)
	} else {
		fmt.Println(string(body))
	}

	return nil
}

func replayControlCommand(args []string) error {
	fs := flag.NewFlagSet("replay control", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	sessionID := fs.String("session", "", "Session ID (required)")
	action := fs.String("action", "", "Control action: pause, resume, stop, seek (required)")
	position := fs.String("position", "", "Position to seek to (for seek action)")
	fs.Parse(args)

	if *sessionID == "" {
		return fmt.Errorf("--session is required")
	}

	if *action == "" {
		return fmt.Errorf("--action is required (pause, resume, stop, seek)")
	}

	c := client.NewClient(*host, *port)

	// Build endpoint
	endpoint := fmt.Sprintf("/api/replay/control/%s/%s", *sessionID, *action)
	if *action == "seek" && *position != "" {
		endpoint += fmt.Sprintf("?position=%s", *position)
	}

	// Send control command
	_, err := c.Post(endpoint, []byte{})
	if err != nil {
		return err
	}

	fmt.Printf("Control command sent: %s\n", *action)
	return nil
}

func printReplayUsage() {
	fmt.Printf(`Replay historical agent sessions

USAGE:
    wrapper-cli replay <subcommand> [options]

SUBCOMMANDS:
    start        Start replaying a session
    list         List available sessions (alias for 'query sessions')
    export       Export session to file
    control      Control active replay (pause, resume, stop, seek)

OPTIONS:
    --host       API server host (default: localhost)
    --port       API server port (default: 8151)
    --session    Session ID (required for most commands)
    --speed      Replay speed multiplier (default: 1.0)
    --format     Output/export format
    --output     Output file path (for export)
    --action     Control action (for control command)
    --position   Seek position (for seek action)

EXAMPLES:
    # List available sessions
    wrapper-cli replay list --agent codex

    # Start replay at normal speed
    wrapper-cli replay start --session sess_abc123

    # Replay at 2x speed
    wrapper-cli replay start --session sess_abc123 --speed 2.0

    # Replay at half speed
    wrapper-cli replay start --session sess_abc123 --speed 0.5

    # Export session to JSON file
    wrapper-cli replay export --session sess_abc123 --format json --output session.json

    # Export to HAR format
    wrapper-cli replay export --session sess_abc123 --format har --output session.har

    # Export to CSV
    wrapper-cli replay export --session sess_abc123 --format csv --output session.csv

    # Control replay
    wrapper-cli replay control --session sess_abc123 --action pause
    wrapper-cli replay control --session sess_abc123 --action resume
    wrapper-cli replay control --session sess_abc123 --action stop

NOTES:
    - Replay preserves original timing of events
    - Speed multiplier affects playback rate (2.0 = 2x faster)
    - SSE format streams events in real-time
    - Export formats: JSON, CSV, HAR, XML

`)
}
