package stream

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"
)

const (
	// BufferSize for buffered writer (4KB - small to reduce memory)
	BufferSize = 4096

	// FlushInterval - force flush every N seconds
	FlushInterval = 2 * time.Second

	// MaxLogSize - rotate log when it exceeds this (100MB)
	MaxLogSize = 100 * 1024 * 1024
)

// StreamLogger handles efficient streaming to disk with ANSI cleaning
type StreamLogger struct {
	name     string          // Stream name (stdout/stderr)
	logPath  string          // Full path to log file
	file     *os.File        // File handle
	writer   *bufio.Writer   // Buffered writer
	cleaner  *ANSICleaner    // ANSI escape code stripper
	mu       sync.Mutex      // Protects file operations
	closed   bool            // Track if closed
	bytesWritten int64       // Total bytes written
	lastFlush time.Time      // Last flush timestamp
}

// NewStreamLogger creates a new stream logger
func NewStreamLogger(agentName, streamName string, logsDir string) (*StreamLogger, error) {
	// Create agent-specific directory
	agentDir := filepath.Join(logsDir, agentName)
	if err := os.MkdirAll(agentDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create log dir: %w", err)
	}

	// Create log file with timestamp
	timestamp := time.Now().Format("2006-01-02-15-04-05")
	filename := fmt.Sprintf("%s-%s.log", timestamp, streamName)
	logPath := filepath.Join(agentDir, filename)

	file, err := os.Create(logPath)
	if err != nil {
		return nil, fmt.Errorf("failed to create log file: %w", err)
	}

	sl := &StreamLogger{
		name:      streamName,
		logPath:   logPath,
		file:      file,
		writer:    bufio.NewWriterSize(file, BufferSize),
		cleaner:   NewANSICleaner(),
		lastFlush: time.Now(),
	}

	// Write header
	header := fmt.Sprintf("# %s log - %s\n# Agent: %s\n\n",
		streamName, time.Now().Format(time.RFC3339), agentName)
	sl.writer.WriteString(header)

	return sl, nil
}

// Write implements io.Writer interface
// Cleans ANSI codes and writes to disk
func (sl *StreamLogger) Write(p []byte) (n int, err error) {
	sl.mu.Lock()
	defer sl.mu.Unlock()

	if sl.closed {
		return 0, fmt.Errorf("logger closed")
	}

	// Clean ANSI escape codes
	cleaned := sl.cleaner.Clean(p)

	// Write to buffer
	written, err := sl.writer.Write(cleaned)
	if err != nil {
		return 0, err
	}

	sl.bytesWritten += int64(written)

	// Auto-flush if buffer is getting full or time elapsed
	if sl.writer.Available() < BufferSize/2 || time.Since(sl.lastFlush) > FlushInterval {
		sl.writer.Flush()
		sl.lastFlush = time.Now()
	}

	// Check for rotation needed
	if sl.bytesWritten > MaxLogSize {
		sl.rotate()
	}

	return len(p), nil // Return original length (before cleaning)
}

// rotate creates a new log file when size limit is reached
func (sl *StreamLogger) rotate() error {
	// Flush current buffer
	sl.writer.Flush()

	// Close current file
	sl.file.Close()

	// Create new file with new timestamp
	timestamp := time.Now().Format("2006-01-02-15-04-05")
	dir := filepath.Dir(sl.logPath)
	filename := fmt.Sprintf("%s-%s.log", timestamp, sl.name)
	newPath := filepath.Join(dir, filename)

	file, err := os.Create(newPath)
	if err != nil {
		return err
	}

	// Update state
	sl.file = file
	sl.writer = bufio.NewWriterSize(file, BufferSize)
	sl.logPath = newPath
	sl.bytesWritten = 0

	return nil
}

// Flush forces a flush of buffered data
func (sl *StreamLogger) Flush() error {
	sl.mu.Lock()
	defer sl.mu.Unlock()

	if sl.closed {
		return nil
	}

	err := sl.writer.Flush()
	if err == nil {
		sl.lastFlush = time.Now()
	}
	return err
}

// Close flushes and closes the logger
func (sl *StreamLogger) Close() error {
	sl.mu.Lock()
	defer sl.mu.Unlock()

	if sl.closed {
		return nil
	}

	sl.closed = true

	// Flush buffer
	sl.writer.Flush()

	// Close file
	return sl.file.Close()
}

// GetPath returns the current log file path
func (sl *StreamLogger) GetPath() string {
	sl.mu.Lock()
	defer sl.mu.Unlock()
	return sl.logPath
}

// StreamToDisk continuously reads from reader and writes to logger
// This is a helper function for goroutine usage
func StreamToDisk(reader io.Reader, logger *StreamLogger, wg *sync.WaitGroup) {
	defer wg.Done()

	// Use a small buffer for reading
	buf := make([]byte, 4096)

	for {
		n, err := reader.Read(buf)
		if n > 0 {
			logger.Write(buf[:n])
		}
		if err != nil {
			if err != io.EOF {
				fmt.Fprintf(os.Stderr, "[ERROR] Stream read error: %v\n", err)
			}
			break
		}
	}

	logger.Flush()
}
