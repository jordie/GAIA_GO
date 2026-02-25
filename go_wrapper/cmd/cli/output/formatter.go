package output

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"text/tabwriter"
)

// Color codes for terminal output
const (
	ColorReset  = "\033[0m"
	ColorRed    = "\033[31m"
	ColorGreen  = "\033[32m"
	ColorYellow = "\033[33m"
	ColorBlue   = "\033[34m"
	ColorPurple = "\033[35m"
	ColorCyan   = "\033[36m"
	ColorWhite  = "\033[37m"
	ColorBold   = "\033[1m"
)

var NoColor = false

// Colorize adds color to text if colors are enabled
func Colorize(color, text string) string {
	if NoColor {
		return text
	}
	return color + text + ColorReset
}

// PrintTable prints data in table format
func PrintTable(headers []string, rows [][]string) {
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 3, ' ', 0)

	// Print headers in bold
	headerLine := make([]string, len(headers))
	for i, h := range headers {
		headerLine[i] = Colorize(ColorBold+ColorCyan, h)
	}
	fmt.Fprintln(w, strings.Join(headerLine, "\t"))

	// Print separator
	separators := make([]string, len(headers))
	for i := range headers {
		separators[i] = strings.Repeat("-", len(headers[i]))
	}
	fmt.Fprintln(w, strings.Join(separators, "\t"))

	// Print rows
	for _, row := range rows {
		fmt.Fprintln(w, strings.Join(row, "\t"))
	}

	w.Flush()
}

// PrintJSON prints data in JSON format
func PrintJSON(data interface{}) error {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	return encoder.Encode(data)
}

// PrintJSONCompact prints data in compact JSON format (one line)
func PrintJSONCompact(data interface{}) error {
	bytes, err := json.Marshal(data)
	if err != nil {
		return err
	}
	fmt.Println(string(bytes))
	return nil
}

// PrintCSV prints data in CSV format
func PrintCSV(headers []string, rows [][]string) error {
	w := csv.NewWriter(os.Stdout)
	defer w.Flush()

	if err := w.Write(headers); err != nil {
		return err
	}

	for _, row := range rows {
		if err := w.Write(row); err != nil {
			return err
		}
	}

	return nil
}

// PrintSuccess prints a success message in green
func PrintSuccess(message string) {
	fmt.Println(Colorize(ColorGreen, "✓ "+message))
}

// PrintError prints an error message in red
func PrintError(message string) {
	fmt.Fprintln(os.Stderr, Colorize(ColorRed, "✗ "+message))
}

// PrintWarning prints a warning message in yellow
func PrintWarning(message string) {
	fmt.Println(Colorize(ColorYellow, "⚠ "+message))
}

// PrintInfo prints an info message in blue
func PrintInfo(message string) {
	fmt.Println(Colorize(ColorBlue, "ℹ "+message))
}

// PrintKeyValue prints a key-value pair with color
func PrintKeyValue(key, value string) {
	fmt.Printf("%s: %s\n",
		Colorize(ColorBold, key),
		value)
}

// StreamLines streams lines from reader with optional prefix
func StreamLines(reader io.Reader, prefix string) error {
	buf := make([]byte, 4096)
	for {
		n, err := reader.Read(buf)
		if n > 0 {
			lines := strings.Split(string(buf[:n]), "\n")
			for _, line := range lines {
				if line != "" {
					if prefix != "" {
						fmt.Printf("%s %s\n", Colorize(ColorCyan, prefix), line)
					} else {
						fmt.Println(line)
					}
				}
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
	}
	return nil
}

// FormatBytes formats bytes as human-readable string
func FormatBytes(bytes uint64) string {
	const unit = 1024
	if bytes < unit {
		return fmt.Sprintf("%d B", bytes)
	}
	div, exp := uint64(unit), 0
	for n := bytes / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(bytes)/float64(div), "KMGTPE"[exp])
}

// FormatDuration formats duration in human-readable format
func FormatDuration(seconds float64) string {
	if seconds < 60 {
		return fmt.Sprintf("%.1fs", seconds)
	}
	minutes := int(seconds / 60)
	secs := int(seconds) % 60
	if minutes < 60 {
		return fmt.Sprintf("%dm%ds", minutes, secs)
	}
	hours := minutes / 60
	mins := minutes % 60
	return fmt.Sprintf("%dh%dm%ds", hours, mins, secs)
}

// FormatStatus formats status with color
func FormatStatus(status string) string {
	switch strings.ToLower(status) {
	case "running", "active", "healthy", "ok":
		return Colorize(ColorGreen, status)
	case "stopped", "inactive", "failed", "error":
		return Colorize(ColorRed, status)
	case "degraded", "warning", "pending":
		return Colorize(ColorYellow, status)
	default:
		return status
	}
}

// ProgressBar shows a simple progress bar
type ProgressBar struct {
	Total   int
	Current int
	Width   int
}

// NewProgressBar creates a new progress bar
func NewProgressBar(total int) *ProgressBar {
	return &ProgressBar{
		Total:   total,
		Current: 0,
		Width:   40,
	}
}

// Update updates the progress bar
func (pb *ProgressBar) Update(current int) {
	pb.Current = current
	pb.Render()
}

// Increment increments the progress bar
func (pb *ProgressBar) Increment() {
	pb.Current++
	pb.Render()
}

// Render renders the progress bar
func (pb *ProgressBar) Render() {
	percent := float64(pb.Current) / float64(pb.Total)
	filled := int(percent * float64(pb.Width))

	bar := strings.Repeat("█", filled) + strings.Repeat("░", pb.Width-filled)
	fmt.Printf("\r[%s] %d/%d (%.1f%%)", bar, pb.Current, pb.Total, percent*100)

	if pb.Current >= pb.Total {
		fmt.Println()
	}
}
