from __future__ import absolute_import

import errno
import os
import socket

from Queue import Empty

from anyjson import loads, dumps

import zmq

from kombu.exceptions import StdChannelError
from kombu.log import get_logger
from kombu.utils import cached_property
from kombu.utils.eventio import poll, READ

from . import virtual

logger = get_logger('kombu.transport.zmq')

DEFAULT_PORT = 5555
DEFAULT_HWM = 16
DEFAULT_INCR = 1


class MultiChannelPoller(object):
    eventflags = READ

    def __init__(self):
        # active channels
        self._channels = set()
        # file descriptor -> channel map
        self._fd_to_chan = {}
        # poll implementation (epoll/kqueue/select)
        self.poller = poll()

    def close(self):
        for fd in self._fd_to_chan:
            try:
                self.poller.unregister(fd)
            except KeyError:
                pass
        self._channels.clear()
        self._fd_to_chan.clear()
        self.poller = None

    def add(self, channel):
        self._channels.add(channel)

    def discard(self, channel):
        self._channels.discard(channel)
        self._fd_to_chan.pop(channel.client.connection.fd, None)

    def _register(self, channel):
        conn = channel.client.connection
        self._fd_to_chan[conn.fd] = channel
        self.poller.register(conn.fd, self.eventflags)

    def on_poll_start(self):
        for channel in self._channels:
            self._register(channel)

    def handle_event(self, fileno, event):
        chan = self._fd_to_chan[fileno]
        return (chan.drain_events(), chan)

    def get(self, timeout=None):
        self.on_poll_start()

        events = self.poller.poll(timeout)
        for fileno, event in events or []:
            ret = self.handle_event(fileno, event)
            if ret:
                return ret

        raise Empty()

    @property
    def fds(self):
        return self._fd_to_chan


class Client(object):
    def __init__(self, uri='tcp://127.0.0.1', port=DEFAULT_PORT, hwm=DEFAULT_HWM, swap_size=None, enable_sink=True, context=None):
        scheme, parts = uri.split('://')
        endpoints = parts.split(';')

        if scheme != 'tcp':
            raise NotImplementedError('Currently only TCP can be used')

        self.context = context or zmq.Context.instance()

        if enable_sink:
            self.sink = self.context.socket(zmq.PULL)
            self.sink.bind('tcp://*:%s' % port)
        else:
            self.sink = None

        self.vent = self.context.socket(zmq.PUSH)
        self.vent.setsockopt(zmq.HWM, hwm)
        if swap_size:
            self.vent.setsockopt(zmq.SWAP, swap_size)

        for endpoint in endpoints:
            if scheme == 'tcp' and ':' not in endpoint:
                endpoint += ':' + str(DEFAULT_PORT)

            endpoint = ''.join([scheme, '://', endpoint])

            self.connect(endpoint)

    def connect(self, endpoint):
        self.vent.connect(endpoint)

    def get(self, queue=None, timeout=None):
        try:
            return self.sink.recv(flags=zmq.NOBLOCK)
        except zmq.ZMQError, e:
            if e.errno == zmq.EAGAIN:
                raise socket.error(errno.EAGAIN, e.strerror)
            else:
                raise

    def put(self, queue, message, **kwargs):
        return self.vent.send(message)

    def close(self):
        if self.sink and not self.sink.closed:
            self.sink.close()
        if not self.vent.closed:
            self.vent.close()

    @property
    def connection(self):
        if self.sink:
            return self.sink
        return self.vent


class Channel(virtual.Channel):
    Client = Client

    hwm = DEFAULT_HWM
    swap_size = None
    enable_sink = True
    port_incr = DEFAULT_INCR

    from_transport_options = (virtual.Channel.from_transport_options
                            + ('hwm',
                               'swap_size',
                               'enable_sink',
                               'port_incr'))

    def __init__(self, *args, **kwargs):
        super_ = super(Channel, self)
        super_.__init__(*args, **kwargs)

        # Evaluate socket
        self.client.connection.closed

        self.connection.cycle.add(self)
        self.connection_errors = self.connection.connection_errors

    def _get(self, queue, timeout=None):
        ret = self.client.get(queue, timeout)
        if ret:
            return loads(ret)
        raise Empty()

    def _put(self, queue, message, **kwargs):
        self.client.put(queue, dumps(message), **kwargs)

    def _purge(self, queue):
        return 0

    def _poll(self, cycle, timeout=None):
        try:
            return cycle.get(timeout=timeout)
        except socket.error, exc:
            if exc.errno == errno.EAGAIN:
                raise Empty()
            raise

    def close(self):
        if not self.closed:
            self.connection.cycle.discard(self)
            try:
                self.__dict__['client'].close()
            except KeyError:
                pass
        super(Channel, self).close()

    def _create_client(self):
        conninfo = self.connection.client
        return self.Client(uri=conninfo.hostname or 'tcp://127.0.0.1',
                           port=(conninfo.port or DEFAULT_PORT) + ((self.channel_id - 1) * self.port_incr),
                           hwm=self.hwm,
                           swap_size=self.swap_size,
                           enable_sink=self.enable_sink,
                           context=self.connection.context)

    @cached_property
    def client(self):
        return self._create_client()


class Transport(virtual.Transport):
    Channel = Channel

    default_port = DEFAULT_PORT
    driver_type = 'zeromq'
    driver_name = 'zmq'

    connection_errors = (zmq.ZMQError,)
    channel_errors = (zmq.ZMQError, StdChannelError,)

    polling_interval = None
    nb_keep_draining = True

    def __init__(self, *args, **kwargs):
        super(Transport, self).__init__(*args, **kwargs)

        self.cycle = MultiChannelPoller()

    def driver_version(self):
        return zmq.__version__

    def on_poll_init(self, poller):
        self.cycle.poller = poller

    def on_poll_start(self):
        cycle = self.cycle
        cycle.on_poll_start()
        return dict((fd, self.handle_event) for fd in cycle.fds)

    def handle_event(self, fileno, event):
        evt = self.cycle.handle_event(fileno, event)
        self._handle_event(evt)

    def drain_events(self, connection, timeout=None):
        for channel in connection.channels:
            while 1:
                try:
                    evt = channel.cycle.get(timeout=timeout)
                except socket.error, e:
                    if e.errno == errno.EAGAIN:
                        break
                    raise
                else:
                    connection._handle_event((evt, channel))

        raise socket.error(errno.EAGAIN, os.strerror(errno.EAGAIN))

    def _handle_event(self, evt):
        item, channel = evt
        message, queue = item
        if not queue or queue not in self._callbacks:
            raise KeyError(
                "Received message for queue '%s' without consumers: %s" % (
                    queue, message))
        self._callbacks[queue](message)

    def establish_connection(self):
        self.context.closed
        return super(Transport, self).establish_connection()

    def close_connection(self, connection):
        super(Transport, self).close_connection(connection)
        try:
            connection.__dict__['context'].term()
        except KeyError:
            pass

    @cached_property
    def context(self):
        return zmq.Context(1)

    @property
    def default_connection_params(self):
        return {'port': self.default_port, 'hostname': 'tcp://127.0.0.1'}
