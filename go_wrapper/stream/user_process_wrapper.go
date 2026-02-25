package stream

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/creack/pty"
)

// UserProcessWrapper wraps a process running as a specific Unix user
type UserProcessWrapper struct {
	agentName   string
	username    string
	logsDir     string
	environment string
	cmd         *exec.Cmd
	stdoutLog   *StreamLogger
	stderrLog   *StreamLogger
	ptyFile     *os.File
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	exitCode    int
	exitError   error
	broadcaster *Broadcaster
	envManager  *EnvironmentManager
	feedback    *FeedbackTracker
	userManager *UserManager
	workerUser  *WorkerUser
	startTime   time.Time
}

// NewUserProcessWrapper creates a process wrapper that runs as a specific user
func NewUserProcessWrapper(agentName, username, logsDir, environment string, command string, args ...string) (*UserProcessWrapper, error) {
	// Initialize user manager
	userManager, err := NewUserManager("config/worker_users.json")
	if err != nil {
		return nil, fmt.Errorf("failed to initialize user manager: %w", err)
	}

	// Get worker user
	workerUser, err := userManager.GetUser(username)
	if err != nil {
		return nil, fmt.Errorf("worker user not found: %s - %w", username, err)
	}

	// Check if we can sudo
	if !CanSudo() {
		return nil, fmt.Errorf("sudo access required to run as user %s", username)
	}

	ctx, cancel := context.WithCancel(context.Background())

	// Build command to run as user
	// We use sudo -u to switch user, with environment preserved
	fullCommand := command
	if len(args) > 0 {
		fullCommand = command + " " + strings.Join(args, " ")
	}

	// Create command that runs as the specified user
	sudoArgs := []string{
		"-u", username,
		"-i", // Run as login shell to get user's environment
		"bash", "-c",
		fullCommand,
	}

	upw := &UserProcessWrapper{
		agentName:   agentName,
		username:    username,
		logsDir:     logsDir,
		environment: environment,
		cmd:         exec.CommandContext(ctx, "sudo", sudoArgs...),
		ctx:         ctx,
		cancel:      cancel,
		exitCode:    -1,
		broadcaster: NewBroadcaster(),
		userManager: userManager,
		workerUser:  workerUser,
	}

	// Initialize environment manager
	envConfigPath := "config/environments.json"
	envManager, err := NewEnvironmentManager(envConfigPath, environment)
	if err != nil {
		fmt.Printf("[User Wrapper] Environment manager disabled: %v\n", err)
	} else {
		upw.envManager = envManager

		// Setup environment for the worker user
		envSetup := NewEnvironmentSetup(envManager.GetEnvironment(), agentName)
		if err := envSetup.Initialize(); err != nil {
			fmt.Printf("[User Wrapper] Warning: Environment setup failed: %v\n", err)
		}
	}

	// Initialize feedback tracker
	if upw.envManager != nil && upw.envManager.ShouldTrackFeedback() {
		feedbackPath := filepath.Join(workerUser.WorkspaceDir, "data", "feedback")
		feedback, err := NewFeedbackTracker(agentName, environment, feedbackPath)
		if err != nil {
			fmt.Printf("[User Wrapper] Feedback tracker disabled: %v\n", err)
		} else {
			upw.feedback = feedback
		}
	}

	fmt.Printf("[User Wrapper] Initialized for agent %s as user %s (role: %s)\n",
		agentName, username, workerUser.Role)
	fmt.Printf("[User Wrapper] Workspace: %s\n", workerUser.WorkspaceDir)
	fmt.Printf("[User Wrapper] Git: %s <%s>\n", workerUser.GitConfig.Name, workerUser.GitConfig.Email)

	return upw, nil
}

