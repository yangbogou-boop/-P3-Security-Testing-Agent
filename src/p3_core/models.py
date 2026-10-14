"""Immutable trusted configuration and strictly parsed, untrusted proposals."""
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import math
import re
from urllib.parse import urlsplit


class InvalidInput(ValueError):
    pass


class RunState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    NOT_EVALUATED = "NOT_EVALUATED"


class ExecutionState(str, Enum):
    NOT_EXECUTED = "NOT_EXECUTED"
    EXECUTED = "EXECUTED"  # Reserved: only an actual HTTP response can justify this.
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class Conclusion(str, Enum):
    PASS = "PASS"  # Reserved for future response-and-control-based evaluation.
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


def fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise InvalidInput("INVALID_FIELDS")


def identifier(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
        raise InvalidInput("INVALID_IDENTIFIER")
    return value


def number(value, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise InvalidInput("INVALID_NUMBER")
    if positive and value <= 0:
        raise InvalidInput("INVALID_NUMBER")
    return value


@dataclass(frozen=True)
class Check:
    check_id: str
    kind: str
    endpoint_id: str
    method: str
    identity_ref: str
    params: tuple
    expected: str
    control_id: object = None

    @classmethod
    def parse(cls, raw):
        fields(raw, "check_id kind endpoint_id method identity_ref params expected control_id")
        for key in ("check_id", "endpoint_id", "identity_ref"):
            identifier(raw[key])
        if raw["kind"] not in ("anonymous", "object", "role", "control"):
            raise InvalidInput("INVALID_KIND")
        if type(raw["method"]) is not str or raw["method"] not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"):
            raise InvalidInput("INVALID_METHOD")
        if raw["expected"] not in ("ALLOW", "DENY"):
            raise InvalidInput("INVALID_EXPECTATION")
        if raw["control_id"] is not None:
            identifier(raw["control_id"])
        if type(raw["params"]) is not dict:
            raise InvalidInput("INVALID_PARAMETERS")
        for key, value in raw["params"].items():
            identifier(key)
            if type(value) is not str or len(value) > 256:
                raise InvalidInput("INVALID_PARAMETERS")
        return cls(**{**raw, "params": tuple(sorted(raw["params"].items()))})

    def to_dict(self):
        return {"check_id": self.check_id, "kind": self.kind,
                "endpoint_id": self.endpoint_id, "method": self.method,
                "identity_ref": self.identity_ref, "params": dict(self.params),
                "expected": self.expected, "control_id": self.control_id}

    def permission_key(self):
        return self.endpoint_id, self.method, self.identity_ref, self.params


@dataclass(frozen=True)
class Budget:
    max_checks: int
    logical_timeout_seconds: float
    concurrency: int


@dataclass(frozen=True)
class Endpoint:
    endpoint_id: str
    method: str
    path: str
    parameter_names: tuple


@dataclass(frozen=True)
class Permission:
    endpoint_id: str
    method: str
    identity_ref: str
    params: tuple
    expected: str

    def key(self):
        return self.endpoint_id, self.method, self.identity_ref, self.params


@dataclass(frozen=True)
class Authorization:
    authorization_id: str
    version: str
    approved_by: str
    permission_ref: str
    active: bool
    valid_until_epoch: float
    origin: str


@dataclass(frozen=True)
class Configuration:
    authorization: Authorization
    budget: Budget
    endpoints: tuple
    identities: tuple
    candidates: tuple
    permissions: tuple
    contract_version: str
    matrix_version: str
    fixture_version: str
    strategy_version: str

    @classmethod
    def parse(cls, raw):
        fields(raw, "mode authorization budget endpoints identities candidates permissions contract_version matrix_version fixture_version strategy_version")
        if raw["mode"] != "offline":
            raise InvalidInput("OFFLINE_ONLY")
        a = raw["authorization"]
        fields(a, "authorization_id version approved_by permission_ref active valid_until_epoch origin")
        for key in ("authorization_id", "version", "approved_by", "permission_ref"):
            identifier(a[key])
        if type(a["active"]) is not bool or not a["active"]:
            raise InvalidInput("INACTIVE_AUTHORIZATION")
        number(a["valid_until_epoch"], True)
        if type(a["origin"]) is not str:
            raise InvalidInput("INVALID_ORIGIN")
        try:
            origin = urlsplit(a["origin"])
            if (origin.scheme != "http" or not ipaddress.ip_address(origin.hostname).is_loopback
                    or origin.port is None or origin.username or origin.password
                    or origin.path or origin.query or origin.fragment):
                raise ValueError()
        except (ValueError, TypeError):
            raise InvalidInput("INVALID_LOCAL_ORIGIN") from None
        b = raw["budget"]
        fields(b, "max_checks logical_timeout_seconds concurrency")
        if type(b["max_checks"]) is not int or b["max_checks"] <= 0:
            raise InvalidInput("INVALID_CHECK_BUDGET")
        number(b["logical_timeout_seconds"], True)
        if type(b["concurrency"]) is not int or b["concurrency"] != 1:
            raise InvalidInput("SERIAL_ONLY")
        for key in ("contract_version", "matrix_version", "fixture_version", "strategy_version"):
            identifier(raw[key])
        for key in ("endpoints", "identities", "candidates", "permissions"):
            if type(raw[key]) is not list or not raw[key]:
                raise InvalidInput("MISSING_REGISTRY")
        identities = tuple(identifier(x) for x in raw["identities"])
        if len(set(identities)) != len(identities):
            raise InvalidInput("DUPLICATE_IDENTITY")
        endpoints = []
        for e in raw["endpoints"]:
            fields(e, "endpoint_id method path read_only parameter_names")
            identifier(e["endpoint_id"])
            if e["method"] != "GET" or e["read_only"] is not True:
                raise InvalidInput("READ_ONLY_GET_REQUIRED")
            if type(e["path"]) is not str or not re.fullmatch(r"/[A-Za-z0-9_/-]*", e["path"]) or "//" in e["path"]:
                raise InvalidInput("INVALID_PATH")
            if type(e["parameter_names"]) is not list:
                raise InvalidInput("INVALID_PARAMETERS")
            names = tuple(identifier(x) for x in e["parameter_names"])
            if len(set(names)) != len(names):
                raise InvalidInput("DUPLICATE_PARAMETER")
            endpoints.append(Endpoint(e["endpoint_id"], e["method"], e["path"], tuple(sorted(names))))
        if len({e.endpoint_id for e in endpoints}) != len(endpoints):
            raise InvalidInput("DUPLICATE_ENDPOINT")
        candidates = tuple(Check.parse(c) for c in raw["candidates"])
        by_id = {c.check_id: c for c in candidates}
        if len(by_id) != len(candidates):
            raise InvalidInput("DUPLICATE_CHECK")
        permissions = []
        for p in raw["permissions"]:
            fields(p, "endpoint_id method identity_ref params expected")
            parsed = Check.parse(dict(p, check_id="matrix", kind="control", control_id=None))
            permissions.append(Permission(parsed.endpoint_id, parsed.method, parsed.identity_ref, parsed.params, parsed.expected))
        matrix = {p.key(): p.expected for p in permissions}
        if len(matrix) != len(permissions):
            raise InvalidInput("DUPLICATE_OR_CONFLICTING_MATRIX_CELL")
        def registered(c):
            e = next((e for e in endpoints if e.endpoint_id == c.endpoint_id), None)
            return e and c.method == e.method and c.identity_ref in identities and tuple(k for k, v in c.params) == e.parameter_names
        if any(not registered(p) for p in permissions):
            raise InvalidInput("UNREGISTERED_MATRIX_CELL")
        for c in candidates:
            if not registered(c) or matrix.get(c.permission_key()) != c.expected:
                raise InvalidInput("CANDIDATE_MATRIX_MISMATCH")
            if c.expected == "DENY" and c.control_id is None:
                raise InvalidInput("MISSING_CONTROL")
            if c.control_id is not None:
                control = by_id.get(c.control_id)
                if (control is None or control.kind != "control" or control.expected != "ALLOW"
                        or control.endpoint_id != c.endpoint_id or control.params != c.params
                        or control.control_id is not None):
                    raise InvalidInput("INVALID_CONTROL")
        return cls(Authorization(**a), Budget(**b), tuple(endpoints), identities, candidates,
                   tuple(permissions), *(raw[k] for k in ("contract_version", "matrix_version", "fixture_version", "strategy_version")))


@dataclass
class CheckResult:
    slot_id: str
    check: object
    source: str
    authorization: AuthorizationDecision = AuthorizationDecision.NOT_EVALUATED
    execution: ExecutionState = ExecutionState.NOT_EXECUTED
    conclusion: Conclusion = Conclusion.INCONCLUSIVE
    reason: str = "NOT_ATTEMPTED"
    attempt_id: object = None
    evidence_ids: list = field(default_factory=list)
    processed: bool = False
