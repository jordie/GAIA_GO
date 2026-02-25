#!/usr/bin/env python3
"""
Architect Browser Agent - WebSocket Server
Receives events from Chrome extension and sends commands
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Set

import websockets
from websockets.server import WebSocketServerProtocol

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Server state
connected_clients: Set[WebSocketServerProtocol] = set()
extension_clients: Dict = {}  # Map extension socket to (client_id, remote_address)
command_clients: Set[WebSocketServerProtocol] = set()   # External command clients
pending_commands: Dict = {}  # Map command_id to (requesting_client, command)
extension_pending_commands: Dict = {}  # Map extension_id to list of pending commands
browser_state = {"tabs": {}, "groups": {}, "windows": {}, "last_event": None, "event_count": 0}


async def handle_client(websocket: WebSocketServerProtocol):
    """Handle a connected client (extension or command client)."""
    client_id = id(websocket)
    client_type = "unknown"
    connected_clients.add(websocket)
    logger.info(f"Client connected: {client_id} from {websocket.remote_address}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                # Detect client type from first message
                if client_type == "unknown":
                    if data.get("event") == "CONNECTED":
                        client_type = "extension"
                        ext_id = f"ext_{client_id}"
                        extension_clients[websocket] = (ext_id, websocket.remote_address)
                        extension_pending_commands[ext_id] = []
                        logger.info(f"🔌 Identified as extension: {client_id} ({ext_id})")
                    elif data.get("command"):
                        client_type = "command"
                        command_clients.add(websocket)
                        logger.info(f"Identified as command client: {client_id}")

                await handle_message(websocket, data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from client {client_id}: {e}")
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {e}", exc_info=True)

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_id} ({client_type})")
    finally:
        connected_clients.discard(websocket)
        if websocket in extension_clients:
            ext_id = extension_clients[websocket][0]
            del extension_clients[websocket]
            if ext_id in extension_pending_commands:
                del extension_pending_commands[ext_id]
        command_clients.discard(websocket)


async def handle_message(websocket: WebSocketServerProtocol, data: Dict):
    """Process incoming messages from extension or command clients."""

    # Handle pong
    if data.get("pong"):
        return

    # Handle heartbeat
    if data.get("heartbeat"):
        logger.debug("Heartbeat received")
        return

    # Handle commands FROM external clients - route to extension
    if data.get("command"):
        await handle_command_from_client(websocket, data)
        return

    # Handle events
    if "event" in data:
        event_type = data["event"]
        event_data = data.get("data", {})

        logger.info(f"Event: {event_type}")

        # Update browser state
        browser_state["last_event"] = {
            "type": event_type,
            "data": event_data,
            "timestamp": datetime.now().isoformat(),
        }
        browser_state["event_count"] += 1

        # Handle specific events
        if event_type == "CONNECTED":
            logger.info("Extension connected, waiting for FULL_STATE")

        elif event_type == "FULL_STATE":
            # Update complete browser state
            browser_state["tabs"] = {tab["id"]: tab for tab in event_data.get("tabs", [])}
            browser_state["groups"] = {group["id"]: group for group in event_data.get("groups", [])}
            browser_state["windows"] = {win["id"]: win for win in event_data.get("windows", [])}
            logger.info(
                f"Browser state updated: {len(browser_state['tabs'])} tabs, "
                f"{len(browser_state['groups'])} groups"
            )

        elif event_type == "TAB_CREATED":
            tab = event_data
            browser_state["tabs"][tab["id"]] = tab
            logger.info(f"Tab created: {tab['id']} - {tab.get('title', 'Untitled')}")

        elif event_type == "TAB_CLOSED":
            tab_id = event_data.get("tabId")
            if tab_id in browser_state["tabs"]:
                del browser_state["tabs"][tab_id]
            logger.info(f"Tab closed: {tab_id}")

        elif event_type == "PAGE_LOADED":
            tab_id = event_data.get("tabId")
            if tab_id in browser_state["tabs"]:
                browser_state["tabs"][tab_id].update(
                    {
                        "url": event_data.get("url"),
                        "title": event_data.get("title"),
                        "status": "complete",
                    }
                )
            logger.info(f"Page loaded: {tab_id} - {event_data.get('title')}")

        elif event_type == "GROUP_CREATED":
            group = event_data
            browser_state["groups"][group["id"]] = group
            logger.info(f"Group created: {group['id']} - {group.get('title', 'Untitled')}")

        elif event_type == "COMET_RESPONSE":
            logger.info(f"Comet response: {event_data.get('responseId')}")
            logger.info(f"Text preview: {event_data.get('text', '')[:100]}...")

        elif event_type == "COMMAND_RESULT":
            cmd_id = event_data.get("id")
            status = event_data.get("status")
            logger.info(f"🎯 Command result received: {cmd_id} - {status}")
            if status == "error":
                logger.error(f"❌ Command error: {event_data.get('message')}")
            else:
                logger.info(f"✅ Command succeeded: {cmd_id}")

            # Route response back to requesting client
            if cmd_id in pending_commands:
                requesting_client, original_cmd = pending_commands[cmd_id]
                try:
                    await requesting_client.send(json.dumps({
                        "event": "COMMAND_RESULT",
                        "data": event_data
                    }))
                    logger.info(f"Sent command result back to client: {cmd_id}")
                except Exception as e:
                    logger.error(f"Failed to send result to client: {e}")
                finally:
                    del pending_commands[cmd_id]

        # Check if this is an extension and send pending commands
        if websocket in extension_clients:
            ext_id = extension_clients[websocket][0]
            if ext_id in extension_pending_commands and extension_pending_commands[ext_id]:
                pending = extension_pending_commands[ext_id].pop(0)
                logger.info(f"📤 Sending pending command to extension {ext_id}: {pending.get('id')}")
                try:
                    await websocket.send(json.dumps({
                        "command": pending.get("command"),
                        "id": pending.get("id")
                    }))
                except Exception as e:
                    logger.error(f"Failed to send pending command: {e}")

        # Placeholder for task planner integration
        # TODO: Forward events to task planner for decision-making


async def handle_command_from_client(client_websocket: WebSocketServerProtocol, data: Dict):
    """Handle command from external client and queue to extension."""
    command_data = data.get("command", {})
    cmd_id = command_data.get("id") or f"cmd-{datetime.now().timestamp()}"

    logger.info(f"📨 Command from client: {command_data.get('action')} (id: {cmd_id})")

    # Mark client as command client
    if client_websocket not in command_clients:
        command_clients.add(client_websocket)

    # Check if extensions are available
    if not extension_clients:
        logger.error(f"❌ No extension available for command: {cmd_id}")
        try:
            await client_websocket.send(json.dumps({
                "event": "COMMAND_RESULT",
                "data": {
                    "id": cmd_id,
                    "status": "error",
                    "message": "No browser extension connected"
                }
            }))
        except Exception as e:
            logger.error(f"Failed to send error to client: {e}")
        return

    # Get first available extension
    extension_socket = list(extension_clients.keys())[0]
    ext_id, ext_addr = extension_clients[extension_socket]

    # Track this command for response routing
    pending_commands[cmd_id] = (client_websocket, command_data)

    # Queue command to extension (will be sent on next event)
    extension_pending_commands[ext_id].append({
        "command": command_data,
        "id": cmd_id
    })

    logger.info(f"✅ Queued command {cmd_id} to extension {ext_id} (will send on next event)")
    logger.info(f"   Pending queue size: {len(extension_pending_commands[ext_id])}")


async def send_command(websocket: WebSocketServerProtocol, command: Dict):
    """Send a command to the extension."""
    try:
        json_str = json.dumps(command)
        logger.info(f"📤 Sending to extension: {json_str[:100]}...")
        await websocket.send(json_str)
        logger.info(f"✅ Command sent: {command.get('command', {}).get('action', '?')} (id: {command.get('id')})")
    except Exception as e:
        logger.error(f"❌ Failed to send command: {e}")


async def send_queued_commands():
    """Periodically send queued commands to extensions."""
    while True:
        await asyncio.sleep(2)  # Check every 2 seconds

        for ext_socket, (ext_id, ext_addr) in list(extension_clients.items()):
            if ext_id in extension_pending_commands:
                while extension_pending_commands[ext_id]:
                    pending = extension_pending_commands[ext_id].pop(0)
                    try:
                        logger.info(f"📤 Sending queued command to {ext_id}: {pending.get('id')}")
                        await ext_socket.send(json.dumps({
                            "command": pending.get("command"),
                            "id": pending.get("id")
                        }))
                    except Exception as e:
                        logger.error(f"Failed to send queued command: {e}")
                        # Put it back if send failed
                        extension_pending_commands[ext_id].insert(0, pending)
                        break


async def periodic_ping():
    """Send periodic ping to all connected clients."""
    while True:
        await asyncio.sleep(30)

        if connected_clients:
            logger.debug(f"Pinging {len(connected_clients)} clients")

            for client in list(connected_clients):
                try:
                    await client.send(json.dumps({"ping": True, "test": "can_you_hear_me"}))
                    logger.debug(f"Sent ping to client {id(client)}")
                except Exception as e:
                    logger.warning(f"Failed to ping client {id(client)}: {e}")


async def demo_task():
    """Demo: Send a test command every 60 seconds."""
    await asyncio.sleep(10)  # Wait for initial connection

    while True:
        await asyncio.sleep(60)

        if not connected_clients:
            logger.info("No clients connected for demo")
            continue

        client = list(connected_clients)[0]

        # Demo: Get current tabs
        command = {
            "command": True,
            "id": f"demo-{datetime.now().timestamp()}",
            "action": "GET_TABS",
            "params": {},
        }

        await send_command(client, command)


async def main():
    """Start the WebSocket server."""
    host = "0.0.0.0"  # Listen on all network interfaces for cross-machine connections
    port = 8765

    logger.info(f"Starting Architect Browser Agent WebSocket server on 0.0.0.0:{port}")

    # Start server
    async with websockets.serve(handle_client, host, port):
        logger.info(f"✓ Server listening on ws://{host}:{port}")
        logger.info("Waiting for Chrome extension to connect...")

        # Start background tasks
        _ping_task = asyncio.create_task(periodic_ping())
        _command_task = asyncio.create_task(send_queued_commands())
        # _demo_task = asyncio.create_task(demo_task())  # Uncomment for demo

        # Run forever
        await asyncio.Future()  # Run until cancelled


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nServer shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
