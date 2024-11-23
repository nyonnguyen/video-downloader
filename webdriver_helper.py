from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from seleniumwire import webdriver  # Use selenium-wire's webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
import time
from datetime import datetime


def locator_parser(locator):
    parse_locator = locator.split(':')
    by = parse_locator[0]
    locator_str = parse_locator[1]
    if by == 'xpath':
        return By.XPATH, locator_str
    elif by == 'id':
        return By.ID, locator_str
    elif by == 'class':
        return By.CLASS_NAME, locator_str
    elif by == 'name':
        return By.NAME, locator_str
    elif by == 'tag':
        return By.TAG_NAME, locator_str
    elif by == 'css':
        return By.CSS_SELECTOR, locator_str
    else:
        raise Exception(f"Invalid locator type: {locator}")


class WebDriverHelper:

    def __init__(self, browser='firefox'):
        if browser == 'firefox':
            options = webdriver.FirefoxOptions()
            options.add_argument("--headless")  # Optionally run in headless mode
            options.set_preference("media.volume_scale", "0.0")
            self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
        else:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--mute-audio")
            self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        self.video_page_url = None
        self.resolution = None

    def quit(self):
        self.driver.quit()

    def get_requests(self):
        return self.driver.requests

    def wait_until_element_found(self, by, value, timeout=10):
        """
        Waits until the element specified by `by` and `value` is found within the given `timeout`.

        :param driver: Selenium WebDriver instance
        :param by: By method to locate the element (e.g., By.TAG_NAME)
        :param value: Value to locate the element (e.g., 'video')
        :param timeout: Maximum wait time in seconds (default is 10 seconds)
        :return: WebElement if found, None if not found within the timeout
        """
        try:
            # Wait for the element to be present
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception as e:
            print(f"Element not found within {timeout} seconds. Error: {e}")
            return None

    def reload_page(self):
        self.load_video_page(self.video_page_url, resolution=self.resolution, max_retries=2, timeout=30)

    def load_video_page(self, video_page_url, resolution="auto", max_retries=3, timeout=30):
        """
        Tries to load the video page and checks if the page is loaded successfully.
        If not, it retries loading the page up to `max_retries` times before raising an error.

        :param resolution: The video resolution to set (default is auto) auto | 360p | 480p | 720p | 1080p
        :param video_page_url: The URL of the video page to load
        :param max_retries: Maximum number of retries if page fails to load (default is 3)
        :param timeout: Maximum wait time for page load (default is 30 seconds)
        :return: None
        """
        self.video_page_url = video_page_url
        self.resolution = resolution

        print(f"Loading page: {video_page_url}")
        retries = 0
        while retries < max_retries:
            try:
                # Attempt to load the video page
                self.driver.get(video_page_url)

                # Optionally, wait for some condition that confirms the page is loaded
                if self.wait_until_element_found(By.TAG_NAME, 'video', timeout=timeout):
                    print(f"Page loaded successfully: {video_page_url}")

                # This trick to set video resolution by setting driver local storage
                # This works for ixigua.com video site
                # TODO: Test and define the function for this trick
                # Set video resolution by set driver local storage xgplayer_pc_localSettings-all
                # Get the current date and time and format it
                date = datetime.now().strftime("%Y/%m/%d")
                key = "xgplayer_pc_localSettings-all"
                resolution_value = '{"definition":"%s","definitionSetDate":"%s"}' % (resolution, date)
                self.driver.execute_script("window.localStorage.setItem('%s', '%s');" % (key, resolution_value))

                # Attempt to load the video page
                self.driver.get(video_page_url)

                # Optionally, wait for some condition that confirms the page is loaded
                if self.wait_until_element_found(By.TAG_NAME, 'video', timeout=timeout):
                    print(f"Reload page again successfully: {video_page_url}")
                    return  # Page is successfully loaded

            except (TimeoutException, WebDriverException) as e:
                retries += 1
                print(f"Attempt {retries}/{max_retries} failed: {str(e)}. Retrying...")
                time.sleep(3)  # Optional: wait before retrying

        raise Exception(f"Failed to load page {video_page_url} after {max_retries} attempts.")

    def get_video_title(self, by, locator):
        ele = self.wait_until_element_found(by, locator)
        return ele.get_attribute('textContent') if ele else ''
