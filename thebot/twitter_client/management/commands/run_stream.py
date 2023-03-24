from django.core.management.base import BaseCommand
from twitter_client.models import Tweet

from django.conf import settings

from tweepy import StreamingClient, StreamRule


class FollowBot(StreamingClient):
    def process_tweet(self,tweet):
        try:
            tweet_object = Tweet(
                tweet_id=tweet.id,
                author_id=tweet.author_id,
                text=tweet.text,
                created_on=tweet.created_at
            )

            tweet_object.save()
        except Exception as e:
            print(e)

        return

    def on_tweet(self,tweet):
        self.process_tweet(tweet)
        return


class Command(BaseCommand):
    help = "Listen Twitter for given keywords"

    def handle(self, *args, **options):
        bot = FollowBot(bearer_token=settings.TWITTER_BEARER_TOKEN, wait_on_rate_limit=True)
        bot.add_rules(
            [StreamRule(value='@BankofAfrica_Ke OR \"Bank of Africa\" OR @AbsaKenya OR \"Absa Bank\" OR @KCBGroup OR \"KCB bank\" OR @KeEquityBank OR \"Equity Bank\" OR @FamilyBankKenya OR \"Family Bank\" OR @Coopbankenya OR \"Cooperative Bank\"')] # Will match any tweet containing both Equity and Bank
        )
        bot.filter(tweet_fields=["author_id", "id", "text", "created_at"])
