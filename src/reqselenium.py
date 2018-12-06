import os
from typing import Union

import requests
import tldextract
from random_useragent.random_useragent import Randomize
from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy, ProxyType

from .mixin import ReqSeleniumChrome, ReqSeleniumFirefox
from .response import ReqSeleniumResponse

r_agent = Randomize()

class Session(requests.Session):
    def __init__(self, browser='firefox', default_timeout=30, http_proxy=None, ssl_proxy=None):
        super(Session, self).__init__()
        self._desired_capabilities = None
        self._driver = None
        self.browser = browser
        self.default_timeout = default_timeout
        self.http_proxy = http_proxy
        self.ssl_proxy = ssl_proxy
        self.user_agent = r_agent.random_agent('desktop', 'windows')

        if not self.browser in ['chrome', 'firefox']:
            raise ValueError(
                'Invalid Argument: browser must be chrome or firefox, not: %s', self.browser)
        elif browser == 'chrome':
            self._driver_initializer = self._start_chromedriver
        else:
            self._driver_initializer = self._start_geckodriver

    @property
    def driver(self) -> Union[ReqSeleniumChrome, ReqSeleniumFirefox]:
        if self._driver is None:
            self._driver = self._driver_initializer()
        return self._driver

    @property
    def desired_capabilities(self):
        if self.http_proxy and self.ssl_proxy and self._desired_capabilities is None:
            proxy = Proxy()
            proxy.proxy_type = ProxyType.MANUAL
            proxy.http_proxy = self.http_proxy
            proxy.ssl_proxy = self.ssl_proxy
            if self.browser == 'firefox':
                capabilities = webdriver.DesiredCapabilities.FIREFOX
            else:
                capabilities = webdriver.DesiredCapabilities.CHROME
            proxy.add_to_capabilities(capabilities)
            self._desired_capabilities = capabilities
        return self._desired_capabilities

    def _start_chromedriver(self) -> ReqSeleniumChrome:
        return ReqSeleniumChrome(timeout=self.default_timeout, desired_capabilities=self.desired_capabilities)

    def _start_geckodriver(self) -> webdriver.Firefox:
        profile_directory = os.path.normpath(os.path.join(os.getcwd(), 'profile'))
        profile = webdriver.FirefoxProfile(profile_directory=profile_directory)
        profile.set_preference('general.useragent.override', self.user_agent)
        return ReqSeleniumFirefox(
            firefox_profile=profile,
            desired_capabilities=self.desired_capabilities,
            timeout=self.default_timeout
        )

    def transfer_session_cookies_to_driver(self, domain=None):
        """Copies the Session's cookies into the webdriver
        Using the 'domain' parameter we choose the cookies we wish to transfer, we only
        transfer the cookies which belong to that domain. The domain defaults to our last visited
        site if not provided.
        """
        if not domain and self._last_requests_url:
            domain = tldextract.extract(self._last_requests_url).registered_domain
        elif not domain and not self._last_requests_url:
            raise Exception('Trying to transfer cookies to selenium without specifying a domain '
                            'and without having visited any page in the current session')

        # Transfer cookies
        for c in [c for c in self.cookies if domain in c.domain]:
            self.driver.ensure_add_cookie({'name': c.name, 'value': c.value, 'path': c.path,
                                            'expiry': c.expires, 'domain': c.domain})

    def transfer_driver_cookies_to_session(self, copy_user_agent=True):
        if copy_user_agent:
            self.copy_user_agent_from_driver()

        for cookie in self.driver.get_cookies():
            self.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    def get(self, *args, **kwargs):
        resp = super(Session, self).get(*args, **kwargs)
        self._last_requests_url = resp.url
        return ReqSeleniumResponse(resp)

    def post(self, *args, **kwargs):
        resp = super(Session, self).post(*args, **kwargs)
        self._last_requests_url = resp.url
        return ReqSeleniumResponse(resp)

    def put(self, *args, **kwargs):
        resp = super(Session, self).put(*args, **kwargs)
        self._last_requests_url = resp.url
        return ReqSeleniumResponse(resp)

    def copy_user_agent_from_driver(self):
        """ Updates requests' session user-agent with the driver's user agent
        This method will start the browser process if its not already running.
        """
        selenium_user_agent = self.driver.execute_script("return navigator.userAgent;")
        print('#' * 32)
        print(selenium_user_agent)
        self.headers.update({"user-agent": selenium_user_agent})
