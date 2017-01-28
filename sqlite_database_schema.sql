CREATE TABLE auto_bans (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    host text NOT NULL,
    channels text NOT NULL,
    reason text NOT NULL
);

CREATE TABLE control_commands (
    id integer NOT NULL,
    command text NOT NULL
);

CREATE TABLE country_codes (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    name text,
    tld character(2) NOT NULL
);

CREATE TABLE denies (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    subject text NOT NULL
);

CREATE TABLE factoids (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    subject text NOT NULL,
    separator text NOT NULL,
    factoid text NOT NULL,
    whoadded text NOT NULL,
    whenadded datetime DEFAULT CURRENT_TIMESTAMP NOT NULL,
    groupid integer DEFAULT 0 NOT NULL
);

CREATE TABLE gui_message (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    msg_type text NOT NULL,
    msg_text text
);

CREATE TABLE ignores (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    name text NOT NULL,
    hostmask text NOT NULL,
    endtime integer DEFAULT 0 NOT NULL,
    whoignored text NOT NULL
);

CREATE TABLE subjects (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    subject text NOT NULL,
    groupid integer DEFAULT 0 NOT NULL
);

CREATE TABLE user_flags (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    userid integer NOT NULL,
    channel text NOT NULL,
    flags text NOT NULL
);

CREATE TABLE user_messages (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    sender text NOT NULL,
    receiver text NOT NULL,
    message text NOT NULL,
    send_time integer DEFAULT 0 NOT NULL,
    sender_host text NOT NULL
);

CREATE TABLE users (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    username text NOT NULL,
    userpass text NOT NULL,
    userpass_salt text NOT NULL,
    userlevel text NOT NULL,
    hosts text DEFAULT '' NOT NULL,
    autovoice text,
    autoop text
);

INSERT INTO users (username, userpass, userlevel, hosts) VALUES ('admin', '200ceb26807d6bf99fd6f4f0d1ca54d4', 'abdegmnos', '');