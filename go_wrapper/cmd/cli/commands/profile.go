package commands

import (
	"flag"
	"fmt"
	"os"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
)

type ProfilingMetrics struct {
	Uptime         string `json:"uptime"`
	MemoryAlloc    int64  `json:"memory_alloc"`
	MemorySys      int64  `json:"memory_sys"`
	Goroutines     int    `json:"goroutines"`
	GCRuns         uint32 `json:"gc_runs"`
	NextGC         int64  `json:"next_gc"`
	APIRequests    int64  `json:"api_requests"`
}

type MemoryMetrics struct {
	Alloc         int64   `json:"alloc"`
	TotalAlloc    int64   `json:"total_alloc"`
	Sys           int64   `json:"sys"`
	NumGC         uint32  `json:"num_gc"`
	GCCPUPercent  float64 `json:"gc_cpu_percent"`
}

type GCMetrics struct {
	NumGC          uint32  `json:"num_gc"`
	LastGC         string  `json:"last_gc"`
	NextGC         int64   `json:"next_gc"`
	PauseTotal     int64   `json:"pause_total_ns"`
	PauseAvg       int64   `json:"pause_avg_ns"`
	GCCPUPercent   float64 `json:"gc_cpu_percent"`
}

type GoroutineMetrics struct {
	Total        int `json:"total"`
	Running      int `json:"running"`
	Waiting      int `json:"waiting"`
}

type RuntimeMetrics struct {
	GoVersion    string  `json:"go_version"`
	GOOS         string  `json:"goos"`
	GOARCH       string  `json:"goarch"`
	NumCPU       int     `json:"num_cpu"`
	GOMAXPROCS   int     `json:"gomaxprocs"`
}

func ProfileCommand(args []string) error {
	if len(args) == 0 {
		return profileMetricsCommand([]string{})
	}

	subcommand := args[0]

	switch subcommand {
	case "metrics":
		return profileMetricsCommand(args[1:])
	case "memory":
		return profileMemoryCommand(args[1:])
	case "gc":
		return profileGCCommand(args[1:])
	case "goroutines":
		return profileGoroutinesCommand(args[1:])
	case "runtime":
		return profileRuntimeCommand(args[1:])
	case "cpu":
		return profileCPUCommand(args[1:])
	case "heap":
		return profileHeapCommand(args[1:])
	case "force-gc":
		return profileForceGCCommand(args[1:])
	case "help", "-h", "--help":
		printProfileUsage()
		return nil
	default:
		return fmt.Errorf("unknown subcommand: %s", subcommand)
	}
}

