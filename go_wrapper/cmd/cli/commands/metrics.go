package commands

import (
	"flag"
	"fmt"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

type MetricsResponse struct {
	System  map[string]interface{} `json:"system"`
	Agents  []AgentMetrics         `json:"agents"`
	SSE     map[string]interface{} `json:"sse"`
	Version string                 `json:"version"`
}

type AgentMetrics struct {
	Name           string  `json:"name"`
	Status         string  `json:"status"`
	StartedAt      string  `json:"started_at"`
	Duration       int64   `json:"duration"`
	ExitCode       int     `json:"exit_code"`
	LogLines       int64   `json:"log_lines"`
	Extractions    int64   `json:"extractions"`
	CodeBlocks     int64   `json:"code_blocks"`
	Errors         int64   `json:"errors"`
	BytesProcessed int64   `json:"bytes_processed"`
	ExtractionRate float64 `json:"extraction_rate"`
	LogRate        float64 `json:"log_rate"`
}

func MetricsCommand(args []string) error {
	if len(args) == 0 {
		return metricsGetCommand([]string{})
	}

	subcommand := args[0]

	switch subcommand {
	case "get", "show":
		return metricsGetCommand(args[1:])
	case "export":
		return metricsExportCommand(args[1:])
	case "help", "-h", "--help":
		printMetricsUsage()
		return nil
	default:
		// Default to get
		return metricsGetCommand(args)
	}
}

func metricsGetCommand(args []string) error {
	fs := flag.NewFlagSet("metrics get", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp MetricsResponse
	if err := c.GetJSON("/api/metrics", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		if len(resp.Agents) == 0 {
			output.PrintInfo("No agents running")
			return nil
		}

		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Agent Metrics"))
		fmt.Println(output.Colorize(output.ColorBold, "============="))
		fmt.Println()

		headers := []string{"AGENT", "STATUS", "LOGS", "EXTRACTIONS", "CODE BLOCKS", "ERRORS", "DURATION"}
		rows := make([][]string, 0, len(resp.Agents))

		for _, m := range resp.Agents {
			duration := output.FormatDuration(float64(m.Duration) / 1e9) // Convert nanoseconds to seconds
			rows = append(rows, []string{
				m.Name,
				output.FormatStatus(m.Status),
				fmt.Sprintf("%d", m.LogLines),
				fmt.Sprintf("%d", m.Extractions),
				fmt.Sprintf("%d", m.CodeBlocks),
				fmt.Sprintf("%d", m.Errors),
				duration,
			})
		}

		output.PrintTable(headers, rows)
		fmt.Println()

		// Show summary stats if available
		if resp.System != nil {
			if totalAgents, ok := resp.System["total_agents"].(float64); ok {
				output.PrintKeyValue("Total Agents", fmt.Sprintf("%.0f", totalAgents))
			}
			if runningAgents, ok := resp.System["running_agents"].(float64); ok {
				output.PrintKeyValue("Running Agents", fmt.Sprintf("%.0f", runningAgents))
			}
			if uptime, ok := resp.System["uptime_seconds"].(float64); ok {
				output.PrintKeyValue("System Uptime", output.FormatDuration(uptime))
			}
			fmt.Println()
		}
	}

	return nil
}

func metricsExportCommand(args []string) error {
	fs := flag.NewFlagSet("metrics export", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "prometheus", "Export format (prometheus, influxdb)")
	fs.Parse(args)

	c := client.NewClient(*host, *port)

	var endpoint string
	switch *format {
	case "prometheus":
		endpoint = "/api/metrics/prometheus"
	case "influxdb":
		endpoint = "/api/metrics/influxdb"
	default:
		return fmt.Errorf("unknown format: %s", *format)
	}

	body, err := c.Get(endpoint)
	if err != nil {
		return err
	}

	fmt.Println(string(body))
	return nil
}

func printMetricsUsage() {
	fmt.Printf(`View agent metrics and statistics

USAGE:
    wrapper-cli metrics <subcommand> [options]

SUBCOMMANDS:
    get, show      Get current metrics
    export         Export metrics in Prometheus/InfluxDB format

OPTIONS:
    --host         API server host (default: localhost)
    --port         API server port (default: 8151)
    --format       Output format: table, json, prometheus, influxdb

EXAMPLES:
    # Get metrics for all agents
    wrapper-cli metrics

    # Get metrics in JSON
    wrapper-cli metrics --format json

    # Export in Prometheus format
    wrapper-cli metrics export --format prometheus

    # Export in InfluxDB line protocol
    wrapper-cli metrics export --format influxdb

`)
}
