import time
from datetime import datetime

from instagram_helper import InstagramAPICycler

from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError

from secrets import TOKENS

cycler = InstagramAPICycler(TOKENS)
for i in range(10000):
    api = cycler.api