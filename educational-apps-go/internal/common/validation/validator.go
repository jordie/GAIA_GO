package validation

import (
	"fmt"

	"github.com/go-playground/validator/v10"
)

var validate *validator.Validate

func init() {
	validate = validator.New()
}

type ValidationError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
}

func Validate(data interface{}) []ValidationError {
	err := validate.Struct(data)
	if err == nil {
		return nil
	}

	var errors []ValidationError
	for _, err := range err.(validator.ValidationErrors) {
		errors = append(errors, ValidationError{
			Field:   err.Field(),
			Message: fmt.Sprintf("field must satisfy %s constraint", err.Tag()),
		})
	}
	return errors
}

// Custom validators
func ValidateStringRange(s string, min, max int) error {
	if len(s) < min || len(s) > max {
		return fmt.Errorf("string length must be between %d and %d", min, max)
	}
	return nil
}

func ValidateIntRange(value, min, max int) error {
	if value < min || value > max {
		return fmt.Errorf("value must be between %d and %d", min, max)
	}
	return nil
}

func ValidateFloatRange(value float64, min, max float64) error {
	if value < min || value > max {
		return fmt.Errorf("value must be between %f and %f", min, max)
	}
	return nil
}
