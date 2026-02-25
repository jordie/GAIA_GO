package commands

import (
	"flag"
	"fmt"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

// SessionsCommand is a convenient wrapper around query sessions
func SessionsCommand(args []string) error {
	if len(args) == 0 {
		return sessionsListCommand([]string{})
	}

	subcommand := args[0]

	switch subcommand {
	case "list":
		return sessionsListCommand(args[1:])
	case "show":
		return sessionsShowCommand(args[1:])
	case "help", "-h", "--help":
		printSessionsUsage()
		return nil
	default:
		// Try to interpret as session ID for show command
		return sessionsShowCommand(args)
	}
}

func sessionsListCommand(args []string) error {
	fs := flag.NewFlagSet("sessions list", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	agent := fs.String("agent", "", "Filter by agent name (required)")
	limit := fs.Int("limit", 50, "Maximum number of results")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if *agent == "" {
		return fmt.Errorf("--agent is required")
	}

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	query := fmt.Sprintf("/api/query/sessions?agent=%s&limit=%d", *agent, *limit)

	var resp SessionsResponse
	if err := c.GetJSON(query, &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		if len(resp.Sessions) == 0 {
			output.PrintInfo("No sessions found")
			return nil
		}

		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Agent Sessions"))
		fmt.Println(output.Colorize(output.ColorBold, "=============="))
		fmt.Println()

		headers := []string{"ID", "SESSION ID", "STARTED", "EXIT CODE", "LINES", "EXTRACTIONS"}
		rows := make([][]string, 0, len(resp.Sessions))

		for _, s := range resp.Sessions {
			sessionID := s.SessionID
			if len(sessionID) > 12 {
				sessionID = sessionID[:12] + "..."
			}
			rows = append(rows, []string{
				fmt.Sprintf("%d", s.ID),
				sessionID,
				s.StartedAt,
				fmt.Sprintf("%d", s.ExitCode),
				fmt.Sprintf("%d", s.TotalLinesProcessed),
				fmt.Sprintf("%d", s.TotalExtractionEvents),
			})
		}

		output.PrintTable(headers, rows)
		fmt.Println()
		output.PrintKeyValue("Total", fmt.Sprintf("%d sessions", resp.Total))
		fmt.Println()
	}

	return nil
}

func sessionsShowCommand(args []string) error {
	fs := flag.NewFlagSet("sessions show", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("session ID is required")
	}

	sessionID := fs.Arg(0)
	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp Session
	if err := c.GetJSON(fmt.Sprintf("/api/query/session/%s", sessionID), &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Session Details"))
		fmt.Println(output.Colorize(output.ColorBold, "==============="))
		output.PrintKeyValue("ID", fmt.Sprintf("%d", resp.ID))
		output.PrintKeyValue("Agent Name", resp.AgentName)
		output.PrintKeyValue("Session ID", resp.SessionID)
		output.PrintKeyValue("Environment", resp.Environment)
		output.PrintKeyValue("Started At", resp.StartedAt)
		if resp.EndedAt != "" {
			output.PrintKeyValue("Ended At", resp.EndedAt)
		}
		output.PrintKeyValue("Exit Code", fmt.Sprintf("%d", resp.ExitCode))
		output.PrintKeyValue("Lines Processed", fmt.Sprintf("%d", resp.TotalLinesProcessed))
		output.PrintKeyValue("Extraction Events", fmt.Sprintf("%d", resp.TotalExtractionEvents))
		output.PrintKeyValue("Feedback Outcomes", fmt.Sprintf("%d", resp.TotalFeedbackOutcomes))
		fmt.Println()
	}

	return nil
}

func printSessionsUsage() {
	fmt.Printf(`View and manage agent sessions

USAGE:
    wrapper-cli sessions <subcommand> [options]
    wrapper-cli sessions <session-id>  (shorthand for 'show')

SUBCOMMANDS:
    list         List agent sessions
    show         Show session details

OPTIONS:
    --host       API server host (default: localhost)
    --port       API server port (default: 8151)
    --agent      Agent name (required for list)
    --format     Output format: table, json, text
    --limit      Maximum number of results (default: 50)

EXAMPLES:
    # List sessions for an agent
    wrapper-cli sessions list --agent codex

    # Show session details
    wrapper-cli sessions show <session-id>

    # Shorthand for show
    wrapper-cli sessions <session-id>

    # List with limit
    wrapper-cli sessions list --agent codex --limit 10

NOTE:
    This is a convenience wrapper around 'query sessions'.
    For advanced filtering, use: wrapper-cli query sessions

`)
}
