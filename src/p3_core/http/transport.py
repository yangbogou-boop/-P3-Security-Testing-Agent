"""Memory-only scripted transport. Deliberately no socket import or live adapter."""
from collections import deque


class MemoryTransport:
    def __init__(self, *, connect='CONNECTED', writes=(), chunks=(), peer=('127.0.0.1', 8765)):
        self.connect_result = connect
        self.writes = deque(writes)
        self.chunks = deque(chunks)
        self.peer = peer
        self.calls = []  # lengths/offsets only: credentials never copied to records.
        self.closed = False

    def connect(self, address):
        self.calls.append(('connect', address))
        if isinstance(self.connect_result, Exception): raise self.connect_result
        return self.connect_result

    def connected(self):
        self.calls.append(('connected',))
        return self.peer

    def send(self, buffer, offset):
        self.calls.append(('send', offset, len(buffer)))
        value = self.writes.popleft() if self.writes else len(buffer)
        if isinstance(value, Exception): raise value
        if value == 'WAIT': raise BlockingIOError()
        return value

    def receive(self):
        self.calls.append(('receive',))
        value = self.chunks.popleft() if self.chunks else b''
        if isinstance(value, Exception): raise value
        return value

    def close(self):
        self.closed = True
        self.calls.append(('close',))
