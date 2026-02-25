def celsius_to_fahrenheit(celsius):
    """
    Convert temperature from Celsius to Fahrenheit.

    Formula: F = (C × 9/5) + 32

    Args:
        celsius (float): Temperature in Celsius

    Returns:
        float: Temperature in Fahrenheit
    """
    fahrenheit = (celsius * 9 / 5) + 32
    return fahrenheit


if __name__ == "__main__":
    # Example usage
    test_temps = [0, 100, -40, 37, 25]

    print("Celsius to Fahrenheit Conversion")
    print("-" * 35)
    for temp_c in test_temps:
        temp_f = celsius_to_fahrenheit(temp_c)
        print(f"{temp_c:>6.1f}°C = {temp_f:>6.1f}°F")
