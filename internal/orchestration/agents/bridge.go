package agents

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Bridge manages coordination between multiple AI agents
type Bridge struct {
	db              *sql.DB
	agents          map[AgentID]Agent
	agentsMutex     sync.RWMutex
	taskQueue       chan *AgentTask
	results         map[string]*AgentResult
	resultsMutex    sync.RWMutex
	maxQueueSize    int
	closeOnce       sync.Once
	closeChan       chan struct{}
	taskWorkers     int
}

// NewBridge creates a new agent bridge
func NewBridge(db *sql.DB, taskWorkers int) *Bridge {
	if taskWorkers == 0 {
		taskWorkers = 4 // Default workers
	}

	bridge := &Bridge{
		db:            db,
		agents:        make(map[AgentID]Agent),
		taskQueue:     make(chan *AgentTask, 100),
		results:       make(map[string]*AgentResult),
		maxQueueSize:  100,
		taskWorkers:   taskWorkers,
		closeChan:     make(chan struct{}),
	}

	// Start task processing workers
	for i := 0; i < taskWorkers; i++ {
		go bridge.taskWorker()
	}

	return bridge
}

// RegisterAgent registers an agent with the bridge
func (b *Bridge) RegisterAgent(agent Agent) error {
	b.agentsMutex.Lock()
	defer b.agentsMutex.Unlock()

	agentID := agent.GetID()

	// Check if already registered
	if _, exists := b.agents[agentID]; exists {
		return fmt.Errorf("agent already registered: %s", agentID)
	}

	b.agents[agentID] = agent
	return nil
}

// UnregisterAgent removes an agent from the bridge
func (b *Bridge) UnregisterAgent(agentID AgentID) error {
	b.agentsMutex.Lock()
	defer b.agentsMutex.Unlock()

	if _, exists := b.agents[agentID]; !exists {
		return fmt.Errorf("agent not found: %s", agentID)
	}

	delete(b.agents, agentID)
	return nil
}

// GetAgent retrieves an agent by ID
func (b *Bridge) GetAgent(agentID AgentID) (Agent, error) {
	b.agentsMutex.RLock()
	defer b.agentsMutex.RUnlock()

	agent, exists := b.agents[agentID]
	if !exists {
		return nil, fmt.Errorf("agent not found: %s", agentID)
	}

	return agent, nil
}

// ListAgents returns all registered agents
func (b *Bridge) ListAgents() []Agent {
	b.agentsMutex.RLock()
	defer b.agentsMutex.RUnlock()

	agents := make([]Agent, 0, len(b.agents))
	for _, agent := range b.agents {
		agents = append(agents, agent)
	}

	return agents
}

// ExecuteTask queues a single task for execution
func (b *Bridge) ExecuteTask(ctx context.Context, task *AgentTask) (*AgentResult, error) {
	// Validate agent exists
	agent, err := b.GetAgent(task.AgentID)
	if err != nil {
		return nil, fmt.Errorf("agent not available: %w", err)
	}

	// Set task ID if not provided
	if task.ID == "" {
		task.ID = uuid.New().String()
	}

	task.CreatedAt = time.Now()

	// Queue task
	select {
	case b.taskQueue <- task:
	case <-b.closeChan:
		return nil, fmt.Errorf("bridge is shutting down")
	case <-ctx.Done():
		return nil, ctx.Err()
	}

	// Execute directly if synchronous execution is needed
	// For now, queue and return eventually
	return agent.Execute(ctx, task)
}

// ExecuteParallel executes multiple tasks concurrently
func (b *Bridge) ExecuteParallel(ctx context.Context, tasks []*AgentTask) ([]*AgentResult, error) {
	results := make([]*AgentResult, len(tasks))
	var wg sync.WaitGroup
	errors := make([]error, len(tasks))

	for i, task := range tasks {
		wg.Add(1)

		go func(index int, t *AgentTask) {
			defer wg.Done()

			result, err := b.ExecuteTask(ctx, t)
			if err != nil {
				errors[index] = err
			}
			results[index] = result
		}(i, task)
	}

	wg.Wait()

	// Check for errors
	for _, err := range errors {
		if err != nil {
			return results, err
		}
	}

	return results, nil
}

