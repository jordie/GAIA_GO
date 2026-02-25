#!/usr/bin/env python3
"""
HTTPS Wrapper with HTTP Redirect

Listens on a single port and handles both HTTP and HTTPS:
- HTTPS connections are proxied to the Flask app
- HTTP connections receive a redirect to HTTPS

Usage:
    python3 https_wrapper.py --port 8085
"""

import argparse
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / os.environ.get("APP_ENV", "prod")
CERT_FILE = DATA_DIR / "server.crt"
KEY_FILE = DATA_DIR / "server.key"


def generate_certs():
    """Generate self-signed certificates if needed."""
    if not CERT_FILE.exists():
        print("Generating SSL certificates...")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(KEY_FILE),
                "-out",
                str(CERT_FILE),
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
        )


def handle_client(client_socket, client_address, ssl_context, flask_port, public_port):
    """Handle incoming connection - detect HTTP vs HTTPS."""
    try:
        # Peek at first bytes to detect protocol
        client_socket.settimeout(5)
        first_bytes = client_socket.recv(5, socket.MSG_PEEK)

        if not first_bytes:
            client_socket.close()
            return

        # TLS handshake starts with 0x16 (22 = handshake) 0x03 (SSL 3.0+)
        is_tls = first_bytes[0] == 0x16 and first_bytes[1] == 0x03

        if is_tls:
            # HTTPS - wrap socket and proxy to Flask
            try:
                ssl_socket = ssl_context.wrap_socket(client_socket, server_side=True)
                proxy_to_flask(ssl_socket, flask_port, use_ssl=True)
            except ssl.SSLError as e:
                pass  # Client disconnected or invalid TLS
        else:
            # HTTP - send redirect
            send_http_redirect(client_socket, client_address, public_port)

    except socket.timeout:
        pass
    except Exception as e:
        pass
    finally:
        try:
            client_socket.close()
        except:
            pass


def send_http_redirect(client_socket, client_address, https_port):
    """Send HTTP 301 redirect to HTTPS."""
    try:
        # Read the HTTP request to get the path
        request = b""
        while b"\r\n\r\n" not in request and len(request) < 4096:
            chunk = client_socket.recv(1024)
            if not chunk:
                break
            request += chunk

        # Parse the request line
        request_line = request.split(b"\r\n")[0].decode("utf-8", errors="ignore")
        parts = request_line.split()
        path = parts[1] if len(parts) > 1 else "/"

        # Get Host header
        host = "100.112.58.92"
        for line in request.split(b"\r\n"):
            if line.lower().startswith(b"host:"):
                host = line.split(b":", 1)[1].strip().decode("utf-8", errors="ignore")
                host = host.split(":")[0]  # Remove port if present
                break

        # Send redirect response
        redirect_url = f"https://{host}:{https_port}{path}"
        response = (
            f"HTTP/1.1 301 Moved Permanently\r\n"
            f"Location: {redirect_url}\r\n"
            f"Content-Length: 0\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()

        client_socket.sendall(response)
    except Exception as e:
        pass


def proxy_to_flask(ssl_socket, flask_port, use_ssl=True):
    """Proxy the SSL connection to Flask backend."""
    try:
        # Connect to Flask backend
        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if use_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            backend = ctx.wrap_socket(backend)

        backend.connect(("127.0.0.1", flask_port))
        backend.settimeout(30)
        ssl_socket.settimeout(30)

        # Bidirectional proxy
        def forward(src, dst):
            try:
                while True:
                    data = src.recv(4096)
                    if not data:
                        break
                    dst.sendall(data)
            except:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except:
                    pass

        t1 = threading.Thread(target=forward, args=(ssl_socket, backend))
        t2 = threading.Thread(target=forward, args=(backend, ssl_socket))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    except Exception as e:
        pass
    finally:
        try:
            backend.close()
        except:
            pass


def run_flask_backend(port):
    """Start Flask app on internal port."""
    env = os.environ.copy()
    subprocess.Popen(
        [sys.executable, "app.py", "--ssl", "--port", str(port)],
        cwd=str(BASE_DIR),
        env=env,
        stdout=open("/tmp/arch_flask.log", "w"),
        stderr=subprocess.STDOUT,
    )


def main():
    parser = argparse.ArgumentParser(description="HTTPS wrapper with HTTP redirect")
    parser.add_argument("--port", type=int, default=8085, help="Public port")
    parser.add_argument("--flask-port", type=int, default=8086, help="Internal Flask port")
    args = parser.parse_args()

    generate_certs()

    # Create SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(str(CERT_FILE), str(KEY_FILE))

    # Start Flask backend
    print(f"Starting Flask backend on port {args.flask_port}...")
    run_flask_backend(args.flask_port)
    time.sleep(3)

    # Start listening on public port
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", args.port))
    server.listen(100)

    print(
        f"""
╔════════════════════════════════════════════════════════════╗
║       HTTPS Wrapper with HTTP Redirect                     ║
╠════════════════════════════════════════════════════════════╣
║  Public port: {args.port} (HTTP redirects to HTTPS)
║  Flask port:  {args.flask_port} (internal)
║  http://*:{args.port}  → redirects to → https://*:{args.port}
║  https://*:{args.port} → proxied to Flask
╚════════════════════════════════════════════════════════════╝
"""
    )

    try:
        while True:
            client_socket, client_address = server.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address, ssl_context, args.flask_port, args.port),
            )
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
