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
from twitter_client.models import Keyword, Webhook, Follow
from twitter_client.management.utils.twitter_utils import create_headers, reset_twitter_subscription_rules
from twitter_client.management.utils.utils import log

from datetime import datetime, timezone
import ntplib

import time

import math

import requests

import tweepy

from django.conf import settings

# For debugging query
from django.db import connection


class ElonBot:
    def __init__(self,
                 asset: str,
                 auto_buy_delay: float,
                 auto_sell_delay: float,
                 use_image_signal: bool,
                 order_size: float,
                 process_tweet_text: Optional[str],
                 dry_run: bool):
        self.dry_run = dry_run
        self.asset = asset
        self.auto_buy_delay = auto_buy_delay
        self.auto_sell_delay = auto_sell_delay
        self.use_image_signal = use_image_signal
        self.order_size = order_size
        self.process_tweet_text = process_tweet_text
        if not self.validate_env():
            return

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
        twitter_test = (
            settings.CONSUMER_KEY, settings.CONSUMER_SECRET,
            settings.ACCESS_TOKEN, settings.ACCESS_SECRET
        )

        google_test = settings.GOOGLE_APPLICATION_CREDENTIALS

        if not google_test and verbose:
            log('Please, provide GOOGLE_APPLICATION_CREDENTIALS environment variable.')

        if not all(twitter_test) and verbose:
            log('Please, provide all the consumer keys and access keys for twitter.'
                'Check ".env.sample" for a list of the required variables'
            )

        return google_test and twitter_test


    def process_tweet(self, tweet_json: str, utc_time):
        process_start = time.perf_counter()

        tweet_json = json.loads(tweet_json)
        print("\n")
        log("Tweet received")
        # log("Tweet received\n", json.dumps(tweet_json, indent=4, sort_keys=True), "\n")
        tweet_text = tweet_json.get('text', '')
        image_url = (tweet_json.get('extended_entities', {}).get('media', [])[0:1] or [{}])[0].get('media_url', '')

        image_text = ''
        if self.use_image_signal:
            start = time.perf_counter()
            image_text = ElonBot.get_image_text(image_url)
            scan_time = time.perf_counter() - start
        else:
            scan_time = 0

        full_text = f'{tweet_text} {image_text}'

        keywords = list(Keyword.objects.filter(enabled=True).values_list('name', 'ticker'))

        for keyword, ticker in keywords:
            t = unidecode(full_text)
            if re.search(keyword, t, flags=re.I) is not None:
                log(f'Tweet matched pattern "{keyword}", buying corresponding ticker {ticker}')

                tweet_time = int(tweet_json['timestamp_ms'])/1000

                timelapse = utc_time - tweet_time
                timelapse_int = math.ceil(timelapse)

                # Get necessary API endpoint
                webhook = Webhook.objects.filter(
                    timerange_lower__lte=timelapse_int,
                    timerange_upper__gte=timelapse_int
                ).order_by("-timerange_lower")

                if webhook:
                    url = webhook[0].url
                    message = webhook[0].message
                    log(f"Range selected: {webhook[0].timerange_lower} to {webhook[0].timerange_upper}")
                else:
                    # if there is no record for this time range, run default webhook
                    url = settings.DEFAULT_WEBHOOK
                    message = settings.DEFAULT_MESSAGE
                    log("Range selected: Default")

                # Make API call
                R = requests.post(url, data=message)

                if R.status_code != 200:
                    log(f"Failed to post '{message}' to {url} (Response {R.status_code})")
                else:
                    log(f"Posted '{message}' to {url} (Response {R.status_code})")

                # For debugging purposes -> Indent this whole section to the left after confirming requirements
                total_process_time = (time.perf_counter() - process_start) + timelapse

                print(f"\nTIMING LOGS\nReceived timestamp (UTC): {utc_time}\nTweet timestamp (UTC): {tweet_time}")
                print(f"Tweet took {timelapse} seconds to get to the app")

                if image_text:
                    print(f"Google took {scan_time} seconds to scan text from the image")

                # Checking how much time it took to run the query
                if connection.queries:
                    # Get the last two queries
                    query_time = float(connection.queries[-1].get("time")) + float(connection.queries[-2].get("time"))
                    print(f"Retrieving keyword and webhook records took {query_time} seconds")
                else:
                    query_time = 0

                webhook_time = R.elapsed.total_seconds()
                print(f"Webhook responded in {webhook_time} seconds")

                network_time = timelapse + webhook_time + scan_time

                print(f"\nTOTAL SECONDS ELAPSED: {total_process_time}\n({network_time} on Twitter,webhook and Google Vision)\n")

                return

        return None

    def run(self, timeout: int = 24 * 3600) -> None:
        if self.process_tweet_text is not None:
            utc_time = datetime.now(timezone.utc).replace(tzinfo=timezone.utc).timestamp()
            self.process_tweet(self.process_tweet_text, utc_time)
            return
        while True:
            try:
                user = Follow.objects.all()
                if not user:
                    print("No user defined -> Add user from user interface")
                    exit()

                params = {"follow": user[0].userid}

                auth = tweepy.OAuth1UserHandler(
                    settings.CONSUMER_KEY, settings.CONSUMER_SECRET,
                    settings.ACCESS_TOKEN, settings.ACCESS_SECRET
                )

                response = requests.get(
                    "https://stream.twitter.com/1.1/statuses/filter.json",
                    auth=auth.apply_auth(), params=params, stream=True, timeout=timeout
                )
                response.connection.close()
                log('Subscribing to twitter updates. HTTP status:', response.status_code)
                if response.status_code != 200:
                    raise Exception("Cannot get stream (HTTP {}): {}".format(response.status_code, response.text))
                for response_line in response.iter_lines():
                    if response_line:
                        utc_time = datetime.now(timezone.utc).replace(tzinfo=timezone.utc).timestamp()
                        self.process_tweet(response_line, utc_time)
            except Exception as ex:
                log(ex, 'restarting socket')
                time.sleep(60)
                continue



class Command(BaseCommand):
    help = "Send data to webhooks using Twitter signal"

    def add_arguments(self, parser):
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
