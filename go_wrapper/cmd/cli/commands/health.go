package commands

import (
	"flag"
	"fmt"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

type HealthResponse struct {
	Status    string   `json:"status"`
	Uptime    string   `json:"uptime"`
	StartedAt string   `json:"started_at"`
	Agents    int      `json:"agents"`
	Version   string   `json:"version,omitempty"`
	Issues    []string `json:"issues,omitempty"`
}

func HealthCommand(args []string) error {
	fs := flag.NewFlagSet("health", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp HealthResponse
	if err := c.GetJSON("/api/health", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Server Health Status"))
		fmt.Println(output.Colorize(output.ColorBold, "===================="))
		output.PrintKeyValue("Status", output.FormatStatus(resp.Status))
		output.PrintKeyValue("Uptime", resp.Uptime)
		output.PrintKeyValue("Active Agents", fmt.Sprintf("%d", resp.Agents))
		if resp.Version != "" {
			output.PrintKeyValue("Version", resp.Version)
		}

		if len(resp.Issues) > 0 {
			fmt.Println()
			output.PrintWarning("Issues detected:")
			for _, issue := range resp.Issues {
				fmt.Printf("  • %s\n", issue)
			}
		}
		fmt.Println()
	}

	return nil
}
