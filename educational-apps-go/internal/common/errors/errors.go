package errors

import (
	"fmt"
)

type AppError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
	Status  int    `json:"status"`
}

func (e *AppError) Error() string {
	return fmt.Sprintf("[%s] %s: %s", e.Code, e.Message, e.Details)
}

// Common error codes
const (
	CodeValidation       = "VALIDATION_ERROR"
	CodeNotFound         = "NOT_FOUND"
	CodeUnauthorized     = "UNAUTHORIZED"
	CodeForbidden        = "FORBIDDEN"
	CodeConflict         = "CONFLICT"
	CodeInternalError    = "INTERNAL_ERROR"
	CodeBadRequest       = "BAD_REQUEST"
	CodeUnprocessable    = "UNPROCESSABLE_ENTITY"
)

// Error constructors
func Validation(message string, details string) *AppError {
	return &AppError{
		Code:    CodeValidation,
		Message: message,
		Details: details,
		Status:  400,
	}
}

func NotFound(resource string) *AppError {
	return &AppError{
		Code:    CodeNotFound,
		Message: fmt.Sprintf("%s not found", resource),
		Status:  404,
	}
}

func Unauthorized(message string) *AppError {
	return &AppError{
		Code:    CodeUnauthorized,
		Message: message,
		Status:  401,
	}
}

func Forbidden(message string) *AppError {
	return &AppError{
		Code:    CodeForbidden,
		Message: message,
		Status:  403,
	}
}

func Conflict(message string) *AppError {
	return &AppError{
		Code:    CodeConflict,
		Message: message,
		Status:  409,
	}
}

func Internal(message string, details string) *AppError {
	return &AppError{
		Code:    CodeInternalError,
		Message: message,
		Details: details,
		Status:  500,
	}
}

func BadRequest(message string) *AppError {
	return &AppError{
		Code:    CodeBadRequest,
		Message: message,
		Status:  400,
	}
}

func Unprocessable(message string, details string) *AppError {
	return &AppError{
		Code:    CodeUnprocessable,
		Message: message,
		Details: details,
		Status:  422,
	}
}
