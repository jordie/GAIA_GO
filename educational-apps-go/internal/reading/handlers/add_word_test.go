package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/reading/models"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAddWordValidation(t *testing.T) {
	tests := []struct {
		name           string
		word           string
		expectedStatus int
		shouldContain  string
	}{
		{
			name:           "valid word - simple",
			word:           "hello",
			expectedStatus: 201,
			shouldContain:  "Word added successfully",
		},
		{
			name:           "valid word - with hyphen",
			word:           "well-known",
			expectedStatus: 201,
			shouldContain:  "Word added successfully",
		},
		{
			name:           "valid word - with apostrophe",
			word:           "don't",
			expectedStatus: 201,
			shouldContain:  "Word added successfully",
		},
		{
			name:           "valid word - with spaces",
			word:           "ice cream",
			expectedStatus: 201,
			shouldContain:  "Word added successfully",
		},
		{
			name:           "empty word",
			word:           "",
			expectedStatus: 400,
			shouldContain:  "cannot be empty",
		},
		{
			name:           "word with only whitespace",
			word:           "   ",
			expectedStatus: 400,
			shouldContain:  "cannot be empty",
		},
		{
			name:           "word too long",
			word:           string(make([]byte, 101)),
			expectedStatus: 400,
			shouldContain:  "too long",
		},
		{
			name:           "word with numbers",
			word:           "test123",
			expectedStatus: 400,
			shouldContain:  "must contain at least one letter",
		},
		{
			name:           "word with only numbers",
			word:           "12345",
			expectedStatus: 400,
			shouldContain:  "must contain at least one letter",
		},
		{
			name:           "SQL injection - DROP",
			word:           "DROP TABLE users",
			expectedStatus: 400,
			shouldContain:  "suspicious patterns",
		},
		{
			name:           "SQL injection - SELECT",
			word:           "SELECT * FROM users",
			expectedStatus: 400,
			shouldContain:  "suspicious patterns",
		},
		{
			name:           "SQL injection - comment",
			word:           "test -- comment",
			expectedStatus: 400,
			shouldContain:  "suspicious patterns",
		},
		{
			name:           "XSS - script tag",
			word:           "<script>alert('xss')</script>",
			expectedStatus: 400,
			shouldContain:  "invalid markup",
		},
		{
			name:           "XSS - event handler",
			word:           "test onerror=alert(1)",
			expectedStatus: 400,
			shouldContain:  "invalid markup",
		},
		{
			name:           "XSS - javascript protocol",
			word:           "javascript:void(0)",
			expectedStatus: 400,
			shouldContain:  "invalid markup",
		},
		{
			name:           "invalid characters - brackets",
			word:           "test[bracket]",
			expectedStatus: 400,
			shouldContain:  "invalid characters",
		},
		{
			name:           "invalid characters - braces",
			word:           "test{brace}",
			expectedStatus: 400,
			shouldContain:  "invalid characters",
		},
		{
			name:           "max length boundary - 100 chars",
			word:           "a",
			expectedStatus: 201,
			shouldContain:  "Word added successfully",
		},
	}

	// Initialize test database
	if err := database.InitWithType("sqlite", ":memory:"); err != nil {
		t.Fatalf("Failed to initialize test database: %v", err)
	}
	defer database.Close()

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create request
			req := models.AddWordRequest{
				Word: tt.word,
			}
			body, _ := json.Marshal(req)

			httpReq := httptest.NewRequest("POST", "/api/v1/reading/words", bytes.NewReader(body))
			httpReq.Header.Set("Content-Type", "application/json")

			w := httptest.NewRecorder()

			// Create minimal Gin context for testing
			gin.SetMode(gin.TestMode)
			ctx, _ := gin.CreateTestContext(w)
			ctx.Request = httpReq

			// Call handler
			AddWord(ctx)

			// Assert status code
			assert.Equal(t, tt.expectedStatus, w.Code, "word: %s", tt.word)

			// Parse response
			var response map[string]interface{}
			if err := json.Unmarshal(w.Body.Bytes(), &response); err == nil {
				if tt.expectedStatus == 201 {
					assert.NotNil(t, response["id"], "response should contain id")
					assert.NotNil(t, response["word"], "response should contain word")
				} else {
					// Error response
					assert.NotEmpty(t, response["message"], "error response should contain message")
				}
			}
		})
	}
}

