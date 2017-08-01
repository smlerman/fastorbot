import hashlib
import logging
import os
import sqlite3

from BotUser import *
from Factoid import *

class SQLiteDatabase(object):
    def __init__(self, dsn):
        self.connection = sqlite3.connect(dsn, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
    
    def close(self):
        self.connection.commit()
        self.connection.close()
    
    def fetch_factoid(self, subject, factoid_number):
        if factoid_number is not None:
            factoid_number_clause = "ORDER BY factoids.id LIMIT 1 OFFSET :factoid_number"
            params = {
                "subject": subject,
                "factoid_number": int(factoid_number)
            }
        else:
            factoid_number_clause = "ORDER BY RANDOM() LIMIT 1"
            params = {
                "subject": subject
            }
        
        self.cursor.execute("""
            SELECT
                factoids.id,
                factoids.subject,
                factoids.separator,
                factoids.factoid,
                factoids.whoadded,
                factoids.whenadded,
                factoids.groupid
            FROM
                factoids
            JOIN
                subjects
            ON
                factoids.groupid = subjects.groupid
            WHERE
                LOWER(subjects.subject) = LOWER(:subject)
            {factoid_number_clause}
        """.format(factoid_number_clause=factoid_number_clause), params)
        
        rows = self.cursor.fetchall()
        
        if len(rows) > 0:
            row = rows[0]
            asynciologger = logging.getLogger('asyncio')
            asynciologger.info("fetch_factoid " + str(row))
            
            factoid = Factoid(row["id"], row["subject"], row["separator"], row["factoid"], row["whoadded"], row["whenadded"], row["groupid"])
        else:
            if factoid_number is not None:
                factoid = Factoid(None, None, None, "There is no factoid number {factoid_number:d} for {subject}".format(factoid_number=factoid_number,subject=subject), None, None, 0)
            else:
                factoid = Factoid(None, None, None, "There are no factoids for " + subject, None, None, 0)
        
        return factoid
    
    def fetch_random_factoid(self):
        self.cursor.execute("""
            SELECT
                factoids.id,
                factoids.subject,
                factoids.separator,
                factoids.factoid,
                factoids.whoadded,
                factoids.whenadded,
                factoids.groupid
            FROM
                factoids
            ORDER BY RANDOM() LIMIT 1
        """)
        
        rows = self.cursor.fetchall()
        
        row = rows[0]
        factoid = Factoid(row["id"], row["subject"], row["separator"], row["factoid"], row["whoadded"], row["whenadded"], row["groupid"])
        
        return factoid
    
    def get_factoid(self, subject, separator, factoid):
        params = {
            "subject": subject,
            "separator": separator,
            "factoid": factoid
        }
        
        self.cursor.execute("""
            SELECT
                factoids.id,
                factoids.subject,
                factoids.separator,
                factoids.factoid,
                factoids.whoadded,
                factoids.whenadded,
                factoids.groupid
            FROM
                factoids
            WHERE
                LOWER(subject) = LOWER(:subject)
            AND
                separator = :separator
            AND
                factoid = :factoid
        """, params)
    
        rows = self.cursor.fetchall()
        
        if len(rows) > 0:
            row = rows[0]
            factoid = Factoid(row["id"], row["subject"], row["separator"], row["factoid"], row["whoadded"], row["whenadded"], row["groupid"])
        else:
            factoid = Factoid(0, None, None, "There are no factoids for " + subject, None, None, 0)
        
        return factoid
    
    def get_factoid_by_id(self, id):
        params = {
            "id": id
        }
        
        self.cursor.execute("""
            SELECT
                factoids.id,
                factoids.subject,
                factoids.separator,
                factoids.factoid,
                factoids.whoadded,
                factoids.whenadded,
                factoids.groupid
            FROM
                factoids
            WHERE
                id = :id
        """, params)
    
        rows = self.cursor.fetchall()
        
        if len(rows) > 0:
            row = rows[0]
            factoid = Factoid(row["id"], row["subject"], row["separator"], row["factoid"], row["whoadded"], row["whenadded"], row["groupid"])
        else:
            factoid = Factoid(0, None, None, "There are no factoids for " + subject, None, None, 0)
        
        return factoid
    
    def count_factoids(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            SELECT
                COUNT(*)
            FROM
                factoids
            JOIN
                subjects
            ON
                factoids.groupid = subjects.groupid
            WHERE
                LOWER(subjects.subject) = LOWER(:subject)
        """, params)
        
        rows = self.cursor.fetchall()
        
        return rows[0][0]
    
    # Get a factoid's "number", its position in the list of factoids for a subject ordered by when they were added
    # If there are 3 factoids for a subject, [X, Y, Z], the factoid number of X is 0, Y is 1, Z is 2
    def get_factoid_number(self, factoid):
        params = {
            "subject": factoid.subject,
            "factoid_id": factoid.id
        }
        
        self.cursor.execute("""
            SELECT
                COUNT(id)
            FROM
                factoids
            WHERE
                LOWER(subject) = LOWER(:subject)
            AND
                id < :factoid_id
        """, params)
        
        rows = self.cursor.fetchall()
        
        return rows[0][0]
    
    def factoid_exists(self, subject, separator, factoid):
        params = {
            "subject": subject,
            "separator": separator,
            "factoid": factoid
        }
        
        self.cursor.execute("""
            SELECT
                COUNT(*) AS factoid_exists
            FROM
                factoids
            WHERE
                LOWER(subject) = LOWER(:subject)
            AND
                separator = :separator
            AND
                factoid = :factoid
        """, params)
    
        rows = self.cursor.fetchall()
        
        if rows[0]["factoid_exists"] > 0:
            return True
        else:
            return False
    
    def add_factoid(self, subject, separator, factoid, who_added, subject_group):
        params = {
            "subject": subject,
            "separator": separator,
            "factoid": factoid,
            "whoadded": who_added,
            "groupid": subject_group
        }
        
        self.cursor.execute("""
            INSERT INTO factoids
                (subject, separator, factoid, whoadded, groupid)
            VALUES
                (:subject, :separator, :factoid, :whoadded, :groupid)
        """, params)
        
        results = self.cursor.fetchall()
        
        self.connection.commit()
        
        return self.cursor.lastrowid
    
    def delete_factoid_by_id(self, factoid_id):
        params = {
            "id": factoid_id
        }
        
        self.cursor.execute("""
            DELETE FROM
                factoids
            WHERE
                id = :id
        """, params)
        
        results = self.cursor.fetchall()
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def get_subject_group(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            SELECT
                    groupid
            FROM
                    subjects
            WHERE
                    subject = :subject
        """, params)
        
        results = self.cursor.fetchall()
        
        if len(results) > 0:
            group_id = int(results[0][0])
        else:
            group_id = None
        
        return group_id
    
    def add_subject(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            INSERT INTO subjects
                    (subject)
            VALUES
                    (:subject)
        """, params)
        
        results = self.cursor.fetchall()
        
        self.initialize_group_id(subject)
        
        self.connection.commit()
    
    def initialize_group_id(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            UPDATE
                    subjects
            SET
                    groupid = id
            WHERE
                    subject = :subject
        """, params)
        
        self.connection.commit()
    
    def add_deny(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            INSERT INTO denies
                    (subject)
            VALUES
                    (:subject)
        """, params)
        
        results = self.cursor.fetchall()
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def remove_deny(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            DELETE FROM denies
            WHERE
                subject = :subject
        """, params)
        
        results = self.cursor.fetchall()
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def is_subject_denied(self, subject):
        params = {
            "subject": subject
        }
        
        self.cursor.execute("""
            SELECT
                COUNT(*)
            FROM
                denies
            WHERE
                subject = :subject
        """, params)
        
        results = self.cursor.fetchall()
        
        rowcount = results[0][0]
        
        if rowcount == 0:
            return False
        else:
            return True
    
    def get_user_by_name(self, username):
        params = {
            "username": username
        }
        
        self.cursor.execute("""
            SELECT
                id,
                username,
                userlevel AS flags,
                hosts AS host
            FROM
                users
            WHERE
                username = :username
        """, params)
        
        rows = self.cursor.fetchall()
        
        if len(rows) > 0:
            row = rows[0]
            bot_user = BotUser(row["id"], row["username"], row["userlevel"], row["host"])
        else:
            bot_user = None
        
        return bot_user
    
    def get_user_salt(self, username):
        # Get the salt from the database
        params = {
            "username": username
        }
        
        self.cursor.execute("""
            SELECT
                userpass_salt
            FROM
                users
            WHERE
                username = :username
        """, params)
        
        rows = self.cursor.fetchall()
        
        if len(rows) == 0:
            salt = None
        else:
            salt = rows[0][0]
        
        return salt
    
    def gen_user_key(self, password, salt):
        user_key = hashlib.pbkdf2_hmac("sha512", password.encode(), bytes.fromhex(salt), 500000)
        return user_key.hex()
    
    def identify(self, username, password):
        salt = self.get_user_salt(username)
        
        if salt is None:
            return None
        
        # Generate the hash and check the database
        user_key = self.gen_user_key(password, salt)
        
        params = {
            "username": username,
            "password": user_key
        }
        
        self.cursor.execute("""
            SELECT
                id,
                username,
                userlevel AS flags,
                hosts AS hostmask
            FROM
                users
            WHERE
                username = :username
            AND
                userpass = :password
        """, params)
        
        rows = self.cursor.fetchall()
        
        if len(rows) > 0:
            row = rows[0]
            bot_user = BotUser(row[0], row[1], row[2], row[3])
        else:
            bot_user = None
        
        return bot_user
    
    def set_user_host(self, user_id, hostmask):
        params = {
            "id": user_id,
            "hostmask": hostmask
        }
        
        self.cursor.execute("""
            UPDATE
                users
            SET
                hosts = :hostmask
            WHERE
                id = :id
        """, params)
        
        self.connection.commit()
    
    def add_user(self, username, password, flags):
        # Generate a salt and hash the password
        salt = os.urandom(32).hex()
        
        user_key = self.gen_user_key(password, salt)
        
        params = {
            "username": username,
            "password": user_key,
            "salt": salt,
            "flags": flags
        }
        
        self.cursor.execute("""
            INSERT INTO users
                    (username, userpass, userpass_salt, userlevel)
            VALUES
                    (:username, :password, :salt, :flags)
        """, params)
        
        new_id = self.cursor.lastrowid
        
        self.connection.commit()
        
        return new_id
    
    def remove_user(self, username):
        params = {
            "username": username
        }
        
        self.cursor.execute("""
            DELETE FROM
                users
            WHERE
                username = :username
        """, params)
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def change_password(self, username, oldpass, newpass):
        salt = self.get_user_salt(username)
        if salt is None:
            return None
        
        old_key = self.gen_user_key(oldpass, salt)
        new_key = self.gen_user_key(newpass, salt)
        
        params = {
            "username": username,
            "oldpass": old_key,
            "newpass": new_key
        }
        
        self.cursor.execute("""
            UPDATE
                users
            SET
                userpass = :newpass
            WHERE
                username = :username
            AND
                userpass = :oldpass
        """, params)
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def get_identified_users(self):
        self.cursor.execute("""
            SELECT
                id,
                username,
                userlevel AS flags,
                hosts AS hostmask
            FROM
                users
        """)
        
        rows = self.cursor.fetchall()
        
        identified_users = list()
        
        for row in rows:
            bot_user = BotUser(row[0], row[1], row[2], row[3])
            identified_users.append(bot_user)
        
        return identified_users
    
    def add_ignore(self, nick, host, endtime, whoignored):
        
        params = {
            "nick": nick,
            "host": host,
            "endtime": endtime,
            "whoignored": whoignored
        }
        
        self.cursor.execute("""
            INSERT INTO ignores
                    (name, hostmask, endtime, whoignored)
            VALUES
                    (:nick, :host, :endtime, :whoignored)
        """, params)
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def remove_ignore(self, nick, host):
        
        params = {
            "nick": nick,
            "host": host
        }
        
        self.cursor.execute("""
            DELETE FROM
                ignores
            WHERE
                name = :nick
            AND
                hostmask = :host
        """, params)
        
        self.connection.commit()
        
        return self.cursor.rowcount
    
    def is_user_ignored(self, host):
        params = {
            "host": host
        }
        
        self.cursor.execute("""
            SELECT
                COUNT(*)
            FROM
                ignores
            WHERE
                hostmask = :host
            AND
                endtime > CURRENT_TIMESTAMP
        """, params)
        
        results = self.cursor.fetchall()
        
        rowcount = results[0][0]
        
        if rowcount == 0:
            return False
        else:
            return True
