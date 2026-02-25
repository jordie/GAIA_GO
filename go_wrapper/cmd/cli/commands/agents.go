package commands

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

type Agent struct {
	Name      string `json:"name"`
	Command   string `json:"command"`
	PID       int    `json:"pid"`
	Status    string `json:"status"`
	StartedAt string `json:"started_at"`
	Env       string `json:"env,omitempty"`
}

type AgentsResponse struct {
	Agents []Agent `json:"agents"`
	Count  int     `json:"count"`
}

type CreateAgentRequest struct {
	Name    string `json:"name"`
	Command string `json:"command"`
	Args    string `json:"args,omitempty"`
	Env     string `json:"env,omitempty"`
}

func AgentsCommand(args []string) error {
	if len(args) == 0 {
		printAgentsUsage()
		return nil
	}

	subcommand := args[0]

	switch subcommand {
	case "list", "ls":
		return agentsListCommand(args[1:])
	case "start", "create":
		return agentsStartCommand(args[1:])
	case "stop":
		return agentsStopCommand(args[1:])
	case "kill":
		return agentsKillCommand(args[1:])
	case "status", "info":
		return agentsStatusCommand(args[1:])
	case "pause":
		return agentsPauseCommand(args[1:])
	case "resume":
		return agentsResumeCommand(args[1:])
	case "help", "-h", "--help":
		printAgentsUsage()
		return nil
	default:
		fmt.Fprintf(os.Stderr, "Unknown subcommand: %s\n\n", subcommand)
		printAgentsUsage()
		return fmt.Errorf("unknown subcommand: %s", subcommand)
	}
}

