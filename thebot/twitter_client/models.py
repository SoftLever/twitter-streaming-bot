from django.db import models

class Tweet(models.Model):
    tweet_id = models.CharField(max_length=30)
    author_id = models.CharField(max_length=30)
    text = models.TextField()
    created_on = models.DateTimeField()
