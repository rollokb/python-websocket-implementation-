# Websocket Implementation

This was an exercise for myself to see how one can implement the WebSocket
protocol as defined in [RFC6455](https://tools.ietf.org/html/rfc6455) in
roughly 2 hours only using the Python standard library. I needed to understand how the
protocol works a bit better so I can meaningfully evaluate the WebSocket
libraries on offer. If you don't know how it works, don't use it.

I implemented a small subset of the RFC, allowing for connections to be
upgraded to a normal TCP socket, and for events to be passed both ways. I have
only implemented the ability to pass textual events. My WebSocket event handler
performs a simple function of making any text sent to it uppercase.

I began to implement some form of concurrency, but I was a bit lazy and didn't
implement any way to handle connection terminations. Meaning that workers will
just get used up.