// CoordinateWorkflow executes a workflow with proper agent assignment
// This integrates with the Workflow Orchestrator from Component 2
func (b *Bridge) CoordinateWorkflow(ctx context.Context, workflowTasks []*AgentTask) (map[string]*AgentResult, error) {
	results := make(map[string]*AgentResult)
	resultsMutex := sync.RWMutex{}

	// Group tasks by agent for better load distribution
	tasksByAgent := make(map[AgentID][]*AgentTask)
	for _, task := range workflowTasks {
		tasksByAgent[task.AgentID] = append(tasksByAgent[task.AgentID], task)
	}

	var wg sync.WaitGroup

	// Execute tasks for each agent
	for agentID, agentTasks := range tasksByAgent {
		wg.Add(1)

		go func(aID AgentID, tasks []*AgentTask) {
			defer wg.Done()

			agent, err := b.GetAgent(aID)
			if err != nil {
				return
			}

			// Execute tasks sequentially or in parallel based on agent capacity
			for _, task := range tasks {
				result, err := agent.Execute(ctx, task)

				resultsMutex.Lock()
				if result != nil {
					results[task.ID] = result
				}
				resultsMutex.Unlock()

				if err != nil && task.Priority > 5 {
					// High priority task, propagate error
					continue
				}
			}
		}(agentID, agentTasks)
	}

	wg.Wait()

	return results, nil
}

// GetResult retrieves the result of a completed task
func (b *Bridge) GetResult(taskID string) (*AgentResult, error) {
	b.resultsMutex.RLock()
	defer b.resultsMutex.RUnlock()

	result, exists := b.results[taskID]
	if !exists {
		return nil, fmt.Errorf("result not found: %s", taskID)
	}

	return result, nil
}

// GetAgentStats returns statistics for a specific agent
func (b *Bridge) GetAgentStats(agentID AgentID) (*AgentStats, error) {
	agent, err := b.GetAgent(agentID)
	if err != nil {
		return nil, err
	}

	// Type assert to get stats (Claude and Gemini agents implement GetStats)
	switch a := agent.(type) {
	case *ClaudeAgent:
		return a.GetStats(), nil
	case *GeminiAgent:
		return a.GetStats(), nil
	default:
		return nil, fmt.Errorf("agent does not support stats")
	}
}

// Close gracefully shuts down the bridge
func (b *Bridge) Close() error {
	var err error
	b.closeOnce.Do(func() {
		close(b.closeChan)
		close(b.taskQueue)
	})

	return err
}

// Helper methods

func (b *Bridge) taskWorker() {
	for task := range b.taskQueue {
		select {
		case <-b.closeChan:
			return
		default:
		}

		agent, err := b.GetAgent(task.AgentID)
		if err != nil {
			continue
		}

		// Execute task
		result, _ := agent.Execute(context.Background(), task)

		// Store result
		b.resultsMutex.Lock()
		if result != nil {
			b.results[task.ID] = result
		}
		b.resultsMutex.Unlock()

		// Persist to database
		if result != nil {
			_ = b.persistResult(result)
		}
	}
}

func (b *Bridge) persistResult(result *AgentResult) error {
	outputJSON, _ := json.Marshal(result.ModifiedFiles)

	_, err := b.db.Exec(
		"INSERT OR REPLACE INTO gaia_agent_results (id, task_id, agent_id, success, output, modified_files, error, duration_seconds, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
		uuid.New().String(), result.TaskID, result.AgentID, result.Success, result.Output, string(outputJSON), result.Error, int64(result.Duration.Seconds()), result.CompletedAt,
	)

	return err
}
