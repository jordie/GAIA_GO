#!/usr/bin/env python3
"""
Binary Search Algorithm Implementation

Binary search is an efficient algorithm for finding a target value within a sorted array.
Time Complexity: O(log n)
Space Complexity: O(1) for iterative, O(log n) for recursive
"""


def binary_search_iterative(arr, target):
    """
    Iterative implementation of binary search.

    Args:
        arr: Sorted list of elements
        target: Element to search for

    Returns:
        Index of target if found, -1 otherwise
    """
    left = 0
    right = len(arr) - 1

    while left <= right:
        mid = left + (right - left) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


def binary_search_recursive(arr, target, left=0, right=None):
    """
    Recursive implementation of binary search.

    Args:
        arr: Sorted list of elements
        target: Element to search for
        left: Left boundary (default 0)
        right: Right boundary (default len(arr) - 1)

    Returns:
        Index of target if found, -1 otherwise
    """
    if right is None:
        right = len(arr) - 1

    if left > right:
        return -1

    mid = left + (right - left) // 2

    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search_recursive(arr, target, mid + 1, right)
    else:
        return binary_search_recursive(arr, target, left, mid - 1)


def binary_search_first_occurrence(arr, target):
    """
    Find the first occurrence of target in array with duplicates.

    Args:
        arr: Sorted list of elements (may contain duplicates)
        target: Element to search for

    Returns:
        Index of first occurrence if found, -1 otherwise
    """
    left = 0
    right = len(arr) - 1
    result = -1

    while left <= right:
        mid = left + (right - left) // 2

        if arr[mid] == target:
            result = mid
            right = mid - 1
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return result


def binary_search_last_occurrence(arr, target):
    """
    Find the last occurrence of target in array with duplicates.

    Args:
        arr: Sorted list of elements (may contain duplicates)
        target: Element to search for

    Returns:
        Index of last occurrence if found, -1 otherwise
    """
    left = 0
    right = len(arr) - 1
    result = -1

    while left <= right:
        mid = left + (right - left) // 2

        if arr[mid] == target:
            result = mid
            left = mid + 1
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return result


if __name__ == "__main__":
    # Example usage
    sorted_array = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

    print("Array:", sorted_array)
    print()

    # Test iterative version
    target = 7
    result = binary_search_iterative(sorted_array, target)
    print(f"Iterative search for {target}: index {result}")

    # Test recursive version
    target = 13
    result = binary_search_recursive(sorted_array, target)
    print(f"Recursive search for {target}: index {result}")

    # Test not found
    target = 8
    result = binary_search_iterative(sorted_array, target)
    print(f"Search for {target} (not in array): {result}")

    print()

    # Test with duplicates
    array_with_duplicates = [1, 2, 2, 2, 3, 4, 4, 5, 6, 6, 6, 6, 7]
    print("Array with duplicates:", array_with_duplicates)

    target = 6
    first = binary_search_first_occurrence(array_with_duplicates, target)
    last = binary_search_last_occurrence(array_with_duplicates, target)
    print(f"First occurrence of {target}: index {first}")
    print(f"Last occurrence of {target}: index {last}")
    print(f"Total occurrences: {last - first + 1 if first != -1 else 0}")
