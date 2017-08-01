from IRCUser import *

class IRCChannel(object):
    def __init__(self, channel):
        self.name = channel
        self.users = dict()

    def add_user(self, nick, ident, host, voice=False, op=False):
        new_user = IRCUser(nick, ident, host, voice, op)
        self.users[nick] = new_user
    
    def add_irc_user(self, irc_user):
        self.users[irc_user.nick] = irc_user
    
    def remove_user(self, nick):
        if nick in self.users:
            del self.users[nick]
    
    def change_nick(self, old_nick, new_nick):
        if old_nick in self.users:
            self.users[new_nick] = self.users[old_nick]
            del self.users[old_nick]
