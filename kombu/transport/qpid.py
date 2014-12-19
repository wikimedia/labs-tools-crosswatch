"""
kombu.transport.qpid
=======================

`Qpid`_ transport using `qpid-python`_ as the client and `qpid-tools`_ for
broker management.

.. _`Qpid`: http://qpid.apache.org/
.. _`qpid-python`: http://pypi.python.org/pypi/qpid-python/
.. _`qpid-tools`: http://pypi.python.org/pypi/qpid-tools/
.. _`Issue 2199`: https://github.com/celery/celery/issues/2199

The use this transport you must install the necessary dependencies. These
dependencies are available via PyPI and can be installed using the pip
command:

`pip install qpid-tools qpid-python`

.. admonition:: Python 3 and PyPy Limitations

    The Qpid transport does not support Python 3 or PyPy environments due
    to underlying dependencies not being compatible. This version is
    tested and works with with Python 2.7.

.. admonition:: Potential Deadlock

    This transport should be used with caution due to a known
    potential deadlock. See `Issue 2199`_ for more details.

"""
from __future__ import absolute_import

"""Kombu transport using a Qpid broker as a message store."""

import fcntl
import os
import select
import socket
import ssl
import sys
import threading
import time

from itertools import count

import amqp.protocol

try:
    import qpidtoollibs
except ImportError:  # pragma: no cover
    qpidtoollibs = None     # noqa

try:
    from qpid.messaging.exceptions import ConnectionError
    from qpid.messaging.exceptions import Empty as QpidEmpty
except ImportError:  # pragma: no cover
    ConnectionError = None
    QpidEmpty = None

try:
    import qpid
except ImportError:  # pragma: no cover
    qpid = None

from kombu.exceptions import ChannelError
from kombu.five import Empty, items
from kombu.log import get_logger
from kombu.transport.virtual import Base64, Message
from kombu.transport import base
from kombu.utils.compat import OrderedDict


logger = get_logger(__name__)


DEFAULT_PORT = 5672

OBJECT_ALREADY_EXISTS_STRING = 'object already exists'

VERSION = (1, 0, 0)
__version__ = '.'.join(map(str, VERSION))

PY3 = sys.version_info[0] == 3


def dependency_is_none(dependency):
    """Return True if the dependency is None, otherwise False. This is done
    using a function so that tests can mock this behavior easily.

    :param dependency: The module to check if it is None
    :return: True if dependency is None otherwise False.

    """
    return dependency is None


class AuthenticationFailure(Exception):
    pass


class QpidMessagingExceptionHandler(object):
    """An exception handling decorator that silences some exceptions.

    An exception handling class designed to silence specific exceptions
    that qpid.messaging raises as part of normal operation. qpid.messaging
    exceptions require string parsing, and are not machine consumable.
    This is designed to be used as a decorator, and accepts a whitelist
    string as an argument.

    Usage:
    @QpidMessagingExceptionHandler('whitelist string goes here')

    """

    def __init__(self, allowed_exception_string):
        """Instantiate a QpidMessagingExceptionHandler object.

        :param allowed_exception_string: a string that, if present in the
            exception message, will be silenced.
        :type allowed_exception_string: str

        """
        self.allowed_exception_string = allowed_exception_string

    def __call__(self, original_fun):
        """The decorator method.

        Method that wraps the actual function with exception silencing
        functionality. Any exception that contains the string
        self.allowed_exception_string in the message will be silenced.

        :param original_fun: function that is automatically passed in
        when this object is used as a decorator.
        :type original_fun: function

        :return: A function that decorates (wraps) the original function.
        :rtype: function
        """

        def decorator(*args, **kwargs):
            """A runtime-built function that will be returned which contains
            a reference to the original function, and wraps a call to it in
            a try/except block that can silence errors.
            """
            try:
                return original_fun(*args, **kwargs)
            except Exception as exc:
                if self.allowed_exception_string not in str(exc):
                    raise

        return decorator


class QoS(object):
    """A helper object for message prefetch and ACKing purposes.

    NOTE: prefetch_count is currently hard set to 1, and needs to be improved

    This object is instantiated 1-for-1 with a :class:`Channel`. QoS
    allows prefetch_count to be set to the number of outstanding messages
    the corresponding :class:`Channel` should be allowed to prefetch.
    Setting prefetch_count to 0 disables prefetch limits, and the object
    can hold an arbitrary number of messages.

    Messages are added using :meth:`append`, which are held until they are
    ACKed asynchronously through a call to :meth:`ack`. Messages that are
    received, but not ACKed will not be delivered by the broker to another
    consumer until an ACK is received, or the session is closed. Messages
    are referred to using delivery_tag integers, which are unique per
    :class:`Channel`. Delivery tags are managed outside of this object and
    are passed in with a message to :meth:`append`. Un-ACKed messages can
    be looked up from QoS using :meth:`get` and can be rejected and
    forgotten using :meth:`reject`.

    """

    def __init__(self, session, prefetch_count=1):
        """Instantiate a QoS object.

        :keyword prefetch_count: Initial prefetch count, hard set to 1.
        :type prefetch_count: int

        """
        self.session = session
        self.prefetch_count = 1
        self._not_yet_acked = OrderedDict()

    def can_consume(self):
        """Return True if the :class:`Channel` can consume more messages,
        else False.

        Used to ensure the client adheres to currently active prefetch
        limits.

        :returns: True, if this QoS object can accept more messages
            without violating the prefetch_count. If prefetch_count is 0,
            can_consume will always return True.
        :rtype: bool
        """
        return not self.prefetch_count or len(self._not_yet_acked) < self\
            .prefetch_count

    def can_consume_max_estimate(self):
        """Return the remaining message capacity for the associated
        :class:`Channel`.

        Returns an estimated number of outstanding messages that a
        :class:`Channel` can accept without exceeding prefetch_count. If
        prefetch_count is 0, then this method returns 1.

        :returns: The number of estimated messages that can be fetched
            without violating the prefetch_count.
        :rtype: int
        """
        if self.prefetch_count:
            return self.prefetch_count - len(self._not_yet_acked)
        else:
            return 1

    def append(self, message, delivery_tag):
        """Append message to the list of un-ACKed messages.

        Add a message, referenced by the integer delivery_tag, for ACKing,
        rejecting, or getting later. Messages are saved into an
        :class:`~kombu.utils.compat.OrderedDict` by delivery_tag.

        :param message: A received message that has not yet been ACKed.
        :type message: qpid.messaging.Message
        :param delivery_tag: An integer number to refer to this message by
            upon receipt.
        :type delivery_tag: int
        """
        self._not_yet_acked[delivery_tag] = message

    def get(self, delivery_tag):
        """
        Get an un-ACKed message by delivery_tag. If called with an invalid
        delivery_tag a KeyError is raised.

        :param delivery_tag: The delivery tag associated with the message
            to be returned.
        :type delivery_tag: int

        :return: An un-ACKed message that is looked up by delivery_tag.
        :rtype: qpid.messaging.Message
        """
        return self._not_yet_acked[delivery_tag]

    def ack(self, delivery_tag):
        """Acknowledge a message by delivery_tag.

        Called asynchronously once the message has been handled and can be
        forgotten by the broker.

        :param delivery_tag: the delivery tag associated with the message
            to be acknowledged.
        :type delivery_tag: int
        """
        message = self._not_yet_acked.pop(delivery_tag)
        self.session.acknowledge(message=message)

    def reject(self, delivery_tag, requeue=False):
        """Reject a message by delivery_tag.

        Explicitly notify the broker that the :class:`Channel` associated
        with this QoS object is rejecting the message that was previously
        delivered.

        If requeue is False, then the message is not requeued for delivery
        to another consumer. If requeue is True, then the message is
        requeued for delivery to another consumer.

        :param delivery_tag: The delivery tag associated with the message
            to be rejected.
        :type delivery_tag: int
        :keyword requeue: If True, the broker will be notified to requeue
            the message. If False, the broker will be told to drop the
            message entirely. In both cases, the message will be removed
            from this object.
        :type requeue: bool
        """
        message = self._not_yet_acked.pop(delivery_tag)
        QpidDisposition = qpid.messaging.Disposition
        if requeue:
            disposition = QpidDisposition(qpid.messaging.RELEASED)
        else:
            disposition = QpidDisposition(qpid.messaging.REJECTED)
        self.session.acknowledge(message=message, disposition=disposition)


