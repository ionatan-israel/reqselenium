from os.path import dirname, getsize, join, realpath

import selenium.webdriver.support.ui as ui

from src.reqselenium import Session

out_img = join(dirname(realpath(__file__)), "screenshot.png")
s = Session(browser='firefox', http_proxy='127.0.0.1:8123', ssl_proxy='127.0.0.1:8123')
s.driver.get('http://www.whatsmyrealip.com/')
wait = ui.WebDriverWait(s.driver, 10)
s.driver.get_screenshot_as_file(out_img)
print("Screenshot is saved as %s (%s bytes)" % (out_img, getsize(out_img)))
