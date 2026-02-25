package commands

import (
	"flag"
	"fmt"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

type NodesResponse struct {
	Nodes []ClusterNode `json:"nodes"`
	Total int           `json:"total"`
}

type ClusterNode struct {
	ID           string  `json:"id"`
	Address      string  `json:"address"`
	Status       string  `json:"status"`
	LastHeartbeat string  `json:"last_heartbeat"`
	Load         float64 `json:"load"`
	Agents       int     `json:"agents"`
	IsLeader     bool    `json:"is_leader"`
}

type ClusterStatsResponse struct {
	TotalNodes       int     `json:"total_nodes"`
	ActiveNodes      int     `json:"active_nodes"`
	TotalAgents      int     `json:"total_agents"`
	AverageLoad      float64 `json:"average_load"`
	LeaderID         string  `json:"leader_id"`
	BalancingStrategy string  `json:"balancing_strategy"`
}

type LeaderResponse struct {
	LeaderID      string `json:"leader_id"`
	LeaderAddress string `json:"leader_address"`
	Term          int    `json:"term"`
}

type AssignmentsResponse struct {
	Assignments []Assignment `json:"assignments"`
	Total       int          `json:"total"`
}

type Assignment struct {
	AgentName string `json:"agent_name"`
	NodeID    string `json:"node_id"`
	AssignedAt string `json:"assigned_at"`
	Status    string `json:"status"`
}

func ClusterCommand(args []string) error {
	if len(args) == 0 {
		return clusterNodesCommand([]string{})
	}

	subcommand := args[0]

	switch subcommand {
	case "nodes":
		return clusterNodesCommand(args[1:])
	case "status":
		return clusterStatusCommand(args[1:])
	case "stats":
		return clusterStatsCommand(args[1:])
	case "leader":
		return clusterLeaderCommand(args[1:])
	case "assignments":
		return clusterAssignmentsCommand(args[1:])
	case "balance":
		return clusterBalanceCommand(args[1:])
	case "help", "-h", "--help":
		printClusterUsage()
		return nil
	default:
		return fmt.Errorf("unknown subcommand: %s", subcommand)
	}
}

func clusterNodesCommand(args []string) error {
	fs := flag.NewFlagSet("cluster nodes", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp NodesResponse
	if err := c.GetJSON("/api/cluster/nodes", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		if len(resp.Nodes) == 0 {
			output.PrintInfo("No cluster nodes found")
			return nil
		}

		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Cluster Nodes"))
		fmt.Println(output.Colorize(output.ColorBold, "============="))
		fmt.Println()

		headers := []string{"NODE ID", "ADDRESS", "STATUS", "AGENTS", "LOAD", "LEADER", "LAST HEARTBEAT"}
		rows := make([][]string, 0, len(resp.Nodes))

		for _, node := range resp.Nodes {
			leader := ""
			if node.IsLeader {
				leader = "⭐"
			}
			rows = append(rows, []string{
				node.ID,
				node.Address,
				output.FormatStatus(node.Status),
				fmt.Sprintf("%d", node.Agents),
				fmt.Sprintf("%.2f", node.Load),
				leader,
				node.LastHeartbeat,
			})
		}

		output.PrintTable(headers, rows)
		fmt.Println()
		output.PrintKeyValue("Total Nodes", fmt.Sprintf("%d", resp.Total))
		fmt.Println()
	}

	return nil
}

func clusterStatusCommand(args []string) error {
	// Alias for stats
	return clusterStatsCommand(args)
}

func clusterStatsCommand(args []string) error {
	fs := flag.NewFlagSet("cluster stats", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp ClusterStatsResponse
	if err := c.GetJSON("/api/cluster/stats", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Cluster Statistics"))
		fmt.Println(output.Colorize(output.ColorBold, "=================="))
		output.PrintKeyValue("Total Nodes", fmt.Sprintf("%d", resp.TotalNodes))
		output.PrintKeyValue("Active Nodes", fmt.Sprintf("%d", resp.ActiveNodes))
		output.PrintKeyValue("Total Agents", fmt.Sprintf("%d", resp.TotalAgents))
		output.PrintKeyValue("Average Load", fmt.Sprintf("%.2f", resp.AverageLoad))
		output.PrintKeyValue("Leader ID", resp.LeaderID)
		output.PrintKeyValue("Balancing Strategy", resp.BalancingStrategy)
		fmt.Println()
	}

	return nil
}

func clusterLeaderCommand(args []string) error {
	fs := flag.NewFlagSet("cluster leader", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp LeaderResponse
	if err := c.GetJSON("/api/cluster/leader", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Cluster Leader"))
		fmt.Println(output.Colorize(output.ColorBold, "=============="))
		output.PrintKeyValue("Leader ID", resp.LeaderID)
		output.PrintKeyValue("Leader Address", resp.LeaderAddress)
		output.PrintKeyValue("Term", fmt.Sprintf("%d", resp.Term))
		fmt.Println()
	}

	return nil
}

func clusterAssignmentsCommand(args []string) error {
	fs := flag.NewFlagSet("cluster assignments", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "table", "Output format (table, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp AssignmentsResponse
	if err := c.GetJSON("/api/cluster/assignments", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		if len(resp.Assignments) == 0 {
			output.PrintInfo("No agent assignments found")
			return nil
		}

		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Agent Assignments"))
		fmt.Println(output.Colorize(output.ColorBold, "================="))
		fmt.Println()

		headers := []string{"AGENT NAME", "NODE ID", "STATUS", "ASSIGNED AT"}
		rows := make([][]string, 0, len(resp.Assignments))

		for _, a := range resp.Assignments {
			rows = append(rows, []string{
				a.AgentName,
				a.NodeID,
				output.FormatStatus(a.Status),
				a.AssignedAt,
			})
		}

		output.PrintTable(headers, rows)
		fmt.Println()
		output.PrintKeyValue("Total Assignments", fmt.Sprintf("%d", resp.Total))
		fmt.Println()
	}

	return nil
}

func clusterBalanceCommand(args []string) error {
	fs := flag.NewFlagSet("cluster balance", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	strategy := fs.String("strategy", "", "Balancing strategy: round-robin, least-loaded, random")
	fs.Parse(args)

	if *strategy == "" {
		return fmt.Errorf("--strategy is required (round-robin, least-loaded, random)")
	}

	c := client.NewClient(*host, *port)

	endpoint := fmt.Sprintf("/api/cluster/balance?strategy=%s", *strategy)

	_, err := c.Post(endpoint, []byte{})
	if err != nil {
		return err
	}

	fmt.Printf("Load balancing strategy changed to: %s\n", *strategy)
	return nil
}

func printClusterUsage() {
	fmt.Printf(`Manage cluster nodes and coordination

USAGE:
    wrapper-cli cluster <subcommand> [options]

SUBCOMMANDS:
    nodes          List all cluster nodes
    status, stats  Get cluster statistics
    leader         Show current leader
    assignments    List agent assignments
    balance        Change load balancing strategy

OPTIONS:
    --host       API server host (default: localhost)
    --port       API server port (default: 8151)
    --format     Output format: table, json, text
    --strategy   Balancing strategy (for balance command)

EXAMPLES:
    # List cluster nodes
    wrapper-cli cluster nodes

    # Get cluster statistics
    wrapper-cli cluster stats

    # Show current leader
    wrapper-cli cluster leader

    # List agent assignments
    wrapper-cli cluster assignments

    # Change balancing strategy
    wrapper-cli cluster balance --strategy round-robin
    wrapper-cli cluster balance --strategy least-loaded
    wrapper-cli cluster balance --strategy random

BALANCING STRATEGIES:
    round-robin    Distribute agents evenly in rotation
    least-loaded   Assign to node with lowest current load
    random         Randomly distribute agents

NOTES:
    - Cluster mode must be enabled on the API server
    - Leader election is automatic via Raft consensus
    - Nodes send heartbeats every 30 seconds
    - Failed nodes are automatically detected and removed

`)
}
