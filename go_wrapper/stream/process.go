package stream

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
	"syscall"
	"time"

	"github.com/creack/pty"
	"github.com/architect/go_wrapper/data"
)

// ProcessWrapper wraps a child process with streaming log capture
type ProcessWrapper struct {
	cmd         *exec.Cmd
	agentName   string
	logsDir     string
	stdoutLog   *StreamLogger
	stderrLog   *StreamLogger
	ptyFile     *os.File
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	exitCode    int
	exitError   error
	broadcaster *Broadcaster
	extractor   *ConfigurableExtractor
	envManager  *EnvironmentManager
	feedback    *FeedbackTracker
	lineNum     int
	startTime   time.Time

	// Database persistence fields
	sessionStore *data.SessionStore
	sessionID    string
	environment  string
}

// NewProcessWrapper creates a new process wrapper
func NewProcessWrapper(agentName, logsDir string, command string, args ...string) *ProcessWrapper {
	return NewProcessWrapperWithEnvironment(agentName, logsDir, "dev", command, args...)
}

// NewProcessWrapperWithEnvironment creates a new process wrapper with environment enforcement
func NewProcessWrapperWithEnvironment(agentName, logsDir, environment string, command string, args ...string) *ProcessWrapper {
	ctx, cancel := context.WithCancel(context.Background())

	pw := &ProcessWrapper{
		cmd:         exec.CommandContext(ctx, command, args...),
		agentName:   agentName,
		logsDir:     logsDir,
		ctx:         ctx,
		cancel:      cancel,
		exitCode:    -1,
		broadcaster: NewBroadcaster(),
		lineNum:     0,
		environment: environment,
	}

	// Initialize environment manager
	envConfigPath := "config/environments.json"
	envManager, err := NewEnvironmentManager(envConfigPath, environment)
	if err != nil {
		fmt.Printf("[Wrapper] Environment manager disabled: %v\n", err)
	} else {
		pw.envManager = envManager

		// Setup environment automatically
		envSetup := NewEnvironmentSetup(envManager.GetEnvironment(), agentName)
		if err := envSetup.Initialize(); err != nil {
			fmt.Printf("[Wrapper] Warning: Environment setup failed: %v\n", err)
		}

		// Enforce working directory
		if err := envManager.EnforceWorkingDirectory(); err != nil {
			fmt.Printf("[Wrapper] Warning: Failed to enforce working directory: %v\n", err)
		}
	}

	// Initialize feedback tracker if environment supports it
	if pw.envManager != nil && pw.envManager.ShouldTrackFeedback() {
		feedbackPath := "data/feedback"
		feedback, err := NewFeedbackTracker(agentName, environment, feedbackPath)
		if err != nil {
			fmt.Printf("[Wrapper] Feedback tracker disabled: %v\n", err)
		} else {
			pw.feedback = feedback
		}
	}

	// Initialize extraction layer (optional - graceful fallback if config missing)
	configPath := "config/extraction_patterns.json"
	extractor, err := NewConfigurableExtractor(agentName, configPath)
	if err != nil {
		fmt.Printf("[Wrapper] Extraction layer disabled (config not found): %v\n", err)
	} else {
		pw.extractor = extractor
		fmt.Printf("[Wrapper] Extraction layer enabled: %d patterns loaded\n", len(extractor.GetConfig().Patterns))
	}

	return pw
}

// Start starts the process and begins log streaming
func (pw *ProcessWrapper) Start() error {
	// Create loggers
	var err error
	pw.stdoutLog, err = NewStreamLogger(pw.agentName, "stdout", pw.logsDir)
	if err != nil {
		return fmt.Errorf("failed to create stdout logger: %w", err)
	}

	pw.stderrLog, err = NewStreamLogger(pw.agentName, "stderr", pw.logsDir)
	if err != nil {
		pw.stdoutLog.Close()
		return fmt.Errorf("failed to create stderr logger: %w", err)
	}

	// Set working directory to current directory
	pw.cmd.Dir, _ = os.Getwd()

	// Start process with PTY for full terminal emulation
	ptmx, err := pty.Start(pw.cmd)
	if err != nil {
		pw.stdoutLog.Close()
		pw.stderrLog.Close()
		return fmt.Errorf("failed to start process: %w", err)
	}
	pw.ptyFile = ptmx

	pw.startTime = time.Now()

	fmt.Printf("[Wrapper] Started %s (PID: %d)\n", pw.agentName, pw.cmd.Process.Pid)
	fmt.Printf("[Wrapper] Logs: %s\n", pw.stdoutLog.GetPath())

	// Record session start in database
	if err := pw.recordSessionStart(); err != nil {
		fmt.Printf("[Wrapper] Warning: Failed to record session start: %v\n", err)
	}

	// Broadcast start state
	pw.broadcaster.BroadcastState("started", map[string]interface{}{
		"pid":       pw.cmd.Process.Pid,
		"logs_dir":  pw.logsDir,
		"timestamp": pw.startTime,
	})

	// Start streaming goroutine
	pw.wg.Add(1)
	go pw.streamOutput()

	return nil
}

