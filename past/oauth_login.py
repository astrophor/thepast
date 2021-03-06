# -*- coding: utf-8 -*-

import time
from warnings import warn
import urllib
import cgi

import tweepy
from tweepy.error import TweepError

import config
from past.utils.escape import json_encode, json_decode
from past.utils import httplib2_request
from past.model.data import SinaWeiboUser, DoubanUser, TwitterUser

class OAuthLoginError(Exception):
    def __init__(self, msg):
        if isinstance(msg, TweepError):
            self.msg = "%s:%s" %(msg.reason, msg.response) 
        else:
            self.msg = msg

    def __str__(self):
        return "%s" % (self.msg,)
    __repr__ = __str__

class TwitterOAuthLogin(object):
    def __init__(self, apikey, apikey_secret, redirect_uri):
        self.consumer_key = apikey
        self.consumer_secret = apikey_secret
        self.callback = redirect_uri
        self.auth = self._get_auth()

    def _get_auth(self):
        return tweepy.OAuthHandler(self.consumer_key, self.consumer_secret, self.callback)

    def get_login_uri(self):
        return self.auth.get_authorization_url()

    def get_access_token(self, verifier=None):
        self.auth.get_access_token(verifier)
        print self.auth.access_token.key
        t = {"access_token":self.auth.access_token.key, 
            "access_token_secret": self.auth.access_token.secret,}
        return t
    
    def save_request_token_to_session(self, session_):
        t = {"key": self.auth.request_token.key,
            "secret": self.auth.request_token.secret,}
        session_['request_token'] = json_encode(t)

    def get_request_token_from_session(self, session_, delete=True):
        t = session_.get("request_token")
        token = json_decode(t) if t else {}
        if delete:
            self.delete_request_token_from_session(session_)
        return token

    def delete_request_token_from_session(self, session_):
        session_.pop("request_token", None)

    def api(self, access_token=None, access_token_secret=None):
        if access_token and access_token_secret:
            self.auth.set_access_token(access_token, access_token_secret)

        return tweepy.API(self.auth, parser=tweepy.parsers.JSONParser())

    def get_user_info(self, api):
        user = api.me()
        return TwitterUser(user)

class OAuth2Login(object):
    version = '2.0'

    authorize_uri       = ''
    access_token_uri    = ''
    
    def __init__(self, apikey, apikey_secret, redirect_uri, 
            scope=None, state=None, display=None):

        self.apikey = apikey
        self.apikey_secret = apikey_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.state = state
        self.display = display

    def get_login_uri(self):
        qs = {
            'client_id'     : self.apikey,
            'response_type' : 'code',
            'redirect_uri'  : self.redirect_uri,
        }
        if self.display:
            qs['display'] = self.display
        if self.scope:
            qs['scope'] = self.scope
        if self.state:
            qs['state'] = self.state
            
        qs = urllib.urlencode(qs)
        uri = '%s?%s' %(self.authorize_uri, qs)

        return uri

    def get_access_token(self, authorization_code):
        qs = {
            "client_id": self.apikey,
            "client_secret": self.apikey_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "code": authorization_code,
        }
        qs = urllib.urlencode(qs)
        resp, content = httplib2_request(self.access_token_uri, "POST", body=qs)
        print '--------resp, content', content, type(content)
        if resp.status != 200:
            raise OAuthLoginError('get_access_token, status=%s:reason=%s:content=%s' \
                    %(resp.status, resp.reason, content))
        return json_decode(content)


class DoubanLogin(OAuth2Login):
    provider = config.OPENID_DOUBAN   

    authorize_uri = 'https://www.douban.com/service/auth2/auth'
    access_token_uri = 'https://www.douban.com/service/auth2/token' 
    user_info_uri = 'https://api.douban.com/people/@me'

    def __init__(self, apikey, apikey_secret, redirect_uri, 
            scope=None, state=None, display=None):
        super(DoubanLogin, self).__init__(apikey, apikey_secret, redirect_uri, scope)

    def get_user_info(self, access_token, uid=None):
        headers = {"Authorization": "Bearer %s" % access_token}     
        qs = {
            "alt":"json",
        }
        uri = "%s?%s" %(self.user_info_uri, urllib.urlencode(qs))
        resp, content = httplib2_request(uri, "GET", 
                headers = headers)
        print '--------resp, content', content, type(content)
        if resp.status != 200:
            raise OAuthLoginError('get_access_token, status=%s:reason=%s:content=%s' \
                    %(resp.status, resp.reason, content))
        r = json_decode(content)
        user_info = DoubanUser(r)

        return user_info
        
