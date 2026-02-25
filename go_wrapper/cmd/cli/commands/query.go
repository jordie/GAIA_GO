package commands

import (
	"flag"
	"fmt"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

type ExtractionsResponse struct {
	Extractions []Extraction `json:"extractions"`
	Total       int          `json:"total"`
	Page        int          `json:"page"`
}

type Extraction struct {
	ID             int    `json:"id"`
	AgentName      string `json:"agent_name"`
	SessionID      string `json:"session_id"`
	Timestamp      string `json:"timestamp"`
	EventType      string `json:"event_type"`
	Pattern        string `json:"pattern"`
	MatchedValue   string `json:"matched_value"`
	OriginalLine   string `json:"original_line"`
	LineNumber     int    `json:"line_number"`
	RiskLevel      string `json:"risk_level"`
	AutoConfirmable bool   `json:"auto_confirmable"`
}

type CodeBlocksResponse struct {
	CodeBlocks []CodeBlock `json:"code_blocks"`
	Total      int         `json:"total"`
}

type CodeBlock struct {
	ID        int    `json:"id"`
	AgentName string `json:"agent_name"`
	SessionID string `json:"session_id"`
	Timestamp string `json:"timestamp"`
	Language  string `json:"language"`
	Content   string `json:"content"`
	LineStart int    `json:"line_start"`
	LineEnd   int    `json:"line_end"`
	Digest    string `json:"digest"`
}

type SessionsResponse struct {
	Sessions []Session `json:"sessions"`
	Total    int       `json:"total"`
}

type Session struct {
	ID                       int    `json:"id"`
	AgentName                string `json:"agent_name"`
	SessionID                string `json:"session_id"`
	Environment              string `json:"environment"`
	StartedAt                string `json:"started_at"`
	EndedAt                  string `json:"ended_at,omitempty"`
	ExitCode                 int    `json:"exit_code"`
	TotalLinesProcessed      int    `json:"total_lines_processed"`
	TotalExtractionEvents    int    `json:"total_extraction_events"`
	TotalFeedbackOutcomes    int    `json:"total_feedback_outcomes"`
}

type AgentStatsResponse struct {
	AgentName          string                 `json:"agent_name"`
	TotalSessions      int                    `json:"total_sessions"`
	TotalExtractions   int                    `json:"total_extractions"`
	ExtractionsByType  map[string]int         `json:"extractions_by_type"`
	AvgSessionDuration string                 `json:"avg_session_duration"`
	SuccessRate        float64                `json:"success_rate"`
}

func QueryCommand(args []string) error {
	if len(args) == 0 {
		printQueryUsage()
		return nil
	}

	subcommand := args[0]

	switch subcommand {
	case "extractions":
		return queryExtractionsCommand(args[1:])
	case "code-blocks":
		return queryCodeBlocksCommand(args[1:])
	case "sessions":
		return querySessionsCommand(args[1:])
	case "session":
		return querySessionCommand(args[1:])
	case "stats":
		return queryStatsCommand(args[1:])
	case "help", "-h", "--help":
		printQueryUsage()
		return nil
	default:
		return fmt.Errorf("unknown subcommand: %s", subcommand)
	}
}

func queryExtractionsCommand(args []string) error {
	fs := flag.NewFlagSet("query extractions", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	agent := fs.String("agent", "", "Filter by agent name (required)")
	eventType := fs.String("type", "", "Filter by event type")
	pattern := fs.String("pattern", "", "Filter by pattern")
	limit := fs.Int("limit", 100, "Maximum number of results")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if *agent == "" {
		return fmt.Errorf("--agent is required")
	}

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	// Build query string
	query := fmt.Sprintf("/api/query/extractions?agent=%s&limit=%d", *agent, *limit)
	if *eventType != "" {
		query += fmt.Sprintf("&type=%s", *eventType)
	}
	if *pattern != "" {
		query += fmt.Sprintf("&pattern=%s", *pattern)
	}

	var resp ExtractionsResponse
	if err := c.GetJSON(query, &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		if len(resp.Extractions) == 0 {
			output.PrintInfo("No extractions found")
			return nil
		}

		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Extraction Events"))
		fmt.Println(output.Colorize(output.ColorBold, "=================="))
		fmt.Println()

		headers := []string{"ID", "TYPE", "PATTERN", "VALUE", "LINE", "RISK"}
		rows := make([][]string, 0, len(resp.Extractions))

		for _, e := range resp.Extractions {
			value := e.MatchedValue
			if len(value) > 40 {
				value = value[:37] + "..."
			}
			rows = append(rows, []string{
				fmt.Sprintf("%d", e.ID),
				e.EventType,
				e.Pattern,
				value,
				fmt.Sprintf("%d", e.LineNumber),
				e.RiskLevel,
			})
		}

		output.PrintTable(headers, rows)
		fmt.Println()
		output.PrintKeyValue("Total", fmt.Sprintf("%d extractions", resp.Total))
		fmt.Println()
	}

	return nil
}

func queryCodeBlocksCommand(args []string) error {
	fs := flag.NewFlagSet("query code-blocks", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	agent := fs.String("agent", "", "Filter by agent name (required)")
	language := fs.String("language", "", "Filter by language")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if *agent == "" {
		return fmt.Errorf("--agent is required")
	}

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	// Build query string
	query := fmt.Sprintf("/api/query/code-blocks?agent=%s", *agent)
	if *language != "" {
		query += fmt.Sprintf("&language=%s", *language)
	}

	var resp CodeBlocksResponse
	if err := c.GetJSON(query, &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		if len(resp.CodeBlocks) == 0 {
			output.PrintInfo("No code blocks found")
			return nil
		}

		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Code Blocks"))
		fmt.Println(output.Colorize(output.ColorBold, "==========="))
		fmt.Println()

		headers := []string{"ID", "LANGUAGE", "LINES", "DIGEST", "TIMESTAMP"}
		rows := make([][]string, 0, len(resp.CodeBlocks))

		for _, cb := range resp.CodeBlocks {
			lineRange := fmt.Sprintf("%d-%d", cb.LineStart, cb.LineEnd)
			digest := cb.Digest
			if len(digest) > 12 {
				digest = digest[:12] + "..."
			}
			rows = append(rows, []string{
				fmt.Sprintf("%d", cb.ID),
				cb.Language,
				lineRange,
				digest,
				cb.Timestamp,
			})
		}

		output.PrintTable(headers, rows)
		fmt.Println()
		output.PrintKeyValue("Total", fmt.Sprintf("%d code blocks", resp.Total))
		fmt.Println()
	}

	return nil
}

func querySessionsCommand(args []string) error {
	fs := flag.NewFlagSet("query sessions", flag.ExitOnError)
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

func querySessionCommand(args []string) error {
	fs := flag.NewFlagSet("query session", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if len(args) == 0 {
		return fmt.Errorf("session ID is required")
	}

	sessionID := args[0]
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

func queryStatsCommand(args []string) error {
	fs := flag.NewFlagSet("query stats", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	agent := fs.String("agent", "", "Agent name (required)")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	if *agent == "" {
		return fmt.Errorf("--agent is required")
	}

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp AgentStatsResponse
	if err := c.GetJSON(fmt.Sprintf("/api/query/stats/agent/%s", *agent), &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Agent Statistics"))
		fmt.Println(output.Colorize(output.ColorBold, "================"))
		output.PrintKeyValue("Agent Name", resp.AgentName)
		output.PrintKeyValue("Total Sessions", fmt.Sprintf("%d", resp.TotalSessions))
		output.PrintKeyValue("Total Extractions", fmt.Sprintf("%d", resp.TotalExtractions))
		output.PrintKeyValue("Avg Session Duration", resp.AvgSessionDuration)
		output.PrintKeyValue("Success Rate", fmt.Sprintf("%.1f%%", resp.SuccessRate*100))

		if len(resp.ExtractionsByType) > 0 {
			fmt.Println()
			fmt.Println(output.Colorize(output.ColorBold, "Extractions by Type:"))
			for eventType, count := range resp.ExtractionsByType {
				output.PrintKeyValue("  "+eventType, fmt.Sprintf("%d", count))
			}
		}
		fmt.Println()
	}

	return nil
}

func printQueryUsage() {
	fmt.Printf(`Query extraction events from the database

USAGE:
    wrapper-cli query <subcommand> [options]

SUBCOMMANDS:
    extractions  Query extraction events
    code-blocks  Query code blocks
    sessions     List agent sessions
    session      Get session details
    stats        Get agent statistics

OPTIONS:
    --host       API server host (default: localhost)
    --port       API server port (default: 8151)
    --agent      Agent name (required for most commands)
    --format     Output format: table, json, text

EXAMPLES:
    # Query extractions for an agent
    wrapper-cli query extractions --agent codex

    # Filter by event type
    wrapper-cli query extractions --agent codex --type error

    # Query code blocks in Go
    wrapper-cli query code-blocks --agent codex --language go

    # List sessions
    wrapper-cli query sessions --agent codex --limit 20

    # Get session details
    wrapper-cli query session <session-id>

    # Get agent statistics
    wrapper-cli query stats --agent codex

`)
}
