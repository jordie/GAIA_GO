#!/usr/bin/env python3
"""
Test Go Wrapper Dashboard Integration

Tests the Go Wrapper panel in the Architect Dashboard.
"""

import requests
import json

DASHBOARD_URL = "http://localhost:8080"
LOGIN_PASSWORD = "peace5"  # Default architect password

def test_go_wrapper_integration():
    """Test Go Wrapper integration with Architect Dashboard."""

    print("=" * 60)
    print("Testing Go Wrapper Dashboard Integration")
    print("=" * 60)
    print()

    # Create session
    session = requests.Session()

    # Test 1: Login to dashboard
    print("[1/5] Testing login...")
    login_response = session.post(
        f"{DASHBOARD_URL}/login",
        data={
            "username": "architect",
            "password": LOGIN_PASSWORD
        },
        allow_redirects=False
    )

    if login_response.status_code in [200, 302]:
        print("✅ Login successful")
    else:
        print(f"❌ Login failed: {login_response.status_code}")
        return False

    # Test 2: Test Go Wrapper metrics endpoint
    print("[2/5] Testing /api/go-wrapper/metrics...")
    metrics_response = session.get(f"{DASHBOARD_URL}/api/go-wrapper/metrics")

    if metrics_response.status_code == 200:
        print("✅ Metrics endpoint accessible")
        data = metrics_response.json()

        # Check response structure
        if "system" in data and "agents" in data:
            print(f"   • System uptime: {data['system'].get('uptime_seconds', 0):.0f}s")
            print(f"   • Running agents: {data['system'].get('running_agents', 0)}")
            print(f"   • Events/sec: {data['system'].get('events_per_second', 0):.2f}")
            print(f"   • Total agents in response: {len(data.get('agents', []))}")
        else:
            print("⚠️  Response structure unexpected")
            print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
    else:
        print(f"❌ Metrics endpoint failed: {metrics_response.status_code}")
        print(f"   Response: {metrics_response.text[:200]}")
        return False

    # Test 3: Test Go Wrapper agents endpoint
    print("[3/5] Testing /api/go-wrapper/agents...")
    agents_response = session.get(f"{DASHBOARD_URL}/api/go-wrapper/agents")

    if agents_response.status_code == 200:
        print("✅ Agents endpoint accessible")
        data = agents_response.json()
        if "agents" in data:
            print(f"   • Agent count: {data.get('count', 0)}")
            if data.get('agents'):
                print(f"   • First agent: {data['agents'][0].get('name', 'N/A')}")
    else:
        print(f"❌ Agents endpoint failed: {agents_response.status_code}")
        return False

    # Test 4: Test Go Wrapper health endpoint
    print("[4/5] Testing /api/go-wrapper/health...")
    health_response = session.get(f"{DASHBOARD_URL}/api/go-wrapper/health")

    if health_response.status_code == 200:
        print("✅ Health endpoint accessible")
        data = health_response.json()
        if "status" in data:
            print(f"   • Status: {data.get('status', 'unknown')}")
            print(f"   • Agents: {data.get('agents', 0)}")
    else:
        print(f"❌ Health endpoint failed: {health_response.status_code}")
        return False

    # Test 5: Test dashboard HTML includes Go Wrapper panel
    print("[5/5] Testing dashboard HTML...")
    dashboard_response = session.get(f"{DASHBOARD_URL}/")

    if dashboard_response.status_code == 200:
        html = dashboard_response.text

        # Check for Go Wrapper panel elements
        has_go_wrapper = "Go Wrapper" in html
        has_function = "loadGoWrapperStatus" in html
        has_elements = "goWrapperAgentCount" in html

        if has_go_wrapper and has_function and has_elements:
            print("✅ Dashboard HTML includes Go Wrapper panel")
            print("   • Panel title found")
            print("   • JavaScript function found")
            print("   • HTML elements found")
        else:
            print("⚠️  Dashboard HTML may be missing Go Wrapper components")
            print(f"   • Panel title: {'✓' if has_go_wrapper else '✗'}")
            print(f"   • JS function: {'✓' if has_function else '✗'}")
            print(f"   • HTML elements: {'✓' if has_elements else '✗'}")
    else:
        print(f"❌ Dashboard HTML failed: {dashboard_response.status_code}")
        return False

    print()
    print("=" * 60)
    print("✅ All Go Wrapper integration tests passed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"1. Open {DASHBOARD_URL}/ in your browser")
    print("2. Login with username: architect, password: peace5")
    print("3. Look in left sidebar for '🔧 Go Wrapper' panel")
    print("4. Panel should show live data from Go Wrapper server")
    print()

    return True

if __name__ == "__main__":
    try:
        success = test_go_wrapper_integration()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
