import re
from selenium.webdriver.support.ui import WebDriverWait

class VideoElement:
    """
    The VideoElement is and HTML element for audio and video elements.
    The supported properties, methods and events are documented at:
        https://www.w3schools.com/tags/ref_av_dom.asp
    This element is also a WebElement and supported selenium's functions

    Examples for how to use:
        Definition (where video_player_element is <video> webElement:
            video = VideoElement(video_player_element)
        Video Method:
            video.do_play()  # add prefix 'do_' before method name
            video.set_currentTime(20) # 'set_' property with param
        Video Property:
            video.get_duration() # 'get_' property value
        Selenium:
            video.is_enabled()
            video.is_displayed()

    This element also supports checking playback functions:
        video.check_playing_to_end()
    """

    STATE_READY = 4
    NETWORK_LOADING = 2

    def __init__(self, driver, element):
        self.driver = driver
        self.el = element

    def __getattr__(self, item):
        def wrapper(*args, **kw):
            try:
                func = eval("self.el.%s" % item)(*args, **kw)
                callable(func)
                return func
            except AttributeError:
                js = "return arguments[0].%s"
                if item.startswith('do_'):
                    js = js % re.sub('do_', '', item) + '()'
                elif item.startswith('set_'):
                    js = (js + "= %s") % (re.sub('set_', '', item), args[0])
                elif item.startswith('get_'):
                    js = js % re.sub('get_', '', item)
                else:
                    raise Exception(f"Method {item} not found")
            return self.driver.execute_script(js, self.el)
        return wrapper

    def is_ready(self):
        return self.get_readyState() == self.STATE_READY

    def is_network_loading(self):
        return self.get_networkState() == self.NETWORK_LOADING

    def wait_until_ready(self, timeout=60):
        try:
            # Wait until the condition self.is_ready() is met
            WebDriverWait(self.driver, timeout).until(lambda driver: self.is_ready())
            print("Video is ready")
        except Exception as e:
            raise TimeoutError(f"Timeout after {timeout} seconds waiting for video to be ready. Error: {str(e)}")

    def play(self):
        self.wait_until_ready()
        self.do_play()

    def pause(self):
        self.do_pause()
