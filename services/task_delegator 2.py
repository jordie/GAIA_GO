"""
Intelligent Task Delegation System

Routes tasks to the optimal AI agent/model based on task type and complexity.
Optimizes token usage by using appropriate models for different tasks.

Routing Strategy:
    - UI tasks → Comet (browser automation)
    - Coding tasks → Codex (code generation)
    - Simple queries → Haiku (cheap)
    - Complex analysis → Sonnet 4.5 (expensive)
    - Background tasks → Ollama (free)

Usage:
    from services.task_delegator import TaskDelegator, TaskType

    delegator = TaskDelegator()

    # Delegate a task
    result = delegator.delegate_task(
        task="Fix the login button styling",
        task_type=TaskType.UI,
        priority="high"
    )
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task type classifications."""

    UI = "ui"  # UI/frontend work → Comet
    CODING = "coding"  # Code generation → Codex
    TESTING = "testing"  # Test generation → Codex
    DEBUGGING = "debugging"  # Bug fixing → Codex
    ANALYSIS = "analysis"  # Code analysis → Haiku/Sonnet
    RESEARCH = "research"  # Research/exploration → Haiku
    DOCUMENTATION = "documentation"  # Docs → Haiku
    CHAT = "chat"  # General chat → Haiku
    AUTOMATION = "automation"  # Automation scripts → Codex
    DATABASE = "database"  # SQL/database work → Codex
    API = "api"  # API development → Codex
    UNKNOWN = "unknown"  # Unknown → Sonnet


class AgentType(Enum):
    """Available agent types."""

    COMET = "comet"  # Browser automation agent
    CODEX = "codex"  # Code generation agent
    CLAUDE_SONNET = "claude-sonnet"  # Claude Sonnet 4.5 (premium)
    CLAUDE_HAIKU = "claude-haiku"  # Claude Haiku (cheap)
    OLLAMA = "ollama"  # Local Ollama (free)


class TaskComplexity(Enum):
    """Task complexity levels."""

    SIMPLE = "simple"  # Simple queries, basic tasks
    MEDIUM = "medium"  # Standard development tasks
    COMPLEX = "complex"  # Complex analysis, architecture
    CRITICAL = "critical"  # Mission-critical work


@dataclass
class DelegationResult:
    """Result of task delegation."""

    task_type: TaskType
    agent: AgentType
    model: str
    complexity: TaskComplexity
    estimated_tokens: int
    reasoning: str
    session_target: Optional[str] = None  # tmux session to use


