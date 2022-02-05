import argparse
import json
import os
import re
import sys
import time
from decimal import Decimal
from typing import Dict, Optional

import requests
from unidecode import unidecode


from django.core.management.base import BaseCommand
from twitter_client.models import Keyword, Webhook
from twitter_client.management.utils.twitter_utils import create_headers, reset_twitter_subscription_rules
from twitter_client.management.utils.utils import log

from datetime import datetime, timezone
import ntplib

import time

import math

import requests


class ElonBot:
    def __init__(self, user: str,
                 asset: str,
                 auto_buy_delay: float,
                 auto_sell_delay: float,
                 use_image_signal: bool,
                 # margin_type: MarginType,
                 order_size: float,
                 process_tweet_text: Optional[str],
                 dry_run: bool):
        self.dry_run = dry_run
        self.user = user
        self.asset = asset
        self.auto_buy_delay = auto_buy_delay
        self.auto_sell_delay = auto_sell_delay
        self.use_image_signal = use_image_signal
        self.order_size = order_size
        self.process_tweet_text = process_tweet_text
        if not self.validate_env():
            return
        log('Starting elon.py')
        log('  User:', user)
        log('  self.asset:', self.asset)
        log('  Auto buy time:', auto_buy_delay)
        log('  Auto sell time:', auto_sell_delay)
        log('  Use image signal:', use_image_signal)
        log('  Order size:', order_size)

    @staticmethod
    def get_image_text(uri: str) -> str:
        """Detects text in the file located in Google Cloud Storage or on the Web.
        """
        if uri is None or uri == '':
            return ''
        from google.cloud import vision
        try:
            client = vision.ImageAnnotatorClient()
            image = vision.Image()
            image.source.image_uri = uri
            response = client.text_detection(image=image)
            if response.error.message:
                log('{}\nFor more info on error messages, check: '
                    'https://cloud.google.com/apis/design/errors'.format(response.error.message))
                return ''
            texts = response.text_annotations
            result = ' '.join([text.description for text in texts])
            log('Extracted from the image:', result)
            return result
        except Exception as ex:
            log('Failed to process attached image', ex)
            return ''

    def validate_env(self, verbose=False) -> bool:
        google_test = not self.use_image_signal or ('GOOGLE_APPLICATION_CREDENTIALS' in os.environ)
        if not google_test and verbose:
            log('Please, provide GOOGLE_APPLICATION_CREDENTIALS environment variable. '
                'Check https://github.com/vslaykovsky/elonbot for details')
        twitter_test = 'TWITTER_BEARER_TOKEN' in os.environ
        if not twitter_test and verbose:
            log('Please, provide TWITTER_BEARER_TOKEN environment variable. '
                'Check https://github.com/vslaykovsky/elonbot for details')
        return google_test and twitter_test # and binance_test


    def process_tweet(self, tweet_json: str):
        tweet_json = json.loads(tweet_json)
        log("Tweet received\n", json.dumps(tweet_json, indent=4, sort_keys=True), "\n")
        tweet_text = tweet_json['data']['text']
        image_url = (tweet_json.get('includes', {}).get('media', [])[0:1] or [{}])[0].get('url', '')
        image_text = ''
        if self.use_image_signal:
            image_text = ElonBot.get_image_text(image_url)
        full_text = f'{tweet_text} {image_text}'

        keywords = list(Keyword.objects.filter(enabled=True).values_list('name', 'ticker'))

        for keyword, ticker in keywords:
            t = unidecode(full_text)
            if re.search(keyword, t, flags=re.I) is not None:
                log(f'Tweet matched pattern "{keyword}", buying corresponding ticker {ticker}')

                utc_time = datetime.now(timezone.utc).replace(tzinfo=timezone.utc).timestamp()
                # utc_time = ntplib.NTPClient().request('europe.pool.ntp.org').tx_time
                # utc_time = datetime.strptime(
                #     requests.get('http://worldtimeapi.org/api/timezone/Europe/London.txt').text.split("\n")[2][10:],
                #     "%Y-%m-%dT%H:%M:%S.%f%z"
                # ).timestamp()
                tweet_time = datetime.strptime(tweet_json['data']['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()

                print(f"current system time (UTC): {utc_time}\ntweet time (UTC): {tweet_time}")

                timelapse = math.ceil(utc_time - tweet_time)

                # Get necessary API endpoint
                webhook = Webhook.objects.filter(
                    timerange_lower__lte=timelapse,
                    timerange_upper__gte=timelapse
                ).order_by("-timerange_lower")

                if webhook:
                    url = webhook[0].url
                    message = webhook[0].message
                    print(f"Range selected: {webhook[0].timerange_lower} to {webhook[0].timerange_upper}")
                else:
                    # if there is no record for this time range, run default webhook
                    url = os.environ.get("DEFAULT_WEBHOOK")
                    message = os.environ.get("DEFAULT_MESSAGE")
                    print("Range selected: Default")

                print(f"Seconds Elapsed: {timelapse}")

                # Make API call

                R = requests.post(url, data=message)

                if R.status_code != 200:
                    print(f"{R.status_code}:Failed to post '{message}' to {url}")
                else:
                    print(f"{R.status_code}:Posted '{message}' to {url}")

                return

        return None

    def run(self, timeout: int = 24 * 3600) -> None:
        if self.process_tweet_text is not None:
            self.process_tweet(self.process_tweet_text)
            return
        reset_twitter_subscription_rules(self.user)
        while True:
            try:
                params = {'expansions': 'attachments.media_keys',
                          'media.fields': 'preview_image_url,media_key,url',
                          'tweet.fields': 'attachments,entities,created_at'}
                response = requests.get(
                    "https://api.twitter.com/2/tweets/search/stream",
                    headers=create_headers(), params=params, stream=True, timeout=timeout
                )
                log('Subscribing to twitter updates. HTTP status:', response.status_code)
                if response.status_code != 200:
                    raise Exception("Cannot get stream (HTTP {}): {}".format(response.status_code, response.text))
                for response_line in response.iter_lines():
                    if response_line:
                        self.process_tweet(response_line)
            except Exception as ex:
                log(ex, 'restarting socket')
                time.sleep(60)
                continue



class Command(BaseCommand):
    help = "Send data to webhooks using Twitter signal"

    def add_arguments(self, parser):
        parser.add_argument('--user', help='Twitter user to follow. Example: elonmusk', required=True)

        parser.add_argument('--auto-buy-delay', type=float, help='Buy after auto-buy-delay seconds', default=10)
        parser.add_argument('--auto-sell-delay', type=float, help='Sell after auto-sell-delay seconds', default=60 * 5)
        parser.add_argument('--asset', default='USDT', help='asset to use to buy cryptocurrency. This is your "base" '
                                                            'cryptocurrency used to store your deposit. Reasonable options '
                                                            'are: USDT, BUSD, USDC. You must convert your deposit to one '
                                                            'of these currencies in order to use the script')
        parser.add_argument('--use-image-signal', action='store_true',
                            help='Extract text from attached twitter images using Google OCR. '
                                 'Requires correct value of GOOGLE_APPLICATION_CREDENTIALS environment variable.'
                                 'Check https://github.com/vslaykovsky/elonbot for more details',
                            default=False)
        parser.add_argument('--order-size', help='Size of orders to execute. 1.0 means 100%% of the deposit; '
                                                 '0.5 - 50%% of the deposit; 2.0 - 200%% of the deposit (marginal trade)'
                                                 '"max" - maximum borrowable amount. max corresponds to  3x deposit '
                                                 'for cross-margin account and up to 5x for isolated-margin account',
                            default='max')
        parser.add_argument('--dry-run', action='store_true', help="Don't execute orders, only show debug output",
                            default=False)
        parser.add_argument('--process-tweet',
                            help="Don't subscribe to Twitter feed, only process a single tweet provided as a json string "
                                 "(useful for testing). Example value: "
                                 "'{\"data\": {\"text\": \"Dodge coin is not what we need\"}, \"includes\": {\"media\": "
                                 "[{\"url\": \"...\"}]}}'",
                            default=None)

    def handle(self, *args, **options):
        bot = ElonBot(
            options["user"],
            options["asset"],
            options["auto_buy_delay"],
            options["auto_sell_delay"],
            options["use_image_signal"],
            options["order_size"],
            options["process_tweet"],
            options["dry_run"]
        )
        if not bot.validate_env(verbose=True):
            sys.exit(-1)
        bot.run()