// streamOutput reads from PTY and writes to both stdout and log
func (pw *ProcessWrapper) streamOutput() {
	defer pw.wg.Done()

	// Create a TeeReader to write to both stdout and log
	tee := io.TeeReader(pw.ptyFile, os.Stdout)

	buf := make([]byte, 4096)
	lineBuffer := make([]byte, 0, 4096)

	for {
		n, err := tee.Read(buf)
		if n > 0 {
			// Write to log (ANSI cleaned)
			pw.stdoutLog.Write(buf[:n])

			// Parse lines for broadcasting
			for i := 0; i < n; i++ {
				if buf[i] == '\n' {
					// Complete line found
					line := string(lineBuffer)
					lineBuffer = lineBuffer[:0]

					pw.lineNum++

					// Extract events from line
					if pw.extractor != nil {
						events := pw.extractor.ProcessLine(line)
						// Broadcast extracted events
						for _, event := range events {
							pw.broadcaster.BroadcastExtraction(Match{
								Type:      event.EventType,
								Pattern:   event.Pattern,
								Value:     event.Matched,
								Line:      line,
								LineNum:   pw.lineNum,
								Timestamp: time.Now(),
								Metadata:  event.Metadata,
							})
						}
					}

					// Broadcast log line
					pw.broadcaster.BroadcastLog("stdout", line, pw.lineNum)
				} else {
					lineBuffer = append(lineBuffer, buf[i])
				}
			}
		}
		if err != nil {
			if err != io.EOF {
				fmt.Fprintf(os.Stderr, "[ERROR] PTY read error: %v\n", err)
			}
			break
		}
	}

	// Broadcast any remaining line
	if len(lineBuffer) > 0 {
		line := string(lineBuffer)
		pw.lineNum++

		// Extract events from final line
		if pw.extractor != nil {
			events := pw.extractor.ProcessLine(line)
			for _, event := range events {
				pw.broadcaster.BroadcastExtraction(Match{
					Type:      event.EventType,
					Pattern:   event.Pattern,
					Value:     event.Matched,
					Line:      line,
					LineNum:   pw.lineNum,
					Timestamp: time.Now(),
					Metadata:  event.Metadata,
				})
			}
		}

		pw.broadcaster.BroadcastLog("stdout", line, pw.lineNum)
	}

	pw.stdoutLog.Flush()
}

// Wait waits for the process to complete
func (pw *ProcessWrapper) Wait() error {
	// Wait for process to exit
	pw.exitError = pw.cmd.Wait()

	// Capture exit code
	if pw.exitError != nil {
		if exitErr, ok := pw.exitError.(*exec.ExitError); ok {
			pw.exitCode = exitErr.ExitCode()
		}
	} else {
		pw.exitCode = 0
	}

	// Wait for streaming to complete
	pw.wg.Wait()

	// Calculate duration
	duration := time.Since(pw.startTime)

	// Record session completion in database
	if err := pw.recordSessionComplete(); err != nil {
		fmt.Printf("[Wrapper] Warning: Failed to record session completion: %v\n", err)
	}

	// Broadcast completion
	pw.broadcaster.BroadcastComplete(pw.exitCode, duration)

	// Close loggers
	pw.stdoutLog.Close()
	pw.stderrLog.Close()
	pw.ptyFile.Close()

	// Close extractor
	if pw.extractor != nil {
		if err := pw.extractor.Close(); err != nil {
			fmt.Printf("[Wrapper] Error closing extractor: %v\n", err)
		}
	}

	// Generate feedback report and close tracker
	if pw.feedback != nil {
		fmt.Println("\n" + pw.feedback.GenerateReport())
		if err := pw.feedback.Close(); err != nil {
			fmt.Printf("[Wrapper] Error closing feedback tracker: %v\n", err)
		}
	}

	return pw.exitError
}

