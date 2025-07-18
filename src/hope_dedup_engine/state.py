import contextlib
import json
from copy import copy
from dataclasses import dataclass, astuple
from datetime import datetime, timedelta
from threading import local
from typing import Any, Iterator, Mapping, Protocol

# TODO: find out what is correct value for this
not_set = None


class AnyRequest(Protocol):
    COOKIES: Mapping[str, Any]


class AnyResponse(Protocol):
    def set_cookie(self, name: str, *args: Any) -> None:
        pass


@dataclass
class Cookie:
    value: str | int
    max_age: int | float | timedelta | None = None
    expires: str | datetime | None = None
    path: str = "/"
    domain: str | None = None
    secure: bool = False
    httponly: bool = False
    samesite: str | None = None


class State(local):
    request: AnyRequest | None = None
    cookies: dict[str, list[Any]] = {}

    def __repr__(self) -> str:
        return f"<State {id(self)}>"

    def add_cookie(
        self,
        key: str,
        cookie: Cookie,
    ) -> None:
        cookie.value = json.dumps(cookie.value)
        self.cookies[key] = list(astuple(cookie))

    def get_cookie(self, name: str) -> str | None:
        return self.request.COOKIES.get(name)

    def set_cookies(self, response: "AnyResponse") -> None:
        for name, args in self.cookies.items():
            response.set_cookie(name, *args)

    @contextlib.contextmanager
    def configure(self, **kwargs: "dict[str,Any]") -> "Iterator[None]":
        pre = copy(self.__dict__)
        self.reset()
        with self.set(**kwargs):
            yield
        for k, v in pre.items():
            setattr(self, k, v)

    @contextlib.contextmanager
    def set(self, **kwargs: "dict[str,Any]") -> "Iterator[None]":
        pre = {}
        for k, v in kwargs.items():
            if hasattr(self, k):
                pre[k] = getattr(self, k)
            else:
                pre[k] = not_set
            setattr(self, k, v)
        yield
        for k, v in pre.items():
            if v is not_set:
                delattr(self, k)
            else:
                setattr(self, k, v)

    def reset(self) -> None:
        self.request = None
        self.cookies = {}


state = State()
