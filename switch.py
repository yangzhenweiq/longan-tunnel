"""Platform for Tunnel."""
import logging
import asyncio
import uuid
import base64
import os
import re


import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (
    SwitchDevice, PLATFORM_SCHEMA
)

CONF_INLETS_BIN = "inlets_bin"
CONF_SUBDOMAIN = "subdomain"
CONF_LOCAL_PORT = "port_local"

DEFAULT_INLETS_BIN = "inlets"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_INLETS_BIN,
            default=DEFAULT_INLETS_BIN
        ): cv.string,
        vol.Optional(CONF_LOCAL_PORT): cv.string,
        vol.Optional(CONF_SUBDOMAIN): cv.string,
    }
)

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
        return stdout.decode()
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')
        return stderr.decode()

async def info_stream(level, stream):
    while not stream.at_eof():
        data = await stream.readline()
        line = data.decode('ascii').rstrip()
        # _LOGGER.info(line)
        with open('/tmp/inlets_info', 'a+') as f:
            f.write(line)

async def error_stream(level, stream):
    while not stream.at_eof():
        data = await stream.readline()
        line = data.decode('ascii').rstrip()
        # _LOGGER.error(line)
        with open('/tmp/inlets_error', 'a+') as f:
            f.write(line)


def setup_platform(hass,
                   config,
                   add_entities,
                   discovery_info=None):
    """Set up the Tunnel Switch platform."""

    command = config.get(CONF_INLETS_BIN)
    subdomain = config.get(CONF_SUBDOMAIN)
    port_local = config.get(CONF_LOCAL_PORT)

    if subdomain is None:
        mid1 = uuid.getnode()
        mid2 = mid1.to_bytes((mid1.bit_length() + 7) // 8, byteorder='big')
        mid3 = base64.b32encode(mid2)
        subdomain = mid3.decode().rstrip('=').lower()

    subdomain_host = "wormhole.eliteu.cn"

    url = "%s.%s" % (subdomain, subdomain_host)
    debug_url = "%s_debug.%s" % (subdomain, subdomain_host)

    http_url = "https://" + url
    http_jupyter_url = "https://" + debug_url

    upstream = f"--upstream={url}=http://127.0.0.1:{port_local}"
    jupyter_upstream = f"--upstream={debug_url}=http://0.0.0.0:8889"

    wss_url = "wss://%s.%s" % (subdomain, subdomain_host)
    wss_jupyter_url = "wss://%s_debug.%s" % (subdomain, subdomain_host)

    inlets_cmd = [
        command,
        'client',
        '--remote', wss_url,
        upstream,
        '--token', "8dfe81c68460c8b259af5a6ac842708804e37577",
    ]

    jupyter_tunnel_cmd = [
        command,
        'client',
        '--remote', wss_jupyter_url,
        jupyter_upstream,
        '--token', "8dfe81c68460c8b259af5a6ac842708804e37577",
    ]

    jupyter_cmd = ['jupyter',
                   'notebook',
                   '--ip',
                   '0.0.0.0']

    # Add devices
    add_entities([TunnelSwitch(http_url, inlets_cmd),
                  JupyterSwitch(http_jupyter_url,
                                jupyter_tunnel_cmd,
                                jupyter_cmd)])


class TunnelSwitch(SwitchDevice):
    """Representation of an Tunnel Switch."""

    def __init__(self, url, inlets_cmd):
        """Initialize an TunnelSwitch."""
        self._url = url
        self._inlets_cmd = inlets_cmd
        self._name = "公网访问"
        self._process = None
        self._attributes = {"url": None}

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def is_on(self):
        """Return true if tunnel is on."""
        if self._process:
            return True
        else:
            return False

    async def turn_on(self, **kwargs):
        """Instruct the light to turn on. """
        self._process = await asyncio.create_subprocess_exec(
            *self._inlets_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE
        )

        # tasks = [asyncio.ensure_future(info_stream(logging.INFO, self._process.stdout)),
        #      asyncio.ensure_future(error_stream(logging.ERROR, self._process.stderr)),
        #      asyncio.ensure_future(self._process.wait())]
        # await asyncio.wait(tasks)

        self._attributes["url"] = self._url
        _LOGGER.info("tunnel started, hass can be visited from internet - %s",
                     self._url)
        _LOGGER.info("tunnel pid: %d", self._process.pid)

    def turn_off(self, **kwargs):
        """Instruct the Tunnel to turn off."""
        if self.is_on:
            self._process.terminate()
            self._process = None
            self._attributes["url"] = None
            _LOGGER.info("tunnel stoped!")

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        pass
    # self._light.update()
    # self._state = self._light.is_on()
    # self._brightness = self._light.brightness


class JupyterSwitch(SwitchDevice):
    """Representation of an Jupyter Switch."""

    def __init__(self, url, jupyter_tunnel_cmd, jupyter_cmd):
        """Initialize an JupyterSwitch."""
        self._url = url
        self._inlets_cmd = jupyter_tunnel_cmd
        self._jupyter_cmd = jupyter_cmd
        self._name = "远程调试"
        self._process = None
        self._jupyter_process = None
        self._attributes = {"url": None}

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def is_on(self):
        """Return true if jupyter is on."""
        if self._process:
            return True
        else:
            return False

    async def turn_on(self, **kwargs):
        """Instruct the jupyter to turn on. """

        # self._jupyter_process = await asyncio.create_subprocess_exec(
        #     *self._jupyter_cmd,
        #     stdout=asyncio.subprocess.PIPE,
        #     stderr=asyncio.subprocess.PIPE,
        #     stdin=asyncio.subprocess.PIPE
        # )

        self._process = await asyncio.create_subprocess_exec(
            *self._inlets_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE
        )

        _LOGGER.info("jupyter started, hass can be visited from internet - %s",
                     self._url)
        _LOGGER.info("jupyter pid: %d", self._process.pid)
        jupyter_str = await run("jupyter notebook list")
        result = re.findall(".*=(.*)::.*", jupyter_str)
        if len(result) > 0:
            self._attributes["token"] = result[0].strip()
            self._attributes["url"] = self._url

    def turn_off(self, **kwargs):
        """Instruct the jupyter to turn off."""
        if self.is_on:
            self._process.terminate()
            self._process = None
            self._attributes["token"] = None
            self._attributes["url"] = None
            # self._jupyter_process.terminate()
            # self._jupyter_process = None
            _LOGGER.info("jupyter stoped!")

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        pass
    # self._light.update()
    # self._state = self._light.is_on()
    # self._brightness = self._light.brightness
