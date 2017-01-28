import logging

from IRCUser import *

class IRCMessage(object):
    
    def __init__(self, message_text, is_ctcp=False):
        self.message_text = message_text
        if is_ctcp:
            self.ctcp_quote()
        
        message_parts = self.message_text.split(" ", 3)
        
        self.source = IRCUser.from_userinfo(message_parts[0])
        if len(message_parts) == 4:
            self.rest = message_parts[3].lstrip(":")
            if (len(self.rest) > 0) and (self.rest[0] == chr(1)):
                self.is_ctcp = True
                self.rest = self.rest[1:len(self.rest) - 2]
            
            self.destination = message_parts[2].lstrip(":")
            self.command = message_parts[1]
        elif len(message_parts) == 3:
            self.rest = ""
            self.destination = message_parts[2].lstrip(":")
            self.command = message_parts[1]
        elif len(message_parts) == 2:
            self.rest = ""
            self.destination = ""
            self.command = message_parts[1]
        else:
            self.rest = ""
            self.destination = ""
            self.command = ""
        
        # Determine where responses should be sent (e.g. if the message was sent to a channel or to the bot in a private message)
        if self.destination.startswith("#"):
            self.response_destination = self.destination
        else:
            self.response_destination = self.source.nick

    def ctcp_quote(self):
        self.message_text = self.message_text.replace(chr(16), chr(16) + chr(16))
        self.message_text = self.message_text.replace("\r", chr(16) + "r")
        self.message_text = self.message_text.replace("\n", chr(16) + "n")
        self.message_text = self.message_text.replace(chr(0), chr(16) + "0")
        self.message_text = self.message_text.replace("\\", "\\\\")
        self.message_text = self.message_text.replace(chr(1), "\\a")
        self.message_text = chr(1) + self.message_text + chr(1)

    def ctcp_unquote(self):
        self.message_text = self.message_text[1:-2]
        self.message_text = self.message_text.replace("\\a", chr(1))
        self.message_text = self.message_text.replace("\\\\", "\\")
        self.message_text = self.message_text.replace(chr(16) + "0", chr(0))
        self.message_text = self.message_text.replace(chr(16) + "n", "\n")
        self.message_text = self.message_text.replace(chr(16) + "r", "\r")
        self.message_text = self.message_text.replace(chr(16) + chr(16), chr(16))
    
    def __str__(self):
        return "IRCMessage: {{source: \"{source}\", command: \"{command}\", destination: \"{destination}\", rest: \"{rest}\"}}".format(
            source=self.source,
            command=self.command,
            destination=self.destination,
            rest=self.rest
        )
