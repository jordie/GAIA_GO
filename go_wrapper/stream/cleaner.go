package stream

import (
	"bytes"
	"regexp"
)

// ANSICleaner strips terminal escape codes from byte streams
type ANSICleaner struct {
	// Compiled regex patterns for escape sequences
	csiPattern   *regexp.Regexp // Control Sequence Introducer
	oscPattern   *regexp.Regexp // Operating System Command
	simpleEscape *regexp.Regexp // Simple escapes like \x1b[m
}

// NewANSICleaner creates a new ANSI cleaner
func NewANSICleaner() *ANSICleaner {
	return &ANSICleaner{
		// CSI sequences: ESC [ ... (letter)
		// Matches things like: \x1b[0m, \x1b[1;32m, \x1b[2K, etc.
		csiPattern: regexp.MustCompile(`\x1b\[[0-9;?]*[A-Za-z]`),

		// OSC sequences: ESC ] ... (ST or BEL)
		// Matches things like: \x1b]0;title\x07, \x1b]0;title\x1b\\
		oscPattern: regexp.MustCompile(`\x1b\][^\x07\x1b]*(\x07|\x1b\\)`),

		// Simple escapes: ESC followed by single char
		// Matches things like: \x1b(B, \x1b)0
		simpleEscape: regexp.MustCompile(`\x1b[\(\)][A-Za-z0-9]`),
	}
}

// Clean removes all ANSI escape codes from input bytes
// Preserves newlines, tabs, and regular text
func (c *ANSICleaner) Clean(input []byte) []byte {
	// Apply patterns in order
	result := c.csiPattern.ReplaceAll(input, []byte{})
	result = c.oscPattern.ReplaceAll(result, []byte{})
	result = c.simpleEscape.ReplaceAll(result, []byte{})

	// Additional cleanup: remove any remaining ESC sequences
	// This catches edge cases like \x1b7, \x1b8 (save/restore cursor)
	result = bytes.ReplaceAll(result, []byte{0x1b, '7'}, []byte{})
	result = bytes.ReplaceAll(result, []byte{0x1b, '8'}, []byte{})
	result = bytes.ReplaceAll(result, []byte{0x1b, 'c'}, []byte{})

	// Remove carriage returns that aren't followed by newline
	// (These cause overwriting in terminals but are noise in logs)
	result = cleanCarriageReturns(result)

	return result
}

// cleanCarriageReturns removes standalone \r characters
// but preserves \r\n (Windows line endings)
func cleanCarriageReturns(input []byte) []byte {
	var result []byte
	for i := 0; i < len(input); i++ {
		if input[i] == '\r' {
			// Keep \r only if followed by \n
			if i+1 < len(input) && input[i+1] == '\n' {
				result = append(result, '\r')
			}
			// Otherwise skip it
		} else {
			result = append(result, input[i])
		}
	}
	return result
}

// CleanString is a convenience method for string input
func (c *ANSICleaner) CleanString(input string) string {
	return string(c.Clean([]byte(input)))
}