class Channel(base.StdChannel):
    """Supports broker configuration and messaging send and receive.

    A Channel object is designed to have method-parity with a Channel as
    defined in AMQP 0-10 and earlier, which allows for the following broker
    actions:

        - exchange declare and delete
        - queue declare and delete
        - queue bind and unbind operations
        - queue length and purge operations
        - sending/receiving/rejecting messages
        - structuring, encoding, and decoding messages
        - supports synchronous and asynchronous reads
        - reading state about the exchange, queues, and bindings

    Channels are designed to all share a single TCP connection with a
    broker, but provide a level of isolated communication with the broker
    while benefiting from a shared TCP connection. The Channel is given
    its :class:`Connection` object by the :class:`Transport` that
    instantiates the Channel.

    This Channel inherits from :class:`~kombu.transport.base.StdChannel`,
    which makes this a 'native' Channel versus a 'virtual' Channel which
    would inherit from :class:`kombu.transports.virtual`.

    Messages sent using this Channel are assigned a delivery_tag. The
    delivery_tag is generated for a message as they are prepared for
    sending by :meth:`basic_publish`. The delivery_tag is unique per
    Channel instance using :meth:`~itertools.count`. The delivery_tag has
    no meaningful context in other objects, and is only maintained in the
    memory of this object, and the underlying :class:`QoS` object that
    provides support.

    Each Channel object instantiates exactly one :class:`QoS` object for
    prefetch limiting, and asynchronous ACKing. The :class:`QoS` object is
    lazily instantiated through a property method :meth:`qos`. The
    :class:`QoS` object is a supporting object that should not be accessed
    directly except by the Channel itself.

    Synchronous reads on a queue are done using a call to :meth:`basic_get`
    which uses :meth:`_get` to perform the reading. These methods read
    immediately and do not accept any form of timeout. :meth:`basic_get`
    reads synchronously and ACKs messages before returning them. ACKing is
    done in all cases, because an application that reads messages using
    qpid.messaging, but does not ACK them will experience a memory leak.
    The no_ack argument to :meth:`basic_get` does not affect ACKing
    functionality.

    Asynchronous reads on a queue are done by starting a consumer using
    :meth:`basic_consume`. Each call to :meth:`basic_consume` will cause a
    :class:`~qpid.messaging.endpoints.Receiver` to be created on the
    :class:`~qpid.messaging.endpoints.Session` started by the :class:
    `Transport`. The receiver will asynchronously read using
    qpid.messaging, and prefetch messages before the call to
    :meth:`Transport.basic_drain` occurs. The prefetch_count value of the
    :class:`QoS` object is the capacity value of the new receiver. The new
    receiver capacity must always be at least 1, otherwise none of the
    receivers will appear to be ready for reading, and will never be read
    from.

    Each call to :meth:`basic_consume` creates a consumer, which is given a
    consumer tag that is identified by the caller of :meth:`basic_consume`.
    Already started consumers can be cancelled using by their consumer_tag
    using :meth:`basic_cancel`. Cancellation of a consumer causes the
    :class:`~qpid.messaging.endpoints.Receiver` object to be closed.

    Asynchronous message ACKing is supported through :meth:`basic_ack`,
    and is referenced by delivery_tag. The Channel object uses its
    :class:`QoS` object to perform the message ACKing.

    """

    #: A class reference that will be instantiated using the qos property.
    QoS = QoS

    #: A class reference that identifies
    # :class:`~kombu.transport.virtual.Message` as the message class type
    Message = Message

    #: Default body encoding.
    #: NOTE: ``transport_options['body_encoding']`` will override this value.
    body_encoding = 'base64'

    #: Binary <-> ASCII codecs.
    codecs = {'base64': Base64()}

    #: counter used to generate delivery tags for this channel.
    _delivery_tags = count(1)

    def __init__(self, connection, transport):
        """Instantiate a Channel object.

        :param connection: A Connection object that this Channel can
            reference. Currently only used to access callbacks.
        :type connection: Connection
        :param transport: The Transport this Channel is associated with.
        :type transport: Transport
        """
        self.connection = connection
        self.transport = transport
        qpid_connection = connection.get_qpid_connection()
        self._broker = qpidtoollibs.BrokerAgent(qpid_connection)
        self.closed = False
        self._tag_to_queue = {}
        self._receivers = {}
        self._qos = None

    def _get(self, queue):
        """Non-blocking, single-message read from a queue.

        An internal method to perform a non-blocking, single-message read
        from a queue by name. This method creates a
        :class:`~qpid.messaging.endpoints.Receiver` to read from the queue
        using the :class:`~qpid.messaging.endpoints.Session` saved on the
        associated :class:`Transport`. The receiver is closed before the
        method exits. If a message is available, a
        :class:`qpid.messaging.Message` object is returned. If no message is
        available, a :class:`qpid.messaging.exceptions.Empty` exception is
        raised.

        This is an internal method. External calls for get functionality
        should be done using :meth:`basic_get`.

        :param queue: The queue name to get the message from
        :type queue: str

        :return: The received message.
        :rtype: :class:`qpid.messaging.Message`
        """
        rx = self.transport.session.receiver(queue)
        try:
            message = rx.fetch(timeout=0)
        finally:
            rx.close()
        return message

    def _put(self, routing_key, message, exchange=None, **kwargs):
        """Synchronous send of a single message onto a queue or exchange.

        An internal method which synchronously sends a single message onto
        a given queue or exchange. If exchange is not specified,
        the message is sent directly to a queue specified by routing_key.
        If no queue is found by the name of routing_key while exchange is
        not specified an exception is raised. If an exchange is specified,
        then the message is delivered onto the requested
        exchange using routing_key. Message sending is synchronous using
        sync=True because large messages in kombu funtests were not being
        fully sent before the receiver closed.

        This method creates a :class:`qpid.messaging.endpoints.Sender` to
        send the message to the queue using the
        :class:`qpid.messaging.endpoints.Session` created and referenced by
        the associated :class:`Transport`. The sender is closed before the
        method exits.

        External calls for put functionality should be done using
        :meth:`basic_publish`.

        :param routing_key: If exchange is None, treated as the queue name
            to send the message to. If exchange is not None, treated as the
            routing_key to use as the message is submitted onto the exchange.
        :type routing_key: str
        :param message: The message to be sent as prepared by
            :meth:`basic_publish`.
        :type message: dict
        :keyword exchange: keyword parameter of the exchange this message
            should be sent on. If no exchange is specified, the message is
            sent directly to a queue specified by routing_key.
        :type exchange: str
        """
        if not exchange:
            address = '%s; {assert: always, node: {type: queue}}' % \
                      routing_key
            msg_subject = None
        else:
            address = '%s/%s; {assert: always, node: {type: topic}}' % (
                exchange, routing_key)
            msg_subject = str(routing_key)
        sender = self.transport.session.sender(address)
        qpid_message = qpid.messaging.Message(content=message,
                                              subject=msg_subject)
        try:
            sender.send(qpid_message, sync=True)
        finally:
            sender.close()

    def _purge(self, queue):
        """Purge all undelivered messages from a queue specified by name.

        An internal method to purge all undelivered messages from a queue
        specified by name. The queue message depth is first checked,
        and then the broker is asked to purge that number of messages. The
        integer number of messages requested to be purged is returned. The
        actual number of messages purged may be different than the
        requested number of messages to purge (see below).

        Sometimes delivered messages are asked to be purged, but are not.
        This case fails silently, which is the correct behavior when a
        message that has been delivered to a different consumer, who has
        not ACKed the message, and still has an active session with the
        broker. Messages in that case are not safe for purging and will be
        retained by the broker. The client is unable to change this
        delivery behavior.

        This is an internal method. External calls for purge functionality
        should be done using :meth:`queue_purge`.

        :param queue: the name of the queue to be purged
        :type queue: str

        :return: The number of messages requested to be purged.
        :rtype: int
        """
        queue_to_purge = self._broker.getQueue(queue)
        if queue_to_purge is None:
            raise ChannelError("queue.purge: server channel error 404, message: "
                               "NOT_FOUND - no queue '%s'" % queue)
        message_count = queue_to_purge.values['msgDepth']
        if message_count > 0:
            queue_to_purge.purge(message_count)
        return message_count

    def _size(self, queue):
        """Get the number of messages in a queue specified by name.

        An internal method to return the number of messages in a queue
        specified by name. It returns an integer count of the number
        of messages currently in the queue.

        :param queue: The name of the queue to be inspected for the number
            of messages
        :type queue: str

        :return the number of messages in the queue specified by name.
        :rtype: int
        """
        queue_to_check = self._broker.getQueue(queue)
        message_depth = queue_to_check.values['msgDepth']
        return message_depth

    def _delete(self, queue, *args, **kwargs):
        """Delete a queue and all messages on that queue.

        An internal method to delete a queue specified by name and all the
        messages on it. First, all messages are purged from a queue using a
        call to :meth:`_purge`. Second, the broker is asked to delete the
        queue.

        This is an internal method. External calls for queue delete
        functionality should be done using :meth:`queue_delete`.

        :param queue: The name of the queue to be deleted.
        :type queue: str
        """
        self._purge(queue)
        self._broker.delQueue(queue)

    def _has_queue(self, queue, **kwargs):
        """Determine if the broker has a queue specified by name.

        :param queue: The queue name to check if the queue exists.
        :type queue: str

        :return: True if a queue exists on the broker, and false
            otherwise.
        :rtype: bool
        """
        if self._broker.getQueue(queue):
            return True
        else:
            return False

    def queue_declare(self, queue, passive=False, durable=False,
                      exclusive=False, auto_delete=True, nowait=False,
                      arguments=None):
        """Create a new queue specified by name.

        If the queue already exists, no change is made to the queue,
        and the return value returns information about the existing queue.

        The queue name is required and specified as the first argument.

        If passive is True, the server will not create the queue. The
        client can use this to check whether a queue exists without
        modifying the server state. Default is False.

        If durable is True, the queue will be durable. Durable queues
        remain active when a server restarts. Non-durable queues (
        transient queues) are purged if/when a server restarts. Note that
        durable queues do not necessarily hold persistent messages,
        although it does not make sense to send persistent messages to a
        transient queue. Default is False.

        If exclusive is True, the queue will be exclusive. Exclusive queues
        may only be consumed by the current connection. Setting the
        'exclusive' flag always implies 'auto-delete'. Default is False.

        If auto_delete is True,  the queue is deleted when all consumers
        have finished using it. The last consumer can be cancelled either
        explicitly or because its channel is closed. If there was no
        consumer ever on the queue, it won't be deleted. Default is True.

        The nowait parameter is unused. It was part of the 0-9-1 protocol,
        but this AMQP client implements 0-10 which removed the nowait option.

        The arguments parameter is a set of arguments for the declaration of
        the queue. Arguments are passed as a dict or None. This field is
        ignored if passive is True. Default is None.

        This method returns a :class:`~collections.namedtuple` with the name
        'queue_declare_ok_t' and the queue name as 'queue', message count
        on the queue as 'message_count', and the number of active consumers
        as 'consumer_count'. The named tuple values are ordered as queue,
        message_count, and consumer_count respectively.

        Due to Celery's non-ACKing of events, a ring policy is set on any
        queue that starts with the string 'celeryev' or ends with the string
        'pidbox'. These are celery event queues, and Celery does not ack
        them, causing the messages to build-up. Eventually Qpid stops serving
        messages unless the 'ring' policy is set, at which point the buffer
        backing the queue becomes circular.

        :param queue: The name of the queue to be created.
        :type queue: str
        :param passive: If True, the sever will not create the queue.
        :type passive: bool
        :param durable: If True, the queue will be durable.
        :type durable: bool
        :param exclusive: If True, the queue will be exclusive.
        :type exclusive: bool
        :param auto_delete: If True, the queue is deleted when all
            consumers have finished using it.
        :type auto_delete: bool
        :param nowait: This parameter is unused since the 0-10
            specification does not include it.
        :type nowait: bool
        :param arguments: A set of arguments for the declaration of the
            queue.
        :type arguments: dict or None

        :return: A named tuple representing the declared queue as a named
            tuple. The tuple values are ordered as queue, message count,
            and the active consumer count.
        :rtype: :class:`~collections.namedtuple`

        """
        options = {'passive': passive,
                   'durable': durable,
                   'exclusive': exclusive,
                   'auto-delete': auto_delete,
                   'arguments': arguments}
        if queue.startswith('celeryev') or queue.endswith('pidbox'):
            options['qpid.policy_type'] = 'ring'
        try:
            self._broker.addQueue(queue, options=options)
        except Exception as exc:
            if OBJECT_ALREADY_EXISTS_STRING not in str(exc):
                raise exc
        queue_to_check = self._broker.getQueue(queue)
        message_count = queue_to_check.values['msgDepth']
        consumer_count = queue_to_check.values['consumerCount']
        return amqp.protocol.queue_declare_ok_t(queue, message_count,
                                                consumer_count)

    def queue_delete(self, queue, if_unused=False, if_empty=False, **kwargs):
        """Delete a queue by name.

        Delete a queue specified by name. Using the if_unused keyword
        argument, the delete can only occur if there are 0 consumers bound
        to it. Using the if_empty keyword argument, the delete can only
        occur if there are 0 messages in the queue.

        :param queue: The name of the queue to be deleted.
        :type queue: str
        :keyword if_unused: If True, delete only if the queue has 0
            consumers. If False, delete a queue even with consumers bound
            to it.
        :type if_unused: bool
        :keyword if_empty: If True, only delete the queue if it is empty. If
            False, delete the queue if it is empty or not.
        :type if_empty: bool
        """
        if self._has_queue(queue):
            if if_empty and self._size(queue):
                return
            queue_obj = self._broker.getQueue(queue)
            consumer_count = queue_obj.getAttributes()['consumerCount']
            if if_unused and consumer_count > 0:
                return
            self._delete(queue)

    @QpidMessagingExceptionHandler(OBJECT_ALREADY_EXISTS_STRING)
    def exchange_declare(self, exchange='', type='direct', durable=False,
                         **kwargs):
        """Create a new exchange.

        Create an exchange of a specific type, and optionally have the
        exchange be durable. If an exchange of the requested name already
        exists, no action is taken and no exceptions are raised. Durable
        exchanges will survive a broker restart, non-durable exchanges will
        not.

        Exchanges provide behaviors based on their type. The expected
        behaviors are those defined in the AMQP 0-10 and prior
        specifications including 'direct', 'topic', and 'fanout'
        functionality.

        :keyword type: The exchange type. Valid values include 'direct',
        'topic', and 'fanout'.
        :type type: str
        :keyword exchange: The name of the exchange to be created. If no
        exchange is specified, then a blank string will be used as the name.
        :type exchange: str
        :keyword durable: True if the exchange should be durable, or False
        otherwise.
        :type durable: bool
        """
        options = {'durable': durable}
        self._broker.addExchange(type, exchange, options)

    def exchange_delete(self, exchange_name, **kwargs):
        """Delete an exchange specified by name

        :param exchange_name: The name of the exchange to be deleted.
        :type exchange_name: str
        """
        self._broker.delExchange(exchange_name)

    def queue_bind(self, queue, exchange, routing_key, **kwargs):
        """Bind a queue to an exchange with a bind key.

        Bind a queue specified by name, to an exchange specified by name,
        with a specific bind key. The queue and exchange must already
        exist on the broker for the bind to complete successfully. Queues
        may be bound to exchanges multiple times with different keys.

        :param queue: The name of the queue to be bound.
        :type queue: str
        :param exchange: The name of the exchange that the queue should be
            bound to.
        :type exchange: str
        :param routing_key: The bind key that the specified queue should
            bind to the specified exchange with.
        :type routing_key: str
        """
        self._broker.bind(exchange, queue, routing_key)

    def queue_unbind(self, queue, exchange, routing_key, **kwargs):
        """Unbind a queue from an exchange with a given bind key.

        Unbind a queue specified by name, from an exchange specified by
        name, that is already bound with a bind key. The queue and
        exchange must already exist on the broker, and bound with the bind
        key for the operation to complete successfully. Queues may be
        bound to exchanges multiple times with different keys, thus the
        bind key is a required field to unbind in an explicit way.

        :param queue: The name of the queue to be unbound.
        :type queue: str
        :param exchange: The name of the exchange that the queue should be
            unbound from.
        :type exchange: str
        :param routing_key: The existing bind key between the specified
            queue and a specified exchange that should be unbound.
        :type routing_key: str
        """
        self._broker.unbind(exchange, queue, routing_key)

    def queue_purge(self, queue, **kwargs):
        """Remove all undelivered messages from queue.

        Purge all undelivered messages from a queue specified by name. The
        queue message depth is first checked, and then the broker is asked
        to purge that number of messages. The integer number of messages
        requested to be purged is returned. The actual number of messages
        purged may be different than the requested number of messages to
        purge.

        Sometimes delivered messages are asked to be purged, but are not.
        This case fails silently, which is the correct behavior when a
        message that has been delivered to a different consumer, who has
        not ACKed the message, and still has an active session with the
        broker. Messages in that case are not safe for purging and will be
        retained by the broker. The client is unable to change this
        delivery behavior.

        Internally, this method relies on :meth:`_purge`.

        :param queue: The name of the queue which should have all messages
            removed.
        :type queue: str

        :return: The number of messages requested to be purged.
        :rtype: int
        """
        return self._purge(queue)

    def basic_get(self, queue, no_ack=False, **kwargs):
        """Non-blocking single message get and ACK from a queue by name.

        Internally this method uses :meth:`_get` to fetch the message. If
        an :class:`~qpid.messaging.exceptions.Empty` exception is raised by
        :meth:`_get`, this method silences it and returns None. If
        :meth:`_get` does return a message, that message is ACKed. The no_ack
        parameter has no effect on ACKing behavior, and all messages are
        ACKed in all cases. This method never adds fetched Messages to the
        internal QoS object for asynchronous ACKing.

        This method converts the object type of the method as it passes
        through. Fetching from the broker, :meth:`_get` returns a
        :class:`qpid.messaging.Message`, but this method takes the payload
        of the :class:`qpid.messaging.Message` and instantiates a
        :class:`~kombu.transport.virtual.Message` object with the payload
        based on the class setting of self.Message.

        :param queue: The queue name to fetch a message from.
        :type queue: str
        :keyword no_ack: The no_ack parameter has no effect on the ACK
            behavior of this method. Un-ACKed messages create a memory leak in
            qpid.messaging, and need to be ACKed in all cases.
        :type noack: bool

        :return: The received message.
        :rtype: :class:`~kombu.transport.virtual.Message`
        """
        try:
            qpid_message = self._get(queue)
            raw_message = qpid_message.content
            message = self.Message(self, raw_message)
            self.transport.session.acknowledge(message=qpid_message)
            return message
        except Empty:
            pass

    def basic_ack(self, delivery_tag):
        """Acknowledge a message by delivery_tag.

        Acknowledges a message referenced by delivery_tag. Messages can
        only be ACKed using :meth:`basic_ack` if they were acquired using
        :meth:`basic_consume`. This is the ACKing portion of the
        asynchronous read behavior.

        Internally, this method uses the :class:`QoS` object, which stores
        messages and is responsible for the ACKing.

        :param delivery_tag: The delivery tag associated with the message
            to be acknowledged.
        :type delivery_tag: int
        """
        self.qos.ack(delivery_tag)

    def basic_reject(self, delivery_tag, requeue=False):
        """Reject a message by delivery_tag.

        Rejects a message that has been received by the Channel, but not
        yet acknowledged. Messages are referenced by their delivery_tag.

        If requeue is False, the rejected message will be dropped by the
        broker and not delivered to any other consumers. If requeue is
        True, then the rejected message will be requeued for delivery to
        another consumer, potentially to the same consumer who rejected the
        message previously.

        :param delivery_tag: The delivery tag associated with the message
            to be rejected.
        :type delivery_tag: int
        :keyword requeue: If False, the rejected message will be dropped by
            the broker and not delivered to any other consumers. If True,
            then the rejected message will be requeued for delivery to
            another consumer, potentially to the same consumer who rejected
            the message previously.
        :type requeue: bool

        """
        self.qos.reject(delivery_tag, requeue=requeue)

    def basic_consume(self, queue, no_ack, callback, consumer_tag, **kwargs):
        """Start an asynchronous consumer that reads from a queue.

        This method starts a consumer of type
        :class:`~qpid.messaging.endpoints.Receiver` using the
        :class:`~qpid.messaging.endpoints.Session` created and referenced by
        the :class:`Transport` that reads messages from a queue
        specified by name until stopped by a call to :meth:`basic_cancel`.


        Messages are available later through a synchronous call to
        :meth:`Transport.drain_events`, which will drain from the consumer
        started by this method. :meth:`Transport.drain_events` is
        synchronous, but the receiving of messages over the network occurs
        asynchronously, so it should still perform well.
        :meth:`Transport.drain_events` calls the callback provided here with
        the Message of type self.Message.

        Each consumer is referenced by a consumer_tag, which is provided by
        the caller of this method.

        This method sets up the callback onto the self.connection object in a
        dict keyed by queue name. :meth:`~Transport.drain_events` is
        responsible for calling that callback upon message receipt.

        All messages that are received are added to the QoS object to be
        saved for asynchronous ACKing later after the message has been
        handled by the caller of :meth:`~Transport.drain_events`. Messages
        can be ACKed after being received through a call to :meth:`basic_ack`.

        If no_ack is True, the messages are immediately ACKed to avoid a
        memory leak in qpid.messaging when messages go un-ACKed. The no_ack
        flag indicates that the receiver of the message does not intent to
        call :meth:`basic_ack`.

        :meth:`basic_consume` transforms the message object type prior to
        calling the callback. Initially the message comes in as a
        :class:`qpid.messaging.Message`. This method unpacks the payload
        of the :class:`qpid.messaging.Message` and creates a new object of
        type self.Message.

        This method wraps the user delivered callback in a runtime-built
        function which provides the type transformation from
        :class:`qpid.messaging.Message` to
        :class:`~kombu.transport.virtual.Message`, and adds the message to
        the associated :class:`QoS` object for asynchronous ACKing
        if necessary.

        :param queue: The name of the queue to consume messages from
        :type queue: str
        :param no_ack: If True, then messages will not be saved for ACKing
            later, but will be ACKed immediately. If False, then messages
            will be saved for ACKing later with a call to :meth:`basic_ack`.
        :type no_ack: bool
        :param callback: a callable that will be called when messages
            arrive on the queue.
        :type callback: a callable object
        :param consumer_tag: a tag to reference the created consumer by.
            This consumer_tag is needed to cancel the consumer.
        :type consumer_tag: an immutable object
        """
        self._tag_to_queue[consumer_tag] = queue

        def _callback(qpid_message):
            raw_message = qpid_message.content
            message = self.Message(self, raw_message)
            delivery_tag = message.delivery_tag
            self.qos.append(qpid_message, delivery_tag)
            if no_ack:
                # Celery will not ack this message later, so we should to
                # avoid a memory leak in qpid.messaging due to un-ACKed
                # messages.
                self.basic_ack(delivery_tag)
            return callback(message)

        self.connection._callbacks[queue] = _callback
        new_receiver = self.transport.session.receiver(queue)
        new_receiver.capacity = self.qos.prefetch_count
        self._receivers[consumer_tag] = new_receiver

    def basic_cancel(self, consumer_tag):
        """Cancel consumer by consumer tag.

        Request the consumer stops reading messages from its queue. The
        consumer is a :class:`~qpid.messaging.endpoints.Receiver`, and it is
        closed using :meth:`~qpid.messaging.endpoints.Receiver.close`.

        This method also cleans up all lingering references of the consumer.

        :param consumer_tag: The tag which refers to the consumer to be
            cancelled. Originally specified when the consumer was created
            as a parameter to :meth:`basic_consume`.
        :type consumer_tag: an immutable object
        """
        if consumer_tag in self._receivers:
            receiver = self._receivers.pop(consumer_tag)
            receiver.close()
            queue = self._tag_to_queue.pop(consumer_tag, None)
            self.connection._callbacks.pop(queue, None)

    def close(self):
        """Close Channel and all associated messages.

        This cancels all consumers by calling :meth:`basic_cancel` for each
        known consumer_tag. It also closes the self._broker sessions. Closing
        the sessions implicitly causes all outstanding, un-ACKed messages to
        be considered undelivered by the broker.
        """
        if not self.closed:
            self.closed = True
            for consumer_tag in self._receivers.keys():
                self.basic_cancel(consumer_tag)
            if self.connection is not None:
                self.connection.close_channel(self)
            self._broker.close()

    @property
    def qos(self):
        """:class:`QoS` manager for this channel.

        Lazily instantiates an object of type :class:`QoS` upon access to
        the self.qos attribute.

        :return: An already existing, or newly created QoS object
        :rtype: :class:`QoS`
        """
        if self._qos is None:
            self._qos = self.QoS(self.transport.session)
        return self._qos

    def basic_qos(self, prefetch_count, *args):
        """Change :class:`QoS` settings for this Channel.

        Set the number of un-acknowledged messages this Channel can fetch and
        hold. The prefetch_value is also used as the capacity for any new
        :class:`~qpid.messaging.endpoints.Receiver` objects.

        Currently, this value is hard coded to 1.

        :param prefetch_count: Not used. This method is hard-coded to 1.
        :type prefetch_count: int
        """
        self.qos.prefetch_count = 1

    def prepare_message(self, body, priority=None, content_type=None,
                        content_encoding=None, headers=None, properties=None):
        """Prepare message data for sending.

        This message is typically called by
        :meth:`kombu.messaging.Producer._publish` as a preparation step in
        message publication.

        :param body: The body of the message
        :type body: str
        :keyword priority: A number between 0 and 9 that sets the priority of
            the message.
        :type priority: int
        :keyword content_type: The content_type the message body should be
            treated as. If this is unset, the
            :class:`qpid.messaging.endpoints.Sender` object tries to
            autodetect the content_type from the body.
        :type content_type: str
        :keyword content_encoding: The content_encoding the message body is
            encoded as.
        :type content_encoding: str
        :keyword headers: Additional Message headers that should be set.
            Passed in as a key-value pair.
        :type headers: dict
        :keyword properties: Message properties to be set on the message.
        :type properties: dict

        :return: Returns a dict object that encapsulates message
            attributes. See parameters for more details on attributes that
            can be set.
        :rtype: dict
        """
        properties = properties or {}
        info = properties.setdefault('delivery_info', {})
        info['priority'] = priority or 0

        return {'body': body,
                'content-encoding': content_encoding,
                'content-type': content_type,
                'headers': headers or {},
                'properties': properties or {}}

    def basic_publish(self, message, exchange, routing_key, **kwargs):
        """Publish message onto an exchange using a routing key.

        Publish a message onto an exchange specified by name using a
        routing key specified by routing_key. Prepares the message in the
        following ways before sending:

        - encodes the body using :meth:`encode_body`
        - wraps the body as a buffer object, so that
            :class:`qpid.messaging.endpoints.Sender` uses a content type
            that can support arbitrarily large messages.
        - assigns a delivery_tag generated through self._delivery_tags
        - sets the exchange and routing_key info as delivery_info

        Internally uses :meth:`_put` to send the message synchronously. This
        message is typically called by
        :class:`kombu.messaging.Producer._publish` as the final step in
        message publication.

        :param message: A dict containing key value pairs with the message
            data. A valid message dict can be generated using the
            :meth:`prepare_message` method.
        :type message: dict
        :param exchange: The name of the exchange to submit this message
            onto.
        :type exchange: str
        :param routing_key: The routing key to be used as the message is
            submitted onto the exchange.
        :type routing_key: str
        """
        message['body'], body_encoding = self.encode_body(
            message['body'], self.body_encoding,
        )
        message['body'] = buffer(message['body'])
        props = message['properties']
        props.update(
            body_encoding=body_encoding,
            delivery_tag=next(self._delivery_tags),
        )
        props['delivery_info'].update(
            exchange=exchange,
            routing_key=routing_key,
        )
        self._put(routing_key, message, exchange, **kwargs)

    def encode_body(self, body, encoding=None):
        """Encode a body using an optionally specified encoding.

        The encoding can be specified by name, and is looked up in
        self.codecs. self.codecs uses strings as its keys which specify
        the name of the encoding, and then the value is an instantiated
        object that can provide encoding/decoding of that type through
        encode and decode methods.

        :param body: The body to be encoded.
        :type body: str
        :keyword encoding: The encoding type to be used. Must be a supported
            codec listed in self.codecs.
        :type encoding: str

        :return: If encoding is specified, return a tuple with the first
            position being the encoded body, and the second position the
            encoding used. If encoding is not specified, the body is passed
            through unchanged.
        :rtype: tuple
        """
        if encoding:
            return self.codecs.get(encoding).encode(body), encoding
        return body, encoding

    def decode_body(self, body, encoding=None):
        """Decode a body using an optionally specified encoding.

        The encoding can be specified by name, and is looked up in
        self.codecs. self.codecs uses strings as its keys which specify
        the name of the encoding, and then the value is an instantiated
        object that can provide encoding/decoding of that type through
        encode and decode methods.

        :param body: The body to be encoded.
        :type body: str
        :keyword encoding: The encoding type to be used. Must be a supported
            codec listed in self.codecs.
        :type encoding: str

        :return: If encoding is specified, the decoded body is returned.
            If encoding is not specified, the body is returned unchanged.
        :rtype: str
        """
        if encoding:
            return self.codecs.get(encoding).decode(body)
        return body

    def typeof(self, exchange, default='direct'):
        """Get the exchange type.

        Lookup and return the exchange type for an exchange specified by
        name. Exchange types are expected to be 'direct', 'topic',
        and 'fanout', which correspond with exchange functionality as
        specified in AMQP 0-10 and earlier. If the exchange cannot be
        found, the default exchange type is returned.

        :param exchange: The exchange to have its type lookup up.
        :type exchange: str
        :keyword default: The type of exchange to assume if the exchange does
            not exist.
        :type default: str

        :return: The exchange type either 'direct', 'topic', or 'fanout'.
        :rtype: str
        """
        qpid_exchange = self._broker.getExchange(exchange)
        if qpid_exchange:
            qpid_exchange_attributes = qpid_exchange.getAttributes()
            return qpid_exchange_attributes['type']
        else:
            return default


