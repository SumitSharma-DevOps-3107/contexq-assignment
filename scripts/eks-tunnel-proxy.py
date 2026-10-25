"""Loopback CONNECT bridge to one SSM-forwarded EKS endpoint; TLS stays end-to-end.

Run after AWS-StartPortForwardingSessionToRemoteHost maps EKS:443 to localhost.
This proxy never decrypts traffic or accepts arbitrary destination hosts.
"""
import argparse
import select
import socket
import socketserver


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--ssm-port", type=int, default=18443)
    p.add_argument("--port", type=int, default=18444)
    args = p.parse_args()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(15)
            header = bytearray()
            while not header.endswith(b"\r\n\r\n") and len(header) < 8192:
                data = self.request.recv(1)
                if not data:
                    return
                header.extend(data)
            line = bytes(header).split(b"\r\n", 1)[0].decode("ascii", "replace")
            parts = line.split()
            if len(parts) != 3 or parts[0] != "CONNECT" or parts[1] != args.host + ":443":
                self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                return
            try:
                with socket.create_connection(("127.0.0.1", args.ssm_port), timeout=15) as upstream:
                    self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    self.request.settimeout(None)
                    upstream.settimeout(None)
                    while True:
                        ready, _, _ = select.select([self.request, upstream], [], [], 60)
                        for src in ready:
                            data = src.recv(65536)
                            if not data:
                                return
                            (upstream if src is self.request else self.request).sendall(data)
            except (OSError, TimeoutError):
                return

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server(("127.0.0.1", args.port), Handler) as server:
        print("Private EKS CONNECT bridge ready on loopback", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
