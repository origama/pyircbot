import time
import sys
import re
from twisted.words.protocols import irc

from message_logger import MessageLogger
from karma.karma_manager import KarmaManager
from karma.karma_rate import KarmaRateLimiter

class IRCBot(irc.IRCClient):
    """Python Twisted IRC BOT. irc.IRCClient specialization."""
    
    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        try:
            logfile = open(self.factory.log_filename, "a")
        except IOError, error:
            sys.exit(error)
        self.logger = MessageLogger(logfile)
        self.logger.log(
            "[connected at %s]" %
            time.asctime(time.localtime(time.time()))
        )
        self.karma_manager = KarmaManager(self.factory.data_folder)
        self.karmrator = KarmaRateLimiter()

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        self.logger.log("[disconnected at %s]" % self.get_current_timestamp() )
        self.logger.close()

    # TODO (sentenza) ConfigManager password
    def identify(self):
        if self.password:
            self.msg('NickServ', 'RELEASE %s %s' % (self.nickname, self.password))
            self.msg('NickServ', 'RELEASE %s %s' % (self.nickname, self.password))
            self.msg('NickServ', 'IDENTIFY %s %s' % (self.nickname, self.password))

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        self.join(self.factory.channel)
        self.identify()

    def action(self, user, channel, msg):
        """This will get called when the bot sees someone do an action."""
        # e.g. /me <action>
        user = user.split('!', 1)[0]
        self.logger.log("* %s %s" % (user, msg))

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message."""
        user = user.split('!', 1)[0]
        self.logger.log("<%s> %s" % (user, msg))
        
        # Check to see if they're sending me a private message
        if channel == self.nickname:
            msg = "It isn't nice to whisper!  Play nice with the group."
            self.msg(user, msg)
            return

        # Otherwise check to see if it is a message directed at me
        n = self.nickname
        # Check if you are talking with me, like BOT: <msg> || BOT, <msg> || BOT <msg>
        if msg.startswith((n + ":", n + ",", n)):
            msg = "%s: I am BOT, do not waste your time!" % user
            self.msg(channel, msg)
            self.logger.log("<%s> %s" % (self.nickname, msg))
        elif msg.startswith('!'):
            self.evaluate_command(user, channel, msg)
        #elif msg.endswith( ("++","--") ):
        elif re.match(re.compile('\w+\+\+|\w+--'), msg):
            self.karma_update(user, channel, msg)

    def evaluate_command(self, user, channel, msg):
        # check for commands starting with bang!
        if msg.startswith('!karma'):
            msg_splits = msg.split()
            if len(msg_splits) == 1:
                fetch_user = user
            elif len(msg_splits) == 2:
                fetch_user = msg_splits[1]

            self.msg(channel, self.karma_manager.fetch_karma(fetch_user)) 

    def karma_update(self, user, channel, msg):
        """Try to modify the Karma for a given nickname"""
        receiver_nickname = msg[:-2]
        # TODO (sentenza) Check if the given nick is present on DB or if is on chan with /WHO command
        if receiver_nickname == user:
            self.msg(channel, "%s: you can't alter your own karma!" % user)
            return
        if self.karmrator.is_rate_limited(user):
            waiting_minutes = self.karmrator.user_timeout(user) / 60
            self.msg(channel, "%s: you have to wait %s min for your next karmic request!" % (user, waiting_minutes))
            return
        if msg.endswith('++'):
            self.karma_manager.update_karma(receiver_nickname, plus=True)
        if msg.endswith('--'):
            self.karma_manager.update_karma(receiver_nickname, plus=False)
        self.msg(channel, self.karma_manager.fetch_karma(receiver_nickname)) 
        self.logger.log("%s modified Karma: %s" % (user, receiver_nickname))

    def get_current_timestamp(self):
        return time.asctime(time.localtime(time.time()))
