import time
from functools import partial

import tldextract
from parsel.selector import Selector
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class DriverMixin(object):
    """Provides helper methods to our driver classes
    This is a temporary solution.
    When Chrome headless is finally stable, and we therefore stop using Phantomjs,
    it will make sense to stop having this as a mixin and just add these methods to
    the RequestiumChrome class, as it will be our only driver class.
    (We plan to stop supporting Phantomjs because the developer stated he won't be
    maintaining the project any longer)
    """

    def __init__(self, *args, **kwargs):
        self.default_timeout = kwargs['timeout']
        del kwargs['desired_capabilities']
        super(DriverMixin, self).__init__(*args, **kwargs)

    def ensure_add_cookie(self, cookie, override_domain=None):
        """Ensures a cookie gets added to the driver
        Selenium needs the driver to be currently at the domain of the cookie
        before allowing you to add it, so we need to get through this limitation.
        The cookie parameter is a dict which must contain the keys (name, value, domain) and
        may contain the keys (path, expiry).
        We first check that we aren't currently in the cookie's domain, if we aren't, we GET
        the cookie's domain and then add the cookies to the driver.
        We can override the cookie's domain using 'override_domain'. The use for this
        parameter is that sometimes GETting the cookie's domain redirects you to a different
        sub domain, and therefore adding the cookie fails. So sometimes the user may
        need to override the cookie's domain to a less strict one, Eg.: 'site.com' instead of
        'home.site.com', in this way even if the site redirects us to a subdomain, the cookie will
        stick. If you set the domain to '', the cookie gets added with whatever domain the browser
        is currently at (at least in chrome it does), so this ensures the cookie gets added.
        It also retries adding the cookie with a more permissive domain if it fails in the first
        try, and raises an exception if that fails. The standard selenium behaviour in this case
        was to not do anything, which was very hard to debug.
        """
        if override_domain:
            cookie['domain'] = override_domain

        cookie_domain = cookie['domain'] if cookie['domain'][0] != '.' else cookie['domain'][1:]
        try:
            browser_domain = tldextract.extract(self.current_url).fqdn
        except AttributeError:
            browser_domain = ''
        if cookie_domain not in browser_domain:
            # TODO Check if hardcoding 'http' causes trouble
            # TODO Consider using a new proxy for this next request to not cause an anomalous
            #      request. This way their server sees our ip address as continuously having the
            #      same cookies and not have a request mid-session with no cookies
            self.get('http://' + cookie_domain)

        # Fixes phantomjs bug, all domains must start with a period
        # if self.name == "phantomjs": cookie['domain'] = '.' + cookie['domain']
        self.add_cookie(cookie)

        # If we fail adding the cookie, retry with a more permissive domain
        if not self.is_cookie_in_driver(cookie):
            cookie['domain'] = tldextract.extract(cookie['domain']).registered_domain
            self.add_cookie(cookie)
            if not self.is_cookie_in_driver(cookie):
                raise WebDriverException(
                    "Couldn't add the following cookie to the webdriver\n{}\n".format(cookie)
                )

    def is_cookie_in_driver(self, cookie):
        """We check that the cookie is correctly added to the driver
        We only compare name, value and domain, as the rest can produce false negatives.
        We are a bit lenient when comparing domains.
        """
        for driver_cookie in self.get_cookies():
            if (cookie['name'] == driver_cookie['name'] and
                cookie['value'] == driver_cookie['value'] and
                (cookie['domain'] == driver_cookie['domain'] or
                 '.' + cookie['domain'] == driver_cookie['domain'])):
                return True
        return False

    def ensure_element_by_id(self, selector, state="present", timeout=None):
        return self.ensure_element('id', selector, state, timeout)

    def ensure_element_by_name(self, selector, state="present", timeout=None):
        return self.ensure_element('name', selector, state, timeout)

    def ensure_element_by_xpath(self, selector, state="present", timeout=None):
        return self.ensure_element('xpath', selector, state, timeout)

    def ensure_element_by_link_text(self, selector, state="present", timeout=None):
        return self.ensure_element('link_text', selector, state, timeout)

    def ensure_element_by_partial_link_text(self, selector, state="present", timeout=None):
        return self.ensure_element('partial_link_text', selector, state, timeout)

    def ensure_element_by_tag_name(self, selector, state="present", timeout=None):
        return self.ensure_element('tag_name', selector, state, timeout)

    def ensure_element_by_class_name(self, selector, state="present", timeout=None):
        return self.ensure_element('class_name', selector, state, timeout)

    def ensure_element_by_css_selector(self, selector, state="present", timeout=None):
        return self.ensure_element('css_selector', selector, state, timeout)

    def ensure_element(self, locator, selector, state="present", timeout=None):
        """This method allows us to wait till an element appears or disappears in the browser
        The webdriver runs in parallel with our scripts, so we must wait for it everytime it
        runs javascript. Selenium automatically waits till a page loads when GETing it,
        but it doesn't do this when it runs javascript and makes AJAX requests.
        So we must explicitly wait in that case.
        The 'locator' argument defines what strategy we use to search for the element.
        The 'state' argument allows us to chose between waiting for the element to be visible,
        clickable, present, or invisible. Presence is more inclusive, but sometimes we want to
        know if the element is visible. Careful, its not always intuitive what Selenium considers
        to be a visible element. We can also wait for it to be clickable, although this method
        is a bit buggy in selenium, an element can be 'clickable' according to selenium and
        still fail when we try to click it.
        More info at: http://selenium-python.readthedocs.io/waits.html
        """
        locators = {'id': By.ID,
                    'name': By.NAME,
                    'xpath': By.XPATH,
                    'link_text': By.LINK_TEXT,
                    'partial_link_text': By.PARTIAL_LINK_TEXT,
                    'tag_name': By.TAG_NAME,
                    'class_name': By.CLASS_NAME,
                    'css_selector': By.CSS_SELECTOR}
        locator = locators[locator]
        if not timeout: timeout = self.default_timeout

        if state == 'visible':
            element = WebDriverWait(self, timeout).until(
                EC.visibility_of_element_located((locator, selector))
            )
        elif state == 'clickable':
            element = WebDriverWait(self, timeout).until(
                EC.element_to_be_clickable((locator, selector))
            )
        elif state == 'present':
            element = WebDriverWait(self, timeout).until(
                EC.presence_of_element_located((locator, selector))
            )
        elif state == 'invisible':
            WebDriverWait(self, timeout).until(
                EC.invisibility_of_element_located((locator, selector))
            )
            element = None
        else:
            raise ValueError(
                "The 'state' argument must be 'visible', 'clickable', 'present' "
                "or 'invisible', not '{}'".format(state)
            )

        # We add this method to our element to provide a more robust click. Chromedriver
        # sometimes needs some time before it can click an item, specially if it needs to
        # scroll into it first. This method ensures clicks don't fail because of this.
        if element:
            element.ensure_click = partial(_ensure_click, element)
        return element

    @property
    def selector(self):
        """Returns the current state of the browser in a Selector
        We re-parse the site on each xpath, css, re call because we are running a web browser
        and the site may change between calls"""
        return Selector(text=self.page_source)

    def xpath(self, *args, **kwargs):
        return self.selector.xpath(*args, **kwargs)

    def css(self, *args, **kwargs):
        return self.selector.css(*args, **kwargs)

    def re(self, *args, **kwargs):
        return self.selector.re(*args, **kwargs)

    def re_first(self, *args, **kwargs):
        return self.selector.re_first(*args, **kwargs)


