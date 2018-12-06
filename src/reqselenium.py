import requests
from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy, ProxyType

from .mixin import ReqSeleniumFirefox
from .response import ReqSeleniumResponse


class Session(requests.Session):
    def __init__(self, browser, default_timeout=10, http_proxy=None, ssl_proxy=None):
        super(Session, self).__init__()
        self._desired_capabilities = None
        self._driver = None
        self.browser = browser
        self.default_timeout = default_timeout
        self.http_proxy = http_proxy
        self.ssl_proxy = ssl_proxy

        if not self.browser in ['chrome', 'firefox']:
            raise ValueError(
                'Invalid Argument: browser must be chrome or firefox, not: %s', self.browser)
        elif browser == 'chrome':
            self._driver_initializer = self._start_chromedriver
        else:
            self._driver_initializer = self._start_geckodriver

    @property
    def driver(self):
        if self._driver is None:
            self._driver = self._driver_initializer()
        return self._driver

    def _start_chromedriver(self):
        return webdriver.Chrome(desired_capabilities=self.desired_capabilities)

    def _start_geckodriver(self):
        return ReqSeleniumFirefox(default_timeout=self.default_timeout, desired_capabilities=self.desired_capabilities)

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
