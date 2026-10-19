"""Strict byte-to-business adapter. Pure function path; no listening socket."""
import re
from .core import MockRequest, RequestRejected


class ServiceAdapter:
    def __init__(self, fixture, port, header_limit=4096):
        if type(port) is not int or not 1 <= port <= 65535:
            raise RequestRejected('INVALID_SERVICE_PORT')
        if type(header_limit) is not int or header_limit <= 0:
            raise RequestRejected('INVALID_HEADER_LIMIT')
        self.fixture, self.port, self.header_limit = fixture, port, header_limit

    def handle_bytes(self, raw):
        if type(raw) is not bytes or len(raw) > self.header_limit:
            raise RequestRejected('INVALID_HTTP_REQUEST')
        if not raw.endswith(b'\r\n\r\n') or raw.count(b'\r\n\r\n') != 1:
            raise RequestRejected('BODY_OR_PIPELINING_FORBIDDEN')
        try:
            lines = raw[:-4].decode('ascii').split('\r\n')
            method, target, version = lines[0].split(' ')
            if version != 'HTTP/1.1' or method != 'GET': raise ValueError()
            headers = {}
            allowed = {'host','accept','connection','user-agent','x-p3-action-id','authorization','content-length'}
            for line in lines[1:]:
                name, value = line.split(':',1)
                if not re.fullmatch(r'[A-Za-z0-9-]+',name): raise ValueError()
                name=name.lower()
                if name in headers or name not in allowed or not re.fullmatch(r'[\x20-\x7e]*',value):
                    raise ValueError()
                headers[name]=value.strip()
            if (headers.get('host') != '127.0.0.1:'+str(self.port)
                    or headers.get('accept') != 'application/json'
                    or headers.get('connection','').lower() != 'close'
                    or headers.get('content-length','0') != '0'
                    or 'x-p3-action-id' not in headers): raise ValueError()
            token=None
            if 'authorization' in headers:
                if not re.fullmatch(r'Bearer [A-Za-z0-9._~-]{1,256}',headers['authorization']): raise ValueError()
                token=headers['authorization'][7:]
        except (ValueError, UnicodeError):
            raise RequestRejected('INVALID_HTTP_REQUEST') from None
        return self.fixture.handle(MockRequest(method,target,headers['x-p3-action-id'],token)).to_bytes()