// Stop gracefully stops the process
func (pw *ProcessWrapper) Stop() error {
	fmt.Printf("[Wrapper] Stopping %s...\n", pw.agentName)

	// Cancel context (sends SIGTERM)
	pw.cancel()

	// Give it 5 seconds to exit gracefully
	done := make(chan error)
	go func() {
		done <- pw.Wait()
	}()

	select {
	case <-time.After(5 * time.Second):
		// Force kill if not stopped
		fmt.Printf("[Wrapper] Force killing %s\n", pw.agentName)
		pw.cmd.Process.Kill()
		return <-done
	case err := <-done:
		return err
	}
}

// GetExitCode returns the process exit code
func (pw *ProcessWrapper) GetExitCode() int {
	return pw.exitCode
}

// GetLogPaths returns paths to stdout and stderr logs
func (pw *ProcessWrapper) GetLogPaths() (stdout, stderr string) {
	if pw.stdoutLog != nil {
		stdout = pw.stdoutLog.GetPath()
	}
	if pw.stderrLog != nil {
		stderr = pw.stderrLog.GetPath()
	}
	return
}

// GetBroadcaster returns the broadcaster for this process
func (pw *ProcessWrapper) GetBroadcaster() *Broadcaster {
	return pw.broadcaster
}

// GetRecentOutput reads the last n bytes from the stdout log file
// Returns empty string if log is not available or on error
func (pw *ProcessWrapper) GetRecentOutput(n int) string {
	if pw.stdoutLog == nil {
		return ""
	}

	logPath := pw.stdoutLog.GetPath()

	// Open file for reading
	file, err := os.Open(logPath)
	if err != nil {
		return ""
	}
	defer file.Close()

	// Get file size
	stat, err := file.Stat()
	if err != nil {
		return ""
	}

	fileSize := stat.Size()
	if fileSize == 0 {
		return ""
	}

	// Determine how many bytes to read
	bytesToRead := int64(n)
	if bytesToRead > fileSize {
		bytesToRead = fileSize
	}

	// Seek to position
	offset := fileSize - bytesToRead
	_, err = file.Seek(offset, 0)
	if err != nil {
		return ""
	}

	// Read the bytes
	buf := make([]byte, bytesToRead)
	bytesRead, err := file.Read(buf)
	if err != nil && err != io.EOF {
		return ""
	}

	return string(buf[:bytesRead])
}

// GetExtractor returns the extraction layer (may be nil if disabled)
func (pw *ProcessWrapper) GetExtractor() *ConfigurableExtractor {
	return pw.extractor
}

// GetExtractionStats returns extraction statistics if extractor is enabled
func (pw *ProcessWrapper) GetExtractionStats() map[string]interface{} {
	if pw.extractor == nil {
		return map[string]interface{}{
			"enabled": false,
		}
	}
	stats := pw.extractor.GetStats()
	stats["enabled"] = true
	return stats
}

// GetEnvironmentManager returns the environment manager (may be nil)
func (pw *ProcessWrapper) GetEnvironmentManager() *EnvironmentManager {
	return pw.envManager
}

// GetFeedbackTracker returns the feedback tracker (may be nil)
func (pw *ProcessWrapper) GetFeedbackTracker() *FeedbackTracker {
	return pw.feedback
}

// RecordFeedback records an operation outcome
func (pw *ProcessWrapper) RecordFeedback(outcome FeedbackOutcome) error {
	if pw.feedback == nil {
		return nil // Feedback tracking not enabled
	}
	return pw.feedback.RecordOutcome(outcome)
}

// GetEnvironmentInfo returns information about the current environment
func (pw *ProcessWrapper) GetEnvironmentInfo() map[string]interface{} {
	info := make(map[string]interface{})

	if pw.envManager != nil {
		info["environment"] = pw.envManager.GetEnvironmentName()
		info["working_dir"] = pw.envManager.GetWorkingDirectory()
		info["constraints"] = pw.envManager.GetConstraintsSummary()
	} else {
		info["environment"] = "none"
	}

	if pw.feedback != nil {
		info["feedback_enabled"] = true
		info["feedback_stats"] = pw.feedback.GetStats()
	} else {
		info["feedback_enabled"] = false
	}

	return info
}

// EnableDatabase configures database persistence for this process
func (pw *ProcessWrapper) EnableDatabase(sessionStore *data.SessionStore, extractionStore *data.ExtractionStore) error {
	pw.sessionStore = sessionStore
	pw.sessionID = generateSessionID(pw.agentName)

	// Note: ConfigurableExtractor doesn't support database integration yet
	// TODO: Add database support to ConfigurableExtractor

	return nil
}

