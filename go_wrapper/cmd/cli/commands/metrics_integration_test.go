package commands

import (
	"bytes"
	"encoding/json"
	"os"
	"strings"
	"testing"

	"github.com/architect/go_wrapper/cmd/cli/output"
	mocktest "github.com/architect/go_wrapper/cmd/cli/testing"
)

func TestMetricsGetCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("metrics-test-1", "codex", 8001)
	mock.AddAgent("metrics-test-2", "comet", 8002)

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port}

	err := metricsGetCommand(args)
	if err != nil {
		t.Fatalf("metricsGetCommand failed: %v", err)
	}
}

func TestMetricsGetCommand_JSON_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("worker-1", "codex", 9001)

	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	host, port := extractHostPort(mock.Server.URL)
	args := []string{"--host", host, "--port", port, "--format", "json"}

	err := metricsGetCommand(args)
	if err != nil {
		t.Fatalf("metricsGetCommand failed: %v", err)
	}

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	buf.ReadFrom(r)
	outputStr := buf.String()

	// Verify JSON output
	var result MetricsResponse

	if err := json.Unmarshal([]byte(outputStr), &result); err != nil {
		t.Fatalf("Invalid JSON output: %v", err)
	}

	if len(result.Agents) == 0 {
		t.Error("Expected agents in metrics, got none")
	}

	if result.Version == "" {
		t.Error("Expected version in metrics response")
	}
}

func TestMetricsExportCommand_Prometheus_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("test-agent", "codex", 10001)

	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	host, port := extractHostPort(mock.Server.URL)
	args := []string{"--host", host, "--port", port, "--format", "prometheus"}

	err := metricsExportCommand(args)
	if err != nil {
		t.Fatalf("metricsExportCommand failed: %v", err)
	}

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	buf.ReadFrom(r)
	output := buf.String()

	// Verify Prometheus format
	if !strings.Contains(output, "# HELP") {
		t.Error("Expected Prometheus HELP comment")
	}
	if !strings.Contains(output, "# TYPE") {
		t.Error("Expected Prometheus TYPE comment")
	}
	if !strings.Contains(output, "agent_lines_processed") {
		t.Error("Expected metric name in output")
	}
}

func TestMetricsExportCommand_InfluxDB_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("test-agent", "codex", 11001)

	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	host, port := extractHostPort(mock.Server.URL)
	args := []string{"--host", host, "--port", port, "--format", "influxdb"}

	err := metricsExportCommand(args)
	if err != nil {
		t.Fatalf("metricsExportCommand failed: %v", err)
	}

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	buf.ReadFrom(r)
	output := buf.String()

	// Verify InfluxDB line protocol format
	if !strings.Contains(output, "agent_metrics") {
		t.Error("Expected metric name in InfluxDB output")
	}
	if !strings.Contains(output, "agent=") {
		t.Error("Expected tag in InfluxDB output")
	}
}

func TestMetricsExportCommand_InvalidFormat_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)
	args := []string{"--host", host, "--port", port, "--format", "invalid"}

	err := metricsExportCommand(args)
	if err == nil {
		t.Fatal("Expected error for invalid format, got nil")
	}

	if !strings.Contains(err.Error(), "unknown format") {
		t.Errorf("Expected 'unknown format' error, got: %v", err)
	}
}
