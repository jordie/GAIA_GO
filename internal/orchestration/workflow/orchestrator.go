package workflow

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Orchestrator manages workflow execution with task dependency resolution and parallel execution
type Orchestrator struct {
	db              *sql.DB
	executor        *Executor
	workflows       map[string]*Workflow
	workflowMutex   sync.RWMutex
	maxConcurrent   int
	semaphore       chan struct{}
	closeOnce       sync.Once
	closeChan       chan struct{}
}

// NewOrchestrator creates a new workflow orchestrator
func NewOrchestrator(db *sql.DB, executor *Executor, maxConcurrent int) *Orchestrator {
	orch := &Orchestrator{
		db:            db,
		executor:      executor,
		workflows:     make(map[string]*Workflow),
		maxConcurrent: maxConcurrent,
		semaphore:     make(chan struct{}, maxConcurrent),
		closeChan:     make(chan struct{}),
	}

	return orch
}

// CreateWorkflow creates a new workflow from a definition
func (o *Orchestrator) CreateWorkflow(def *WorkflowDefinition, variables map[string]interface{}) (*Workflow, error) {
	parser := NewParser("")
	workflow, err := parser.ToWorkflow(def, variables)
	if err != nil {
		return nil, err
	}

	workflow.ID = uuid.New().String()

	// Persist workflow
	if err := o.persistWorkflow(workflow); err != nil {
		return nil, fmt.Errorf("failed to persist workflow: %w", err)
	}

	// Add to cache
	o.workflowMutex.Lock()
	o.workflows[workflow.ID] = workflow
	o.workflowMutex.Unlock()

	return workflow, nil
}

// GetWorkflow retrieves a workflow by ID
func (o *Orchestrator) GetWorkflow(workflowID string) (*Workflow, error) {
	o.workflowMutex.RLock()
	workflow, exists := o.workflows[workflowID]
	o.workflowMutex.RUnlock()

	if !exists {
		// Try database
		var w Workflow
		var varsJSON string

		err := o.db.QueryRow(
			"SELECT id, name, description, version, status, variables, created_at, started_at, completed_at, error FROM gaia_workflows WHERE id = ?",
			workflowID,
		).Scan(&w.ID, &w.Name, &w.Description, &w.Version, &w.Status, &varsJSON, &w.CreatedAt, &w.StartedAt, &w.CompletedAt, &w.Error)

		if err != nil {
			if err == sql.ErrNoRows {
				return nil, fmt.Errorf("workflow not found: %s", workflowID)
			}
			return nil, fmt.Errorf("failed to query workflow: %w", err)
		}

		if varsJSON != "" {
			_ = json.Unmarshal([]byte(varsJSON), &w.Variables)
		}

		// Load tasks from database
		w.Tasks = make(map[string]*Task)
		if err := o.loadWorkflowTasks(&w); err != nil {
			return nil, fmt.Errorf("failed to load tasks: %w", err)
		}

		// Cache in memory
		o.workflowMutex.Lock()
		o.workflows[workflowID] = &w
		o.workflowMutex.Unlock()

		return &w, nil
	}

	return workflow, nil
}

// StartWorkflow executes a workflow with dependency resolution
func (o *Orchestrator) StartWorkflow(ctx context.Context, workflowID string) error {
	workflow, err := o.GetWorkflow(workflowID)
	if err != nil {
		return err
	}

	if workflow.Status != WorkflowStatusPending && workflow.Status != WorkflowStatusFailed {
		return fmt.Errorf("workflow cannot be started in status: %s", workflow.Status)
	}

	// Update status
	now := time.Now()
	workflow.Status = WorkflowStatusRunning
	workflow.StartedAt = &now
	if err := o.persistWorkflow(workflow); err != nil {
		return fmt.Errorf("failed to update workflow status: %w", err)
	}

	// Build DAG and execute
	dag := NewTaskDAG(workflow)

	// Check for cycles
	if dag.IsCyclic() {
		workflow.Status = WorkflowStatusFailed
		workflow.Error = "circular dependency detected"
		_ = o.persistWorkflow(workflow)
		return fmt.Errorf("workflow has circular dependencies")
	}

	// Execute workflow
	go o.executeWorkflow(ctx, workflow, dag)

	return nil
}

