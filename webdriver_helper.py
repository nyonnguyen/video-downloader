from playwright.sync_api import sync_playwright

class WebDriverHelper:

    def __init__(self, browser='firefox', headless=True, slow_mo=0):
        self.playwright = None
        self.browser_type = browser
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.context = None
        self.video_page_url = None
        self.resolution = None
        self.page = None

    def launch_browser(self):
        """
        Launch the specified browser using Playwright.
        """
        self.playwright = sync_playwright().start()
        if self.browser_type in ["chromium", "chrome"]:
            self.browser = self.playwright.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        elif self.browser_type == "firefox":
            self.browser = self.playwright.firefox.launch(headless=self.headless, slow_mo=self.slow_mo)
        elif self.browser_type == "webkit":
            self.browser = self.playwright.webkit.launch(headless=self.headless, slow_mo=self.slow_mo)
        else:
            raise ValueError(f"Unsupported browser type: {self.browser_type}")

        # Open a new browser context
        self.context = self.browser.new_context()

    def close_browser(self):
        """
        Close the browser and release resources.
        """
        if self.browser:
            self.browser.close()
            self.browser = None
            self.context = None

    def get_request_info(self, request_pattern, timeout=100):
        desired_request = None
        # Define a request handler to capture the specific request
        count = 0
        def handle_request(request):
            nonlocal desired_request, count
            if request_pattern in request.url:  # Replace with your condition
                desired_request = request
            else:
                count += 1

        # Attach the event listener
        self.page.on("request", handle_request)

        # Wait until the request is captured
        while desired_request is None:
            self.page.wait_for_timeout(timeout)  # Polling interval
            if count >= 10:
                self.page.reload()

        return desired_request

    def get_page(self, url):
        """
        Open a new page and navigate to the given URL.

        :param url: The URL to navigate to.
        :return: The Page object.
        """
        if not self.context:
            raise RuntimeError("Browser context is not initialized. Call launch_browser() first.")

        page = self.context.new_page()
        page.goto(url, wait_until='load')
        self.page = page
        return page

    def get_video_title(self, locator):
        return self.context.page.locator(locator).text_content()
