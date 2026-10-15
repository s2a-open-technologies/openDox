"""TRUSTED_PROXY_IPS entries may be single addresses or CIDR ranges."""

import pytest

from backend.components.modules.env import is_trusted_proxy


@pytest.mark.parametrize(
    "host,trusted,expected",
    [
        ("127.0.0.1", ["127.0.0.1", "::1"], True),
        ("10.0.1.7", ["127.0.0.1"], False),
        ("10.0.1.7", ["10.0.1.0/24"], True),  # overlay subnet of a load balancer
        ("10.0.2.7", ["10.0.1.0/24"], False),
        ("172.18.0.1", ["127.0.0.1", "172.18.0.0/16", "10.0.1.0/24"], True),
        ("::1", ["::1"], True),
        ("fd00::5", ["fd00::/8"], True),
        ("10.0.1.7", ["not-an-address", "10.0.1.7"], True),  # bad entry is ignored
        ("10.0.1.7", ["not-an-address"], False),
        ("not-an-ip", ["10.0.1.0/24"], False),
        ("", ["10.0.1.0/24"], False),
        ("10.0.1.7", [], False),
    ],
)
def test_is_trusted_proxy(host, trusted, expected):
    assert is_trusted_proxy(host, trusted) is expected