// StopWorkflow cancels an in-progress workflow
func (o *Orchestrator) StopWorkflow(workflowID string) error {
	workflow, err := o.GetWorkflow(workflowID)
	if err != nil {
		return err
	}

	if workflow.Status != WorkflowStatusRunning {
		return fmt.Errorf("workflow is not running")
	}

	// Cancel all running tasks
	for _, task := range workflow.Tasks {
		if task.Status == TaskStatusRunning || task.Status == TaskStatusRetrying {
			task.Status = TaskStatusSkipped
			_ = o.persistTask(task)
		}
	}

	workflow.Status = WorkflowStatusCanceled
	now := time.Now()
	workflow.CompletedAt = &now

	return o.persistWorkflow(workflow)
}

// GetTask retrieves a specific task from a workflow
func (o *Orchestrator) GetTask(workflowID, taskID string) (*Task, error) {
	workflow, err := o.GetWorkflow(workflowID)
	if err != nil {
		return nil, err
	}

	task, exists := workflow.Tasks[taskID]
	if !exists {
		return nil, fmt.Errorf("task not found: %s", taskID)
	}

	return task, nil
}

// GetTaskLogs returns the output/logs from a task
func (o *Orchestrator) GetTaskLogs(workflowID, taskID string) (string, error) {
	task, err := o.GetTask(workflowID, taskID)
	if err != nil {
		return "", err
	}

	return task.Output, nil
}

// ListWorkflows returns all workflows
func (o *Orchestrator) ListWorkflows(filter WorkflowStatus) ([]*Workflow, error) {
	o.workflowMutex.RLock()
	workflows := make([]*Workflow, 0)
	for _, w := range o.workflows {
		if filter == "" || w.Status == filter {
			workflows = append(workflows, w)
		}
	}
	o.workflowMutex.RUnlock()

	return workflows, nil
}

// Close gracefully shuts down the orchestrator
func (o *Orchestrator) Close() error {
	o.closeOnce.Do(func() {
		close(o.closeChan)
	})
	return nil
}

// Helper methods

func (o *Orchestrator) executeWorkflow(ctx context.Context, workflow *Workflow, dag *TaskDAG) {
	levels, err := dag.TopologicalSort()
	if err != nil {
		workflow.Status = WorkflowStatusFailed
		workflow.Error = err.Error()
		_ = o.persistWorkflow(workflow)
		return
	}

	results := make(map[string]TaskResult)

	// Execute each level sequentially (within a level, tasks can run in parallel)
	for _, level := range levels {
		select {
		case <-ctx.Done():
			workflow.Status = WorkflowStatusCanceled
			_ = o.persistWorkflow(workflow)
			return
		default:
		}

		// Execute all tasks in this level in parallel
		var wg sync.WaitGroup
		for _, task := range level {
			wg.Add(1)

			go func(t *Task) {
				defer wg.Done()

				// Acquire semaphore slot
				select {
				case o.semaphore <- struct{}{}:
					defer func() { <-o.semaphore }()
				case <-ctx.Done():
					return
				}

				// Execute task
				result := o.executeTask(ctx, workflow, t)
				results[t.ID] = result
				dag.MarkCompleted(t.ID)
			}(task)
		}

		wg.Wait()

		// Check if any task failed
		for _, task := range level {
			if task.Status == TaskStatusFailed {
				if task.OnError == ErrorActionFail {
					workflow.Status = WorkflowStatusFailed
					workflow.Error = fmt.Sprintf("task %s failed", task.Name)
					now := time.Now()
					workflow.CompletedAt = &now
					_ = o.persistWorkflow(workflow)
					return
				} else if task.OnError == ErrorActionContinue {
					// Continue to next level
					continue
				}
			}
		}
	}

	// All tasks completed successfully
	workflow.Status = WorkflowStatusCompleted
	now := time.Now()
	workflow.CompletedAt = &now
	_ = o.persistWorkflow(workflow)
}

