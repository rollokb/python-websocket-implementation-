import socket
import hashlib
import base64
import time

from queue import Queue
from threading import Thread


WEBSOCKET_KEY = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def parse_headers(header_text):
    headers = header_text.strip().split(b'\n')

    return {
        h.split()[0][:-1]: h.split()[1] for h in headers
    }


def frame_parser(data):
    """
    Ultra barebones parser that makes a bunch of
    rather stupid assumptions about the data

    1. It's always text
    2. The payload length is less than 128
    3. There is a mask.

    #  0                   1                   2                   3
    #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    # +-+-+-+-+-------+-+-------------+-------------------------------+
    # |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
    # |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
    # |N|V|V|V|       |S|             |   (if payload len==126/127)   |
    # | |1|2|3|       |K|             |                               |
    # +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
    # |     Extended payload length continued, if payload len == 127  |
    # + - - - - - - - - - - - - - - - +-------------------------------+
    # |                               |Masking-key, if MASK set to 1  |
    # +-------------------------------+-------------------------------+
    # | Masking-key (continued)       |          Payload Data         |
    # +-------------------------------- - - - - - - - - - - - - - - - +
    # :                     Payload Data continued ...                :
    # + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
    # |                     Payload Data continued ...                |
    # +---------------------------------------------------------------+
    """
    state = 'OPCODE'
    payload = bytearray()
    payload_index = 0
    masking_key = bytearray()

    for index, d in enumerate(data):
        if state == 'OPCODE':
            # Just going to assume it's text
            state = 'MASK_AND_LENGTH'
            continue

        if state == 'MASK_AND_LENGTH':
            state = 'MASKING_KEY'
            continue

        if state == 'MASKING_KEY':
            if len(masking_key) < 4:
                masking_key.append(d)
            else:
                state = 'PAYLOAD'

        if state == 'PAYLOAD':
            payload.append(d ^ masking_key[payload_index % 4])
            payload_index = payload_index + 1

    return payload.decode()


def frame_generator(payload):
    data = bytearray()

    data.append(
        # The first bit indicates this is the complete message
        # The last four bit is the opcode. in this case 0b11
        # 3 indicates we're going to send a text message
        0b10000001
    )

    data.append(
        # The first bit indicates we're not using a mask, servers cannot
        # send masked messages.
        # The last 7 bits is the length of the payload (hopefully under 127)
        0b01111111 & len(payload)
    )

    for d in payload:
        data.append(d)

    return data


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    port = 8000

    s.bind(('localhost', port))
    s.listen(10)

    worker_queue = Queue()

    def worker():
        clientsocket = worker_queue.get()

        while True:
            data = clientsocket.recv(1024)
            payload = frame_parser(data)

            payload = payload.encode('utf')
            payload = frame_generator(payload)
            payload = payload.upper()

            clientsocket.send(bytes(payload))

    def server():
        while True:
            # establish a connection
            clientsocket, addr = s.accept()

            print("Got a connection from %s" % str(addr))

            request_text = clientsocket.recv(1024)
            request_line, headers_alone = request_text.split(b'\r\n', 1)
            headers = parse_headers(headers_alone)
            sec_websocket_accept = headers[b'Sec-WebSocket-Key'] + WEBSOCKET_KEY

            sha1 = hashlib.sha1()
            sha1.update(sec_websocket_accept)
            sec_websocket_accept = base64.b64encode(sha1.digest())

            msg = '\n'.join([
                'HTTP/1.1 101 Switching Protocols',
                'Upgrade: websocket',
                'Connection: Upgrade',
                'Sec-WebSocket-Accept: {}\r\n\r\n'.format(
                    sec_websocket_accept.decode('utf')
                )
            ])

            clientsocket.send(msg.encode('utf'))

            # Now the handshake is done. We need to move this to a worker
            worker_queue.put(clientsocket)

    server_thread = Thread(target=server)
    server_thread.start()

    worker_threads = []
    for _ in range(4):
        t = Thread(target=worker)
        t.start()
        worker_threads.append(t)

    while True:
        try:
            time.sleep(1)
        except:
            for t in worker_threads:
                t.join()

            server.join()

    s.close()
