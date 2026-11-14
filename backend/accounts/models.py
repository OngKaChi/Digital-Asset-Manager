from django.db import models
from django.contrib.auth.models import User
from auditlog.registry import auditlog

auditlog.register(User, exclude_fields=['password', 'last_login']) 

# Create your models here.
