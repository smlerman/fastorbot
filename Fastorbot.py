import asyncio
import datetime
import logging
import math
import random
import re
import signal
import sqlite3
import sys
import time
import xml.etree.ElementTree as etree

from BotCommand import *
from BotUser import *
from IRCConnection import *
from SQLiteDatabase import *

class Fastorbot(object):
    
    def __init__(self):
        tree = etree.parse("config.xml")
        self.config_tree = tree.getroot()
        
        # Bot commands
        self.commands = dict()
        self.add_command(BotCommand("that", self.command_that, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("whoadded", self.command_whoadded, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("forget", self.command_forget, BotUser.FLAG_DELFACTS))
        self.add_command(BotCommand("count", self.command_count, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("random", self.command_random, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("deny", self.command_deny, BotUser.FLAG_BOTADMIN))
        self.add_command(BotCommand("undeny", self.command_undeny, BotUser.FLAG_BOTADMIN))
        
        self.add_command(BotCommand("adduser", self.command_add_user, BotUser.FLAG_BOTADMIN))
        self.add_command(BotCommand("deluser", self.command_remove_user, BotUser.FLAG_BOTADMIN))
        self.add_command(BotCommand("identify", self.command_identify, BotUser.FLAG_NONE))
        self.add_command(BotCommand("password", self.command_password, BotUser.FLAG_NONE))
        
        self.add_command(BotCommand("ignore", self.command_ignore, BotUser.FLAG_BOTOP))
        self.add_command(BotCommand("unignore", self.command_unignore, BotUser.FLAG_BOTOP))
        
        self.add_command(BotCommand("time", self.command_time, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("lamenick", self.command_lamenick, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("roll", self.command_roll_dice, BotUser.FLAG_GETFACTS))
        
        self.add_command(BotCommand("startpoll", self.command_startpoll, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("poll", self.command_poll_choose, BotUser.FLAG_GETFACTS))
        self.add_command(BotCommand("endpoll", self.command_endpoll, BotUser.FLAG_GETFACTS))
        
        self.add_command(BotCommand("quit", self.command_quit, BotUser.FLAG_BOTADMIN))
        
        self.separators = list()
        separator_nodes = self.config_tree.findall("global/separators/separator")
        for n in separator_nodes:
            self.separators.append(n.text)
        
        self.command_separators = list()
        separator_nodes = self.config_tree.findall("global/command_separators/command_separator")
        for n in separator_nodes:
            self.command_separators.append(n.text)
        
        self.that_factoids = dict()
        self.identified_users = dict()
        self.default_bot_user = BotUser(0, "", BotUser.FLAG_GETFACTS + BotUser.FLAG_ADDFACTS + BotUser.FLAG_DELOWNFACTS, "")
        self.current_poll = None
        
        self.database_connect()
        
        identified_users = self.db.get_identified_users()
        for bot_user in identified_users:
            self.identified_users[bot_user.hostmask] = bot_user
        
        # Gracefully handle Ctrl-C
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def database_connect(self):
        # Database handle
        database_node = self.config_tree.find("global/database")
        
        if database_node.get("type") == "sqlite":
            self.db = SQLiteDatabase(database_node.get("database"))
        else:
            raise EnvironmentError("Invalid database type")
    
    def irc_connect(self):
        # Connect to the servers listed in the configuration
        server_node = self.config_tree.findall("servers")[0].findall("server")[0]
        host_node = server_node.findall("hosts/host")[0]
        self.irc_connection = IRCConnection(host_node.get("name"), host_node.get("port"), server_node.get("nick"))
        self.irc_connection.set_owner(self)
        
        self.irc_connection.add_callback("JOIN", IRCCallback(self.onjoin_factoid, {"bot": self}))
        
        self.irc_connection.connect()
        
        # connect() won't return normally, so it must be the last thing called in the constructor
    
    def handle_message(self, irc_connection, irc_message):
        asynciologger = logging.getLogger('fastorbot')
        asynciologger.info("handle_message " + str(irc_message))
        
        # Ignore messages from the bot itself
        if irc_message.source.nick == irc_connection.nick:
            return
        
        if irc_message.command == "376": #end of MOTD
            self.on_end_motd(irc_connection, irc_message)
        
        if irc_message.command == "PRIVMSG":
            command_text = BotCommand.get_command_text(irc_connection.nick, irc_message, self.command_separators)
            if command_text is not None:
                # Determine if the host is being ignored
                if self.db.is_user_ignored(irc_message.source.host):
                    return
                
                # Determine the bot user sending the command
                if irc_message.source.hostmask in self.identified_users:
                    bot_user = self.identified_users[irc_message.source.hostmask]
                else:
                    bot_user = self.default_bot_user
                
                command_parts = self.get_command(command_text)
                
                # If the message isn't a registered command, check for adding or fetching a factoid
                if command_parts is None:
                    # Check for separators
                    separators_regex = re.compile("\s({separators})\s".format(separators="|".join(self.separators)))
                    if (separators_regex.search(command_text)):
                        # Add new factoid
                        self.add_factoid(irc_connection, irc_message, command_text)
                        pass
                    else:
                        self.send_factoid(irc_connection, irc_message.response_destination, command_text)
                else:
                    command = command_parts[0]
                    #command.execute(irc_connection, irc_message, command_parts, bot_user)
                    command.execute(command_text, bot_user, irc_connection, irc_message)
    
    def add_command(self, bot_command):
        self.commands[bot_command.command] = bot_command
    
    # Returns a tuple (command, rest) if the first word in the text is a registered command
    def get_command(self, command_text):
        parts = re.split("\s+", command_text, 1)
        command = parts[0]
        
        if len(parts) > 1:
            rest = parts[1]
        else:
            rest = ""
        
        if command in self.commands:
            return (self.commands[command], rest)
        else:
            return None
    
    def send_factoid(self, irc_connection, destination, subject):
        (subject, factoid_number) = Factoid.parse_subject_and_number(subject)
        
        factoid = self.db.fetch_factoid(subject, factoid_number)
        factoid.send(irc_connection, destination)
        
        # Store factoid in That array
        if factoid.id != 0:
            self.that_factoids[destination] = factoid
    
    @staticmethod
    def onjoin_factoid(irc_connection, irc_message, arguments):
        destination = irc_message.response_destination
        bot = arguments["bot"]
        
        should_send = bot.config_tree.findall("servers/server/channels/channel[@name='%s']" % (destination))[0].get("onjoin-factoid")
        
        if should_send == "true":
            subject = irc_message.source.nick
            
            factoid_count = bot.db.count_factoids(subject)
            
            if factoid_count > 0:
                bot.send_factoid(irc_connection, destination, subject)
    
    def add_factoid(self, irc_connection, irc_message, command_text):
        separators_regex = re.compile("\s(" + "|".join(self.separators) + ")\s")
        parts = separators_regex.split(command_text, 1)
        
        subject = parts[0].strip()
        separator = parts[1].strip()
        factoid = parts[2].strip()
        
        if self.db.is_subject_denied(subject):
            irc_connection.send_message(irc_message.response_destination, "Adding factoids for " + subject + " is not allowed")
            return
        
        if subject in self.commands:
            irc_connection.send_message(irc_message.response_destination, "Adding factoids for the command " + subject + " is not allowed")
            return
        
        # Check for special start strings
        if factoid.lower().startswith("<reply>"):
            factoid = factoid[7:].lstrip()
            separator = "<reply>"
        
        if factoid.lower().startswith("<action>"):
            factoid = factoid[8:].lstrip()
            separator = "<action>"
        
        # Check if the factoid already exists
        if self.db.factoid_exists(subject, separator, factoid):
            irc_connection.send_message(irc_message.response_destination, "That factoid already exists")
            return
        
        # Check if the subject already exists, adding it if it doesn't
        subject_group = self.db.get_subject_group(subject)
        if subject_group is None:
            self.db.add_subject(subject)
            subject_group = self.db.get_subject_group(subject)
        
        who_added = irc_message.source.nick + " (" + irc_message.source.hostmask + ")"
        
        new_id = self.db.add_factoid(subject, separator, factoid, who_added, subject_group)
        irc_connection.send_message(irc_message.response_destination, "Factoid added about " + subject)
        
        # Store factoid in That array
        factoid = self.db.get_factoid_by_id(new_id)
        self.that_factoids[irc_message.response_destination] = factoid
    
    def command_that(self, irc_connection, irc_message, arguments, bot_user):
        that_factoid = self.that_factoids[irc_message.response_destination]
        
        if that_factoid is not None:
            factoid_number = self.db.get_factoid_number(that_factoid)
            irc_connection.send_message(irc_message.destination, "That is factoid number %d about %s" % (factoid_number, that_factoid.subject))
    
    def command_whoadded(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            subject = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: whoadded [subject]:[number]")
            return
        
        if subject == "that":
            that_factoid = self.that_factoids[irc_message.response_destination]
            
            if that_factoid is not None:
                factoid_number = self.db.get_factoid_number(that_factoid)
                factoid = that_factoid
        else:
            (subject, factoid_number) = Factoid.parse_subject_and_number(subject)
        
            factoid = self.db.fetch_factoid(subject, factoid_number)
            
            if factoid.id is None:
                factoid.send(irc_connection, irc_message.response_destination)
                return
        
        irc_connection.send_message(irc_message.response_destination, "Factoid number %d about \"%s\" was added by %s on %s" % (factoid_number, factoid.subject, factoid.who_added, factoid.when_added))
    
    def command_forget(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            factoid_identifier = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: forget [subject:num | that]")
            return
        
        if factoid_identifier == "that":
            factoid = self.that_factoids[irc_message.response_destination]
        else:
            factoid = None
        
        if factoid is not None:
            rows_affected = self.db.delete_factoid_by_id(factoid.id)
            
            if rows_affected == 1:
                plural = ""
            else:
                plural = "s"
            
            irc_connection.send_message(irc_message.response_destination, "Removed %d factoid%s for %s" % (rows_affected, plural, factoid.subject))
        
            self.that_factoids[irc_message.response_destination] = None
    
    def command_count(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            subject = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: count [subject]")
            return
        
        factoid_count = self.db.count_factoids(subject)
        
        if factoid_count == 1:
            plural = ""
            is_are = "is"
        else:
            plural = "s"
            is_are = "are"
        
        irc_connection.send_message(irc_message.response_destination, "There %s %d factoid%s for %s" % (is_are, factoid_count, plural, subject))
    
    def command_random(self, irc_connection, irc_message, arguments, bot_user):
        factoid = self.db.fetch_random_factoid()
        factoid.send(irc_connection, irc_message.response_destination)
        
        # Store factoid in That array
        self.that_factoids[irc_message.response_destination] = factoid
    
    def command_deny(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            subject = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: deny [subject]")
            return
        
        rowcount = self.db.add_deny(subject)
        
        if rowcount > 0:
            irc_connection.send_message(irc_message.response_destination, "Adding factoids for %s has been denied" % (subject))
        else:
            irc_connection.send_message(irc_message.response_destination, "An error occured")
    
    def command_undeny(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            subject = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: undeny [subject]")
            return
        
        rowcount = self.db.remove_deny(subject)
        
        if rowcount > 0:
            irc_connection.send_message(irc_message.response_destination, "Adding factoids for %s is now allowed" % (subject))
        else:
            irc_connection.send_message(irc_message.response_destination, "Adding factoids for %s isn't denied" % (subject))
    
    #####
    # User management commands
    #####
    
    def command_identify(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            username = irc_message.source.nick
            password = arguments[0]
        elif len(arguments) == 2:
            username = arguments[0]
            password = arguments[1]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: identify [username] password")
            return
        
        # Check the username and password
        new_user = self.db.identify(username, password)
        if new_user is not None:
                irc_connection.send_notice(irc_message.source.nick, "You have been identified")
                hostmask = irc_message.source.ident + "@" + irc_message.source.host
                self.db.set_user_host(new_user.id, hostmask)
                if hostmask not in self.identified_users:
                    self.identified_users[hostmask] = new_user
        else:
            irc_connection.send_notice(irc_message.source.nick, "Invalid username or password")
    
    def command_add_user(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            username = arguments[0]
            flags = BotUser.FLAG_NONE
        elif len(arguments) == 2:
            username = arguments[0]
            flags = arguments[1]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: adduser username [flags]")
            return
        
        # Users with FLAG_BOTADMIN can add users but can't give the new user FLAG_BOTMASTER or FLAG_BOTADMIN
        if BotUser.FLAG_BOTMASTER not in bot_user.flags:
            flags = flags.replace(BotUser.FLAG_BOTMASTER, "")
            flags = flags.replace(BotUser.FLAG_BOTADMIN, "")
        
        password = Fastorbot.generate_password()
        self.db.add_user(username, password, flags)
        irc_connection.send_notice(irc_message.source.nick, "Added user " + username + " with password " + password + " and flags " + flags)
        irc_connection.send_notice(username, "Your username has been added with flags " + flags + ". Your temporary password is " + "password")
        irc_connection.send_notice(username, "Use '/msg " + irc_connection.nick + " password oldpass newpass' to change your password")
    
    @staticmethod
    def generate_password():
        chars = list(range(ord('a'), ord('z') + 1)) + list(range(ord('A'), ord('Z') + 1)) + list(range(ord('0'), ord('9') + 1))
        
        password = ""
        for i in range(0, 12):
            password += chr(random.choice(chars))

        return password
    
    def command_remove_user(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            username = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: deluser username")
            return
        
        remove_user = self.db.get_user_by_name(username)
        
        if ((BotUser.FLAG_BOTADMIN in remove_user.flags) or (BotUser.FLAG_BOTMASTER in remove_user.flags)) and (BotUser.FLAG_BOTMASTER not in bot_user.flags):
            irc_connection.send_notice(irc_message.source.nick, "You cannot remove admins or masters")
        else:
            rowcount = self.db.remove_user(username)
            
            if rowcount > 0:
                irc_connection.send_notice(irc_message.source.nick, "Removed user " + username)
            else:
                irc_connection.send_notice(irc_message.source.nick, "No such user: " + username)
    
    def command_password(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 2:
            username = irc_message.source.nick
            oldpass = arguments[0]
            newpass = arguments[1]
        elif len(arguments) == 3:
            username = arguments[0]
            oldpass = arguments[1]
            newpass = arguments[2]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: password [username] oldpass newpass")
            return
        
        self.db.change_password(username, oldpass, newpass)
        irc_connection.send_notice(irc_message.source.nick, "Your password has been changed")
    
    #####
    # Administration commands
    #####
    def command_ignore(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 2:
            nick = arguments[0]
            try:
                duration = int(arguments[1])
            except ValueError:
                irc_connection.send_notice(irc_message.source.nick, "Invalid duration - duration must be an integer")
                return
        elif len(arguments) == 1:
            nick = arguments[0]
            duration = 10
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: ignore username [duration]")
            return
        
        host = None
        
        if nick in irc_connection.users:
            host = irc_connection.users[nick].host
            
            if host is None:
                if nick not in irc_connection.waiting_for_whois:
                    irc_connection.send_whois(nick)
                else:
                    irc_connection.waiting_for_whois[nick] += 1
                
                # Wait for the whois to return, maximum 10 seconds
                if irc_connection.waiting_for_whois[nick] < 10:
                    irc_connection.loop.call_later(1, self.command_ignore, irc_connection, irc_message, arguments, bot_user)
                    return
        else:
            # Wait for the whois to return, maximum 10 seconds
            if nick not in irc_connection.waiting_for_whois:
                irc_connection.send_whois(nick)
            else:
                irc_connection.waiting_for_whois[nick] += 1
            
            # Wait for the whois to return, maximum 10 seconds
            if irc_connection.waiting_for_whois[nick] < 10:
                irc_connection.loop.call_later(1, self.command_ignore, irc_connection, irc_message, arguments, bot_user)
                return
        
        if host is not None:
            try:
                endtime = datetime.datetime.now() + datetime.timedelta(minutes=duration)
                
                duration_temp = duration
                duration_millenia = math.floor(duration_temp / 525600000)
                duration_temp -= math.floor(duration_temp / 525600000) * 525600000
                duration_years = math.floor(duration_temp / 525600)
                duration_temp -= math.floor(duration_temp / 525600) * 525600
                duration_weeks = math.floor(duration_temp / 10080)
                duration_temp -= math.floor(duration_temp / 10080) * 10080
                duration_days = math.floor(duration_temp / 1440)
                duration_temp -= math.floor(duration_temp / 1440) * 1440
                duration_hours = math.floor(duration_temp / 60)
                duration_temp -= math.floor(duration_temp / 60) * 60
                duration_minutes = math.floor(duration_temp)
                
                duration_string = ""
                
                if duration_millenia > 1:
                    duration_string += "%d millenia " % (duration_millenia)
                elif duration_millenia > 0:
                    duration_string += "%d millenium " % (duration_millenia)
                
                if duration_years > 1:
                    duration_string += "%d years " % (duration_years)
                elif duration_years > 0:
                    duration_string += "%d year " % (duration_years)
                
                if duration_weeks > 1:
                    duration_string += "%d weeks " % (duration_weeks)
                elif duration_weeks > 0:
                    duration_string += "%d week " % (duration_weeks)
                
                if duration_days > 1:
                    duration_string += "%d days " % (duration_days)
                elif duration_days > 0:
                    duration_string += "%d day " % (duration_days)
                
                if duration_hours > 1:
                    duration_string += "%d hours " % (duration_hours)
                elif duration_hours > 0:
                    duration_string += "%d hour " % (duration_hours)
                
                if duration_minutes > 1:
                    duration_string += "%d minutes " % (duration_minutes)
                elif duration_minutes > 0:
                    duration_string += "%d minute " % (duration_minutes)
            except OverflowError:
                endtime = datetime.datetime.max
                duration_string = "a really long time."
            
            self.db.add_ignore(nick, host, endtime, irc_message.source.to_userinfo())
            
            irc_connection.send_message(irc_message.response_destination, "%s (%s) is being ignored for %s" % (nick, host, duration_string))
        else:
            irc_connection.send_message(irc_message.response_destination, "Could not determine host for %s" % (nick))
    
    def command_unignore(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            nick = arguments[0]
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: unignore username")
            return
        
        host = irc_connection.users[nick].host
        self.db.remove_ignore(nick, host)
        
        irc_connection.send_message(irc_message.response_destination, "%s (%s) is no longer being ignored" % (nick, host))
    
    #####
    # Miscellaneous commands
    #####
    
    def command_lamenick(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            nick = arguments[0]
        else:
            nick = irc_message.source.nick
        
        lameness_points = 0
        
        special_costs = {
            "69": 2000,
            "dea?th": 500,
            "dark": 500,
            "n[i1]ght": 500,
            "n[i1]te": 750,
            "fuck": 5000,
            "sh[i1]t": 5000,
            "coo[l1]": 1000,
            "kew[l1]": 1000,
            "lame": 500,
            "d(oo)|(00)d": 1500,
            "dude": 1000,
            "rool[sz]": 1500,
            "rule[sz]": 1000,
            "[l1](oo?|u)[sz]er": 1000,
            "[l1]eet": 1500,
            "e[l1]ite": 750,
            "[l1]ord": 500,
            "k[i1]ng": 500,
            "pron": 2000,
            "warez": 2500,
            "xx": 250,
            "[rkx]0": 500,
            "0[rkx]": 500,
            "[Cc][Hh][Oo][Bb][Oo]": 10**20
        }
        
        for (pattern, cost) in special_costs.items():
            matches = re.findall(pattern, nick)
            lameness_points += len(matches) * special_costs[pattern]
        
        # Punish consecutive non-alphas
        matches = re.findall("[^A-Za-z0-9]{2,}", nick)
        for match in matches:
            lameness_points += 100 * 2**len(match)
        
        # Starts with one or more digits
        match = re.search("^\d+", nick)
        if match is not None:
            lameness_points += 100 * 1.2**len(match.group(0))
        
        # Starts with non-alphanumeric
        match = re.search("^[^A-Za-z0-9]+", nick)
        if match is not None:
            lameness_points += 500 * 1.5**len(match.group(0))
        
        # Ends with non-alphanumeric
        match = re.search("[^A-Za-z0-9]+$", nick)
        if match is not None:
            lameness_points += 250 * 1.3**len(match.group(0))
        
        # Changes in character type
        num_case_shifts = len(re.findall("[a-z][A-Z]", nick))
        num_case_shifts += len(re.findall("[A-Z][a-z]", nick))
        if num_case_shifts > 1:
            lameness_points += 50 * 1.2**num_case_shifts
        
        num_alnum_shifts = len(re.findall("[a-zA-Z][0-9]", nick))
        num_alnum_shifts += len(re.findall("[0-9][a-zA-Z]", nick))
        if num_alnum_shifts > 0:
            lameness_points += 100 * 1.2**num_alnum_shifts
        
        num_symbol_shifts = len(re.findall("[a-zA-Z0-9][^a-zA-Z0-9]", nick))
        num_symbol_shifts += len(re.findall("[^a-zA-Z0-9][a-zA-Z0-9]", nick))
        if num_symbol_shifts > 0:
            lameness_points += 250 * 1.8**num_symbol_shifts
        
        matches = re.findall("[A-Z]{2,}", nick)
        for match in matches:
            lameness_points += 100 * 1.3**len(match)
        
        matches = re.findall("[^a-zA-Z0-9\(\)\[\]\{\}]", nick)
        if len(matches) > 0:
            lameness_points += 250 * 1.8**len(matches)
        
        #lameness_score = round(200 * (math.atan(lameness_points / 1000) / math.pi), 2)
        lameness_score = round(6400 * (math.atan(lameness_points / 1000) / math.pi)**6, 2)
        lameness_points = round(lameness_points)
        
        irc_connection.send_message(irc_message.response_destination, "The nickname %s scored %d lameness points, for a lameness rating of %d%%" % (nick, lameness_points, lameness_score))
    
    def command_roll_dice(self, irc_connection, irc_message, arguments, bot_user):
        if len(arguments) == 1:
            roll_string = arguments[0]
            roll_match = re.match("(\d+)d(\d+)", roll_string)
            
            if roll_match is not None:
                num_dice = int(roll_match.group(1))
                sides = int(roll_match.group(2))
            else:
                irc_connection.send_notice(irc_message.source.nick, "Incorrect roll format")
                irc_connection.send_notice(irc_message.source.nick, "Usage: roll <num>d<num>")
                return
        else:
            irc_connection.send_notice(irc_message.source.nick, "Incorrect number of parameters")
            irc_connection.send_notice(irc_message.source.nick, "Usage: roll <num>d<num>")
            return
        
        total = 0
        for i in range(0, num_dice):
            die = random.randint(1, sides)
            total += die
        
        irc_connection.send_message(irc_message.response_destination, "Rolled %dd%d for %d" % (num_dice, sides, total))
    
    def command_time(self, irc_connection, irc_message, arguments, bot_user):
        irc_connection.send_message(irc_message.response_destination, "The current time is " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def command_startpoll(self, irc_connection, irc_message, arguments, bot_user):
        if self.current_poll is not None:
            irc_connection.send_message(irc_message.response_destination, "There's already an active poll; use \'endpoll\' to end it")
            return
        
        self.current_poll = dict()
        self.current_poll["question"] = arguments[0]
        
        if len(arguments) > 1:
            poll_choices = arguments[1:]
        else:
            poll_choices = ["Yes", "No"]
        
        self.current_poll["choices"] = dict()
        for choice_number in range(1, len(poll_choices) + 1):
            self.current_poll["choices"][choice_number] = dict()
            self.current_poll["choices"][choice_number]["text"] = poll_choices[choice_number - 1]
            self.current_poll["choices"][choice_number]["votes"] = 0
        
        irc_connection.send_message(irc_message.response_destination, "Poll started for the question \"%s\"" % (self.current_poll["question"]))
        irc_connection.send_message(irc_message.response_destination, "To vote, type \"%s, poll N\" (where N is the number of your choice)" % (irc_connection.nick))
        
        for (choice_number, choice) in self.current_poll["choices"].items():
            irc_connection.send_message(irc_message.response_destination, "(%d) %s" % (choice_number, choice["text"]))
        
    def command_poll_choose(self, irc_connection, irc_message, arguments, bot_user):
        if self.current_poll is None:
            irc_connection.send_message(irc_message.response_destination, "There is no active poll; use \'startpoll\' to start one")
            return
        
        try:
            choice = int(arguments[0])
        except ValueError:
            irc_connection.send_notice(irc_message.source.nick, "Invalid choice")
            return
        
        self.current_poll["choices"][choice]["votes"] += 1
        irc_connection.send_notice(irc_message.source.nick, "Your vote has been recorded")
        
    def command_endpoll(self, irc_connection, irc_message, arguments, bot_user):
        if self.current_poll is None:
            irc_connection.send_message(irc_message.response_destination, "There is no active poll; use \'startpoll\' to start one")
            return
        
        irc_connection.send_message(irc_message.response_destination, "Results for the question \"%s\"" % (self.current_poll["question"]))
        
        for (choice_number, choice) in self.current_poll["choices"].items():
            irc_connection.send_message(irc_message.response_destination, "%d votes for (%d) %s" % (choice["votes"], choice_number, choice["text"]))
            
        self.current_poll = None
    
    #####
    # Bot control commands
    #####
    def command_quit(self, irc_connection, irc_message, arguments, bot_user):
        self.quit()
    
    def signal_handler(self, a, b):
        print("Received Ctrl-C, quitting...")
        self.quit()
    
    def quit(self):
        self.db.close()
        self.irc_connection.disconnect()
        time.sleep(5)
        sys.exit(0)
    
    def on_end_motd(self, irc_connection, irc_message):
        server_node = self.config_tree.findall("servers")[0].findall("server")[0]
        channel_nodes = server_node.findall("channels/channel")
        
        for n in channel_nodes:
            irc_connection.join_channel(n.get("name"))

bot = Fastorbot()
bot.irc_connect()
