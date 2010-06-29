from copy import copy

TRANSIENT_DELIVERY_MODE = 1
PERSISTENT_DELIVERY_MODE = 2
DELIVERY_MODES = {"transient": TRANSIENT_DELIVERY_MODE,
                  "persistent": PERSISTENT_DELIVERY_MODE}

class NotBoundError(Exception):
    """Trying to call channel dependent method on unbound entity."""


class Object(object):
    attrs = ()

    def __init__(self, *args, **kwargs):
        any = lambda v: v
        for name, type_ in self.attrs:
            value = kwargs.get(name)
            if value is not None:
                setattr(self, name, (type_ or any)(value))
            else:
                try:
                    getattr(self, name)
                except AttributeError:
                    setattr(self, name, None)

    def __copy__(self):
        return self.__class__(**dict((name, getattr(self, name))
                                        for name, _ in self.attrs))


def assert_is_bound(fun):

    def if_bound(self, *args, **kwargs):
        if self.is_bound:
            return fun(self, *args, **kwargs)
        raise NotBoundError(
                "Can't call %s on %s not bound to a channel" % (
                    fun.__name__,
                    self.__class__.__name__))
    if_bound.__name__ = fun.__name__
    if_bound.__doc__ = fun.__doc__
    if_bound.__module__ = fun.__module__
    if_bound.__dict__.update(fun.__dict__)
    if_bound.func_name = fun.__name__

    return if_bound


class MaybeChannelBound(Object):
    """Mixin for classes that can be bound to an AMQP channel."""
    channel = None
    _is_bound = False

    def __call__(self, channel):
        return self.bind(channel)

    def bind(self, channel):
        """Create copy of the instance that is bound to a channel."""
        return copy(self).maybe_bind(channel)

    def maybe_bind(self, channel):
        """Bind instance to channel if not already bound."""
        if not self.is_bound and channel:
            self.channel = channel
            self.when_bound()
            self._is_bound = True
        return self

    def when_bound(self):
        """Callback called when the class is bound."""
        pass

    @property
    def is_bound(self):
        """Returns ``True`` if the entity is bound."""
        return self._is_bound and self.channel is not None

    def __repr__(self, item=""):
        if self.is_bound:
            return "<bound %s of %s>" % (item or self.__class__.__name__,
                                         self.channel)
        return "<unbound %s>" % (item, )


class Exchange(MaybeChannelBound):
    TRANSIENT_DELIVERY_MODE = TRANSIENT_DELIVERY_MODE
    PERSISTENT_DELIVERY_MODE = PERSISTENT_DELIVERY_MODE
    name = ""
    type = "direct"
    routing_key = ""
    durable = True
    auto_delete = False
    delivery_mode = PERSISTENT_DELIVERY_MODE

    attrs = (("name", None),
             ("type", None),
             ("routing_key", None),
             ("channel", None),
             ("arguments", None),
             ("durable", bool),
             ("auto_delete", bool),
             ("delivery_mode", lambda m: DELIVERY_MODES.get(m) or m))

    def __init__(self, name="", type="", routing_key="", **kwargs):
        super(Exchange, self).__init__(**kwargs)
        self.name = name or self.name
        self.type = type or self.type
        self.routing_key = routing_key or self.routing_key
        self.maybe_bind(self.channel)

    @assert_is_bound
    def declare(self):
        """Declare the exchange.

        Creates the exchange on the broker.

        """
        return self.channel.exchange_declare(exchange=self.name,
                                             type=self.type,
                                             durable=self.durable,
                                             auto_delete=self.auto_delete,
                                             arguments=self.arguments)

    @assert_is_bound
    def create_message(self, message_data, delivery_mode=None,
                priority=None, content_type=None, content_encoding=None,
                properties=None, headers=None):
        properties = properties or {}
        properties["delivery_mode"] = delivery_mode or self.delivery_mode
        return self.channel.prepare_message(message_data,
                                            properties=properties,
                                            priority=priority,
                                            content_type=content_type,
                                            content_encoding=content_encoding,
                                            headers=headers)

    @assert_is_bound
    def publish(self, message, routing_key=None, mandatory=False,
            immediate=False, headers=None):
        if routing_key is None:
            routing_key = self.routing_key
        return self.channel.basic_publish(message,
                                          exchange=self.name,
                                          routing_key=routing_key,
                                          mandatory=mandatory,
                                          immediate=immediate)

    @assert_is_bound
    def delete(self, if_unused=False):
        return self.channel.exchange_delete(self.name, if_unused=if_unused)

    def __repr__(self):
        return super(Exchange, self).__repr__("Exchange %s(%s)" % (self.name,
                                                                   self.type))


class Binding(MaybeChannelBound):
    name = ""
    exchange = None
    routing_key = ""

    durable = True
    exclusive = False
    auto_delete = False

    attrs = (("name", None),
             ("exchange", None),
             ("routing_key", None),
             ("channel", None),
             ("queue_arguments", None),
             ("binding_arguments", None),
             ("durable", bool),
             ("exclusive", bool),
             ("auto_delete", bool))

    def __init__(self, name="", exchange=None, routing_key="", **kwargs):
        super(Binding, self).__init__(**kwargs)
        self.name = name or self.name
        self.exchange = exchange or self.exchange
        self.routing_key = routing_key or self.routing_key
        # exclusive implies auto-delete.
        if self.exclusive:
            self.auto_delete = True
        self.maybe_bind(self.channel)

    def when_bound(self):
        self.exchange = self.exchange(self.channel)

    @assert_is_bound
    def declare(self):
        """Declares the queue, the exchange and binds the queue to
        the exchange."""
        chan = self.channel
        return (self.exchange and self.exchange.declare(),
                self.name and chan.queue_declare(queue=self.name,
                                            durable=self.durable,
                                            exclusive=self.exclusive,
                                            auto_delete=self.auto_delete,
                                            arguments=self.queue_arguments),
                self.name and chan.queue_bind(queue=self.name,
                                            exchange=self.exchange.name,
                                            routing_key=self.routing_key,
                                            arguments=self.binding_arguments))

    @assert_is_bound
    def get(self, no_ack=None):
        message = self.channel.basic_get(self.name, no_ack=no_ack)
        if message:
            return self.channel.message_to_python(message)

    @assert_is_bound
    def purge(self):
        return self.channel.queue_purge(self.name)

    @assert_is_bound
    def consume(self, consumer_tag, callback, no_ack=None, nowait=True):
        return self.channel.basic_consume(queue=self.name,
                                          no_ack=no_ack,
                                          consumer_tag=consumer_tag,
                                          callback=callback,
                                          nowait=nowait)

    @assert_is_bound
    def cancel(self, consumer_tag):
        return self.channel.basic_cancel(consumer_tag)

    @assert_is_bound
    def delete(self, if_unused=False, if_empty=False):
        return self.channel.queue_delete(self.name, if_unused, if_empty)

    def __repr__(self):
        return super(Binding, self).__repr__(
                 "Binding %s -> %s -> %s" % (self.name,
                                             self.exchange,
                                             self.routing_key))
