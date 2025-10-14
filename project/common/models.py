from django.db import models

class Status(models.TextChoices):
    unofficial = "Unofficial", "Unofficial"
    official = "Official", "Official"
    outdated = "Outdated", "Outdated"