// Start starts the process as the specified user
func (upw *UserProcessWrapper) Start() error {
	// Create loggers
	var err error
	logPath := filepath.Join(upw.logsDir, upw.agentName)
	upw.stdoutLog, err = NewStreamLogger(upw.agentName, "stdout", logPath)
	if err != nil {
		return fmt.Errorf("failed to create stdout logger: %w", err)
	}

	upw.stderrLog, err = NewStreamLogger(upw.agentName, "stderr", logPath)
	if err != nil {
		upw.stdoutLog.Close()
		return fmt.Errorf("failed to create stderr logger: %w", err)
	}

	// Set working directory to user's workspace
	upw.cmd.Dir = upw.workerUser.WorkspaceDir

	// Set environment variables for the user
	upw.cmd.Env = append(os.Environ(),
		fmt.Sprintf("HOME=%s", upw.workerUser.HomeDir),
		fmt.Sprintf("USER=%s", upw.username),
		fmt.Sprintf("LOGNAME=%s", upw.username),
		fmt.Sprintf("ARCHITECT_ENV=%s", upw.environment),
		fmt.Sprintf("ARCHITECT_AGENT=%s", upw.agentName),
		fmt.Sprintf("ARCHITECT_ROLE=%s", upw.workerUser.Role),
	)

	// Start process with PTY
	ptmx, err := pty.Start(upw.cmd)
	if err != nil {
		upw.stdoutLog.Close()
		upw.stderrLog.Close()
		return fmt.Errorf("failed to start process as user %s: %w", upw.username, err)
	}
	upw.ptyFile = ptmx

	upw.startTime = time.Now()

	fmt.Printf("[User Wrapper] Started %s as %s (PID: %d)\n",
		upw.agentName, upw.username, upw.cmd.Process.Pid)
	fmt.Printf("[User Wrapper] Logs: %s\n", upw.stdoutLog.GetPath())

	// Record start in feedback tracker
	if upw.feedback != nil {
		upw.feedback.RecordSuccess("agent_start", "start_as_user",
			fmt.Sprintf("Started as %s", upw.username), 0, map[string]interface{}{
				"username":  upw.username,
				"role":      upw.workerUser.Role,
				"workspace": upw.workerUser.WorkspaceDir,
			})
	}

	// Broadcast start state
	upw.broadcaster.BroadcastState("started", map[string]interface{}{
		"pid":       upw.cmd.Process.Pid,
		"username":  upw.username,
		"role":      upw.workerUser.Role,
		"workspace": upw.workerUser.WorkspaceDir,
		"logs_dir":  upw.logsDir,
		"timestamp": upw.startTime,
	})

	// Start streaming goroutine
	upw.wg.Add(1)
	go upw.streamOutput()

	return nil
}

// streamOutput reads from PTY and writes to logs
func (upw *UserProcessWrapper) streamOutput() {
	defer upw.wg.Done()

	buf := make([]byte, 4096)

	for {
		n, err := upw.ptyFile.Read(buf)
		if n > 0 {
			// Write to stdout log
			upw.stdoutLog.Write(buf[:n])

			// Also write to actual stdout
			os.Stdout.Write(buf[:n])

			// Broadcast output as log event
			upw.broadcaster.BroadcastLog("stdout", string(buf[:n]), 0)
		}

		if err != nil {
			break
		}
	}
}

// Wait waits for the process to complete
func (upw *UserProcessWrapper) Wait() error {
	// Wait for process
	upw.exitError = upw.cmd.Wait()

	// Get exit code
	if upw.exitError != nil {
		if exitErr, ok := upw.exitError.(*exec.ExitError); ok {
			upw.exitCode = exitErr.ExitCode()
		}
	} else {
		upw.exitCode = 0
	}

	duration := time.Since(upw.startTime)

	fmt.Printf("[User Wrapper] %s completed (exit code: %d, duration: %s)\n",
		upw.agentName, upw.exitCode, duration)

	// Record completion
	if upw.feedback != nil {
		if upw.exitCode == 0 {
			upw.feedback.RecordSuccess("agent_completion", "complete",
				"Agent completed successfully", duration, map[string]interface{}{
					"exit_code": upw.exitCode,
					"username":  upw.username,
				})
		} else {
			upw.feedback.RecordFailure("agent_completion", "complete",
				fmt.Sprintf("Exit code %d", upw.exitCode), duration, map[string]interface{}{
					"exit_code": upw.exitCode,
					"username":  upw.username,
				})
		}
	}

	// Wait for streaming to finish
	upw.wg.Wait()

	// Close resources
	if upw.ptyFile != nil {
		upw.ptyFile.Close()
	}

	if upw.stdoutLog != nil {
		upw.stdoutLog.Close()
	}

	if upw.stderrLog != nil {
		upw.stderrLog.Close()
	}

	if upw.feedback != nil {
		report := upw.feedback.GenerateReport()
		if report != "" {
			fmt.Printf("\n%s\n", report)
		}
		upw.feedback.Close()
	}

	// Broadcast completion
	upw.broadcaster.BroadcastState("completed", map[string]interface{}{
		"exit_code": upw.exitCode,
		"duration":  duration.Seconds(),
		"username":  upw.username,
	})

	return upw.exitError
}

// Stop stops the process
func (upw *UserProcessWrapper) Stop() error {
	if upw.cmd.Process != nil {
		return upw.cmd.Process.Kill()
	}
	return nil
}

// GetExitCode returns the process exit code
func (upw *UserProcessWrapper) GetExitCode() int {
	return upw.exitCode
}

// GetUsername returns the username the process is running as
func (upw *UserProcessWrapper) GetUsername() string {
	return upw.username
}

// GetRole returns the user's role (worker/manager)
func (upw *UserProcessWrapper) GetRole() string {
	return upw.workerUser.Role
}

// GetWorkspace returns the user's workspace directory
func (upw *UserProcessWrapper) GetWorkspace() string {
	return upw.workerUser.WorkspaceDir
}

// GetGitConfig returns the user's git configuration
func (upw *UserProcessWrapper) GetGitConfig() GitConfig {
	return upw.workerUser.GitConfig
}

// GetBroadcaster returns the broadcaster
func (upw *UserProcessWrapper) GetBroadcaster() *Broadcaster {
	return upw.broadcaster
}