func (o *Orchestrator) executeTask(ctx context.Context, workflow *Workflow, task *Task) TaskResult {
	result := TaskResult{
		TaskID:      task.ID,
		Status:      TaskStatusCompleted,
		CompletedAt: time.Now(),
	}

	startTime := time.Now()

	// Check if task should be retried
	var lastErr error
	for attempt := 0; attempt <= task.MaxRetries; attempt++ {
		if attempt > 0 {
			task.Status = TaskStatusRetrying
			task.RetryCount = attempt
			_ = o.persistTask(task)
		}

		task.Status = TaskStatusRunning
		now := time.Now()
		task.StartedAt = &now
		_ = o.persistTask(task)

		// Execute with timeout
		execCtx, cancel := context.WithTimeout(ctx, task.Timeout)

		output, err := o.executor.Execute(execCtx, workflow, task)
		cancel()

		task.Output = output

		if err == nil {
			// Success
			task.Status = TaskStatusCompleted
			result.Status = TaskStatusCompleted
			lastErr = nil
			break
		}

		lastErr = err
		task.Error = err.Error()
		result.Error = err.Error()

		if attempt < task.MaxRetries {
			// Wait before retry
			select {
			case <-time.After(time.Second * time.Duration((attempt+1)*2)): // Exponential backoff
			case <-ctx.Done():
				task.Status = TaskStatusSkipped
				result.Status = TaskStatusSkipped
				_ = o.persistTask(task)
				return result
			}
		}
	}

	// Final result
	if lastErr != nil {
		task.Status = TaskStatusFailed
		result.Status = TaskStatusFailed
	}

	now := time.Now()
	task.CompletedAt = &now
	result.Duration = now.Sub(startTime)
	result.CompletedAt = now
	_ = o.persistTask(task)

	return result
}

func (o *Orchestrator) persistWorkflow(workflow *Workflow) error {
	varsJSON, _ := json.Marshal(workflow.Variables)

	_, err := o.db.Exec(
		"INSERT OR REPLACE INTO gaia_workflows (id, name, description, version, status, variables, created_at, started_at, completed_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		workflow.ID, workflow.Name, workflow.Description, workflow.Version, workflow.Status, string(varsJSON), workflow.CreatedAt, workflow.StartedAt, workflow.CompletedAt, workflow.Error,
	)

	return err
}

func (o *Orchestrator) persistTask(task *Task) error {
	timeoutSeconds := int64(task.Timeout.Seconds())

	_, err := o.db.Exec(
		"INSERT OR REPLACE INTO gaia_workflow_tasks (id, workflow_id, name, type, agent, command, status, work_dir, timeout_seconds, max_retries, retry_count, on_error, output, error, started_at, completed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		task.ID, "", task.Name, task.Type, task.Agent, task.Command, task.Status, task.WorkDir, timeoutSeconds, task.MaxRetries, task.RetryCount, task.OnError, task.Output, task.Error, task.StartedAt, task.CompletedAt, time.Now(),
	)

	return err
}

func (o *Orchestrator) loadWorkflowTasks(workflow *Workflow) error {
	rows, err := o.db.QueryContext(context.Background(),
		"SELECT id, name, type, agent, command, status, work_dir, timeout_seconds, max_retries, retry_count, on_error, output, error, started_at, completed_at FROM gaia_workflow_tasks WHERE workflow_id = ?",
		workflow.ID,
	)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var task Task
		var timeoutSeconds int64

		err := rows.Scan(&task.ID, &task.Name, &task.Type, &task.Agent, &task.Command, &task.Status, &task.WorkDir, &timeoutSeconds, &task.MaxRetries, &task.RetryCount, &task.OnError, &task.Output, &task.Error, &task.StartedAt, &task.CompletedAt)
		if err != nil {
			continue
		}

		task.Timeout = time.Duration(timeoutSeconds) * time.Second
		workflow.Tasks[task.ID] = &task
	}

	return rows.Err()
}
