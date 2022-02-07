from django.db import models


class Keyword(models.Model):
    name = models.CharField(max_length=200)
    ticker = models.CharField(max_length=50)

    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# webhook URLs or API endpoints to call
class Webhook(models.Model):
    timerange_lower = models.IntegerField()
    timerange_upper = models.IntegerField()

    url = models.CharField(max_length=300)
    message = models.CharField(max_length=1000)

    class Meta:
        constraints = [
            models.constraints.UniqueConstraint(
                fields=['timerange_lower', 'timerange_upper'],
                name="timerange_constraint"
            )
        ]

    def __str__(self):
        return self.url


class Follow(models.Model):
    userid = models.CharField(max_length=40)

    def __str__(self):
        return self.userid