// DisableDatabase turns off database persistence
func (pw *ProcessWrapper) DisableDatabase() {
	pw.sessionStore = nil
	pw.sessionID = ""
}

// GetSessionID returns the current session ID
func (pw *ProcessWrapper) GetSessionID() string {
	return pw.sessionID
}

// recordSessionStart creates a session record in the database
func (pw *ProcessWrapper) recordSessionStart() error {
	if pw.sessionStore == nil || pw.sessionID == "" {
		return nil // Database not enabled
	}

	return pw.sessionStore.CreateSession(pw.agentName, pw.sessionID, pw.environment)
}

// recordSessionComplete marks the session as completed in the database
func (pw *ProcessWrapper) recordSessionComplete() error {
	if pw.sessionStore == nil || pw.sessionID == "" {
		return nil // Database not enabled
	}

	// Calculate stats
	stats := data.SessionStats{
		TotalLines:       pw.lineNum,
		TotalExtractions: 0, // TODO: Get from ConfigurableExtractor when supported
		TotalFeedback:    0, // TODO: Get from FeedbackTracker when supported
	}

	return pw.sessionStore.CompleteSession(pw.sessionID, pw.exitCode, stats)
}

// recordStateChange records a state transition in the database
func (pw *ProcessWrapper) recordStateChange(state string, metadata map[string]interface{}) error {
	if pw.sessionStore == nil || pw.sessionID == "" {
		return nil // Database not enabled
	}

	change := &data.StateChange{
		SessionID: pw.sessionID,
		Timestamp: time.Now(),
		State:     state,
		Metadata:  metadata,
	}

	if pw.exitCode >= 0 {
		change.ExitCode = &pw.exitCode
	}

	return pw.sessionStore.RecordStateChange(change)
}

// generateSessionID generates a unique session ID for a process
func generateSessionID(agentName string) string {
	timestamp := time.Now().Format("20060102-150405")
	return fmt.Sprintf("%s-%s", agentName, timestamp)
}

// Pause pauses the process (SIGSTOP)
func (pw *ProcessWrapper) Pause() error {
	if pw.cmd == nil || pw.cmd.Process == nil {
		return fmt.Errorf("process not running")
	}

	// Send SIGSTOP signal (Unix only)
	if err := pw.cmd.Process.Signal(syscall.SIGSTOP); err != nil {
		return fmt.Errorf("failed to pause process: %w", err)
	}

	// Record state change
	pw.recordStateChange("paused", map[string]interface{}{
		"action": "pause",
	})

	return nil
}

// Resume resumes the process (SIGCONT)
func (pw *ProcessWrapper) Resume() error {
	if pw.cmd == nil || pw.cmd.Process == nil {
		return fmt.Errorf("process not running")
	}

	// Send SIGCONT signal (Unix only)
	if err := pw.cmd.Process.Signal(syscall.SIGCONT); err != nil {
		return fmt.Errorf("failed to resume process: %w", err)
	}

	// Record state change
	pw.recordStateChange("resumed", map[string]interface{}{
		"action": "resume",
	})

	return nil
}

// SendSignal sends a custom signal to the process
func (pw *ProcessWrapper) SendSignal(signalName string) error {
	if pw.cmd == nil || pw.cmd.Process == nil {
		return fmt.Errorf("process not running")
	}

	// Map signal names to syscall signals (Unix)
	signals := map[string]syscall.Signal{
		"SIGINT":  syscall.SIGINT,
		"SIGTERM": syscall.SIGTERM,
		"SIGKILL": syscall.SIGKILL,
		"SIGHUP":  syscall.SIGHUP,
		"SIGUSR1": syscall.SIGUSR1,
		"SIGUSR2": syscall.SIGUSR2,
	}

	signal, ok := signals[signalName]
	if !ok {
		return fmt.Errorf("unknown signal: %s", signalName)
	}

	if err := pw.cmd.Process.Signal(signal); err != nil {
		return fmt.Errorf("failed to send signal %s: %w", signalName, err)
	}

	// Record state change
	pw.recordStateChange("signal_sent", map[string]interface{}{
		"signal": signalName,
	})

	return nil
}

// GetState returns the current process state
func (pw *ProcessWrapper) GetState() string {
	if pw.cmd == nil {
		return "not_started"
	}

	if pw.cmd.Process == nil {
		return "not_started"
	}

	if pw.exitCode >= 0 {
		if pw.exitCode == 0 {
			return "completed"
		}
		return "failed"
	}

	return "running"
}
