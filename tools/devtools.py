"""Small local Chrome DevTools client, implemented for this project's checks."""
import base64
import hashlib
import json
import os
import socket
import struct
from urllib.parse import urlsplit

class DevTools:
    def __init__(self,url):
        endpoint=urlsplit(url)
        self.socket=socket.create_connection((endpoint.hostname,endpoint.port),timeout=25)
        key=base64.b64encode(os.urandom(16)).decode()
        request=("GET "+endpoint.path+" HTTP/1.1\r\nHost: "+endpoint.netloc+"\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: "+key+"\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.socket.sendall(request.encode())
        reply=bytearray()
        while not reply.endswith(b"\r\n\r\n"): reply.extend(self.socket.recv(1))
        expected=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b" 101 " not in reply or expected not in reply: raise RuntimeError("DevTools WebSocket handshake rejected")
        self.serial=0;self.events=[]
    def receive_bytes(self,count):
        value=bytearray()
        while len(value)<count:
            chunk=self.socket.recv(count-len(value))
            if not chunk: raise EOFError("DevTools disconnected")
            value.extend(chunk)
        return bytes(value)
    def transmit(self,data,opcode=1):
        length=len(data);prefix=bytearray([128|opcode])
        if length<126: prefix.append(128|length)
        elif length<65536: prefix.extend(bytes([254])+struct.pack("!H",length))
        else: prefix.extend(bytes([255])+struct.pack("!Q",length))
        mask=os.urandom(4);prefix.extend(mask)
        prefix.extend(byte^mask[i%4] for i,byte in enumerate(data))
        self.socket.sendall(prefix)
    def message(self):
        combined=bytearray()
        while True:
            first,second=self.receive_bytes(2);size=second&127
            if size==126: size=struct.unpack("!H",self.receive_bytes(2))[0]
            if size==127: size=struct.unpack("!Q",self.receive_bytes(8))[0]
            mask=self.receive_bytes(4) if second&128 else None
            content=self.receive_bytes(size)
            if mask: content=bytes(v^mask[i%4] for i,v in enumerate(content))
            if first&15==9:
                self.transmit(content,10);continue
            if first&15==8: raise EOFError("DevTools closed")
            combined.extend(content)
            if first&128: return json.loads(combined)
    def call(self,method,params=None):
        self.serial+=1;number=self.serial
        self.transmit(json.dumps(dict(id=number,method=method,params=params or {})).encode())
        while True:
            packet=self.message()
            if packet.get("id")==number:
                if packet.get("error"): raise RuntimeError(str(packet["error"]))
                return packet.get("result",{})
            self.events.append(packet)
    def evaluate(self,code):
        result=self.call("Runtime.evaluate",dict(expression=code,awaitPromise=True,returnByValue=True))
        if result.get("exceptionDetails"): raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result",{}).get("value")
