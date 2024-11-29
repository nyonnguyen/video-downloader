# video-downloader


## Setup

1. Install Python 3.9 or higher
2. Install the required packages by running `pip install -r requirements.txt`
3. playwright installation
    - `pip install playwright` (if not already installed)
    - `playwright install`
    - `playwright install chromium`
    - `playwright install firefox`
    - `playwright install webkit`
4. Run the script by running `python main.py <video_link>`
   For example: `python main.py https://www.youtube.com/watch?v=video_id`
5. The video will be downloaded in the `output` directory same as the script.