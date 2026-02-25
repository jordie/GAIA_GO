"""
Fibonacci sequence calculator with memoization optimization.
"""


def fibonacci_memoized(n, memo=None):
    """
    Calculate the nth Fibonacci number using recursive approach with memoization.

    Args:
        n (int): The position in the Fibonacci sequence (0-indexed)
        memo (dict): Cache for previously calculated values

    Returns:
        int: The nth Fibonacci number

    Time Complexity: O(n) with memoization (vs O(2^n) without)
    Space Complexity: O(n) for the memoization cache

    Examples:
        >>> fibonacci_memoized(0)
        0
        >>> fibonacci_memoized(1)
        1
        >>> fibonacci_memoized(10)
        55
        >>> fibonacci_memoized(50)
        12586269025
    """
    if memo is None:
        memo = {}

    # Base cases
    if n == 0:
        return 0
    if n == 1:
        return 1

    # Check if already calculated
    if n in memo:
        return memo[n]

    # Calculate and store in memo
    memo[n] = fibonacci_memoized(n - 1, memo) + fibonacci_memoized(n - 2, memo)
    return memo[n]


class FibonacciCalculator:
    """
    Class-based Fibonacci calculator with persistent memoization.
    Useful when calculating multiple Fibonacci numbers.
    """

    def __init__(self):
        """Initialize with empty cache."""
        self.memo = {}

    def calculate(self, n):
        """
        Calculate the nth Fibonacci number.

        Args:
            n (int): The position in the Fibonacci sequence

        Returns:
            int: The nth Fibonacci number
        """
        if n == 0:
            return 0
        if n == 1:
            return 1

        if n in self.memo:
            return self.memo[n]

        self.memo[n] = self.calculate(n - 1) + self.calculate(n - 2)
        return self.memo[n]

    def get_sequence(self, n):
        """
        Get the Fibonacci sequence up to the nth number.

        Args:
            n (int): The number of Fibonacci numbers to generate

        Returns:
            list: List of Fibonacci numbers from F(0) to F(n-1)
        """
        return [self.calculate(i) for i in range(n)]

    def clear_cache(self):
        """Clear the memoization cache."""
        self.memo = {}


if __name__ == "__main__":
    # Example usage
    print("Fibonacci sequence using memoized function:")
    for i in range(15):
        print(f"F({i}) = {fibonacci_memoized(i)}")

    print("\n" + "=" * 50 + "\n")

    # Using the class-based approach
    print("Fibonacci sequence using class-based calculator:")
    calc = FibonacciCalculator()
    sequence = calc.get_sequence(15)
    print(f"First 15 numbers: {sequence}")

    print("\n" + "=" * 50 + "\n")

    # Performance demonstration
    print("Performance test with large number:")
    import time

    # With memoization
    start = time.time()
    result = fibonacci_memoized(100)
    end = time.time()
    print(f"F(100) = {result}")
    print(f"Time with memoization: {(end - start)*1000:.4f}ms")

    # Show cache benefit
    calc = FibonacciCalculator()
    start = time.time()
    for i in range(100):
        calc.calculate(i)
    end = time.time()
    print(f"\nCalculating F(0) to F(99) with persistent cache:")
    print(f"Time: {(end - start)*1000:.4f}ms")
    print(f"Cache size: {len(calc.memo)} entries")
