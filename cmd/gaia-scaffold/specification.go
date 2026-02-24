package main

import (
	"strings"
)

// Specification represents a parsed application specification
type Specification struct {
	Name        string
	Description string
	Entities    []*Entity
	Operations  []*Operation
}

// Entity represents a data model
type Entity struct {
	Name   string
	Fields []*Field
}

// Field represents a model field
type Field struct {
	Name     string
	Type     string
	JSONTag  string
	Optional bool
}

// Operation represents a handler/endpoint
type Operation struct {
	Name   string
	Entity string
	Type   string // "create", "read", "update", "delete", "list"
	Desc   string
}

// ParseSpecification parses a natural language specification
func ParseSpecification(prompt string) (*Specification, error) {
	spec := &Specification{
		Description: prompt,
	}

	// Extract app name from first meaningful word(s)
	words := strings.Fields(prompt)
	if len(words) > 0 {
		// Use first 1-2 words as app name
		if len(words) >= 2 && strings.ToLower(words[0]) == "build" {
			spec.Name = ToTitle(strings.ToLower(words[1]))
		} else {
			spec.Name = ToTitle(strings.ToLower(words[0]))
		}
	}

	if spec.Name == "" {
		spec.Name = "Application"
	}

	// Extract entities (words that look like nouns)
	spec.Entities = inferEntities(prompt)
	spec.Operations = inferOperations(prompt, spec.Entities)

	return spec, nil
}

// inferEntities extracts likely entity names from the prompt
func inferEntities(prompt string) []*Entity {
	var entities []*Entity

	// Keywords that indicate entities
	entityKeywords := map[string]string{
		"game":        "Game",
		"chess":       "Game",
		"player":      "Player",
		"user":        "User",
		"book":        "Book",
		"movie":       "Movie",
		"task":        "Task",
		"todo":        "Task",
		"note":        "Note",
		"article":     "Article",
		"post":        "Post",
		"comment":     "Comment",
		"match":       "Match",
		"move":        "Move",
		"leaderboard": "Leaderboard",
		"score":       "Score",
		"rating":      "Rating",
		"stat":        "Stat",
		"profile":     "Profile",
		"account":     "Account",
	}

	lowerPrompt := strings.ToLower(prompt)

	// Find all entities mentioned
	foundEntities := make(map[string]bool)
	for keyword, entityName := range entityKeywords {
		if strings.Contains(lowerPrompt, keyword) {
			if !foundEntities[entityName] {
				foundEntities[entityName] = true
				entities = append(entities, &Entity{
					Name:   entityName,
					Fields: getDefaultFields(entityName),
				})
			}
		}
	}

	// Always include User if not already there
	if !foundEntities["User"] {
		entities = append(entities, &Entity{
			Name: "User",
			Fields: []*Field{
				{Name: "ID", Type: "int64", JSONTag: "id"},
				{Name: "Username", Type: "string", JSONTag: "username"},
				{Name: "Email", Type: "string", JSONTag: "email"},
			},
		})
	}

	return entities
}

// inferOperations extracts likely operations from the prompt
func inferOperations(prompt string, entities []*Entity) []*Operation {
	var operations []*Operation

	lowerPrompt := strings.ToLower(prompt)

	// Keywords that indicate operations
	operationKeywords := map[string]string{
		"create":    "create",
		"add":       "create",
		"new":       "create",
		"make":      "create",
		"play":      "create",
		"read":      "read",
		"view":      "read",
		"get":       "read",
		"show":      "read",
		"list":      "list",
		"browse":    "list",
		"search":    "list",
		"find":      "list",
		"update":    "update",
		"modify":    "update",
		"change":    "update",
		"edit":      "update",
		"delete":    "delete",
		"remove":    "delete",
		"track":     "read",
		"leaderboard": "read",
		"rating":    "read",
	}

	// Check operations mentioned
	foundOps := make(map[string]bool)

	for keyword, opType := range operationKeywords {
		if strings.Contains(lowerPrompt, keyword) {
			for _, entity := range entities {
				opKey := entity.Name + ":" + opType
				if !foundOps[opKey] {
					foundOps[opKey] = true
					operations = append(operations, &Operation{
						Name:   strings.ToLower(entity.Name) + "_" + opType,
						Entity: entity.Name,
						Type:   opType,
						Desc:   opType + " " + entity.Name,
					})
				}
			}
		}
	}

	// Add default CRUD operations if not specified
	if len(operations) == 0 {
		for _, entity := range entities {
			if entity.Name != "User" { // Skip User for now
				operations = append(operations,
					&Operation{Name: strings.ToLower(entity.Name) + "_create", Entity: entity.Name, Type: "create", Desc: "Create " + entity.Name},
					&Operation{Name: strings.ToLower(entity.Name) + "_read", Entity: entity.Name, Type: "read", Desc: "Read " + entity.Name},
					&Operation{Name: strings.ToLower(entity.Name) + "_list", Entity: entity.Name, Type: "list", Desc: "List " + entity.Name},
					&Operation{Name: strings.ToLower(entity.Name) + "_update", Entity: entity.Name, Type: "update", Desc: "Update " + entity.Name},
				)
			}
		}
	}

	return operations
}

// getDefaultFields returns default fields for common entity types
func getDefaultFields(entityName string) []*Field {
	switch entityName {
	case "Game":
		return []*Field{
			{Name: "ID", Type: "int64", JSONTag: "id"},
			{Name: "PlayerID", Type: "int64", JSONTag: "player_id"},
			{Name: "Status", Type: "string", JSONTag: "status"},
			{Name: "Score", Type: "int", JSONTag: "score", Optional: true},
			{Name: "CreatedAt", Type: "time.Time", JSONTag: "created_at"},
		}
	case "Player":
		return []*Field{
			{Name: "ID", Type: "int64", JSONTag: "id"},
			{Name: "Username", Type: "string", JSONTag: "username"},
			{Name: "Rating", Type: "int", JSONTag: "rating", Optional: true},
			{Name: "Wins", Type: "int", JSONTag: "wins"},
			{Name: "Losses", Type: "int", JSONTag: "losses"},
		}
	case "Move":
		return []*Field{
			{Name: "ID", Type: "int64", JSONTag: "id"},
			{Name: "GameID", Type: "int64", JSONTag: "game_id"},
			{Name: "PlayerID", Type: "int64", JSONTag: "player_id"},
			{Name: "MoveNumber", Type: "int", JSONTag: "move_number"},
			{Name: "Data", Type: "string", JSONTag: "data"},
		}
	case "Book":
		return []*Field{
			{Name: "ID", Type: "int64", JSONTag: "id"},
			{Name: "Title", Type: "string", JSONTag: "title"},
			{Name: "Author", Type: "string", JSONTag: "author"},
			{Name: "Rating", Type: "float64", JSONTag: "rating", Optional: true},
		}
	default:
		return []*Field{
			{Name: "ID", Type: "int64", JSONTag: "id"},
			{Name: "UserID", Type: "int64", JSONTag: "user_id"},
			{Name: "Data", Type: "string", JSONTag: "data"},
			{Name: "CreatedAt", Type: "time.Time", JSONTag: "created_at"},
		}
	}
}

// ToTitle converts string to title case
func ToTitle(s string) string {
	if len(s) == 0 {
		return s
	}
	return strings.ToUpper(s[:1]) + strings.ToLower(s[1:])
}
