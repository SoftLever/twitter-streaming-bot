from django.shortcuts import render
from .models import Keyword, Webhook

def index(request):
    if request.method == "POST":
        keyword = request.POST.get("keyword")
        url = request.POST.get("url")

        if keyword:
            ticker = request.POST.get("ticker")
            Keyword.objects.get_or_create(name=keyword, ticker=ticker)
        elif url:
            message = request.POST.get("message")
            from_time = int(request.POST.get("from_time"))
            to_time = int(request.POST.get("to_time"))

            # basic validation - time difference is valid and message is not empty
            if (from_time < to_time) and message:
                Webhook.objects.get_or_create(
                    timerange_lower=from_time,
                    timerange_upper=to_time,
                    url=url,
                    message=message
                )


    keyword_id = request.GET.get("keyword_id")
    webhook_id = request.GET.get("webhook_id")

    if request.method == "GET":
        if keyword_id:
            if request.GET.get("enabled").lower() == "false":
                enabled = False
            else:
                enabled = True

            keyword_obj = Keyword.objects.get(id=keyword_id)
            keyword_obj.enabled=enabled
            keyword_obj.save()

        elif webhook_id:
            webhook_obj = Webhook.objects.get(id=webhook_id)
            webhook_obj.delete()


    keywords = Keyword.objects.all()
    webhooks = Webhook.objects.all()
    context = {"keywords": keywords, "webhooks": webhooks}
    return render(request, "index.html", context)