class Connection(object):
    """Encapsulate a connection object for the :class:`Transport`.

    A Connection object is created by a :class:`Transport` during a call to
    :meth:`Transport.establish_connection`. The :class:`Transport` passes in
    connection options as keywords that should be used for any connections
    created. Each :class:`Transport` creates exactly one Connection.

    A Connection object maintains a reference to a
    :class:`~qpid.messaging.endpoints.Connection` which can be accessed
    through a bound getter method named :meth:`get_qpid_connection` method.
    Each Channel uses a the Connection for each
    :class:`~qpidtoollibs.BrokerAgent`, and the Transport maintains a session
    for all senders and receivers.

    The Connection object is also responsible for maintaining the
    dictionary of references to callbacks that should be called when
    messages are received. These callbacks are saved in _callbacks,
    and keyed on the queue name associated with the received message. The
    _callbacks are setup in :meth:`Channel.basic_consume`, removed in
    :meth:`Channel.basic_cancel`, and called in
    :meth:`Transport.drain_events`.

    The following keys are expected to be passed in as keyword arguments
    at a minimum:

    All keyword arguments are collected into the connection_options dict
    and passed directly through to
    :meth:`qpid.messaging.endpoints.Connection.establish`.
    """

    # A class reference to the :class:`Channel` object
    Channel = Channel
    SASL_ANONYMOUS_MECH = 'ANONYMOUS'

    def __init__(self, **connection_options):
        """Instantiate a Connection object.

        The following parameters are expected:

        * host: The host that connections should connect to.
        * port: The port that connection should connect to.
        * username: The username that connections should connect with.
        * password: The password that connections should connect with.
        * transport: The transport type that connections should use. Either
              'tcp', or 'ssl' are expected as values.
        * timeout: the timeout used when a Connection connects to the broker.
        * sasl_mechanisms: The sasl authentication mechanism type to use.
              refer to SASL documentation for an explanation of valid values.

        Creates a :class:`qpid.messaging.endpoints.Connection` object with
        the saved parameters, and stores it as _qpid_conn.

        qpid.messaging has an AuthenticationFailure exception type, but
        instead raises a ConnectionError with a message that indicates an
        authentication failure occurred in those situations. ConnectionError
        is listed as a recoverable error type, so kombu will attempt to retry
        if a ConnectionError is raised. Retrying the operation without
        adjusting the credentials is not correct, so this method specifically
        checks for a ConnectionError that indicates an Authentication Failure
        occurred. In those situations, the error type is mutated while
        preserving the original message and raised so kombu will allow the
        exception to not be considered recoverable.

        """
        self.connection_options = connection_options
        self.channels = []
        self._callbacks = {}
        self._qpid_conn = None
        establish = qpid.messaging.Connection.establish

        # There is a behavior difference in qpid.messaging's sasl_mechanism
        # selection method and cyrus-sasl's. The former will put PLAIN before
        # ANONYMOUS if a username and password is given, but the latter will
        # simply take whichever mech is listed first. Thus, if we had
        # "ANONYMOUS PLAIN" as the default, the user would never be able to
        # select PLAIN if cyrus-sasl was installed.

        # The following code will put ANONYMOUS last in the mech list, and then
        # try sasl mechs one by one. This should still result in secure
        # behavior since it will select the first suitable mech. Unsuitable
        # mechs will be rejected by the server.

        _saslm = connection_options['sasl_mechanisms'].split()
        sasl_mechanisms = [x for x in _saslm
                           if x != self.SASL_ANONYMOUS_MECH]
        if self.SASL_ANONYMOUS_MECH in _saslm:
            sasl_mechanisms.append(self.SASL_ANONYMOUS_MECH)

        for sasl_mech in sasl_mechanisms:
            try:
                logger.debug(
                    'Attempting to connect to qpid '
                    'with SASL mechanism %s', sasl_mech,
                )
                modified_conn_opts = self.connection_options
                modified_conn_opts['sasl_mechanisms'] = sasl_mech
                self._qpid_conn = establish(**modified_conn_opts)
                # connection was successful if we got this far
                logger.info(
                    'Connected to qpid with SASL mechanism %s', sasl_mech,
                )
                break
            except ConnectionError as conn_exc:
                coded_as_auth_failure = getattr(conn_exc, 'code', None) == 320
                contains_auth_fail_text = \
                    'Authentication failed' in conn_exc.text
                contains_mech_fail_text = \
                    'sasl negotiation failed: no mechanism agreed' \
                    in conn_exc.text
                if coded_as_auth_failure or \
                        contains_auth_fail_text or contains_mech_fail_text:
                    logger.debug(
                        'Unable to connect to qpid with SASL mechanism %s',
                        sasl_mech,
                    )
                    continue
                raise

        if not self.get_qpid_connection():
            logger.error(
                'Unable to authenticate to qpid using '
                'the following mechanisms: %s', sasl_mechanisms,
            )
            raise AuthenticationFailure(sys.exc_info()[1])

    def get_qpid_connection(self):
        """Return the existing connection (singleton).

        :return: The existing qpid.messaging.Connection
        :rtype: :class:`qpid.messaging.endpoints.Connection`
        """
        return self._qpid_conn

    def close_channel(self, channel):
        """Close a Channel.

        Close a channel specified by a reference to the :class:`Channel`
        object.

        :param channel: Channel that should be closed.
        :type channel: Channel
        """
        try:
            self.channels.remove(channel)
        except ValueError:
            pass
        finally:
            channel.connection = None


