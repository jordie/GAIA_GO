package main

import (
	"fmt"
	"os"

	"github.com/architect/go_wrapper/cmd/cli/commands"
)

const version = "1.0.0"

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	if len(os.Args) < 2 {
		printUsage()
		return nil
	}

	command := os.Args[1]

	switch command {
	case "agents":
		return commands.AgentsCommand(os.Args[2:])
	case "logs":
		return commands.LogsCommand(os.Args[2:])
	case "metrics":
		return commands.MetricsCommand(os.Args[2:])
	case "query":
		return commands.QueryCommand(os.Args[2:])
	case "sessions":
		return commands.SessionsCommand(os.Args[2:])
	case "replay":
		return commands.ReplayCommand(os.Args[2:])
	case "cluster":
		return commands.ClusterCommand(os.Args[2:])
	case "health":
		return commands.HealthCommand(os.Args[2:])
	case "profile":
		return commands.ProfileCommand(os.Args[2:])
	case "version":
		fmt.Printf("wrapper-cli version %s\n", version)
		return nil
	case "help", "-h", "--help":
		printUsage()
		return nil
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", command)
		printUsage()
		return fmt.Errorf("unknown command: %s", command)
	}
}

func printUsage() {
	fmt.Printf(`wrapper-cli - Command-line interface for Go Agent Wrapper

USAGE:
    wrapper-cli <command> [options]

COMMANDS:
    agents      Manage agents (list, start, stop, kill, status)
    logs        View and search agent logs
    metrics     View agent metrics and statistics
    query       Query extraction events from database
    sessions    Manage and view agent sessions
    replay      Replay historical sessions
    cluster     Manage cluster nodes and coordination
    health      Check server and agent health
    profile     Performance profiling commands
    version     Show CLI version
    help        Show this help message

GLOBAL OPTIONS:
    --host      API server host (default: localhost)
    --port      API server port (default: 8151)
    --format    Output format: table, json, csv (default: table)
    --no-color  Disable colored output

EXAMPLES:
    # List all agents
    wrapper-cli agents list

    # Start a new agent
    wrapper-cli agents start --name worker-1 --command codex

    # View agent logs (tail)
    wrapper-cli logs tail worker-1

    # Get agent metrics
    wrapper-cli metrics get worker-1

    # Query extraction events
    wrapper-cli query extractions --agent worker-1 --type error

    # View cluster status
    wrapper-cli cluster status

    # Get health status
    wrapper-cli health

    # Profile memory usage
    wrapper-cli profile memory

For more information on a specific command:
    wrapper-cli <command> --help

`)
}
