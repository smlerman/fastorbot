import asyncio
import logging

class IRCProtocol(asyncio.Protocol):
    def __init__(self, loop, owner):
        self.loop = loop
        self.owner = owner
        
        asynciologger = logging.getLogger('fastorbot')
        asynciologger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("fastorbot.log")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        asynciologger.addHandler(fh)
    
    def connection_made(self, transport):
        self.owner.on_connect(transport)

    def data_received(self, data):
        self.owner.on_receive(data)

    def connection_lost(self, exc):
        print('The server closed the connection')
        print('Stop the event loop')
        self.loop.stop()
