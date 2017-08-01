import asyncio
import datetime
import logging
import sys
import time

from fastorbot.IRCCallback import *
from fastorbot.IRCChannel import *
from fastorbot.IRCMessage import *
from fastorbot.IRCProtocol import *
from fastorbot.IRCUser import *

class IRCConnection(object):
    def __init__(self, hostname, hostport, nick):
        self.hostname = hostname
        self.hostport = hostport
        
        self.server_name = hostname
        
        self.nick = nick
        self.ident = self.nick
        self.local_hostname = "www.example.com"
        self.real_name = self.nick
        
        self.users = dict()
        self.current_channels = dict()
        
        self.server_data_buffer = ""
        
        self.callbacks = dict()
        
        self.add_callback("JOIN", IRCCallback(IRCConnection.irc_callback_user_join))
        self.add_callback("PART", IRCCallback(IRCConnection.irc_callback_user_part))
        self.add_callback("QUIT", IRCCallback(IRCConnection.irc_callback_user_quit))
        self.add_callback("NICK", IRCCallback(IRCConnection.irc_callback_user_nick))
        self.add_callback("MODE", IRCCallback(IRCConnection.irc_callback_mode_change))
        self.add_callback("353", IRCCallback(IRCConnection.irc_callback_channel_users))
        self.add_callback("366", IRCCallback(IRCConnection.irc_callback_channel_end_users))
        self.add_callback("311", IRCCallback(IRCConnection.irc_callback_whois_user))
        self.add_callback("318", IRCCallback(IRCConnection.irc_callback_whois_end))
        
        self.waiting_for_whois = dict()
    
    def set_owner(self, owner):
        self.owner = owner
    
    def connect(self):
        self.loop = asyncio.get_event_loop()
        self.coroutine = self.loop.create_connection(lambda: IRCProtocol(self.loop, self), self.hostname, self.hostport)
        
        # Set timer to check for a disconnection (no data for ten minutes) every minute
        self.loop.call_later(60, self.check_connection_timeout)
        self.last_activity = datetime.datetime.now()
        
        self.loop.run_until_complete(self.coroutine)
        self.loop.run_forever()
    
    def on_connect(self, transport):
        self.transport = transport
        self.put_message("USER " + self.ident + " " + self.local_hostname + " " + self.server_name + " :" + self.real_name)
        self.put_message("NICK " + self.nick)
    
    def disconnect(self, quit_message="Fastorbot Version 0.1"):
        self.put_message("QUIT :" + quit_message)
    
    def on_receive(self, data):
        try:
            data_string = data.decode(errors="replace")
        except UnicodeDecodeError:
            return
        
        irc_messages = self.parse_server_data(data_string)
        for irc_message in irc_messages:
            self.handle_message(irc_message)
    
    def on_disconnect(self, exc):
        self.reconnect()
    
    def reconnect(self):
        self.disconnect()
        time.sleep(5)
        self.connect()
    
    def parse_server_data(self, data_string):
        # Set last activity timer
        self.last_activity = datetime.datetime.now()
        
        self.server_data_buffer += data_string
        
        messages = self.server_data_buffer.split("\r\n")
        irc_messages = list()
        
        # If the buffer doesn't end with \r\n, the last message is incomplete
        # Take the last (partial) message in the buffer and leave it in the buffer
        if not self.server_data_buffer.endswith("\r\n"):
            self.server_data_buffer = messages.pop()
        else:
            self.server_data_buffer = ""
        
        for message in messages:
            if message == "":
                continue
            
            irc_message = IRCMessage(message)
            
            if (irc_message.source.nick == "PING"):
                self.put_message("PONG " + irc_message.command)
                irc_message.command = "PING"
            
            irc_messages.append(irc_message)
            
        return irc_messages
    
    def handle_message(self, irc_message):
        self.check_callbacks(irc_message)
        
        # If the message source is a user in the channel, check if that user's hostmask is recorded
        nick = irc_message.source.nick
        channel = irc_message.destination
        if channel in self.current_channels:
            channel_users = self.current_channels[channel].users
            if (nick in channel_users) and (channel_users[nick].host is None):
                channel_users[nick].ident = irc_message.source.ident
                channel_users[nick].host = irc_message.source.host
        
        self.owner.handle_message(self, irc_message)

    def put_message(self, message_text):
        text_to_send = message_text + "\r\n"
        self.transport.write(text_to_send.encode())
        self.log_message("put_message: " + message_text)
    
    def join_channel(self, channel_name):
        if channel_name not in self.current_channels:
            self.current_channels[channel_name] = IRCChannel(channel_name)
            self.put_message("JOIN " + channel_name)
    
    def part_channel(self, channel_name):
        if channel_name in self.current_channels:
            del self.current_channels[channel_name]
            self.put_message("PART " + channel_name)
    
    def send_message(self, destination, message_text, is_ctcp=False):
        message = IRCMessage(message_text, is_ctcp)
        self.put_message("PRIVMSG " + destination + " :" + message.message_text)
    
    def send_action(self, destination, message_text):
        message = IRCMessage("ACTION " + message_text, True)
        self.put_message("PRIVMSG " + destination + " :" + message.message_text)
    
    def send_notice(self, destination, message_text, is_ctcp=False):
        message = IRCMessage(message_text, is_ctcp)
        self.put_message("NOTICE " + destination + " :" + message.message_text)
    
    def send_whois(self, nick):
        self.waiting_for_whois[nick] = 0
        self.put_message("WHOIS " + nick)
    
    def add_callback(self, command, method):
        self.callbacks[command] = method

    def remove_callback(self, command, method):
        if (command in self.callbacks) and (self.callbacks[command] == method):
            del self.callbacks[command]

    def check_callbacks(self, irc_message):
        if irc_message.command in self.callbacks:
            callback = self.callbacks[irc_message.command]
            callback.method(self, irc_message, callback.arguments)
    
    @staticmethod
    def irc_callback_user_join(irc_connection, irc_message, arguments):
        irc_user = IRCUser(irc_message.source.nick, irc_message.source.ident, irc_message.source.host)
        irc_connection.users[irc_user.nick] = irc_user
        irc_connection.current_channels[irc_message.destination].add_irc_user(irc_user)

    @staticmethod
    def irc_callback_user_part(irc_connection, irc_message, arguments):
        irc_connection.current_channels[irc_message.destination].remove_user(irc_message.source.nick)
    
    @staticmethod
    def irc_callback_user_quit(irc_connection, irc_message, arguments):
        for channel in irc_connection.current_channels.values():
            channel.remove_user(irc_message.source.nick)
    
    @staticmethod
    def irc_callback_user_nick(irc_connection, irc_message, arguments):
        new_nick = irc_message.destination
        
        if irc_message.source.nick == irc_connection.nick:
            irc_connection.nick = new_nick.lstrip(":")
        
        for channel in irc_connection.current_channels.values():
            channel.change_nick(irc_message.source.nick, new_nick)
    
    @staticmethod
    def irc_callback_mode_change(irc_connection, irc_message, arguments):
        mode_nicks = irc_message.rest.split(" ")
        
        # Get the mode string and remove it from the nick array
        mode_string = mode_nicks.pop(0)
        
        plus_mode = False
        for mode_char in mode_string:
            if (mode_char == "+"):
                plus_mode = True
            elif (mode_char == "-"):
                plus_mode = False
            elif (mode_char == "v"):
                nick = mode_nicks.pop(0)
                if plus_mode:
                    irc_connection.current_channels[irc_message.destination].users[nick].is_voice = True
                else:
                    irc_connection.current_channels[irc_message.destination].users[nick].is_voice = False
            elif (mode_char == "o"):
                nick = mode_nicks.pop(0)
                if plus_mode:
                    irc_connection.current_channels[irc_message.destination].users[nick].is_op = True
                else:
                    irc_connection.current_channels[irc_message.destination].users[nick].is_op = False
    
    @staticmethod
    def irc_callback_channel_users(irc_connection, irc_message, arguments):
        users_list = irc_message.rest.lstrip(" =@*").split(" ")
        channel = users_list.pop(0)
        
        for nick in users_list:
            if len(nick) > 0:
                op = False
                voice = False
                if "+" in nick:
                    voice = True
                    nick = nick.replace("+", "")
                
                if "@" in nick:
                    op = True
                    nick = nick.replace("@", "")
                
                irc_user = IRCUser(nick, None, None, voice, op)
                irc_connection.users[irc_user.nick] = irc_user
                
                if channel in irc_connection.current_channels:
                    irc_connection.current_channels[channel].add_irc_user(irc_user)
    
    @staticmethod
    def irc_callback_channel_end_users(irc_connection, irc_message, arguments):
        pass
    
    #####
    # WHOIS responses
    #####
    
    @staticmethod
    def irc_callback_whois_user(irc_connection, irc_message, arguments):
        whois_data = irc_message.rest.split(" ")
        nick = whois_data[0]
        irc_connection.log_message("Setting host for %s" % (nick))
        
        if nick not in irc_connection.users:
            irc_user = IRCUser(nick, None, None)
            irc_connection.users[nick] = irc_user
        else:
            irc_user = irc_connection.users[nick]
        
        irc_user.ident = whois_data[1]
        irc_user.host = whois_data[2]
        irc_user.set_hostmask()
        """
        for channel in irc_connection.current_channels.values():
            if nick in channel.users:
                irc_connection.log_message("Setting host for %s in channel %s" % (nick, channel.name))
                irc_user = channel.users[nick]
                irc_user.ident = whois_data[1]
                irc_user.host = whois_data[2]
                irc_user.set_hostmask()
                #irc_user.realname = whois_data[3]
        """
    
    @staticmethod
    def irc_callback_whois_server(irc_connection, irc_message, arguments):
        whois_data = irc_message.rest.split(" ")
        server = whois_data[1]
        server_info = whois_data[2]
    
    @staticmethod
    def irc_callback_whois_operator(irc_connection, irc_message, arguments):
        whois_data = irc_message.rest.split(" ")
        is_oper = True
    
    @staticmethod
    def irc_callback_whois_idle(irc_connection, irc_message, arguments):
        whois_data = irc_message.rest.split(" ")
        idle_time = whois_data[1]
    
    @staticmethod
    def irc_callback_whois_channels(irc_connection, irc_message, arguments):
        whois_data = irc_message.rest.split(" ")
        # Remove user's nick from the channel list
        whois_data.pop(0)
        channels = list()
        for channel in whois_data:
            channels.append(channel.lstrip(":"))
    
    @staticmethod
    def irc_callback_whois_end(irc_connection, irc_message, arguments):
        whois_data = irc_message.rest.split(" ")
        nick = whois_data[0]
        irc_connection.log_message("whois end " + nick)
        
        if nick in irc_connection.waiting_for_whois:
            del irc_connection.waiting_for_whois[nick]
            irc_connection.log_message("deleted whois end " + nick)
        
    def check_connection_timeout(self):
        last_activity_delta = datetime.datetime.now() - self.last_activity
        if last_activity_delta.seconds > 600:
            print("Timed out")
            self.reconnect()
        
        self.loop.call_later(60, self.check_connection_timeout)
    
    def log_message(self, message_text):
        logging.getLogger('fastorbot').info(message_text)
    
    def __del__(self):
        self.disconnect()
