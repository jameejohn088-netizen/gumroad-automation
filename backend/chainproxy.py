"""Local CONNECT proxy that chains to the authed upstream egress proxy.

Listens on 127.0.0.1:8888 without auth; forwards CONNECT requests to the
upstream proxy from $https_proxy, injecting Proxy-Authorization.
Kept under ~/workspace (persistent) — /tmp is ephemeral on this VM.
"""
import asyncio
import base64
import os
from urllib.parse import urlparse


def parse_upstream():
    p = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
    u = urlparse(p)
    if not u.hostname or not u.port:
        raise RuntimeError("no usable proxy in env")
    return u.username or "", u.password or "", u.hostname, u.port


UPSTREAM = parse_upstream()


async def pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter):
    try:
        while True:
            data = await r.read(65536)
            if not data:
                break
            w.write(data)
            await w.drain()
    except Exception:
        pass
    finally:
        try:
            w.close()
        except Exception:
            pass


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        line = await reader.readline()
        parts = line.decode("iso-8859-1").split()
        if len(parts) < 2 or parts[0].upper() != "CONNECT":
            writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        target = parts[1]
        while True:
            h = await reader.readline()
            if h in (b"\r\n", b"\n", b""):
                break
        user, pw, uhost, uport = UPSTREAM
        ur, uw = await asyncio.open_connection(uhost, uport)
        auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
        uw.write(
            f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n"
            f"Proxy-Authorization: Basic {auth}\r\n\r\n".encode()
        )
        await uw.drain()
        resp = await ur.readline()
        while True:
            h = await ur.readline()
            if h in (b"\r\n", b"\n", b""):
                break
        if b"200" not in resp:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
            writer.close()
            uw.close()
            return
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        await asyncio.gather(pipe(reader, uw), pipe(ur, writer))
    except Exception:
        try:
            writer.close()
        except Exception:
            pass


async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", 8888)
    print("chain proxy on 127.0.0.1:8888", flush=True)
    await srv.serve_forever()


asyncio.run(main())