class SinaLogin(OAuth2Login):
    provider = config.OPENID_SINA

    authorize_uri = 'https://api.weibo.com/oauth2/authorize'
    access_token_uri = 'https://api.weibo.com/oauth2/access_token' 
    user_info_uri = 'https://api.weibo.com/2/users/show.json' 

    def __init__(self, apikey, apikey_secret, redirect_uri):
        super(SinaLogin, self).__init__(apikey, apikey_secret, redirect_uri)

    def get_user_info(self, access_token, uid):
        qs = {
            "source": self.apikey,
            "access_token": access_token,
            "uid": uid,
        }
        qs = urllib.urlencode(qs)
        uri = "%s?%s" % (self.user_info_uri, qs)
        resp, content = httplib2_request(uri, "GET")
        print '--------resp, content', content, type(content)
        if resp.status != 200:
            raise OAuthLoginError('get_access_token, status=%s:reason=%s:content=%s' \
                    %(resp.status, resp.reason, content))
        r = json_decode(content)
        user = SinaWeiboUser(r)

        return user

class QQLogin(OAuth2Login):
    provider = config.OPENID_QQ

    authorize_uri       = 'https://graph.qq.com/oauth2.0/authorize'
    access_token_uri    = 'https://graph.qq.com/oauth2.0/token' 
    openid_uri          = 'https://graph.qq.com/oauth2.0/me'
    user_info_uri       = 'https://graph.qq.com/user/get_user_info'

    def __init__(self, apikey, apikey_secret, redirect_uri, \
        scope = 'get_user_info', display = '', state = ''):

        super(QQLogin, self).__init__(apikey, apikey_secret, redirect_uri, scope)

    def get_access_token(self, authorization_code):
        qs = {
            'client_id'     : self.apikey,
            'client_secret' : self.apikey_secret,
            'redirect_uri'  : self.redirect_uri,
            'grant_type'    : 'authorization_code',
            'code'          : authorization_code,
        }
        qs = urllib.urlencode(qs)
        uri = '%s?%s' %(self.access_token_uri, qs)
        resp, content = httplib2_request(uri)

        if resp.status != 200:
            raise OAuthLoginError('[QQLogin.get_access_token]msg=http_request_fail:status=%s:reason=%s' %(resp.status, resp.reason))

        r = _parse_qq_response(content)
        token = r and r.get('access_token')
        if not token:
            raise OAuthLoginError('[QQLogin.get_access_token]msg=get_access_token_fail:reason=%s' %content)
        return token

    def get_openid(self, access_token):
        uri = '%s?access_token=%s' %(self.openid_uri, access_token)
        resp, content = httplib2_request(uri)

        if resp.status != 200:
            raise OAuthLoginError('[QQLogin.get_openid]msg=http_request_fail:status=%s:reason=%s' %(resp.status, resp.reason))

        r = _parse_qq_response(content)
        openid = r and r.get('openid')
        if not openid:
            raise OAuthLoginError('[QQLogin.get_openid]msg=get_openid_fail:reason=%s' %content)
        return openid

    def get_user_info(self, access_token, openid):
        qs = {
            'access_token' : access_token,
            'oauth_consumer_key' : self.apikey,
            'openid' : openid,
        }
        qs = urllib.urlencode(qs)
        uri = '%s?%s' %(self.user_info_uri, qs)
        resp, content = httplib2_request(uri)

        if resp.status != 200:
            raise OAuthLoginError('[QQLogin.get_user_info]msg=http_request_fail:status=%s:reason=%s' %(resp.status, resp.reason))

        r = _parse_qq_response(content)
        if not r:
            raise OAuthLoginError('[QQLogin.get_user_info]msg=get_user_info_fail:reason=%s' %content)
        return r

def _parse_qq_response(content):
    if not content:
        return {}
    if content.startswith('callback'):
        l = content.find('(')
        r = content.find(')')
        c = content[l+1:r]
        return json_decode(c) if c else {}
    elif content.startswith('{'):
        return json_decode(content)
    elif content.find('=')>0:
        qs = cgi.parse_qs(content)
        for x in qs:
            qs[x] = qs[x][0]
        return qs
    else:
        return {}
