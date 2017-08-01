class IRCUser(object):

    def __init__(self, nick, ident, host, voice=False, op=False):
        self.nick = nick
        self.ident = ident
        self.host = host
        self.set_hostmask()
        self.is_voice = voice
        self.is_op = op
    
    def set_hostmask(self):
        self.hostmask = "%s@%s" % (self.ident, self.host)
    
    @staticmethod
    def from_userinfo(userinfo):
        nick = ""
        ident = ""
        host = ""
        
        parts = userinfo.split("!", 2)
        nick = parts[0].lstrip(":")
        
        if len(parts) > 1:
            parts = parts[1].split("@", 2)
            ident = parts[0]
            if len(parts) > 1:
                host = parts[1]
        
        return IRCUser(nick, ident, host)
    
    def to_userinfo(self):
        return "%s!%s@%s" % (self.nick, self.ident, self.host)
    
    def __str__(self):
        flags = ""
        if self.is_voice:
            flags += "v"
            
        if self.is_op:
            flags += "o"
        
        return "IRCUser: {{nick: \"{nick}\", ident: \"{ident}\", host: \"{host}\", flags: \"{flags}\"}}".format(
            nick=self.nick,
            ident=self.ident,
            host=self.host,
            flags=flags
        )