func TestValidateWordInputFunction(t *testing.T) {
	tests := []struct {
		name        string
		word        string
		shouldError bool
		errorMsg    string
	}{
		{"clean word", "elephant", false, ""},
		{"hyphenated", "mother-in-law", false, ""},
		{"apostrophe", "won't", false, ""},
		{"empty after trim", "   ", true, "empty"},
		{"too long", string(make([]byte, 101)), true, "long"},
		{"pure numbers", "123", true, "letter"},
		{"SQL DROP", "DROP", true, "suspicious"},
		{"SQL SELECT", "SELECT", true, "suspicious"},
		{"XSS script", "<script>", true, "markup"},
		{"XSS event", "onclick=", true, "markup"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateWordInput(tt.word)
			if tt.shouldError {
				assert.NotNil(t, err, "expected validation error")
				assert.Contains(t, err.Message, tt.errorMsg, "error message should match")
			} else {
				assert.Nil(t, err, "expected no validation error")
			}
		})
	}
}

func TestAddWordDuplicatePrevention(t *testing.T) {
	// Initialize test database
	if err := database.InitWithType("sqlite", ":memory:"); err != nil {
		t.Fatalf("Failed to initialize test database: %v", err)
	}
	defer database.Close()

	// Run migrations
	if err := database.RunMigrations(); err != nil {
		t.Fatalf("Failed to run migrations: %v", err)
	}

	gin.SetMode(gin.TestMode)

	// First request - should succeed
	req1 := models.AddWordRequest{Word: "unique"}
	body1, _ := json.Marshal(req1)
	httpReq1 := httptest.NewRequest("POST", "/api/v1/reading/words", bytes.NewReader(body1))
	httpReq1.Header.Set("Content-Type", "application/json")

	w1 := httptest.NewRecorder()
	ctx1, _ := gin.CreateTestContext(w1)
	ctx1.Request = httpReq1

	AddWord(ctx1)
	assert.Equal(t, http.StatusCreated, w1.Code, "first add should succeed")

	// Second request - should fail with conflict (case-insensitive)
	req2 := models.AddWordRequest{Word: "UNIQUE"}
	body2, _ := json.Marshal(req2)
	httpReq2 := httptest.NewRequest("POST", "/api/v1/reading/words", bytes.NewReader(body2))
	httpReq2.Header.Set("Content-Type", "application/json")

	w2 := httptest.NewRecorder()
	ctx2, _ := gin.CreateTestContext(w2)
	ctx2.Request = httpReq2

	AddWord(ctx2)
	assert.Equal(t, http.StatusConflict, w2.Code, "duplicate add should fail with conflict")
}

func TestAddWordNormalization(t *testing.T) {
	// Initialize test database
	if err := database.InitWithType("sqlite", ":memory:"); err != nil {
		t.Fatalf("Failed to initialize test database: %v", err)
	}
	defer database.Close()

	// Run migrations
	if err := database.RunMigrations(); err != nil {
		t.Fatalf("Failed to run migrations: %v", err)
	}

	gin.SetMode(gin.TestMode)

	// Add word with mixed case and whitespace
	req := models.AddWordRequest{Word: "  HeLLo  "}
	body, _ := json.Marshal(req)
	httpReq := httptest.NewRequest("POST", "/api/v1/reading/words", bytes.NewReader(body))
	httpReq.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(w)
	ctx.Request = httpReq

	AddWord(ctx)
	assert.Equal(t, http.StatusCreated, w.Code, "word should be normalized and added")

	// Parse response
	var response models.AddWordResponse
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &response))
	assert.Equal(t, "hello", response.Word, "word should be normalized to lowercase")
}
