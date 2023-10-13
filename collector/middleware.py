import asyncio
import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from collector.client import ActionLogClient


class ActionLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, url):
        self.url = url
        self.action_log = ActionLogClient()

    async def set_body(self, request: Request, body: bytes):
        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        req_body = await request.body()
        await self.set_body(request, req_body)
        req_body = json.loads(req_body) if req_body else ""
        response = await call_next(request)

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        data = {
            "headers": request.headers,
            "url": request.url,
            "method": request.method,
            "request_body": req_body,
            "query_params": request.query_params,
            "service_name": request.url.path.split("/")[1],
            "source": request.headers["service-name"],
            "response_body": response_body,
            "status_code": response.status_code,
        }

        asyncio.create_task(self.action_log.create_action_log(data, self.url))
        return True
