import re

class Factoid(object):
    def __init__(self, id, subject, separator, fact, who_added, when_added, group_id):
        self.id = id
        self.subject = subject
        self.separator = separator
        self.fact = fact
        self.who_added = who_added
        self.when_added = when_added
        self.group_id = group_id
    
    def send(self, connection, destination):
        if self.id is None:
            connection.send_message(destination, self.fact)
        elif self.separator.lower() == "<reply>":
            connection.send_message(destination, self.fact)
        elif self.separator.lower() == "<action>":
            connection.send_action(destination, self.fact)
        else:
            message_text = self.subject + " " + self.separator + " " + self.fact
            connection.send_message(destination, message_text)
    
    @staticmethod
    def parse_subject_and_number(text):
        factoid_number_regex = re.compile(":(\d+)$")
        factoid_number_matches = factoid_number_regex.search(text)
        
        if factoid_number_matches is not None:
            subject = factoid_number_regex.sub("", text)
            factoid_number = int(factoid_number_matches.group(1))
        else:
            subject = text
            factoid_number = None
        
        return (subject, factoid_number)
    
    def __str__(self):
        return "Factoid: {{id: \"{id}\", subject: \"{subject}\", separator: \"{separator}\", fact: \"{fact}\"}}".format(
            id=self.id,
            subject=self.subject,
            separator=self.separator,
            fact=self.fact
        )