class ReceiversMonitor(threading.Thread):
    """A monitoring thread that reads and handles messages from all receivers.

    A single instance of ReceiversMonitor is expected to be created by
    :class:`Transport`.

    In :meth:`monitor_receivers`, the thread monitors all receivers
    associated with the session created by the Transport using the blocking
    call to session.next_receiver(). When any receiver has messages
    available, a symbol '0' is written to the self._w_fd file descriptor. The
    :meth:`monitor_receivers` is designed not to exit, and loops over
    session.next_receiver() forever.

    The entry point of the thread is :meth:`run` which calls
    :meth:`monitor_receivers` and catches and logs all exceptions raised.
    After an exception is logged, the method sleeps for 10 seconds, and
    re-enters :meth:`monitor_receivers`

    The thread is designed to be daemonized, and will be forcefully killed
    when all non-daemon threads have already exited.
    """

    def __init__(self, session, w):
        """Instantiate a ReceiversMonitor object

        :param session: The session which needs all of its receivers
            monitored.
        :type session: :class:`qpid.messaging.endpoints.Session`
        :param w: The file descriptor to write the '0' into when
            next_receiver unblocks.
        :type w: int
        """
        super(ReceiversMonitor, self).__init__()
        self._session = session
        self._w_fd = w

    def run(self):
        """Thread entry point for ReceiversMonitor

        Calls :meth:`monitor_receivers` with a log-and-reenter behavior. This
        guards against unexpected exceptions which could cause this thread to
        exit unexpectedly.

        If a recoverable error occurs, then the exception needs to be
        propagated to the Main Thread where an exception handler can properly
        handle it. An Exception is checked if it is recoverable, and if so,
        it is stored as saved_exception on the self._session object. The
        character 'e' is then written to the self.w_fd file descriptor
        causing Main Thread to raise the saved exception. Once the Exception
        info is saved and the file descriptor is written, this Thread
        gracefully exits.

        Typically recoverable errors are connection errors, and can be
        recovered through a call to Transport.establish_connection which will
        spawn a new ReceiversMonitor Thread.
        """
        while True:
            try:
                self.monitor_receivers()
            except Transport.connection_errors as exc:
                self._session.saved_exception = exc
                os.write(self._w_fd, 'e')
                break
            except Exception as exc:
                logger.error(exc, exc_info=1)
            time.sleep(10)

    def monitor_receivers(self):
        """Monitor all receivers, and write to _w_fd when a message is ready.

        The call to next_receiver() blocks until a message is ready. Once a
        message is ready, write a '0' to _w_fd.
        """
        while True:
            self._session.next_receiver()
            os.write(self._w_fd, '0')


