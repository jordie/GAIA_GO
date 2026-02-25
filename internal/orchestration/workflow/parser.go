package workflow

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Parser handles YAML workflow definition parsing and validation
type Parser struct {
	templateDir string
}

// NewParser creates a new workflow parser
func NewParser(templateDir string) *Parser {
	return &Parser{
		templateDir: templateDir,
	}
}

// ParseFile reads and parses a workflow YAML file
func (p *Parser) ParseFile(filePath string) (*WorkflowDefinition, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read workflow file: %w", err)
	}

	return p.Parse(string(data))
}

// Parse parses a YAML workflow definition from string
func (p *Parser) Parse(yamlContent string) (*WorkflowDefinition, error) {
	var def WorkflowDefinition

	if err := yaml.Unmarshal([]byte(yamlContent), &def); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	if err := p.validate(&def); err != nil {
		return nil, fmt.Errorf("workflow validation failed: %w", err)
	}

	return &def, nil
}

// ToWorkflow converts a workflow definition to a Workflow object
func (p *Parser) ToWorkflow(def *WorkflowDefinition, variables map[string]interface{}) (*Workflow, error) {
	workflow := &Workflow{
		Name:        def.Name,
		Description: def.Description,
		Version:     def.Version,
		Status:      WorkflowStatusPending,
		Tasks:       make(map[string]*Task),
		Variables:   make(map[string]interface{}),
		CreatedAt:   time.Now(),
	}

	// Merge variables (command-line overrides definition)
	for k, v := range def.Variables {
		workflow.Variables[k] = v
	}
	for k, v := range variables {
		workflow.Variables[k] = v
	}

	// Convert task definitions to tasks
	for _, taskDef := range def.Tasks {
		task, err := p.taskDefToTask(taskDef, workflow.Variables)
		if err != nil {
			return nil, fmt.Errorf("failed to convert task %s: %w", taskDef.ID, err)
		}
		workflow.Tasks[task.ID] = task
	}

	return workflow, nil
}

// Helper methods

func (p *Parser) validate(def *WorkflowDefinition) error {
	if def.Name == "" {
		return fmt.Errorf("workflow name is required")
	}

	if len(def.Tasks) == 0 {
		return fmt.Errorf("workflow must have at least one task")
	}

	// Check for duplicate task IDs
	taskIDs := make(map[string]bool)
	for _, task := range def.Tasks {
		if task.ID == "" {
			return fmt.Errorf("task ID is required")
		}
		if taskIDs[task.ID] {
			return fmt.Errorf("duplicate task ID: %s", task.ID)
		}
		taskIDs[task.ID] = true
	}

	// Validate each task
	for _, task := range def.Tasks {
		if task.Name == "" {
			return fmt.Errorf("task %s must have a name", task.ID)
		}
		if task.Type == "" {
			return fmt.Errorf("task %s must have a type", task.ID)
		}
		if task.Agent == "" {
			return fmt.Errorf("task %s must specify an agent", task.ID)
		}

		// Check if dependencies exist
		for _, dep := range task.Dependencies {
			if !taskIDs[dep] {
				return fmt.Errorf("task %s has invalid dependency: %s", task.ID, dep)
			}
		}
	}

	// Check for circular dependencies
	if p.hasCyclicDependencies(def.Tasks) {
		return fmt.Errorf("circular dependency detected in workflow")
	}

	return nil
}

func (p *Parser) taskDefToTask(def *TaskDefinition, variables map[string]interface{}) (*Task, error) {
	task := &Task{
		ID:           def.ID,
		Name:         def.Name,
		Type:         TaskType(def.Type),
		Agent:        AgentType(def.Agent),
		Command:      p.substituteVariables(def.Command, variables),
		Status:       TaskStatusPending,
		WorkDir:      p.substituteVariables(def.WorkDir, variables),
		Dependencies: def.Dependencies,
		OnError:      ErrorAction(def.OnError),
		MaxRetries:   def.MaxRetries,
		Environment:  make(map[string]string),
	}

	// Parse timeout
	if def.Timeout != "" {
		duration, err := time.ParseDuration(def.Timeout)
		if err != nil {
			// Try as simple minute/hour format
			if strings.HasSuffix(def.Timeout, "m") {
				minutes := strings.TrimSuffix(def.Timeout, "m")
				var m int
				if _, err := fmt.Sscanf(minutes, "%d", &m); err == nil {
					duration = time.Duration(m) * time.Minute
				} else {
					return nil, fmt.Errorf("invalid timeout format: %s", def.Timeout)
				}
			} else {
				return nil, fmt.Errorf("invalid timeout format: %s", def.Timeout)
			}
		}
		task.Timeout = duration
	} else {
		task.Timeout = 30 * time.Minute // Default timeout
	}

	// Substitute variables in environment
	if def.Environment != nil {
		for k, v := range def.Environment {
			task.Environment[k] = p.substituteVariables(v, variables)
		}
	}

	// Set default error action
	if task.OnError == "" {
		task.OnError = ErrorActionFail
	}

	return task, nil
}

// substituteVariables replaces ${var} placeholders with actual values
func (p *Parser) substituteVariables(text string, variables map[string]interface{}) string {
	if text == "" {
		return text
	}

	result := text

	// Pattern to match ${variable_name}
	pattern := regexp.MustCompile(`\$\{([^}]+)\}`)

	result = pattern.ReplaceAllStringFunc(result, func(match string) string {
		varName := strings.TrimPrefix(strings.TrimSuffix(match, "}"), "${")

		if value, exists := variables[varName]; exists {
			return fmt.Sprintf("%v", value)
		}

		// Keep original if variable not found
		return match
	})

	return result
}

// hasCyclicDependencies checks if there are any circular dependencies
func (p *Parser) hasCyclicDependencies(tasks []*TaskDefinition) bool {
	taskMap := make(map[string]*TaskDefinition)
	for _, task := range tasks {
		taskMap[task.ID] = task
	}

	visited := make(map[string]bool)
	recStack := make(map[string]bool)

	for _, task := range tasks {
		if !visited[task.ID] {
			if p.hasCyclicUtil(task.ID, taskMap, visited, recStack) {
				return true
			}
		}
	}

	return false
}

func (p *Parser) hasCyclicUtil(taskID string, taskMap map[string]*TaskDefinition, visited map[string]bool, recStack map[string]bool) bool {
	visited[taskID] = true
	recStack[taskID] = true

	task := taskMap[taskID]
	for _, dep := range task.Dependencies {
		if !visited[dep] {
			if p.hasCyclicUtil(dep, taskMap, visited, recStack) {
				return true
			}
		} else if recStack[dep] {
			return true
		}
	}

	recStack[taskID] = false
	return false
}
