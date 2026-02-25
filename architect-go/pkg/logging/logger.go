package logging

import (
	"fmt"
	"log"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// Logger wraps zap.Logger for structured logging
type Logger struct {
	zap *zap.Logger
	sugar *zap.SugaredLogger
}

// LogLevel represents the logging level
type LogLevel string

const (
	DebugLevel LogLevel = "debug"
	InfoLevel  LogLevel = "info"
	WarnLevel  LogLevel = "warn"
	ErrorLevel LogLevel = "error"
	FatalLevel LogLevel = "fatal"
	PanicLevel LogLevel = "panic"
)

// NewLogger creates a new structured logger
func NewLogger(level LogLevel, format string) (*Logger, error) {
	// Convert LogLevel to zapcore.Level
	zapLevel := stringToZapLevel(level)

	var config zap.Config

	if format == "json" {
		// JSON format for production
		config = zap.NewProductionConfig()
	} else {
		// Human-readable format for development
		config = zap.NewDevelopmentConfig()
		config.EncoderConfig.EncodeLevel = zapcore.CapitalColorLevelEncoder
	}

	config.Level = zap.NewAtomicLevelAt(zapLevel)

	zapLogger, err := config.Build()
	if err != nil {
		return nil, fmt.Errorf("failed to build logger: %w", err)
	}

	return &Logger{
		zap:   zapLogger,
		sugar: zapLogger.Sugar(),
	}, nil
}

// stringToZapLevel converts string to zapcore.Level
func stringToZapLevel(level LogLevel) zapcore.Level {
	switch level {
	case DebugLevel:
		return zapcore.DebugLevel
	case InfoLevel:
		return zapcore.InfoLevel
	case WarnLevel:
		return zapcore.WarnLevel
	case ErrorLevel:
		return zapcore.ErrorLevel
	case FatalLevel:
		return zapcore.FatalLevel
	case PanicLevel:
		return zapcore.PanicLevel
	default:
		return zapcore.InfoLevel
	}
}

// Debug logs a debug message
func (l *Logger) Debug(msg string, fields ...zap.Field) {
	l.zap.Debug(msg, fields...)
}

// Debugf logs a formatted debug message
func (l *Logger) Debugf(format string, args ...interface{}) {
	l.sugar.Debugf(format, args...)
}

// Info logs an info message
func (l *Logger) Info(msg string, fields ...zap.Field) {
	l.zap.Info(msg, fields...)
}

// Infof logs a formatted info message
func (l *Logger) Infof(format string, args ...interface{}) {
	l.sugar.Infof(format, args...)
}

// Warn logs a warning message
func (l *Logger) Warn(msg string, fields ...zap.Field) {
	l.zap.Warn(msg, fields...)
}

// Warnf logs a formatted warning message
func (l *Logger) Warnf(format string, args ...interface{}) {
	l.sugar.Warnf(format, args...)
}

// Error logs an error message
func (l *Logger) Error(msg string, fields ...zap.Field) {
	l.zap.Error(msg, fields...)
}

// Errorf logs a formatted error message
func (l *Logger) Errorf(format string, args ...interface{}) {
	l.sugar.Errorf(format, args...)
}

// Fatal logs a fatal message and exits
func (l *Logger) Fatal(msg string, fields ...zap.Field) {
	l.zap.Fatal(msg, fields...)
}

// Fatalf logs a formatted fatal message and exits
func (l *Logger) Fatalf(format string, args ...interface{}) {
	l.sugar.Fatalf(format, args...)
}

// Panic logs a panic message and panics
func (l *Logger) Panic(msg string, fields ...zap.Field) {
	l.zap.Panic(msg, fields...)
}

// Panicf logs a formatted panic message and panics
func (l *Logger) Panicf(format string, args ...interface{}) {
	l.sugar.Panicf(format, args...)
}

// With returns a new logger with additional fields
func (l *Logger) With(fields ...zap.Field) *Logger {
	ifields := make([]interface{}, len(fields))
	for i, f := range fields {
		ifields[i] = f
	}
	return &Logger{
		zap:   l.zap.With(fields...),
		sugar: l.zap.Sugar().With(ifields...),
	}
}

// WithError returns a new logger with error field
func (l *Logger) WithError(err error) *Logger {
	return l.With(zap.Error(err))
}

// Sync flushes any buffered log entries
func (l *Logger) Sync() error {
	return l.zap.Sync()
}

// Close closes the logger
func (l *Logger) Close() error {
	return l.Sync()
}

// Global logger instance
var globalLogger *Logger

// Init initializes the global logger
func Init(level LogLevel, format string) error {
	logger, err := NewLogger(level, format)
	if err != nil {
		return err
	}
	globalLogger = logger
	return nil
}

// Get returns the global logger
func Get() *Logger {
	if globalLogger == nil {
		// Create a default logger if not initialized
		logger, err := NewLogger(InfoLevel, "json")
		if err != nil {
			log.Fatalf("Failed to create default logger: %v", err)
		}
		globalLogger = logger
	}
	return globalLogger
}

// Convenience functions using global logger
func Debug(msg string, fields ...zap.Field) {
	Get().Debug(msg, fields...)
}

func Debugf(format string, args ...interface{}) {
	Get().Debugf(format, args...)
}

func Info(msg string, fields ...zap.Field) {
	Get().Info(msg, fields...)
}

func Infof(format string, args ...interface{}) {
	Get().Infof(format, args...)
}

func Warn(msg string, fields ...zap.Field) {
	Get().Warn(msg, fields...)
}

func Warnf(format string, args ...interface{}) {
	Get().Warnf(format, args...)
}

func Error(msg string, fields ...zap.Field) {
	Get().Error(msg, fields...)
}

func Errorf(format string, args ...interface{}) {
	Get().Errorf(format, args...)
}

func Fatal(msg string, fields ...zap.Field) {
	Get().Fatal(msg, fields...)
}

func Fatalf(format string, args ...interface{}) {
	Get().Fatalf(format, args...)
}

func Panic(msg string, fields ...zap.Field) {
	Get().Panic(msg, fields...)
}

func Panicf(format string, args ...interface{}) {
	Get().Panicf(format, args...)
}

func With(fields ...zap.Field) *Logger {
	return Get().With(fields...)
}

func WithError(err error) *Logger {
	return Get().WithError(err)
}