func profileMetricsCommand(args []string) error {
	fs := flag.NewFlagSet("profile metrics", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp ProfilingMetrics
	if err := c.GetJSON("/api/profiling/metrics", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Profiling Metrics"))
		fmt.Println(output.Colorize(output.ColorBold, "================="))
		output.PrintKeyValue("Uptime", resp.Uptime)
		output.PrintKeyValue("Memory Allocated", output.FormatBytes(uint64(resp.MemoryAlloc)))
		output.PrintKeyValue("Memory System", output.FormatBytes(uint64(resp.MemorySys)))
		output.PrintKeyValue("Goroutines", fmt.Sprintf("%d", resp.Goroutines))
		output.PrintKeyValue("GC Runs", fmt.Sprintf("%d", resp.GCRuns))
		output.PrintKeyValue("Next GC", output.FormatBytes(uint64(resp.NextGC)))
		output.PrintKeyValue("API Requests", fmt.Sprintf("%d", resp.APIRequests))
		fmt.Println()
	}

	return nil
}

func profileMemoryCommand(args []string) error {
	fs := flag.NewFlagSet("profile memory", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp MemoryMetrics
	if err := c.GetJSON("/api/profiling/memory", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Memory Usage"))
		fmt.Println(output.Colorize(output.ColorBold, "============"))
		output.PrintKeyValue("Current Alloc", output.FormatBytes(uint64(resp.Alloc)))
		output.PrintKeyValue("Total Alloc", output.FormatBytes(uint64(resp.TotalAlloc)))
		output.PrintKeyValue("System Memory", output.FormatBytes(uint64(resp.Sys)))
		output.PrintKeyValue("GC Runs", fmt.Sprintf("%d", resp.NumGC))
		output.PrintKeyValue("GC CPU %", fmt.Sprintf("%.2f%%", resp.GCCPUPercent))
		fmt.Println()
	}

	return nil
}

func profileGCCommand(args []string) error {
	fs := flag.NewFlagSet("profile gc", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp GCMetrics
	if err := c.GetJSON("/api/profiling/gc", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Garbage Collection Stats"))
		fmt.Println(output.Colorize(output.ColorBold, "========================"))
		output.PrintKeyValue("GC Runs", fmt.Sprintf("%d", resp.NumGC))
		output.PrintKeyValue("Last GC", resp.LastGC)
		output.PrintKeyValue("Next GC", output.FormatBytes(uint64(resp.NextGC)))
		output.PrintKeyValue("Total Pause", fmt.Sprintf("%.2f ms", float64(resp.PauseTotal)/1e6))
		output.PrintKeyValue("Avg Pause", fmt.Sprintf("%.2f ms", float64(resp.PauseAvg)/1e6))
		output.PrintKeyValue("GC CPU %", fmt.Sprintf("%.2f%%", resp.GCCPUPercent))
		fmt.Println()
	}

	return nil
}

func profileGoroutinesCommand(args []string) error {
	fs := flag.NewFlagSet("profile goroutines", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp GoroutineMetrics
	if err := c.GetJSON("/api/profiling/goroutines", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Goroutine Statistics"))
		fmt.Println(output.Colorize(output.ColorBold, "===================="))
		output.PrintKeyValue("Total", fmt.Sprintf("%d", resp.Total))
		output.PrintKeyValue("Running", fmt.Sprintf("%d", resp.Running))
		output.PrintKeyValue("Waiting", fmt.Sprintf("%d", resp.Waiting))
		fmt.Println()
	}

	return nil
}

func profileRuntimeCommand(args []string) error {
	fs := flag.NewFlagSet("profile runtime", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	format := fs.String("format", "text", "Output format (text, json)")
	noColor := fs.Bool("no-color", false, "Disable colored output")
	fs.Parse(args)

	output.NoColor = *noColor

	c := client.NewClient(*host, *port)

	var resp RuntimeMetrics
	if err := c.GetJSON("/api/profiling/runtime", &resp); err != nil {
		return err
	}

	switch *format {
	case "json":
		return output.PrintJSON(resp)
	default:
		fmt.Printf("\n%s\n", output.Colorize(output.ColorBold, "Runtime Information"))
		fmt.Println(output.Colorize(output.ColorBold, "==================="))
		output.PrintKeyValue("Go Version", resp.GoVersion)
		output.PrintKeyValue("OS", resp.GOOS)
		output.PrintKeyValue("Architecture", resp.GOARCH)
		output.PrintKeyValue("CPUs", fmt.Sprintf("%d", resp.NumCPU))
		output.PrintKeyValue("GOMAXPROCS", fmt.Sprintf("%d", resp.GOMAXPROCS))
		fmt.Println()
	}

	return nil
}

func profileCPUCommand(args []string) error {
	fs := flag.NewFlagSet("profile cpu", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	duration := fs.Int("duration", 30, "Profile duration in seconds")
	output_file := fs.String("output", "cpu.prof", "Output file path")
	fs.Parse(args)

	c := client.NewClient(*host, *port)

	endpoint := fmt.Sprintf("/api/profiling/cpu-profile?duration=%d", *duration)

	fmt.Printf("Capturing CPU profile for %d seconds...\n", *duration)

	body, err := c.Get(endpoint)
	if err != nil {
		return err
	}

	err = os.WriteFile(*output_file, body, 0644)
	if err != nil {
		return fmt.Errorf("failed to write profile: %w", err)
	}

	fmt.Printf("CPU profile saved to: %s\n", *output_file)
	fmt.Printf("\nAnalyze with: go tool pprof %s\n", *output_file)
	return nil
}

func profileHeapCommand(args []string) error {
	fs := flag.NewFlagSet("profile heap", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	output_file := fs.String("output", "heap.prof", "Output file path")
	fs.Parse(args)

	c := client.NewClient(*host, *port)

	fmt.Println("Capturing heap dump...")

	body, err := c.Get("/api/profiling/heap-dump")
	if err != nil {
		return err
	}

	err = os.WriteFile(*output_file, body, 0644)
	if err != nil {
		return fmt.Errorf("failed to write heap dump: %w", err)
	}

	fmt.Printf("Heap dump saved to: %s\n", *output_file)
	fmt.Printf("\nAnalyze with: go tool pprof %s\n", *output_file)
	return nil
}

func profileForceGCCommand(args []string) error {
	fs := flag.NewFlagSet("profile force-gc", flag.ExitOnError)
	host := fs.String("host", "localhost", "API server host")
	port := fs.Int("port", 8151, "API server port")
	fs.Parse(args)

	c := client.NewClient(*host, *port)

	_, err := c.Post("/api/profiling/force-gc", []byte{})
	if err != nil {
		return err
	}

	fmt.Println("Garbage collection triggered")
	return nil
}

func printProfileUsage() {
	fmt.Printf(`Performance profiling and monitoring

USAGE:
    wrapper-cli profile <subcommand> [options]

SUBCOMMANDS:
    metrics      Show profiling metrics summary
    memory       Show memory usage details
    gc           Show garbage collection statistics
    goroutines   Show goroutine statistics
    runtime      Show runtime information
    cpu          Download CPU profile
    heap         Download heap dump
    force-gc     Trigger garbage collection

OPTIONS:
    --host       API server host (default: localhost)
    --port       API server port (default: 8151)
    --format     Output format: text, json
    --duration   Profile duration in seconds (for CPU profile)
    --output     Output file path (for CPU/heap profiles)

EXAMPLES:
    # Show metrics summary
    wrapper-cli profile metrics

    # Show memory usage
    wrapper-cli profile memory

    # Show GC statistics
    wrapper-cli profile gc

    # Show goroutine count
    wrapper-cli profile goroutines

    # Show runtime info
    wrapper-cli profile runtime

    # Download CPU profile (30 seconds)
    wrapper-cli profile cpu --duration 30 --output cpu.prof

    # Download heap dump
    wrapper-cli profile heap --output heap.prof

    # Force garbage collection
    wrapper-cli profile force-gc

ANALYZING PROFILES:
    # Analyze CPU profile
    go tool pprof cpu.prof

    # Analyze heap dump
    go tool pprof heap.prof

    # Interactive web interface
    go tool pprof -http=:8080 cpu.prof

NOTES:
    - CPU profiling may impact performance during capture
    - Heap dumps can be large (100MB+)
    - Use JSON format for programmatic access
    - force-gc is useful before taking heap dumps

`)
}
