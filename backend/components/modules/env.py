"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)


def env_or_file(env_name: str, default: str | None = None) -> str | None:
    """Fetch an environment variable or the contents of a file specified by it.

    This is necessary for deploying with docker swarm.
    If the environment variable ``{env_name}_FILE`` is set and points to a file,
    read from the file. Otherwise, return the value of the environment variable
    named ``env_name``.

    Args:
        env_name: The name of the environment variable.
        default: The value to return if the environment variable is not set.

    Returns:
        The environment variable value, file contents, or default.
    """
    file_var = os.getenv(f"{env_name}_FILE")
    if file_var and os.path.isfile(file_var):
        with open(file_var, "r") as f:
            return f.read().strip()
    return os.getenv(env_name, default)


def _detect_docker_gateway() -> str | None:
    """Return this host's default-route gateway IP, or None if undetectable.

    Docker publishes container ports via NAT: a connection from the host's
    ``127.0.0.1:APP_PORT`` (e.g. a reverse proxy on the same machine) arrives
    inside the container as coming from the network's gateway IP, not
    ``127.0.0.1`` — this is what a same-host reverse proxy actually looks
    like from inside the container. Parses ``/proc/net/route`` directly
    (Linux-only, no ``ip``/``iproute2`` binary required).
    """
    try:
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if len(fields) >= 3 and fields[1] == "00000000":
                    gateway_hex = fields[2]
                    return ".".join(
                        str(int(gateway_hex[i : i + 2], 16)) for i in (6, 4, 2, 0)
                    )
    except (OSError, ValueError, IndexError):
        pass
    return None


def get_trusted_proxy_ips() -> list[str]:
    """Return the IPs a reverse proxy is allowed to connect from.

    Honors ``TRUSTED_PROXY_IPS`` (comma-separated) if set. Otherwise
    defaults to loopback plus the auto-detected Docker gateway IP, which
    covers "a reverse proxy on the same host" in both bare-metal (loopback)
    and containerized (NAT'd via the gateway) deployments.
    """
    raw = env_or_file("TRUSTED_PROXY_IPS", None)
    if raw:
        return [ip.strip() for ip in raw.split(",") if ip.strip()]

    trusted = ["127.0.0.1", "::1"]
    gateway = _detect_docker_gateway()
    if gateway:
        trusted.append(gateway)
    return trusted