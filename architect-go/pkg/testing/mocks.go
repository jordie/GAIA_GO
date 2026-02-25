package testing

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// HTTPTestCase represents an HTTP test case
type HTTPTestCase struct {
	Name           string
	Method         string
	Path           string
	Body           string
	Headers        map[string]string
	ExpectedStatus int
	ExpectedBody   string
}

// RunHTTPTest runs an HTTP test case
func RunHTTPTest(t *testing.T, handler http.Handler, tc HTTPTestCase) {
	// Create request
	req := httptest.NewRequest(tc.Method, tc.Path, strings.NewReader(tc.Body))

	// Set headers
	for key, value := range tc.Headers {
		req.Header.Set(key, value)
	}

	// Set default content type
	if req.Header.Get("Content-Type") == "" && tc.Body != "" {
		req.Header.Set("Content-Type", "application/json")
	}

	// Create response recorder
	w := httptest.NewRecorder()

	// Call handler
	handler.ServeHTTP(w, req)

	// Verify status code
	if w.Code != tc.ExpectedStatus {
		t.Errorf("%s: expected status %d but got %d", tc.Name, tc.ExpectedStatus, w.Code)
	}

	// Verify body if provided
	if tc.ExpectedBody != "" && w.Body.String() != tc.ExpectedBody {
		t.Errorf("%s: expected body %s but got %s", tc.Name, tc.ExpectedBody, w.Body.String())
	}
}

// MockResponseWriter implements http.ResponseWriter for testing
type MockResponseWriter struct {
	StatusCode int
	Headers    http.Header
	Body       strings.Builder
}

// NewMockResponseWriter creates a new mock response writer
func NewMockResponseWriter() *MockResponseWriter {
	return &MockResponseWriter{
		StatusCode: http.StatusOK,
		Headers:    make(http.Header),
	}
}

// Header returns the header map
func (m *MockResponseWriter) Header() http.Header {
	return m.Headers
}

// Write writes data to the body
func (m *MockResponseWriter) Write(b []byte) (int, error) {
	return m.Body.Write(b)
}

// WriteHeader writes the status code
func (m *MockResponseWriter) WriteHeader(statusCode int) {
	m.StatusCode = statusCode
}

// GetBody returns the response body as string
func (m *MockResponseWriter) GetBody() string {
	return m.Body.String()
}

// MockRequest creates a mock HTTP request
func MockRequest(method string, path string) *http.Request {
	req := httptest.NewRequest(method, path, nil)
	return req
}

// MockRequestWithBody creates a mock HTTP request with body
func MockRequestWithBody(method string, path string, body string) *http.Request {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	return req
}

// MockRequestWithHeaders creates a mock HTTP request with headers
func MockRequestWithHeaders(method string, path string, headers map[string]string) *http.Request {
	req := httptest.NewRequest(method, path, nil)
	for key, value := range headers {
		req.Header.Set(key, value)
	}
	return req
}
