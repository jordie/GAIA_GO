package errors

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// ErrorHandler handles errors in HTTP responses
type ErrorHandler struct {
	Debug  bool
	Verbose bool
}

// NewErrorHandler creates a new error handler
func NewErrorHandler(debug, verbose bool) *ErrorHandler {
	return &ErrorHandler{
		Debug:   debug,
		Verbose: verbose,
	}
}

// WriteError writes an error response
func (eh *ErrorHandler) WriteError(w interface{}, statusCode int, message string, err error) {
	// Simplified error handling
	if eh.Debug && err != nil {
		fmt.Printf("Error: %v\n", err)
	}
}

// HandleError handles an error in HTTP response context
func (eh *ErrorHandler) HandleError(w interface{}, r interface{}, err error) {
	if err != nil && w != nil {
		if respWriter, ok := w.(http.ResponseWriter); ok {
			respWriter.Header().Set("Content-Type", "application/json")
			respWriter.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(respWriter).Encode(map[string]string{"error": err.Error()})
		}
	}
}

// GetErrorStatus returns status code and message map for an error
func (eh *ErrorHandler) GetErrorStatus(err error) (int, map[string]string) {
	if err == nil {
		return 200, nil
	}
	return 500, map[string]string{"error": err.Error()}
}