class Transport(base.Transport):
    """Kombu native transport for a Qpid broker.

    Provide a native transport for Kombu that allows consumers and
    producers to read and write messages to/from a broker. This Transport
    is capable of supporting both synchronous and asynchronous reading.
    All writes are synchronous through the :class:`Channel` objects that
    support this Transport.

    Asynchronous reads are done using a call to :meth:`drain_events`,
    which synchronously reads messages that were fetched asynchronously, and
    then handles them through calls to the callback handlers maintained on
    the :class:`Connection` object.

    The Transport also provides methods to establish and close a connection
    to the broker. This Transport establishes a factory-like pattern that
    allows for singleton pattern to consolidate all Connections into a single
    one.

    The Transport can create :class:`Channel` objects to communicate with the
    broker with using the :meth:`create_channel` method.

    The Transport identifies recoverable errors, allowing for error recovery
    when certain exceptions occur. These exception types are stored in the
    Transport class attribute connection_errors. This adds support for Kombu
    to retry an operation if a ConnectionError occurs. ConnectionErrors occur
    when the Transport cannot communicate with the Qpid broker.

    """

    # Reference to the class that should be used as the Connection object
    Connection = Connection

    # The default port
    default_port = DEFAULT_PORT

    # This Transport does not specify a polling interval.
    polling_interval = None

    # This Transport does support the Celery asynchronous event model.
    supports_ev = True

    # The driver type and name for identification purposes.
    driver_type = 'qpid'
    driver_name = 'qpid'

    connection_errors = (
        ConnectionError,
        select.error
    )

    def __init__(self, *args, **kwargs):
        """Instantiate a Transport object.

        This method creates a pipe, and saves the read and write file
        descriptors as attributes. The behavior of the read file descriptor
        is modified to be non-blocking using fcntl.fcntl.
        """
        self.verify_runtime_environment()
        super(Transport, self).__init__(*args, **kwargs)
        self.r, self._w = os.pipe()
        fcntl.fcntl(self.r, fcntl.F_SETFL, os.O_NONBLOCK)

    def verify_runtime_environment(self):
        """Verify that the runtime environment is acceptable.

        This method is called as part of __init__ and raises a RuntimeError
        in Python3 or PyPi environments. This module is not compatible with
        Python3 or PyPi. The RuntimeError identifies this to the user up
        front along with suggesting Python 2.6+ be used instead.

        This method also checks that the dependencies qpidtoollibs and
        qpid.messaging are installed. If either one is not installed a
        RuntimeError is raised.

        :raises: RuntimeError if the runtime environment is not acceptable.
        """
        if getattr(sys, 'pypy_version_info', None):
            raise RuntimeError(
                'The Qpid transport for Kombu does not '
                'support PyPy. Try using Python 2.6+',
            )
        if PY3:
            raise RuntimeError(
                'The Qpid transport for Kombu does not '
                'support Python 3. Try using Python 2.6+',
            )

        if dependency_is_none(qpidtoollibs):
            raise RuntimeError(
                'The Python package "qpidtoollibs" is missing. Install it '
                'with your package manager. You can also try `pip install '
                'qpid-tools`.')

        if dependency_is_none(qpid):
            raise RuntimeError(
                'The Python package "qpid.messaging" is missing. Install it '
                'with your package manager. You can also try `pip install '
                'qpid-python`.')

    def on_readable(self, connection, loop):
        """Handle any messages associated with this Transport.

        This method clears a single message from the externally monitored
        file descriptor by issuing a read call to the self.r file descriptor
        which removes a single '0' character that was placed into the pipe
        by :class:`ReceiversMonitor`. Once a '0' is read, all available
        events are drained through a call to :meth:`drain_events`.

        The behavior of self.r is adjusted in __init__ to be non-blocking,
        ensuring that an accidental call to this method when no more messages
        will arrive will not cause indefinite blocking.

        If the self.r file descriptor returns the character 'e', a
        recoverable error occurred in the background thread, and this thread
        should raise the saved exception. The exception is stored as
        saved_exception on the session object.

        Nothing is expected to be returned from :meth:`drain_events` because
        :meth:`drain_events` handles messages by calling callbacks that are
        maintained on the :class:`Connection` object. When
        :meth:`drain_events` returns, all associated messages have been
        handled.

        This method calls drain_events() which reads as many messages as are
        available for this Transport, and then returns. It blocks in the
        sense that reading and handling a large number of messages may take
        time, but it does not block waiting for a new message to arrive. When
        :meth:`drain_events` is called a timeout is not specified, which
        causes this behavior.

        One interesting behavior of note is where multiple messages are
        ready, and this method removes a single '0' character from
        self.r, but :meth:`drain_events` may handle an arbitrary amount of
        messages. In that case, extra '0' characters may be left on self.r
        to be read, where messages corresponding with those '0' characters
        have already been handled. The external epoll loop will incorrectly
        think additional data is ready for reading, and will call
        on_readable unnecessarily, once for each '0' to be read. Additional
        calls to :meth:`on_readable` produce no negative side effects,
        and will eventually clear out the symbols from the self.r file
        descriptor. If new messages show up during this draining period,
        they will also be properly handled.

        :param connection: The connection associated with the readable
            events, which contains the callbacks that need to be called for
            the readable objects.
        :type connection: Connection
        :param loop: The asynchronous loop object that contains epoll like
            functionality.
        :type loop: kombu.async.Hub
        """
        symbol = os.read(self.r, 1)
        if symbol == 'e':
            raise self.session.saved_exception
        try:
            self.drain_events(connection)
        except socket.timeout:
            pass

    def register_with_event_loop(self, connection, loop):
        """Register a file descriptor and callback with the loop.

        Register the callback self.on_readable to be called when an
        external epoll loop sees that the file descriptor registered is
        ready for reading. The file descriptor is created by this Transport,
        and is updated by the ReceiversMonitor thread.

        Because supports_ev == True, Celery expects to call this method to
        give the Transport an opportunity to register a read file descriptor
        for external monitoring by celery using an Event I/O notification
        mechanism such as epoll. A callback is also registered that is to
        be called once the external epoll loop is ready to handle the epoll
        event associated with messages that are ready to be handled for
        this Transport.

        The registration call is made exactly once per Transport after the
        Transport is instantiated.

        :param connection: A reference to the connection associated with
            this Transport.
        :type connection: Connection
        :param loop: A reference to the external loop.
        :type loop: kombu.async.hub.Hub
        """
        loop.add_reader(self.r, self.on_readable, connection, loop)

    def establish_connection(self):
        """Establish a Connection object.

        Determines the correct options to use when creating any connections
        needed by this Transport, and create a :class:`Connection` object
        which saves those values for connections generated as they are
        needed. The options are a mixture of what is passed in through the
        creator of the Transport, and the defaults provided by
        :meth:`default_connection_params`. Options cover broker network
        settings, timeout behaviors, authentication, and identity
        verification settings.

        This method also creates and stores a
        :class:`~qpid.messaging.endpoints.Session` using the
        :class:`~qpid.messaging.endpoints.Connection` created by this method.
        The Session is stored on self.

        :return: The created :class:`Connection` object is returned.
        :rtype: :class:`Connection`
        """
        conninfo = self.client
        for name, default_value in items(self.default_connection_params):
            if not getattr(conninfo, name, None):
                setattr(conninfo, name, default_value)
        if conninfo.hostname == 'localhost':
            conninfo.hostname = '127.0.0.1'
        if conninfo.ssl:
            conninfo.qpid_transport = 'ssl'
            conninfo.transport_options['ssl_keyfile'] = conninfo.ssl[
                'keyfile']
            conninfo.transport_options['ssl_certfile'] = conninfo.ssl[
                'certfile']
            conninfo.transport_options['ssl_trustfile'] = conninfo.ssl[
                'ca_certs']
            if conninfo.ssl['cert_reqs'] == ssl.CERT_REQUIRED:
                conninfo.transport_options['ssl_skip_hostname_check'] = False
            else:
                conninfo.transport_options['ssl_skip_hostname_check'] = True
        else:
            conninfo.qpid_transport = 'tcp'
        opts = dict({'host': conninfo.hostname, 'port': conninfo.port,
                     'username': conninfo.userid,
                     'password': conninfo.password,
                     'transport': conninfo.qpid_transport,
                     'timeout': conninfo.connect_timeout,
                     'sasl_mechanisms': conninfo.sasl_mechanisms},
                    **conninfo.transport_options or {})
        conn = self.Connection(**opts)
        conn.client = self.client
        self.session = conn.get_qpid_connection().session()
        monitor_thread = ReceiversMonitor(self.session, self._w)
        monitor_thread.daemon = True
        monitor_thread.start()
        return conn

    def close_connection(self, connection):
        """Close the :class:`Connection` object, and all associated
        :class:`Channel` objects.

        Iterates through all :class:`Channel` objects associated with the
        :class:`Connection`, pops them from the list of channels, and calls
        :meth:Channel.close` on each.

        :param connection: The Connection that should be closed
        :type connection: Connection
        """
        for channel in connection.channels:
                channel.close()

    def drain_events(self, connection, timeout=0, **kwargs):
        """Handle and call callbacks for all ready Transport messages.

        Drains all events that are ready from all
        :class:`~qpid.messaging.endpoints.Receiver` that are asynchronously
        fetching messages.

        For each drained message, the message is called to the appropriate
        callback. Callbacks are organized by queue name.

        :param connection: The :class:`Connection` that contains the
            callbacks, indexed by queue name, which will be called by this
            method.
        :type connection: Connection
        :keyword timeout: The timeout that limits how long this method will
            run for. The timeout could interrupt a blocking read that is
            waiting for a new message, or cause this method to return before
            all messages are drained. Defaults to 0.
        :type timeout: int
        """
        start_time = time.time()
        elapsed_time = -1
        while elapsed_time < timeout:
            try:
                receiver = self.session.next_receiver(timeout=timeout)
                message = receiver.fetch()
                queue = receiver.source
            except QpidEmpty:
                raise socket.timeout()
            else:
                connection._callbacks[queue](message)
            elapsed_time = time.time() - start_time
        raise socket.timeout()

    def create_channel(self, connection):
        """Create and return a :class:`Channel`.

        Creates a new :class:`Channel`, and append the :class:`Channel` to the
        list of channels known by the :class:`Connection`. Once the new
        :class:`Channel` is created, it is returned.

        :param connection: The connection that should support the new
            :class:`Channel`.
        :type connection: Connection

        :return: The new Channel that is made.
        :rtype: :class:`Channel`.
        """
        channel = connection.Channel(connection, self)
        connection.channels.append(channel)
        return channel

    @property
    def default_connection_params(self):
        """Return a dict with default connection parameters.

        These connection parameters will be used whenever the creator of
        Transport does not specify a required parameter.

        NOTE: password is set to '' by default instead of None so the a
        connection is attempted[1]. An empty password is considered valid for
        qpidd if "auth=no" is set on the server.

        [1] https://issues.apache.org/jira/browse/QPID-6109

        :return: A dict containing the default parameters.
        :rtype: dict
        """
        return {'userid': 'guest', 'password': '',
                'port': self.default_port, 'virtual_host': '',
                'hostname': 'localhost', 'sasl_mechanisms': 'PLAIN ANONYMOUS'}
