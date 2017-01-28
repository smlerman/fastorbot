import re
import shlex

class BotCommand(object):
    def __init__(self, command, function, required_flag):
        self.command = command
        self.function = function
        self.required_flag = required_flag
        
    def execute(self, command_text, bot_user, irc_connection, irc_message):
        if (self.required_flag is None) or (self.required_flag in bot_user.flags):
            arguments = BotCommand.get_command_arguments(command_text)
            self.function(irc_connection, irc_message, arguments, bot_user)
        else:
            irc_connection.send_message(irc_message.response_destination, "I don't have to listen to you")
    
    @staticmethod
    def get_command_text(bot_nick, irc_message, command_separators):
        command_pattern = re.compile("^{bot_nick}\s*({command_separators})\s*".format(bot_nick=bot_nick,command_separators="|".join(command_separators)))
        
        # Check if the message begins with the bot's nick or if the message was sent as a private message to the bot
        if command_pattern.search(irc_message.rest) or (irc_message.destination == bot_nick):
            command_text = command_pattern.sub("", irc_message.rest)
        else:
            command_text = None
        
        return command_text
    
    @staticmethod
    def get_command_arguments(command_text):
        # Split the command string on spaces
        #parts = re.split("\s+", command_text)
        parts = shlex.split(command_text)
        
        # Remove the command from the beginning of the list
        parts.pop(0)
        
        return parts