def _ensure_click(self):
    """Ensures a click gets made, because Selenium can be a bit buggy about clicks
    This method gets added to the selenium element returned in '__ensure_element_by_xpath'.
    We should probably add it to more selenium methods, such as all the 'find**' methods though.
    I wrote this method out of frustration with chromedriver and its problems with clicking
    items that need to be scrolled to in order to be clickable. In '__ensure_element_by_xpath' we
    scroll to the item before returning it, but chrome has some problems if it doesn't get some
    time to scroll to the item. This method ensures chromes gets enough time to scroll to the item
    before clicking it. I tried SEVERAL more 'correct' methods to get around this, but none of them
    worked 100% of the time (waiting for the element to be 'clickable' does not work).
    """

    # We ensure the element is scrolled into the middle of the viewport to ensure that
    # it is clickable. There are two main ways an element may not be clickable:
    #   - It is outside of the viewport
    #   - It is under a banner or toolbar
    # This script solves both cases
    script = ("var viewPortHeight = Math.max("
              "document.documentElement.clientHeight, window.innerHeight || 0);"
              "var elementTop = arguments[0].getBoundingClientRect().top;"
              "window.scrollBy(0, elementTop-(viewPortHeight/2));")
    self.parent.execute_script(script, self)  # parent = the webdriver

    for _ in range(10):
        try:
            self.click()
            return
        except WebDriverException as e:
            exception_message = str(e)
            time.sleep(0.2)
    raise WebDriverException(
        "Couldn't click item after trying 10 times, got error message: \n{}".format(
            exception_message
        )
    )


class ReqSeleniumChrome(DriverMixin, webdriver.Chrome):
    pass


class ReqSeleniumFirefox(DriverMixin, webdriver.Firefox):
    pass