class TaskDelegator:
    """
    Intelligent task delegation system.

    Routes tasks to optimal agents based on task type, complexity,
    and resource constraints.
    """

    # Task type detection patterns
    TASK_PATTERNS = {
        TaskType.UI: [
            r"\b(ui|frontend|style|css|html|button|form|modal|page|layout|design|responsive)\b",
            r"\b(click|hover|animation|transition|element|component|widget)\b",
            r"\b(browser|chrome|selenium|playwright|comet)\b",
        ],
        TaskType.CODING: [
            r"\b(code|implement|function|class|method|refactor|optimize)\b",
            r"\b(python|javascript|typescript|java|go|rust)\b",
            r"\b(algorithm|logic|feature|module)\b",
        ],
        TaskType.TESTING: [
            r"\b(test|unittest|pytest|spec|assert|mock|fixture)\b",
            r"\b(coverage|integration|e2e|regression)\b",
        ],
        TaskType.DEBUGGING: [
            r"\b(bug|fix|error|issue|crash|fail|broken)\b",
            r"\b(debug|trace|stacktrace|exception)\b",
        ],
        TaskType.ANALYSIS: [
            r"\b(analyze|review|audit|inspect|examine)\b",
            r"\b(performance|security|quality|complexity)\b",
        ],
        TaskType.RESEARCH: [
            r"\b(research|investigate|explore|learn|understand)\b",
            r"\b(how does|what is|why|explain)\b",
        ],
        TaskType.DOCUMENTATION: [
            r"\b(document|readme|guide|tutorial|comment|docstring)\b",
            r"\b(explain|describe|outline)\b",
        ],
        TaskType.AUTOMATION: [
            r"\b(automate|script|cron|schedule|batch)\b",
            r"\b(workflow|pipeline|deploy|ci/cd)\b",
        ],
        TaskType.DATABASE: [
            r"\b(database|sql|query|table|schema|migration)\b",
            r"\b(postgres|mysql|sqlite|mongodb)\b",
        ],
        TaskType.API: [
            r"\b(api|endpoint|route|request|response|rest|graphql)\b",
            r"\b(http|json|webhook)\b",
        ],
    }

    # Agent routing rules
    AGENT_ROUTING = {
        # UI tasks always go to Comet
        TaskType.UI: AgentType.COMET,
        # Coding tasks go to Codex
        TaskType.CODING: AgentType.CODEX,
        TaskType.TESTING: AgentType.CODEX,
        TaskType.DEBUGGING: AgentType.CODEX,
        TaskType.AUTOMATION: AgentType.CODEX,
        TaskType.DATABASE: AgentType.CODEX,
        TaskType.API: AgentType.CODEX,
        # Simple tasks use cheap Haiku
        TaskType.DOCUMENTATION: AgentType.CLAUDE_HAIKU,
        TaskType.RESEARCH: AgentType.CLAUDE_HAIKU,
        TaskType.CHAT: AgentType.CLAUDE_HAIKU,
        # Complex tasks use premium Sonnet
        TaskType.ANALYSIS: AgentType.CLAUDE_SONNET,
        TaskType.UNKNOWN: AgentType.CLAUDE_SONNET,
    }

    # Model mapping
    AGENT_MODELS = {
        AgentType.COMET: "claude-3-5-haiku-20241022",  # Comet uses Haiku for speed
        AgentType.CODEX: "claude-sonnet-4-5-20250929",  # Codex uses Sonnet for quality
        AgentType.CLAUDE_SONNET: "claude-sonnet-4-5-20250929",
        AgentType.CLAUDE_HAIKU: "claude-3-5-haiku-20241022",
        AgentType.OLLAMA: "llama3.2",
    }

    # Session mapping (tmux sessions)
    SESSION_MAPPING = {
        AgentType.COMET: "claude_comet",
        AgentType.CODEX: "codex",
        AgentType.CLAUDE_SONNET: "claude_premium",
        AgentType.CLAUDE_HAIKU: "claude_budget",
        AgentType.OLLAMA: "ollama_dev",
    }

    def __init__(self):
        logger.info("TaskDelegator initialized")

    def detect_task_type(self, task_description: str) -> TaskType:
        """
        Detect task type from description.

        Args:
            task_description: Natural language task description

        Returns:
            Detected TaskType
        """
        task_lower = task_description.lower()

        # Score each task type
        scores = {}
        for task_type, patterns in self.TASK_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    score += 1
            scores[task_type] = score

        # Return highest scoring type
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                for task_type, score in scores.items():
                    if score == max_score:
                        return task_type

        return TaskType.UNKNOWN

    def estimate_complexity(self, task_description: str, task_type: TaskType) -> TaskComplexity:
        """
        Estimate task complexity.

        Args:
            task_description: Task description
            task_type: Detected task type

        Returns:
            Estimated complexity
        """
        task_lower = task_description.lower()
        word_count = len(task_description.split())

        # Complexity indicators
        complex_indicators = [
            "architecture",
            "design pattern",
            "refactor entire",
            "migrate",
            "performance optimization",
            "security audit",
            "scale",
            "distributed",
            "microservices",
            "infrastructure",
        ]

        simple_indicators = [
            "add comment",
            "update string",
            "fix typo",
            "rename",
            "add log",
            "simple",
            "quick",
            "small change",
        ]

        critical_indicators = [
            "critical",
            "urgent",
            "production",
            "security vulnerability",
            "data loss",
            "outage",
            "emergency",
        ]

        # Check critical first
        if any(ind in task_lower for ind in critical_indicators):
            return TaskComplexity.CRITICAL

        # Check complex
        if any(ind in task_lower for ind in complex_indicators):
            return TaskComplexity.COMPLEX

        # Check simple
        if any(ind in task_lower for ind in simple_indicators):
            return TaskComplexity.SIMPLE

        # Estimate based on length and type
        if word_count < 10:
            return TaskComplexity.SIMPLE
        elif word_count > 50:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.MEDIUM

    def estimate_tokens(self, task_description: str, complexity: TaskComplexity) -> int:
        """
        Estimate tokens needed for task.

        Args:
            task_description: Task description
            complexity: Task complexity

        Returns:
            Estimated token count
        """
        base_tokens = len(task_description) // 4  # Rough estimate: 4 chars per token

        # Multiply based on complexity
        multipliers = {
            TaskComplexity.SIMPLE: 100,
            TaskComplexity.MEDIUM: 500,
            TaskComplexity.COMPLEX: 2000,
            TaskComplexity.CRITICAL: 1000,
        }

        return base_tokens + multipliers[complexity]

    def select_agent(
        self,
        task_type: TaskType,
        complexity: TaskComplexity,
        priority: str = "normal",
        prefer_free: bool = False,
    ) -> AgentType:
        """
        Select optimal agent for task.

        Args:
            task_type: Type of task
            complexity: Task complexity
            priority: Task priority
            prefer_free: Prefer free (Ollama) when possible

        Returns:
            Selected agent
        """
        # Critical tasks always use premium agents
        if complexity == TaskComplexity.CRITICAL:
            if task_type == TaskType.UI:
                return AgentType.COMET
            elif task_type in [TaskType.CODING, TaskType.DEBUGGING]:
                return AgentType.CODEX
            else:
                return AgentType.CLAUDE_SONNET

        # Use routing rules
        agent = self.AGENT_ROUTING.get(task_type, AgentType.CLAUDE_SONNET)

        # Override with free agent if requested and task is simple
        if prefer_free and complexity == TaskComplexity.SIMPLE:
            if task_type not in [TaskType.UI, TaskType.CODING]:
                return AgentType.OLLAMA

        return agent

    def delegate_task(
        self,
        task: str,
        task_type: TaskType = None,
        complexity: TaskComplexity = None,
        priority: str = "normal",
        prefer_free: bool = False,
    ) -> DelegationResult:
        """
        Delegate a task to the optimal agent.

        Args:
            task: Task description
            task_type: Optional explicit task type
            complexity: Optional explicit complexity
            priority: Task priority (low, normal, high, critical)
            prefer_free: Prefer free models when possible

        Returns:
            DelegationResult with routing information
        """
        # Auto-detect if not provided
        if task_type is None:
            task_type = self.detect_task_type(task)

        if complexity is None:
            complexity = self.estimate_complexity(task, task_type)

        # Select agent
        agent = self.select_agent(task_type, complexity, priority, prefer_free)

        # Get model and session
        model = self.AGENT_MODELS[agent]
        session = self.SESSION_MAPPING.get(agent)

        # Estimate tokens
        estimated_tokens = self.estimate_tokens(task, complexity)

        # Generate reasoning
        reasoning = self._generate_reasoning(task_type, agent, complexity)

        result = DelegationResult(
            task_type=task_type,
            agent=agent,
            model=model,
            complexity=complexity,
            estimated_tokens=estimated_tokens,
            reasoning=reasoning,
            session_target=session,
        )

        logger.info(
            f"Delegated task: {task_type.value} → {agent.value} "
            f"(complexity: {complexity.value}, ~{estimated_tokens} tokens)"
        )

        return result

    def _generate_reasoning(
        self, task_type: TaskType, agent: AgentType, complexity: TaskComplexity
    ) -> str:
        """Generate human-readable reasoning for delegation."""
        reasons = []

        # Task type reasoning
        if task_type == TaskType.UI:
            reasons.append("UI task → Comet browser agent")
        elif task_type in [TaskType.CODING, TaskType.TESTING, TaskType.DEBUGGING]:
            reasons.append(f"{task_type.value.title()} task → Codex code agent")
        elif task_type in [TaskType.RESEARCH, TaskType.DOCUMENTATION, TaskType.CHAT]:
            reasons.append(f"{task_type.value.title()} task → Haiku (cost-optimized)")

        # Complexity reasoning
        if complexity == TaskComplexity.CRITICAL:
            reasons.append("Critical priority → premium model")
        elif complexity == TaskComplexity.SIMPLE:
            reasons.append("Simple task → optimized for speed/cost")

        # Agent reasoning
        if agent == AgentType.CLAUDE_HAIKU:
            reasons.append("80% cost savings vs Sonnet")
        elif agent == AgentType.OLLAMA:
            reasons.append("Free local model")

        return "; ".join(reasons)

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get statistics about task routing."""
        return {
            "task_types": [t.value for t in TaskType],
            "agents": [a.value for a in AgentType],
            "routing_rules": {
                task_type.value: agent.value for task_type, agent in self.AGENT_ROUTING.items()
            },
            "session_mapping": {
                agent.value: session for agent, session in self.SESSION_MAPPING.items()
            },
        }


# Global delegator instance
_delegator = None


def get_delegator() -> TaskDelegator:
    """Get global delegator instance."""
    global _delegator
    if _delegator is None:
        _delegator = TaskDelegator()
    return _delegator
