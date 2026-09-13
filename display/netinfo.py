"""
Network helpers shared by the app web servers.
"""
import socket


def local_ip() -> str:
    """This machine's address on the local network.

    The UDP "connect" sends no packets — it just makes the kernel pick the
    outbound interface — so this never blocks and works without internet.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
