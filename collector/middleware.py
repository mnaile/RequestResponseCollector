import re
import json
import asyncio
import logging
from typing import Union
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    DispatchFunction,
    RequestResponseEndpoint,
)
from starlette.types import ASGIApp

from collector.client import ActionLogClient

log = logging.getLogger("collector")


class ActionLogMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        url: str,
        log_handler: object = None,
        dispatch: Union[DispatchFunction, None] = None,
        exclude_path: list[str] = None,
    ) -> None:
        self.url = url
        self.logger = log_handler or log
        self.action_log = ActionLogClient()
        self.exclude_path: list[re.Pattern] = [re.compile(i) for i in exclude_path]

        super().__init__(app, dispatch)

    async def set_body(self, request: Request, body: bytes):
        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive
        request._stream_consumed = False

    def check_exclude_path(self, request_path: str):
        for pattern in self.exclude_path:
            if pattern.search(request_path):
                return True
        return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        try:
            if not self.check_exclude_path(request.url.path):
                req_body = None
                if (
                    not request.headers.get("content-type")
                    or request.headers.get("content-type") == "application/json"
                ):
                    req_body = await request.body()
                    if req_body:
                        await self.set_body(request, req_body)
                    req_body = json.loads(req_body) if req_body else None
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
                    "source": request.headers.get("service-name"),
                    "path_params": request.path_params,
                    "response_body": (
                        jsonable_encoder(response_body) if response_body else {}
                    ),
                    "status_code": str(response.status_code),
                }
                asyncio.create_task(self.action_log.create_action_log(data, self.url))

                await self.logger.info(data)

                return response
            return await call_next(request)
        except Exception as err:
            log.error(err)
            return await call_next(request)
