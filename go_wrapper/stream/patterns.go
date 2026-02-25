package stream

import "regexp"

// Pattern types for categorizing extracted data
const (
	PatternTypeSession    = "session"
	PatternTypePrompt     = "prompt"
	PatternTypeResponse   = "response"
	PatternTypeCodeBlock  = "code_block"
	PatternTypeError      = "error"
	PatternTypeMetric     = "metric"
	PatternTypeStateChange = "state_change"
	PatternTypeFileOp     = "file_operation"
)

// CodexPatterns defines all regex patterns for Codex output parsing
type CodexPatterns struct {
	// Session information
	SessionID    *regexp.Regexp
	Workdir      *regexp.Regexp
	Model        *regexp.Regexp
	Provider     *regexp.Regexp
	Approval     *regexp.Regexp
	Sandbox      *regexp.Regexp
	Reasoning    *regexp.Regexp

	// User interaction
	UserPrompt   *regexp.Regexp
	MCPStartup   *regexp.Regexp

	// Codex responses
	CodexResponse *regexp.Regexp
	CodexThinking *regexp.Regexp

	// Code blocks
	CodeBlockStart *regexp.Regexp
	CodeBlockEnd   *regexp.Regexp
	CodeBlockLang  *regexp.Regexp

	// Metrics
	TokensUsed    *regexp.Regexp
	TimeElapsed   *regexp.Regexp
	MemoryUsage   *regexp.Regexp

	// Errors
	ErrorMessage  *regexp.Regexp
	ErrorStack    *regexp.Regexp
	Warning       *regexp.Regexp

	// File operations
	FileCreated   *regexp.Regexp
	FileModified  *regexp.Regexp
	FileDeleted   *regexp.Regexp
	FileRead      *regexp.Regexp

	// State changes
	TaskStarted   *regexp.Regexp
	TaskCompleted *regexp.Regexp
	TaskFailed    *regexp.Regexp
}

// NewCodexPatterns creates and compiles all Codex parsing patterns
func NewCodexPatterns() *CodexPatterns {
	return &CodexPatterns{
		// Session information patterns
		SessionID: regexp.MustCompile(`session id:\s*([a-f0-9-]+)`),
		Workdir:   regexp.MustCompile(`workdir:\s*(.+?)(?:\s|$)`),
		Model:     regexp.MustCompile(`model:\s*(.+?)(?:\s|$)`),
		Provider:  regexp.MustCompile(`provider:\s*(\w+)`),
		Approval:  regexp.MustCompile(`approval:\s*(\w+)`),
		Sandbox:   regexp.MustCompile(`sandbox:\s*(.+?)(?:\[|$)`),
		Reasoning: regexp.MustCompile(`reasoning effort:\s*(\w+)`),

		// User interaction patterns
		UserPrompt: regexp.MustCompile(`^user\s*$`),
		MCPStartup: regexp.MustCompile(`mcp startup:\s*(.+?)(?:\s|$)`),

		// Codex response patterns
		CodexResponse: regexp.MustCompile(`^codex\s*$`),
		CodexThinking: regexp.MustCompile(`(?i)\[thinking\]`),

		// Code block patterns
		CodeBlockStart: regexp.MustCompile("^```(\\w+)?"),
		CodeBlockEnd:   regexp.MustCompile("^```$"),
		CodeBlockLang:  regexp.MustCompile("^```(python|javascript|go|bash|sql|java|rust|typescript|html|css|json|yaml|xml)"),

		// Metrics patterns
		TokensUsed:  regexp.MustCompile(`tokens used\s*(?:\n|\s+)?([\d,]+)`),
		TimeElapsed: regexp.MustCompile(`(?i)(?:time|duration|elapsed):\s*(\d+(?:\.\d+)?)\s*(s|ms|sec|seconds?|milliseconds?)`),
		MemoryUsage: regexp.MustCompile(`(?i)memory:\s*(\d+(?:\.\d+)?)\s*(MB|GB|KB|bytes?)`),

		// Error patterns
		ErrorMessage: regexp.MustCompile(`(?i)^(?:error|exception|fatal):\s*(.+)$`),
		ErrorStack:   regexp.MustCompile(`(?i)at\s+\w+\s+[\w./]+:\d+:\d+`),
		Warning:      regexp.MustCompile(`(?i)^(?:warning|warn):\s*(.+)$`),

		// File operation patterns
		FileCreated:  regexp.MustCompile(`(?i)(?:created|writing|wrote)\s+(?:file\s+)?[\'\"]?([^\s\'\"]+\.[\w]+)[\'\"]?`),
		FileModified: regexp.MustCompile(`(?i)(?:modified|updated|changed)\s+(?:file\s+)?[\'\"]?([^\s\'\"]+\.[\w]+)[\'\"]?`),
		FileDeleted:  regexp.MustCompile(`(?i)(?:deleted|removed)\s+(?:file\s+)?[\'\"]?([^\s\'\"]+\.[\w]+)[\'\"]?`),
		FileRead:     regexp.MustCompile(`(?i)(?:reading|read)\s+(?:file\s+)?[\'\"]?([^\s\'\"]+\.[\w]+)[\'\"]?`),

		// State change patterns
		TaskStarted:   regexp.MustCompile(`(?i)(?:starting|begin|commenced)\s+(?:task|job|work)[\s:]?\s*(.+?)(?:\s|$)`),
		TaskCompleted: regexp.MustCompile(`(?i)(?:completed|finished|done)\s+(?:task|job|work)[\s:]?\s*(.+?)(?:\s|$)`),
		TaskFailed:    regexp.MustCompile(`(?i)(?:failed|error|aborted)\s+(?:task|job|work)[\s:]?\s*(.+?)(?:\s|$)`),
	}
}

// GeneralPatterns defines language-agnostic patterns
type GeneralPatterns struct {
	// Common patterns across all agents
	Timestamp   *regexp.Regexp
	LogLevel    *regexp.Regexp
	IPAddress   *regexp.Regexp
	URL         *regexp.Regexp
	Email       *regexp.Regexp
	UUID        *regexp.Regexp
	Percentage  *regexp.Regexp
	Number      *regexp.Regexp
	FilePath    *regexp.Regexp
}

// NewGeneralPatterns creates general-purpose parsing patterns
func NewGeneralPatterns() *GeneralPatterns {
	return &GeneralPatterns{
		Timestamp:  regexp.MustCompile(`\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?`),
		LogLevel:   regexp.MustCompile(`(?i)\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|TRACE)\b`),
		IPAddress:  regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`),
		URL:        regexp.MustCompile(`https?://[^\s]+`),
		Email:      regexp.MustCompile(`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`),
		UUID:       regexp.MustCompile(`[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}`),
		Percentage: regexp.MustCompile(`\b\d+(?:\.\d+)?%`),
		Number:     regexp.MustCompile(`\b\d+(?:,\d{3})*(?:\.\d+)?\b`),
		FilePath:   regexp.MustCompile(`(?:/[\w.-]+)+\.[\w]+`),
	}
}

// PatternPriority defines the order in which patterns should be applied
// Higher priority patterns are checked first
var PatternPriority = map[string]int{
	PatternTypeError:      100, // Check errors first
	PatternTypeMetric:     90,  // Then metrics
	PatternTypeCodeBlock:  80,  // Then code blocks
	PatternTypeSession:    70,  // Then session info
	PatternTypeStateChange: 60, // Then state changes
	PatternTypeFileOp:     50,  // Then file ops
	PatternTypePrompt:     40,  // Then prompts
	PatternTypeResponse:   30,  // Then responses
}