func agentsListCommand(args []string) error {
	fs := flag.NewFlagSet("agents list", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "table", "Output format (table, json, csv)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp AgentsResponse
	if err := c.GetJSON("/api/agents", &resp); err != nil {
		return err
	}

	if len(resp.Agents) == 0 {
		output.PrintInfo("No agents running")
		return nil
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	case "csv":
		headers := []string{"Name", "Command", "PID", "Status", "Started", "Env"}
		rows := make([][]string, len(resp.Agents))
		for i, agent := range resp.Agents {
			rows[i] = []string{
				agent.Name,
				agent.Command,
				fmt.Sprintf("%d", agent.PID),
				agent.Status,
				agent.StartedAt,
				agent.Env,
			}
		}
		return output.PrintCSV(headers, rows)
	default: // table
		headers := []string{"NAME", "COMMAND", "PID", "STATUS", "STARTED", "ENV"}
		rows := make([][]string, len(resp.Agents))
		for i, agent := range resp.Agents {
			rows[i] = []string{
				agent.Name,
				agent.Command,
				fmt.Sprintf("%d", agent.PID),
				output.FormatStatus(agent.Status),
				agent.StartedAt,
				agent.Env,
			}
		}
		output.PrintTable(headers, rows)
		fmt.Printf("\nTotal: %d agent(s)\n", resp.Count)
	}

	return nil
}

func agentsStartCommand(args []string) error {
	fs := flag.NewFlagSet("agents start", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	name := fs.String("name", "", "Agent name (required)")
	command := fs.String("command", "", "Command to run (required)")
	cmdArgs := fs.String("args", "", "Command arguments")
	env := fs.String("env", "", "Environment (e.g., production, development)")
	fs.Parse(args)

	if *name == "" {
		return fmt.Errorf("agent name is required (--name)")
	}
	if *command == "" {
		return fmt.Errorf("command is required (--command)")
	}

	c := client.NewClient(*host, *port)

	req := CreateAgentRequest{
		Name:    *name,
		Command: *command,
		Args:    *cmdArgs,
		Env:     *env,
	}

	var resp Agent
	if err := c.PostJSON("/api/agents", req, &resp); err != nil {
		return err
	}

	output.PrintSuccess(fmt.Sprintf("Agent '%s' started successfully", resp.Name))
	output.PrintKeyValue("PID", fmt.Sprintf("%d", resp.PID))
	output.PrintKeyValue("Status", output.FormatStatus(resp.Status))

	return nil
}

func agentsStopCommand(args []string) error {
	fs := flag.NewFlagSet("agents stop", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	c := client.NewClient(*host, *port)

	_, err := c.Delete(fmt.Sprintf("/api/agents/%s", agentName))
	if err != nil {
		return err
	}

	output.PrintSuccess(fmt.Sprintf("Agent '%s' stopped successfully", agentName))
	return nil
}

func agentsKillCommand(args []string) error {
	fs := flag.NewFlagSet("agents kill", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	c := client.NewClient(*host, *port)

	_, err := c.Post(fmt.Sprintf("/api/agents/%s/kill", agentName), nil)
	if err != nil {
		return err
	}

	output.PrintSuccess(fmt.Sprintf("Agent '%s' killed successfully", agentName))
	return nil
}

func agentsStatusCommand(args []string) error {
	fs := flag.NewFlagSet("agents status", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	c := client.NewClient(*host, *port)

	var agent Agent
	if err := c.GetJSON(fmt.Sprintf("/api/agents/%s", agentName), &agent); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(agent)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Agent Information"))
		fmt.Println(output.Colorize(output.ColorBold, "================="))
		output.PrintKeyValue("Name", agent.Name)
		output.PrintKeyValue("Command", agent.Command)
		output.PrintKeyValue("PID", fmt.Sprintf("%d", agent.PID))
		output.PrintKeyValue("Status", output.FormatStatus(agent.Status))
		output.PrintKeyValue("Started", agent.StartedAt)
		if agent.Env != "" {
			output.PrintKeyValue("Environment", agent.Env)
		}
		fmt.Println()
	}

	return nil
}

func agentsPauseCommand(args []string) error {
	fs := flag.NewFlagSet("agents pause", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	c := client.NewClient(*host, *port)

	// Send WebSocket command via REST API fallback
	cmd := map[string]interface{}{
		"command": "pause",
	}

	body, err := c.Post(fmt.Sprintf("/api/agents/%s/command", agentName), cmd)
	if err != nil {
		return err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return err
	}

	output.PrintSuccess(fmt.Sprintf("Agent '%s' paused successfully", agentName))
	return nil
}

func agentsResumeCommand(args []string) error {
	fs := flag.NewFlagSet("agents resume", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	fs.Parse(args)

	if fs.NArg() == 0 {
		return fmt.Errorf("agent name is required")
	}

	agentName := fs.Arg(0)
	c := client.NewClient(*host, *port)

	// Send WebSocket command via REST API fallback
	cmd := map[string]interface{}{
		"command": "resume",
	}

	body, err := c.Post(fmt.Sprintf("/api/agents/%s/command", agentName), cmd)
	if err != nil {
		return err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return err
	}

	output.PrintSuccess(fmt.Sprintf("Agent '%s' resumed successfully", agentName))
	return nil
}

func printAgentsUsage() {
	fmt.Printf(`Manage agents

USAGE:
    wrapper-cli agents <subcommand> [options]

SUBCOMMANDS:
    list, ls       List all running agents
    start          Start a new agent
    stop           Stop an agent gracefully
    kill           Force kill an agent
    status, info   Get agent details
    pause          Pause agent execution
    resume         Resume agent execution

OPTIONS:
    --host         API server host (default: localhost)
    --port         API server port (default: 8151)
    --format       Output format: table, json, csv (default: table)
    --no-color     Disable colored output

EXAMPLES:
    # List all agents
    wrapper-cli agents list

    # List agents in JSON format
    wrapper-cli agents list --format json

    # Start a new agent
    wrapper-cli agents start --name worker-1 --command codex

    # Start agent with environment
    wrapper-cli agents start --name prod-agent --command codex --env production

    # Get agent status
    wrapper-cli agents status worker-1

    # Pause agent
    wrapper-cli agents pause worker-1

    # Resume agent
    wrapper-cli agents resume worker-1

    # Stop agent
    wrapper-cli agents stop worker-1

    # Force kill agent
    wrapper-cli agents kill worker-1

`)
}
