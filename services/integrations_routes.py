"""
Third-Party Integrations API Routes

Flask blueprint for integration management endpoints.
"""

import logging
import sqlite3

from flask import Blueprint, jsonify, request, session

logger = logging.getLogger(__name__)

integrations_bp = Blueprint("integrations", __name__, url_prefix="/api/integrations")


def get_db_path():
    """Get database path from app config."""
    from flask import current_app

    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def require_auth(f):
    """Decorator to require authentication."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


def _sanitize_slack_config(config: dict, include_webhook: bool = False) -> dict:
    """Mask sensitive Slack webhook details unless explicitly requested."""
    if not config:
        return config
    safe = dict(config)
    webhook_url = safe.get("webhook_url")
    if not include_webhook and webhook_url:
        safe.pop("webhook_url", None)
        safe["webhook_url_masked"] = "..." + webhook_url[-8:]
    return safe


@integrations_bp.route("", methods=["GET"])
@require_auth
def list_integrations():
    """List all integrations."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())

        integration_type = request.args.get("type")
        provider = request.args.get("provider")
        enabled_only = request.args.get("enabled", "false").lower() == "true"

        integrations = service.list_integrations(
            integration_type=integration_type, provider=provider, enabled_only=enabled_only
        )

        return jsonify({"integrations": integrations, "count": len(integrations)})
    except Exception as e:
        logger.error(f"Failed to list integrations: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("", methods=["POST"])
@require_auth
def create_integration():
    """Create a new integration."""
    try:
        from services.integrations import get_integration_service

        data = request.get_json()

        required = ["name", "type", "provider"]
        for field in required:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        service = get_integration_service(get_db_path())

        integration = service.create_integration(
            name=data["name"],
            integration_type=data["type"],
            provider=data["provider"],
            config=data.get("config", {}),
            credentials=data.get("credentials"),
            enabled=data.get("enabled", True),
            created_by=session.get("user"),
        )

        return jsonify(integration), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>", methods=["GET"])
@require_auth
def get_integration(integration_id):
    """Get integration details."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        integration = service.get_integration(integration_id)

        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        return jsonify(integration)
    except Exception as e:
        logger.error(f"Failed to get integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>", methods=["PUT"])
@require_auth
def update_integration(integration_id):
    """Update an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        data = request.get_json()

        integration = service.update_integration(integration_id, **data)

        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        return jsonify(integration)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>", methods=["DELETE"])
@require_auth
def delete_integration(integration_id):
    """Delete an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())

        # Get name for response
        integration = service.get_integration(integration_id)
        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        if service.delete_integration(integration_id):
            return jsonify(
                {"success": True, "message": f"Deleted integration '{integration['name']}'"}
            )

        return jsonify({"error": "Failed to delete integration"}), 500
    except Exception as e:
        logger.error(f"Failed to delete integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/enable", methods=["POST"])
@require_auth
def enable_integration(integration_id):
    """Enable an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        integration = service.enable_integration(integration_id)

        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        return jsonify(integration)
    except Exception as e:
        logger.error(f"Failed to enable integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/disable", methods=["POST"])
@require_auth
def disable_integration(integration_id):
    """Disable an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        integration = service.disable_integration(integration_id)

        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        return jsonify(integration)
    except Exception as e:
        logger.error(f"Failed to disable integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/test", methods=["POST"])
@require_auth
def test_integration(integration_id):
    """Test integration connection."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        result = service.test_connection(integration_id)

        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Failed to test integration: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/send", methods=["POST"])
@require_auth
def send_integration_event(integration_id):
    """Send an event to an integration."""
    try:
        from services.integrations import get_integration_service

        data = request.get_json()
        event_type = data.get("event_type", "custom")
        payload = data.get("payload", {})

        service = get_integration_service(get_db_path())
        result = service.send_event(integration_id, event_type, payload)

        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Failed to send event: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/events", methods=["GET"])
@require_auth
def get_integration_events(integration_id):
    """Get events for an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        limit = request.args.get("limit", 50, type=int)

        events = service.get_events(integration_id, limit=limit)

        return jsonify({"events": events, "count": len(events)})
    except Exception as e:
        logger.error(f"Failed to get events: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/stats", methods=["GET"])
@require_auth
def get_integration_stats(integration_id):
    """Get statistics for an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        stats = service.get_stats(integration_id)

        if stats.get("error"):
            return jsonify(stats), 404

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/stats", methods=["GET"])
@require_auth
def get_all_integration_stats():
    """Get overall integration statistics."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        stats = service.get_stats()

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/types", methods=["GET"])
@require_auth
def get_integration_types():
    """Get available integration types."""
    from services.integrations import INTEGRATION_TYPES

    return jsonify({"types": INTEGRATION_TYPES})


@integrations_bp.route("/providers", methods=["GET"])
@require_auth
def get_providers():
    """Get available providers, optionally filtered by type."""
    from services.integrations import INTEGRATION_TYPES, PROVIDERS

    integration_type = request.args.get("type")

    if integration_type:
        if integration_type not in PROVIDERS:
            return jsonify({"error": f"Unknown type: {integration_type}"}), 400

        providers = {}
        for name, info in PROVIDERS[integration_type].items():
            providers[name] = {
                "name": info["name"],
                "auth_type": info.get("auth_type"),
                "config_schema": info.get("config_schema", {}),
                "credential_schema": {
                    k: {sk: sv for sk, sv in v.items() if sk != "sensitive"}
                    for k, v in info.get("credential_schema", {}).items()
                },
            }

        return jsonify(
            {
                "type": integration_type,
                "type_name": INTEGRATION_TYPES.get(integration_type),
                "providers": providers,
            }
        )

    # Return all providers grouped by type
    all_providers = {}
    for itype, providers in PROVIDERS.items():
        all_providers[itype] = {
            "type_name": INTEGRATION_TYPES.get(itype),
            "providers": {
                name: {"name": info["name"], "auth_type": info.get("auth_type")}
                for name, info in providers.items()
            },
        }

    return jsonify({"providers": all_providers})


# =============================================================================
# Slack Integration Endpoints
# =============================================================================


@integrations_bp.route("/slack", methods=["GET"])
@require_auth
def list_slack_configs():
    """List Slack webhook configurations."""
    try:
        import slack_integration
        from db import get_connection

        include_webhook = request.args.get("include_webhook", "false").lower() == "true"

        with get_connection() as conn:
            configs = slack_integration.get_slack_configs(conn)

        configs = [_sanitize_slack_config(c, include_webhook=include_webhook) for c in configs]
        return jsonify({"configs": configs, "count": len(configs)})
    except Exception as e:
        logger.error(f"Failed to list Slack configs: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/<int:config_id>", methods=["GET"])
@require_auth
def get_slack_config(config_id):
    """Get a Slack configuration."""
    try:
        import slack_integration
        from db import get_connection

        include_webhook = request.args.get("include_webhook", "false").lower() == "true"

        with get_connection() as conn:
            config = slack_integration.get_slack_config(conn, config_id=config_id)

        if not config:
            return jsonify({"error": "Slack config not found"}), 404

        return jsonify(_sanitize_slack_config(config, include_webhook=include_webhook))
    except Exception as e:
        logger.error(f"Failed to get Slack config: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack", methods=["POST"])
@require_auth
def create_slack_config():
    """Create a Slack webhook configuration."""
    try:
        import slack_integration
        from db import get_connection

        data = request.get_json() or {}

        for field in ["name", "webhook_url"]:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        enabled = data.get("enabled", True)

        with get_connection() as conn:
            config_id = slack_integration.create_slack_config(
                conn,
                name=data["name"],
                webhook_url=data["webhook_url"],
                channel=data.get("channel"),
                username=data.get("username", "Architect Bot"),
                icon_emoji=data.get("icon_emoji", ":robot_face:"),
                events=data.get("events"),
                filters=data.get("filters"),
            )

            if enabled is False:
                slack_integration.update_slack_config(conn, config_id, enabled=False)

            config = slack_integration.get_slack_config(conn, config_id=config_id)

        return jsonify(_sanitize_slack_config(config)), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except sqlite3.IntegrityError:
        return jsonify({"error": "Slack config name already exists"}), 409
    except Exception as e:
        logger.error(f"Failed to create Slack config: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/<int:config_id>", methods=["PUT"])
@require_auth
def update_slack_config(config_id):
    """Update a Slack webhook configuration."""
    try:
        import slack_integration
        from db import get_connection

        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "Request body required"}), 400

        updates = {
            "name": data.get("name"),
            "webhook_url": data.get("webhook_url"),
            "channel": data.get("channel"),
            "username": data.get("username"),
            "icon_emoji": data.get("icon_emoji"),
            "enabled": data.get("enabled"),
            "events": data.get("events"),
            "filters": data.get("filters"),
        }

        with get_connection() as conn:
            existing = slack_integration.get_slack_config(conn, config_id=config_id)
            if not existing:
                return jsonify({"error": "Slack config not found"}), 404

            updated = slack_integration.update_slack_config(conn, config_id, **updates)
            if not updated:
                return jsonify({"error": "No fields to update"}), 400

            config = slack_integration.get_slack_config(conn, config_id=config_id)

        return jsonify(_sanitize_slack_config(config))

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update Slack config: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/<int:config_id>", methods=["DELETE"])
@require_auth
def delete_slack_config(config_id):
    """Delete a Slack webhook configuration."""
    try:
        import slack_integration
        from db import get_connection

        with get_connection() as conn:
            existing = slack_integration.get_slack_config(conn, config_id=config_id)
            if not existing:
                return jsonify({"error": "Slack config not found"}), 404

            slack_integration.delete_slack_config(conn, config_id)

        return jsonify({"success": True, "deleted": config_id})
    except Exception as e:
        logger.error(f"Failed to delete Slack config: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/test", methods=["POST"])
@require_auth
def test_slack_webhook():
    """Test a Slack webhook URL."""
    try:
        import slack_integration

        data = request.get_json() or {}
        webhook_url = data.get("webhook_url")
        if not webhook_url:
            return jsonify({"error": "webhook_url is required"}), 400

        result = slack_integration.test_slack_webhook(
            webhook_url=webhook_url, channel=data.get("channel")
        )
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Failed to test Slack webhook: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/<int:config_id>/test", methods=["POST"])
@require_auth
def test_slack_config(config_id):
    """Send a test message using an existing Slack configuration."""
    try:
        import slack_integration
        from db import get_connection

        with get_connection() as conn:
            config = slack_integration.get_slack_config(conn, config_id=config_id)

        if not config:
            return jsonify({"error": "Slack config not found"}), 404

        result = slack_integration.test_slack_webhook(
            webhook_url=config["webhook_url"], channel=config.get("channel")
        )
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Failed to test Slack config: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/messages", methods=["GET"])
@require_auth
def get_slack_messages():
    """Get Slack message history."""
    try:
        import slack_integration
        from db import get_connection

        config_id = request.args.get("config_id", type=int)
        event_type = request.args.get("event_type")
        limit = min(request.args.get("limit", 50, type=int), 500)
        offset = request.args.get("offset", 0, type=int)

        with get_connection() as conn:
            messages = slack_integration.get_message_history(
                conn, config_id=config_id, event_type=event_type, limit=limit, offset=offset
            )

        return jsonify({"messages": messages, "count": len(messages)})
    except Exception as e:
        logger.error(f"Failed to get Slack message history: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/stats", methods=["GET"])
@require_auth
def get_slack_stats():
    """Get Slack integration statistics."""
    try:
        import slack_integration
        from db import get_connection

        config_id = request.args.get("config_id", type=int)
        days = request.args.get("days", 7, type=int)

        with get_connection() as conn:
            stats = slack_integration.get_slack_stats(conn, config_id=config_id, days=days)

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get Slack stats: {e}")
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/slack/events", methods=["GET"])
@require_auth
def get_slack_events():
    """Get available Slack event types."""
    import slack_integration

    return jsonify({"events": slack_integration.EVENT_TYPES})


@integrations_bp.route("/webhook/<integration_name>", methods=["POST"])
def receive_webhook(integration_name):
    """Receive incoming webhook from an integration."""
    try:
        from services.integrations import get_integration_service

        service = get_integration_service(get_db_path())
        integration = service.get_integration_by_name(integration_name)

        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        if not integration["enabled"]:
            return jsonify({"error": "Integration is disabled"}), 400

        # Parse the incoming payload
        payload = request.get_json() or {}

        # Determine event type from headers or payload
        event_type = (
            request.headers.get("X-GitHub-Event")
            or request.headers.get("X-GitLab-Event")
            or payload.get("type")
            or "webhook"
        )

        # Log the event
        with service._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO integration_events
                (integration_id, event_type, payload, source_id)
                VALUES (?, ?, ?, ?)
            """,
                (
                    integration["id"],
                    event_type,
                    request.data.decode() if request.data else None,
                    payload.get("id") or request.headers.get("X-Request-ID"),
                ),
            )
            conn.commit()

        logger.info(f"Received webhook for {integration_name}: {event_type}")

        return jsonify({"success": True, "event_type": event_type})

    except Exception as e:
        logger.error(f"Failed to process webhook: {e}")
        return jsonify({"error": str(e)}), 500
