"""Tiny in-memory stand-in for the few Redis commands the app uses in tests."""


class FakeRedis:
    """Supports set(nx/ex), incr, get, ttl, delete and a pipeline of those."""

    def __init__(self):
        self.now = 0.0
        self._data: dict[str, str] = {}
        self._expires: dict[str, float] = {}
        self.fail = False

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _expire_due(self) -> None:
        for key in [k for k, t in self._expires.items() if t <= self.now]:
            self._data.pop(key, None)
            self._expires.pop(key, None)

    def _check(self) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self._expire_due()

    def set(self, key, value, ex=None, nx=False):
        self._check()
        if nx and key in self._data:
            return None
        self._data[key] = str(value)
        if ex is not None:
            self._expires[key] = self.now + ex
        else:
            self._expires.pop(key, None)
        return True

    def incr(self, key):
        self._check()
        value = int(self._data.get(key, "0")) + 1
        self._data[key] = str(value)
        return value

    def get(self, key):
        self._check()
        return self._data.get(key)

    def ttl(self, key):
        self._check()
        if key not in self._data:
            return -2
        if key not in self._expires:
            return -1
        return int(self._expires[key] - self.now)

    def delete(self, *keys):
        self._check()
        return sum(1 for k in keys if self._data.pop(k, None) is not None)

    def pipeline(self):
        return _Pipeline(self)


class _Pipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def __getattr__(self, name):
        def queue(*args, **kwargs):
            self._ops.append((name, args, kwargs))
            return self

        return queue

    def execute(self):
        return [getattr(self._redis, n)(*a, **k) for n, a, k in self._ops]
