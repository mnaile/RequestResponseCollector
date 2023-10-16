import json

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    DispatchFunction,
    RequestResponseEndpoint,
)
from starlette.types import ASGIApp

from collector.client import ActionLogClient


class ActionLogMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, url: str, dispatch: DispatchFunction | None = None
    ) -> None:
        self.url = url
        self.action_log = ActionLogClient()
        super().__init__(app, dispatch)

    async def set_body(self, request: Request, body: bytes):
        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive
        request._stream_consumed = False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        req_body = await request.body()
        await self.set_body(request, req_body)
        req_body = json.loads(req_body) if req_body else ""
        response = await call_next(request)

        response_body = [chunk async for chunk in response.body_iterator]
        response.body_iterator = iterate_in_threadpool(iter(response_body))

        data = {
            "headers": dict(request.headers),
            "url": str(request.url),
            "method": request.method,
            "request_body": req_body,
            "query_params": str(request.query_params),
            "service_name": request.url.path.split("/")[1],
            "source": request.headers["service-name"],
            "response_body": response_body,
            "status_code": str(response.status_code),
        }

        await self.action_log.create_action_log(data, self.url)
        return response
