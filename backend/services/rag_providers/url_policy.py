"""URL normalization and SSRF policy for configurable RAG providers."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


class UrlPolicyError(ValueError):
    pass


_FORBIDDEN_PATH_PARTS = ("/platform/api-docs", "/swagger", "/api-docs")


@dataclass(frozen=True)
class NormalizedUrl:
    service_root: str
    api_base: str


def normalize_service_url(value: str) -> NormalizedUrl:
    raw = (value or "").strip()
    if not raw:
        raise UrlPolicyError("API URL 不能为空")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UrlPolicyError("API URL 必须是绝对 HTTP(S) 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise UrlPolicyError("API URL 不能包含用户信息、查询参数或片段")
    path = parsed.path.rstrip("/")
    lowered = path.lower()
    if any(part in lowered for part in _FORBIDDEN_PATH_PARTS):
        raise UrlPolicyError("请填写服务根地址或业务 API 地址，而不是文档地址")
    while path.lower().endswith("/api/v1/api/v1"):
        path = path[: -len("/api/v1")]
    if path.lower().endswith("/api/v1"):
        root_path = path[: -len("/api/v1")]
    else:
        root_path = path
    root_path = root_path.rstrip("/")
    service_root = urlunsplit((parsed.scheme.lower(), parsed.netloc, root_path, "", ""))
    api_base = f"{service_root}/api/v1"
    return NormalizedUrl(service_root=service_root, api_base=api_base)


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or ip.is_private
    )


def validate_target_host(service_root: str, allowed_hosts: set[str] | None = None) -> None:
    allowed = {host.strip().lower() for host in (allowed_hosts or set()) if host.strip()}
    parsed = urlsplit(service_root)
    host = (parsed.hostname or "").lower()
    if host in allowed:
        return
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, parsed.port or 443)}
    except socket.gaierror as exc:
        raise UrlPolicyError(f"无法解析 RAG 系统主机: {host}") from exc
    if any(_is_blocked_ip(address) for address in addresses):
        raise UrlPolicyError("RAG 系统地址指向受保护网络；请配置精确主机白名单")


def validate_provider_url(value: str, allowed_hosts: set[str] | None = None, allow_http: bool = False) -> NormalizedUrl:
    normalized = normalize_service_url(value)
    if not allow_http and urlsplit(normalized.service_root).scheme != "https":
        host = (urlsplit(normalized.service_root).hostname or "").lower()
        if host not in {h.lower() for h in (allowed_hosts or set())}:
            raise UrlPolicyError("生产连接必须使用 HTTPS")
    validate_target_host(normalized.service_root, allowed_hosts)
    return normalized
