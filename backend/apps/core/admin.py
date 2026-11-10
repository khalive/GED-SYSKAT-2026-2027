from django.contrib import admin

from .models import Notification, Sauvegarde


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("sujet", "destinataire", "canal", "lue", "date_envoi")
    list_filter = ("canal", "lue")


@admin.register(Sauvegarde)
class SauvegardeAdmin(admin.ModelAdmin):
    list_display = ("type", "date", "statut", "verifiee", "lancee_par")
    list_filter = ("type", "statut")