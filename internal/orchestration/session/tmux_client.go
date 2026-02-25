package session

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// TmuxClient wraps tmux CLI commands for programmatic control
type TmuxClient struct {
	tmuxPath string
}

// NewTmuxClient creates a new tmux client, checking for tmux binary availability
func NewTmuxClient() (*TmuxClient, error) {
	// Check if tmux is available
	tmuxPath, err := exec.LookPath("tmux")
	if err != nil {
		return nil, fmt.Errorf("tmux not found in PATH: %w", err)
	}

	return &TmuxClient{
		tmuxPath: tmuxPath,
	}, nil
}

// NewSession creates a new tmux session with the given name
func (tc *TmuxClient) NewSession(ctx context.Context, name, workDir string) (string, error) {
	// Format: tmux new-session -d -s <name> -c <workdir>
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "new-session", "-d", "-s", name, "-c", workDir)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to create session %s: %s: %w", name, stderr.String(), err)
	}

	return name, nil
}

// KillSession terminates a tmux session
func (tc *TmuxClient) KillSession(ctx context.Context, name string) error {
	// Format: tmux kill-session -t <name>
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "kill-session", "-t", name)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		// Session might not exist, which is not an error for cleanup
		if strings.Contains(stderr.String(), "no session") {
			return nil
		}
		return fmt.Errorf("failed to kill session %s: %s: %w", name, stderr.String(), err)
	}

	return nil
}

// NewWindow creates a new window in a session
func (tc *TmuxClient) NewWindow(ctx context.Context, session, windowName string) (string, error) {
	// Format: tmux new-window -t <session> -n <name>
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "new-window", "-t", session, "-n", windowName)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to create window %s in session %s: %s: %w", windowName, session, stderr.String(), err)
	}

	// Window index is returned as output
	return strings.TrimSpace(stdout.String()), nil
}

// SplitPane splits a pane vertically or horizontally
func (tc *TmuxClient) SplitPane(ctx context.Context, target string, vertical bool) (string, error) {
	args := []string{"split-window", "-t", target}

	if vertical {
		args = append(args, "-h") // Horizontal split for vertical panes
	} else {
		args = append(args, "-v") // Vertical split for horizontal panes
	}

	cmd := exec.CommandContext(ctx, tc.tmuxPath, args...)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to split pane at %s: %s: %w", target, stderr.String(), err)
	}

	// Return the new pane index
	return "0", nil
}

// SendKeys sends keys to a target (session, window, or pane)
// Format: tmux send-keys -t <target> <keys> Enter
func (tc *TmuxClient) SendKeys(ctx context.Context, target string, keys string, sendEnter bool) error {
	args := []string{"send-keys", "-t", target, keys}

	if sendEnter {
		args = append(args, "Enter")
	}

	cmd := exec.CommandContext(ctx, tc.tmuxPath, args...)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to send keys to %s: %s: %w", target, stderr.String(), err)
	}

	return nil
}

// CapturePane captures the current contents of a pane
// Format: tmux capture-pane -t <target> -p
func (tc *TmuxClient) CapturePane(ctx context.Context, target string) (string, error) {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "capture-pane", "-t", target, "-p")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to capture pane %s: %s: %w", target, stderr.String(), err)
	}

	return stdout.String(), nil
}

// ListSessions returns all active tmux sessions
// Format: tmux list-sessions -F "#{session_name}"
func (tc *TmuxClient) ListSessions(ctx context.Context) ([]string, error) {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "list-sessions", "-F", "#{session_name}")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		// No sessions is not an error
		if strings.Contains(stderr.String(), "no server running") {
			return []string{}, nil
		}
		return nil, fmt.Errorf("failed to list sessions: %s: %w", stderr.String(), err)
	}

	output := stdout.String()
	if output == "" {
		return []string{}, nil
	}

	return strings.Split(strings.TrimSpace(output), "\n"), nil
}

// ListWindows returns all windows in a session
// Format: tmux list-windows -t <session> -F "#{window_index}:#{window_name}"
func (tc *TmuxClient) ListWindows(ctx context.Context, session string) (map[int]string, error) {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "list-windows", "-t", session, "-F", "#{window_index}:#{window_name}")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("failed to list windows for session %s: %s: %w", session, stderr.String(), err)
	}

	windows := make(map[int]string)
	output := stdout.String()
	if output == "" {
		return windows, nil
	}

	lines := strings.Split(strings.TrimSpace(output), "\n")
	for _, line := range lines {
		parts := strings.Split(line, ":")
		if len(parts) >= 2 {
			// Index:Name format
			var index int
			fmt.Sscanf(parts[0], "%d", &index)
			windows[index] = parts[1]
		}
	}

	return windows, nil
}

// ListPanes returns all panes in a window
// Format: tmux list-panes -t <session>:<window> -F "#{pane_index}:#{pane_pid}"
func (tc *TmuxClient) ListPanes(ctx context.Context, target string) ([]int, error) {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "list-panes", "-t", target, "-F", "#{pane_index}")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("failed to list panes for target %s: %s: %w", target, stderr.String(), err)
	}

	var panes []int
	output := stdout.String()
	if output == "" {
		return panes, nil
	}

	lines := strings.Split(strings.TrimSpace(output), "\n")
	for _, line := range lines {
		var index int
		if _, err := fmt.Sscanf(line, "%d", &index); err == nil {
			panes = append(panes, index)
		}
	}

	return panes, nil
}

// SelectWindow selects/activates a window
func (tc *TmuxClient) SelectWindow(ctx context.Context, target string) error {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "select-window", "-t", target)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to select window %s: %s: %w", target, stderr.String(), err)
	}

	return nil
}

// SelectPane selects/activates a pane
func (tc *TmuxClient) SelectPane(ctx context.Context, target string) error {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "select-pane", "-t", target)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to select pane %s: %s: %w", target, stderr.String(), err)
	}

	return nil
}

// KillPane kills a specific pane
func (tc *TmuxClient) KillPane(ctx context.Context, target string) error {
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "kill-pane", "-t", target)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to kill pane %s: %s: %w", target, stderr.String(), err)
	}

	return nil
}

// GetSessionPath returns the working directory of a session
func (tc *TmuxClient) GetSessionPath(ctx context.Context, session string) (string, error) {
	// Get the working directory from the first pane of the first window
	cmd := exec.CommandContext(ctx, tc.tmuxPath, "display-message", "-t", session, "-p", "#{client_cwd}")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		// Fallback: try to get from environment
		return os.Getenv("HOME"), nil
	}

	path := strings.TrimSpace(stdout.String())
	if path == "" {
		return os.Getenv("HOME"), nil
	}

	return path, nil
}
