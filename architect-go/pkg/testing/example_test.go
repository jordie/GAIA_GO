package testing

import (
	"testing"

	"architect-go/pkg/models"
)

// ExampleTestContextUsage demonstrates how to use TestContext
func TestExampleContextUsage(t *testing.T) {
	// Create test context
	tc := NewTestContext(t)
	defer tc.Cleanup()
	defer tc.CleanupTables()

	// Create a test project
	project := &models.Project{
		ID:          "test-project-1",
		Name:        "Test Project",
		Description: "A test project",
		Status:      "active",
	}

	// Save project using repository
	err := tc.Repos.ProjectRepo.Create(tc.Ctx, project)
	tc.AssertNoError(err, "Failed to create project")

	// Retrieve project
	retrieved, err := tc.Repos.ProjectRepo.Get(tc.Ctx, project.ID)
	tc.AssertNoError(err, "Failed to get project")

	// Verify project
	tc.AssertEqual(project.Name, retrieved.Name, "Project name mismatch")
	tc.AssertEqual(project.Status, retrieved.Status, "Project status mismatch")
}

// ExampleTestAssertions demonstrates various assertion methods
func TestExampleAssertions(t *testing.T) {
	tc := NewTestContext(t)
	defer tc.Cleanup()

	// Test AssertNoError
	err := error(nil)
	tc.AssertNoError(err, "No error expected")

	// Test AssertNil
	var nilValue interface{}
	tc.AssertNil(nilValue, "Expected nil")

	// Test AssertNotNil
	notNilValue := "something"
	tc.AssertNotNil(notNilValue, "Expected non-nil value")

	// Test AssertEqual
	tc.AssertEqual(42, 42, "Values should be equal")

	// Test AssertNotEqual
	tc.AssertNotEqual(42, 43, "Values should not be equal")
}

// ExampleTestDatabase demonstrates database usage in tests
func TestExampleDatabase(t *testing.T) {
	tc := NewTestContext(t)
	defer tc.Cleanup()
	defer tc.CleanupTables()

	// Create multiple projects
	for i := 1; i <= 3; i++ {
		project := &models.Project{
			ID:     "project-" + string(rune(i)),
			Name:   "Project " + string(rune(i)),
			Status: "active",
		}
		err := tc.Repos.ProjectRepo.Create(tc.Ctx, project)
		tc.AssertNoError(err, "Failed to create project")
	}

	// List projects
	projects, total, err := tc.Repos.ProjectRepo.List(tc.Ctx, nil, 10, 0)
	tc.AssertNoError(err, "Failed to list projects")
	tc.AssertEqual(int64(3), total, "Expected 3 projects")

	// Verify project count
	if len(projects) != 3 {
		t.Errorf("Expected 3 projects but got %d", len(projects))
	}
}

// ExampleTestTimeout demonstrates timeout usage
func TestExampleTimeout(t *testing.T) {
	tc := NewTestContext(t)
	defer tc.Cleanup()
	defer tc.CleanupTables()

	// Create a context with timeout
	ctx := tc.Timeout(0)

	// Try to create a project with timeout context
	project := &models.Project{
		ID:     "test-timeout",
		Name:   "Test",
		Status: "active",
	}

	// This should eventually timeout or succeed depending on database
	err := tc.Repos.ProjectRepo.Create(ctx, project)
	if err != nil {
		tc.T.Logf("Operation completed (timeout: %v)", err)
	}
}
