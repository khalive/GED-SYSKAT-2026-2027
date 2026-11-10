from django.contrib import admin

from .models import (
    DemandeDuplicata,
    DocumentGenere,
    EtapeWorkflow,
    Paiement,
    PieceJustificative,
)


class PieceInline(admin.TabularInline):
    model = PieceJustificative
    extra = 0


class EtapeInline(admin.TabularInline):
    model = EtapeWorkflow
    extra = 0


@admin.register(DemandeDuplicata)
class DemandeDuplicataAdmin(admin.ModelAdmin):
    list_display = ("numero_demande", "demandeur", "type_demande", "statut", "date_depot")
    list_filter = ("statut", "type_demande")
    search_fields = ("numero_demande", "demandeur__matricule")
    readonly_fields = ("numero_demande",)
    inlines = [PieceInline, EtapeInline]


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("demande", "montant", "mode", "statut", "numero_recu")
    list_filter = ("statut", "mode")


@admin.register(DocumentGenere)
class DocumentGenereAdmin(admin.ModelAdmin):
    list_display = ("numero_officiel", "demande", "signe", "signe_par", "date_generation")
    readonly_fields = ("code_qr", "date_generation")