package output

import (
	"bytes"
	"io"
	"os"
	"strings"
	"testing"
)

func TestFormatBytes(t *testing.T) {
	tests := []struct {
		bytes    uint64
		expected string
	}{
		{0, "0 B"},
		{512, "512 B"},
		{1024, "1.0 KB"},
		{1536, "1.5 KB"},
		{1048576, "1.0 MB"},
		{1073741824, "1.0 GB"},
		{1099511627776, "1.0 TB"},
	}

	for _, tt := range tests {
		result := FormatBytes(tt.bytes)
		if result != tt.expected {
			t.Errorf("FormatBytes(%d) = %s, expected %s", tt.bytes, result, tt.expected)
		}
	}
}

func TestFormatDuration(t *testing.T) {
	tests := []struct {
		seconds  float64
		expected string
	}{
		{30, "30.0s"},
		{60, "1m0s"},
		{90, "1m30s"},
		{3600, "1h0m0s"},
		{3661, "1h1m1s"},
		{7200, "2h0m0s"},
	}

	for _, tt := range tests {
		result := FormatDuration(tt.seconds)
		if result != tt.expected {
			t.Errorf("FormatDuration(%.0f) = %s, expected %s", tt.seconds, result, tt.expected)
		}
	}
}

func TestFormatStatus(t *testing.T) {
	NoColor = true // Disable colors for testing
	defer func() { NoColor = false }()

	tests := []struct {
		status   string
		expected string
	}{
		{"running", "running"},
		{"stopped", "stopped"},
		{"degraded", "degraded"},
		{"unknown", "unknown"},
	}

	for _, tt := range tests {
		result := FormatStatus(tt.status)
		if result != tt.expected {
			t.Errorf("FormatStatus(%s) = %s, expected %s", tt.status, result, tt.expected)
		}
	}
}

func TestColorize(t *testing.T) {
	NoColor = false
	result := Colorize(ColorRed, "test")
	if !strings.Contains(result, "test") {
		t.Error("Colorize should contain original text")
	}
	if !strings.Contains(result, ColorRed) {
		t.Error("Colorize should contain color code")
	}

	NoColor = true
	result = Colorize(ColorRed, "test")
	if result != "test" {
		t.Error("Colorize with NoColor should return plain text")
	}
}

func TestPrintTable(t *testing.T) {
	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	NoColor = true
	headers := []string{"NAME", "VALUE"}
	rows := [][]string{
		{"test1", "value1"},
		{"test2", "value2"},
	}

	PrintTable(headers, rows)

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "NAME") {
		t.Error("PrintTable should contain headers")
	}
	if !strings.Contains(output, "test1") {
		t.Error("PrintTable should contain row data")
	}
}

func TestPrintJSON(t *testing.T) {
	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	data := map[string]interface{}{
		"name":  "test",
		"value": 123,
	}

	PrintJSON(data)

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "test") {
		t.Error("PrintJSON should contain data")
	}
	if !strings.Contains(output, "123") {
		t.Error("PrintJSON should contain numeric values")
	}
}

func TestPrintCSV(t *testing.T) {
	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	headers := []string{"name", "value"}
	rows := [][]string{
		{"test1", "value1"},
		{"test2", "value2"},
	}

	err := PrintCSV(headers, rows)
	if err != nil {
		t.Errorf("PrintCSV failed: %v", err)
	}

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "name,value") {
		t.Error("PrintCSV should contain headers")
	}
	if !strings.Contains(output, "test1,value1") {
		t.Error("PrintCSV should contain row data")
	}
}

func TestProgressBar(t *testing.T) {
	pb := NewProgressBar(100)

	if pb.Total != 100 {
		t.Errorf("NewProgressBar total = %d, expected 100", pb.Total)
	}
	if pb.Current != 0 {
		t.Errorf("NewProgressBar current = %d, expected 0", pb.Current)
	}

	pb.Update(50)
	if pb.Current != 50 {
		t.Errorf("Update(50) current = %d, expected 50", pb.Current)
	}

	pb.Increment()
	if pb.Current != 51 {
		t.Errorf("Increment() current = %d, expected 51", pb.Current)
	}
}
