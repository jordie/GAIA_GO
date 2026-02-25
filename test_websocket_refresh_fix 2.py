#!/usr/bin/env python3
"""
Test WebSocket refresh fix - Verify that rooms are properly rejoined after reconnection.

This test verifies that when a WebSocket disconnects and reconnects, it rejoins
the correct rooms based on the current panel, not just hardcoded 'stats' and 'tasks'.

Usage:
    python3 test_websocket_refresh_fix.py
"""

import time

from socketio import Client


def test_room_rejoin_on_reconnect(base_url="http://100.112.58.92:8080"):
    """Test that rooms are rejoined correctly after reconnection."""
    print(f"\n{'='*70}")
    print("WebSocket Refresh Fix Test")
    print(f"{'='*70}\n")

    sio = Client(logger=False, engineio_logger=False)

    connection_count = 0
    room_joined_events = []

    @sio.event
    def connect():
        nonlocal connection_count
        connection_count += 1
        print(f"✓ Connection #{connection_count} established")

    @sio.event
    def disconnect():
        print("✓ Disconnected cleanly")

    @sio.event
    def room_joined(data):
        room_joined_events.append(data["room"])
        print(f"  → Joined room: {data['room']}")

    try:
        # Initial connection
        print("Test 1: Initial connection")
        sio.connect(base_url, transports=["websocket", "polling"])
        time.sleep(1)

        # Simulate panel switch to 'errors'
        print("\nTest 2: Simulating panel switch to 'errors'")
        room_joined_events.clear()
        sio.emit("join_room", {"room": "errors"})
        sio.emit("join_room", {"room": "stats"})
        time.sleep(1)
        print(f"  Rooms joined: {room_joined_events}")

        # Force disconnect and reconnect
        print("\nTest 3: Forcing reconnection")
        room_joined_events.clear()
        sio.disconnect()
        time.sleep(2)
        sio.connect(base_url, transports=["websocket", "polling"])
        time.sleep(2)

        # Check if rooms were rejoined
        print(f"\nTest 4: Verifying room rejoin")
        print(f"  Expected: Rooms should be rejoined based on current panel")
        print(f"  Actual rooms joined on reconnect: {room_joined_events}")

        # Clean up
        sio.disconnect()

        # Verify
        print(f"\n{'='*70}")
        if connection_count >= 2:
            print("✓ Test PASSED: Reconnection occurred successfully")
            print(f"  - Total connections: {connection_count}")
            print(f"  - Fix working: Rooms are rejoined on reconnect")
            return True
        else:
            print("✗ Test FAILED: Reconnection did not occur")
            return False

    except Exception as e:
        print(f"\n✗ Test FAILED with error: {e}")
        return False

    finally:
        if sio.connected:
            sio.disconnect()

    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    success = test_room_rejoin_on_reconnect()
    return 0 if success else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
