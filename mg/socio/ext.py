from mg import *
from mg.socio import ForumTopic
import twitter

class Twitter(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-twitter.settings", self.settings)
        self.rhook("forum.topic-menu", self.forum_topic_menu)
        self.rhook("ext-forum.tweet", self.forum_tweet)

    def menu_socio_index(self, menu):
        req = self.req()
        if req.has_access("socio.twitter-settings"):
            menu.append({ "id": "twitter/settings", "text": self._("Twitter settings"), "leaf": True })

    def permissions_list(self, perms):
        perms.append({"id": "socio.twitter", "name": self._("Twitter posting")})
        perms.append({"id": "socio.twitter-settings", "name": self._("Twitter configuration")})

    def settings(self):
        req = self.req()
        api_key = req.param("api_key")
        consumer_key = req.param("consumer_key")
        oauth_token = req.param("oauth_token")
        oauth_token_secret = req.param("oauth_token_secret")
        config = self.app().config
        if req.param("ok"):
            config.set("twitter.api_key", api_key)
            config.set("twitter.consumer_key", consumer_key)
            config.set("twitter.oauth_token", oauth_token)
            config.set("twitter.oauth_token_secret", oauth_token_secret)
            config.store()
            self.call("admin.response", self._("Twitter credentials saved"), {})
        else:
            api_key = config.get("twitter.api_key")
            consumer_key = config.get("twitter.consumer_key")
            oauth_token = config.get("twitter.oauth_token")
            oauth_token_secret = config.get("twitter.oauth_token_secret")
        fields = []
        fields.append({"label": "API key", "name": "api_key", "value": api_key})
        fields.append({"label": "Consumer key", "name": "consumer_key", "value": consumer_key})
        fields.append({"label": "Access Token", "name": "oauth_token", "value": oauth_token})
        fields.append({"label": "Access Token Secret", "name": "oauth_token_secret", "value": oauth_token_secret})
        self.call("admin.advice", {"title": self._("Registering application"), "content": self._('Go to the <a href="http://dev.twitter.com/apps" target="_blank">Twitter Applications</a> page and follow instructions there to get your authentication credentials. Register as "Desktop application".')})
        self.call("admin.form", fields=fields)

    def forum_topic_menu(self, topic, menu):
        req = self.req()
        if req.has_access("socio.twitter"):
            redirect = urlencode(req.uri())
            menu.append({"href": "/forum/tweet/%s?redirect=%s" % (topic.uuid, redirect), "html": self._("tweet"), "right": True})

    def forum_tweet(self):
        self.call("session.require_permission", "socio.twitter")
        req = self.req()
        user_uuid = req.user()
        try:
            topic = self.obj(ForumTopic, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        api_key = self.conf("twitter.api_key")
        consumer_key = self.conf("twitter.consumer_key")
        oauth_token = self.conf("twitter.oauth_token")
        oauth_token_secret = self.conf("twitter.oauth_token_secret")
        api = twitter.Api(consumer_key=api_key, consumer_secret=consumer_key, access_token=oauth_token, access_token_secret=oauth_token_secret)
        print api.VerifyCredentials()
        redirect = req.param("redirect")
        if redirect is None or redirect == "":
            redirect = "/forum/topic/%s" % topic.uuid
        self.call("web.redirect", redirect)
