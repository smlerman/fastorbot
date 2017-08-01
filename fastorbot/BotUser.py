class BotUser(object):
    FLAG_NONE = ""
    FLAG_GETFACTS = "g"
    FLAG_ADDFACTS = "a"
    FLAG_DELOWNFACTS = "e"
    FLAG_DELFACTS = "d"
    FLAG_SENDMESSAGES = "s"
    FLAG_CHANOP = "o"
    FLAG_BOTOP = "b"
    FLAG_BOTADMIN = "n"
    FLAG_BOTMASTER = "m"

    ALLFLAGS = "abdegmnos"
		
    def __init__(self, id, username, flags, hostmask):
        self.id = id
        self.username = username
        self.flags = flags
        self.hostmask = hostmask
